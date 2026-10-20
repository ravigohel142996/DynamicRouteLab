"""Benchmark runner, correctness checks, and summary statistics.

Timing boundary
---------------
Only the call to an algorithm function is timed, with `time.perf_counter_ns()` (monotonic,
high resolution). Graph generation, traffic updates, correctness checks against the reference,
JSON serialisation, and UI rendering all happen OUTSIDE the timed call.

Fairness
--------
* Every algorithm in a snapshot receives the same adjacency, built once from the same payload.
* One untimed warm-up call per algorithm precedes the timed trials.
* Trials are interleaved round-robin (D, A*, BF, D, A*, BF, ...) so that slow drift in the
  host affects all algorithms roughly equally.
* Processing counts are algorithm-specific and are reported under their own name:
  Dijkstra = settled vertices, A* = expanded vertices, Bellman–Ford = relaxation passes.
  Edge relaxations are the cross-algorithm work counter.
"""

from __future__ import annotations

import math
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from importlib import metadata
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from server.algorithms.astar import astar
from server.algorithms.bellman_ford import bellman_ford
from server.algorithms.dijkstra import dijkstra
from server.algorithms.reference import reference_dijkstra
from server.graph.generator import generate_grid, get_positions, graph_to_adjacency
from server.graph.traffic import CONGESTION_SEED_OFFSET, apply_congestion

ALGORITHMS: List[str] = ["dijkstra", "astar", "bellman_ford"]
LABELS: Dict[str, str] = {"dijkstra": "Dijkstra", "astar": "A* Search", "bellman_ford": "Bellman–Ford"}
PROCESSED_KIND: Dict[str, str] = {"dijkstra": "settled", "astar": "expanded", "bellman_ford": "passes"}
COST_TOL = 1e-6


# --------------------------------------------------------------------------- validation

def validate_graph(payload: dict) -> None:
    """Raise ValueError with a human-readable message if the payload is malformed."""
    if not isinstance(payload, dict) or "nodes" not in payload or "edges" not in payload:
        raise ValueError("graph must be an object with 'nodes' and 'edges' arrays")
    node_ids = set()
    for n in payload["nodes"]:
        if "id" not in n or "r" not in n or "c" not in n:
            raise ValueError("every node needs 'id', 'r' and 'c'")
        if n["id"] in node_ids:
            raise ValueError(f"duplicate node id {n['id']!r}")
        node_ids.add(n["id"])
    edge_ids = set()
    for e in payload["edges"]:
        for key in ("id", "source", "target", "weight", "original_weight"):
            if key not in e:
                raise ValueError(f"edge {e.get('id', '?')} is missing '{key}'")
        if e["id"] in edge_ids:
            raise ValueError(f"duplicate edge id {e['id']!r}")
        edge_ids.add(e["id"])
        if e["source"] not in node_ids or e["target"] not in node_ids:
            raise ValueError(f"edge {e['id']} references an unknown node")
        w = float(e["weight"])
        if not math.isfinite(w) or w < 0:
            raise ValueError(f"edge {e['id']} has a negative or non-finite weight")


def validate_endpoints(payload: dict, source: str, target: str) -> None:
    ids = {n["id"] for n in payload["nodes"]}
    if source not in ids:
        raise ValueError(f"source {source!r} is not an intersection in this graph")
    if target not in ids:
        raise ValueError(f"target {target!r} is not an intersection in this graph")


# --------------------------------------------------------------------------- snapshot helpers

def _open_index(payload: dict) -> Dict[frozenset, float]:
    """Unordered pair -> weight for traversable (open) roads. Used for path validation."""
    index: Dict[frozenset, float] = {}
    for e in payload["edges"]:
        if e.get("closed"):
            continue
        key = frozenset((e["source"], e["target"]))
        w = float(e["weight"])
        index[key] = min(w, index.get(key, math.inf))
    return index


def _check_path(index: Dict[frozenset, float], path: Sequence[str], source: str, target: str,
                cost: Optional[float], success: bool) -> Tuple[bool, Optional[float]]:
    """Return (valid_path, recomputed_cost). A failed search must report no path."""
    if not success:
        return (not path and cost is None), None
    if not path or path[0] != source or path[-1] != target:
        return False, None
    total = 0.0
    for u, v in zip(path[:-1], path[1:]):
        w = index.get(frozenset((u, v)))
        if w is None:
            return False, None  # consecutive nodes are not connected by an open road
        total += w
    if cost is None or abs(total - cost) > COST_TOL:
        return False, total
    return True, total


def _run_algorithm(name: str, adj, positions, source: str, target: str) -> dict:
    if name == "dijkstra":
        return dijkstra(adj, source, target)
    if name == "astar":
        return astar(adj, source, target, positions)
    if name == "bellman_ford":
        return bellman_ford(adj, source, target)
    raise ValueError(f"unknown algorithm {name}")


def _clean_cost(cost) -> Optional[float]:
    if cost is None or (isinstance(cost, float) and not math.isfinite(cost)):
        return None
    return float(cost)


def _judge(name: str, res: dict, ref_cost: float, index, source: str, target: str) -> dict:
    """Correctness of one algorithm result against the trusted reference."""
    success = bool(res.get("success"))
    cost = _clean_cost(res.get("cost")) if success else None
    path = list(res.get("path", [])) if success else []
    ref_finite = math.isfinite(ref_cost)
    if not ref_finite:
        cost_match = (not success)
    else:
        cost_match = success and cost is not None and abs(cost - ref_cost) <= COST_TOL
    valid, recomputed = _check_path(index, path, source, target, cost, success)
    status = "pass" if (cost_match and valid) else "fail"
    return {
        "algorithm": name,
        "ref_cost": ref_cost if ref_finite else None,
        "cost_match": cost_match,
        "valid_path": valid,
        "recomputed_cost": recomputed,
        "status": status,
    }


def reference_for(payload: dict, source: str, target: str) -> Tuple[float, List[str]]:
    adj = graph_to_adjacency(payload)
    return reference_dijkstra(adj, source, target)


# --------------------------------------------------------------------------- single snapshot

def run_snapshot(payload: dict, source: str, target: str) -> dict:
    """One untimed-free execution of every algorithm on one snapshot with correctness checks.

    Used by the interactive laboratory. Each algorithm's own `runtime_ms` is its internal
    timer reading for this single execution (single runs are noisy: use the experiment runner).
    """
    validate_graph(payload)
    validate_endpoints(payload, source, target)
    adj = graph_to_adjacency(payload)
    positions = get_positions(payload)
    index = _open_index(payload)
    ref_cost, ref_path = reference_for(payload, source, target)

    results = {}
    for name in ALGORITHMS:
        res = _run_algorithm(name, adj, positions, source, target)
        res = dict(res)
        res.setdefault("runtime_ms", 0.0)
        res["cost"] = _clean_cost(res.get("cost"))
        res["correctness"] = _judge(name, res, ref_cost, index, source, target)
        res["processed"] = res.get(PROCESSED_KIND[name], 0)
        res["processed_kind"] = PROCESSED_KIND[name]
        res["label"] = LABELS[name]
        results[name] = res

    costs = [r["cost"] for r in results.values() if r["cost"] is not None]
    agreement = (max(costs) - min(costs) <= COST_TOL) if costs else True
    return {
        "results": results,
        "reference_cost": ref_cost if math.isfinite(ref_cost) else None,
        "reference_path": ref_path,
        "agreement": agreement,
        "heuristic_scale": results["astar"].get("heuristic_scale"),
        "open_road_count": len(index),
        "timing_note": "Single execution per algorithm; use the Experiment Runner for median/variability.",
    }


# --------------------------------------------------------------------------- repeated trials

def benchmark_snapshot(payload: dict, source: str, target: str, trials: int, warmup: int = 1) -> dict:
    """Repeated timed executions of all algorithms on one snapshot (round-robin ordering)."""
    adj = graph_to_adjacency(payload)
    positions = get_positions(payload)
    index = _open_index(payload)
    ref_cost, _ = reference_for(payload, source, target)

    for _ in range(warmup):
        for name in ALGORITHMS:
            _run_algorithm(name, adj, positions, source, target)

    samples: Dict[str, List[dict]] = {name: [] for name in ALGORITHMS}
    for _ in range(trials):
        for name in ALGORITHMS:
            t0 = time.perf_counter_ns()
            res = _run_algorithm(name, adj, positions, source, target)
            elapsed_ms = (time.perf_counter_ns() - t0) / 1e6
            res = dict(res)
            res["cost"] = _clean_cost(res.get("cost"))
            res["_wall_ms"] = elapsed_ms
            res["_judgement"] = _judge(name, res, ref_cost, index, source, target)
            samples[name].append(res)

    summary: Dict[str, dict] = {}
    for name in ALGORITHMS:
        rows = samples[name]
        times = [r["_wall_ms"] for r in rows]
        first = rows[0]
        processed_counts = {r.get(PROCESSED_KIND[name], 0) for r in rows}
        relax_counts = {r["relaxations"] for r in rows}
        paths = {tuple(r.get("path", [])) for r in rows}
        pass_rate = sum(1 for r in rows if r["_judgement"]["status"] == "pass") / len(rows)
        summary[name] = {
            "algorithm": name,
            "label": LABELS[name],
            "success": bool(first.get("success")),
            "path": list(first.get("path", [])) if first.get("success") else [],
            "path_cost": first["cost"],
            "processed_kind": PROCESSED_KIND[name],
            "processed_median": statistics.median([r.get(PROCESSED_KIND[name], 0) for r in rows]),
            "processed_mean": statistics.mean([r.get(PROCESSED_KIND[name], 0) for r in rows]),
            "relaxations_median": statistics.median([r["relaxations"] for r in rows]),
            "relaxations_mean": statistics.mean([r["relaxations"] for r in rows]),
            "median_runtime_ms": statistics.median(times),
            "mean_runtime_ms": statistics.mean(times),
            "stdev_runtime_ms": statistics.stdev(times) if len(times) > 1 else 0.0,
            "min_runtime_ms": min(times),
            "max_runtime_ms": max(times),
            "cv_runtime": (statistics.stdev(times) / statistics.mean(times))
            if len(times) > 1 and statistics.mean(times) > 0 else 0.0,
            "correctness_pass_rate": pass_rate,
            "correctness": first["_judgement"],
            "counts_consistent": len(processed_counts) == 1 and len(relax_counts) == 1 and len(paths) == 1,
            "has_negative_cycle": bool(first.get("has_negative_cycle", False)),
            "heuristic_scale": first.get("heuristic_scale"),
            "trials_raw": [
                {"trial": i + 1, "runtime_ms": r["_wall_ms"], "cost": r["cost"],
                 "processed": r.get(PROCESSED_KIND[name], 0), "relaxations": r["relaxations"],
                 "correct": r["_judgement"]["status"] == "pass"}
                for i, r in enumerate(rows)
            ],
        }
    return {"summary": summary, "reference_cost": ref_cost if math.isfinite(ref_cost) else None,
            "trials": trials, "warmup": warmup}


# --------------------------------------------------------------------------- experiment

def environment_info() -> dict:
    versions = {}
    for pkg in ("fastapi", "uvicorn", "pydantic"):
        try:
            versions[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            versions[pkg] = None
    return {
        "python_version": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "packages": versions,
        "timer": "time.perf_counter_ns (monotonic, high resolution)",
        "timing_boundary": "Each timed sample is one call to an algorithm function. Generation, traffic updates, reference checks, serialisation, and rendering are excluded.",
        "warmup_calls_per_algorithm": 1,
        "trial_ordering": "round-robin across algorithms",
    }


def _route_change(base_path: List[str], new_path: List[str]) -> bool:
    return base_path != new_path


def run_experiment(
    n: int,
    seed: int,
    topology: str,
    trials: int,
    congestion_pct: float,
    congestion_factor: float,
    source: Optional[str],
    target: Optional[str],
    updates: int = 1,
    weight_min: int = 2,
    weight_max: int = 12,
) -> dict:
    """Reproducible experiment: baseline snapshot plus `updates` independent congestion draws.

    Congestion draw k uses seed `seed + CONGESTION_SEED_OFFSET + k`, so the whole experiment is a
    deterministic function of its configuration (timings aside).
    """
    wall_t0 = time.perf_counter_ns()
    base = generate_grid(n, seed, topology=topology, weight_min=weight_min, weight_max=weight_max)
    src = source or "0_0"
    tgt = target or f"{n - 1}_{n - 1}"
    validate_endpoints(base, src, tgt)

    normal = benchmark_snapshot(base, src, tgt, trials)
    base_route = normal["summary"]["dijkstra"]["path"]
    base_cost = normal["summary"]["dijkstra"]["path_cost"]

    update_rows = []
    first_congested = None
    recompute_totals = []
    for k in range(updates):
        draw_seed = int(seed) + CONGESTION_SEED_OFFSET + k
        congested, changes, affected = apply_congestion(base, congestion_pct, congestion_factor, draw_seed)
        validate_graph(congested)
        snap = benchmark_snapshot(congested, src, tgt, trials)
        route = snap["summary"]["dijkstra"]["path"]
        cost = snap["summary"]["dijkstra"]["path_cost"]
        recompute_ms = sum(snap["summary"][a]["median_runtime_ms"] for a in ALGORITHMS)
        recompute_totals.append(recompute_ms)
        same_cost = (cost is not None and base_cost is not None and abs(cost - base_cost) <= COST_TOL)
        update_rows.append({
            "index": k + 1,
            "congestion_seed": draw_seed,
            "affected_count": len(affected),
            "cost_before": base_cost,
            "cost_after": cost,
            "cost_delta": (cost - base_cost) if (cost is not None and base_cost is not None) else None,
            "cost_unchanged": same_cost,
            "route_before": base_route,
            "route_after": route,
            "route_changed": _route_change(base_route, route),
            "route_changed_cost_unchanged": _route_change(base_route, route) and same_cost,
            "recompute_median_sum_ms": recompute_ms,
            "all_correct": all(snap["summary"][a]["correctness_pass_rate"] == 1.0 for a in ALGORITHMS),
        })
        if k == 0:
            first_congested = (congested, changes, affected, snap)

    if first_congested is None:
        congested_graph, changes, affected, congested_summary = None, [], [], None
    else:
        congested_graph, changes, affected, snap0 = first_congested
        congested_summary = snap0["summary"]

    changed_count = sum(1 for u in update_rows if u["route_changed"])
    first = update_rows[0] if update_rows else None
    wall_ms = (time.perf_counter_ns() - wall_t0) / 1e6

    return {
        "config": {
            "n": n, "seed": seed, "topology": topology, "weight_min": weight_min,
            "weight_max": weight_max, "trials": trials, "congestion_pct": congestion_pct,
            "congestion_factor": congestion_factor, "source": src, "target": tgt,
            "updates": updates, "congestion_seed_offset": CONGESTION_SEED_OFFSET,
        },
        "source": src,
        "target": tgt,
        "normal": normal["summary"],
        "congested": congested_summary,
        "reference_cost_normal": normal["reference_cost"],
        "congested_graph": congested_graph,
        "base_graph": base,
        "traffic_changes": changes,
        "affected_edge_ids": affected,
        "updates": update_rows,
        "route_change_frequency": (changed_count / len(update_rows)) if update_rows else None,
        "recompute_total_ms": sum(recompute_totals),
        "comparison": {
            "route_changed": bool(first and first["route_changed"]),
            "cost_delta": first["cost_delta"] if first else None,
            "normal_cost": base_cost,
            "congested_cost": first["cost_after"] if first else None,
            "cost_unchanged": bool(first and first["cost_unchanged"]),
        },
        "env": environment_info(),
        "wall_clock_ms": wall_ms,
        "timestamp": time.time(),
        "timestamp_iso": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
