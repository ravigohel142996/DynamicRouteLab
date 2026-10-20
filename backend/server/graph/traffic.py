"""Traffic update engine.

All updates are real graph mutations on a *copy* of the payload. Each algorithm then receives
the same adjacency built from the mutated payload, so every algorithm sees the same graph version.

Model
-----
* Congestion multiplies a road's ORIGINAL travel time (`original_weight`) by a factor >= 1.
  Re-applying congestion therefore never compounds multipliers.
* Closure marks a road `closed=True`. Closed roads are excluded from the adjacency used by every
  algorithm (and from the A* heuristic scale), so they are unavailable everywhere consistently.
* Reset restores every road to `original_weight` and reopens it.
"""

import math
import random
from copy import deepcopy
from typing import Dict, List, Optional, Sequence, Tuple

# Derived seed offset used by both the interactive simulator and the experiment runner, so the
# "after congestion" snapshot shown in the UI matches the experiment's first congestion draw.
CONGESTION_SEED_OFFSET = 9999


def _check_finite_non_negative(value: float, name: str) -> float:
    v = float(value)
    if not math.isfinite(v) or v < 0:
        raise ValueError(f"{name} must be a finite non-negative number, got {value!r}")
    return v


def apply_congestion(
    graph_payload: dict,
    congestion_pct: float,
    congestion_factor: float,
    seed: int,
    affected_edge_ids: Optional[Sequence[str]] = None,
) -> Tuple[dict, List[dict], List[str]]:
    """Return (new_payload, change_log, affected_edge_ids).

    If `affected_edge_ids` is None, `congestion_pct` percent of the OPEN roads are sampled with a
    seeded RNG (sample size = round(open * pct / 100), at least 1 when pct > 0).
    """
    factor = _check_finite_non_negative(congestion_factor, "congestion_factor")
    if factor < 1.0:
        raise ValueError("congestion_factor must be >= 1.0 (congestion never shortens a road)")
    if not 0.0 <= float(congestion_pct) <= 100.0:
        raise ValueError("congestion_pct must lie in [0, 100]")

    new_graph = deepcopy(graph_payload)
    edges = new_graph["edges"]
    open_edges = [e for e in edges if not e.get("closed")]

    if affected_edge_ids is None:
        if congestion_pct > 0 and open_edges:
            count = max(1, round(len(open_edges) * float(congestion_pct) / 100.0))
            rng = random.Random(int(seed))
            chosen = rng.sample(open_edges, min(count, len(open_edges)))
            affected = [e["id"] for e in chosen]
        else:
            affected = []
    else:
        affected = list(affected_edge_ids)

    affected_set = set(affected)
    known = {e["id"] for e in edges}
    unknown = affected_set - known
    if unknown:
        raise ValueError(f"Unknown edge ids: {sorted(unknown)[:5]}")

    changes: List[dict] = []
    for e in edges:
        if e["id"] not in affected_set or e.get("closed"):
            continue
        old = float(e["weight"])
        new = round(float(e["original_weight"]) * factor, 6)
        e["weight"] = new
        changes.append({
            "edge_id": e["id"], "source": e["source"], "target": e["target"],
            "old_weight": old, "new_weight": new, "delta": round(new - old, 6),
            "type": "congested",
        })
    return new_graph, changes, affected


def set_edge_weight(graph_payload: dict, edge_id: str, new_weight: float) -> dict:
    weight = _check_finite_non_negative(new_weight, "new_weight")
    new_graph = deepcopy(graph_payload)
    for e in new_graph["edges"]:
        if e["id"] == edge_id:
            e["weight"] = weight  # original_weight is intentionally left untouched
            return new_graph
    raise ValueError(f"Edge {edge_id} not found")


def set_road_closed(graph_payload: dict, edge_id: str, closed: Optional[bool] = None) -> dict:
    """Close or reopen a road. `closed=None` toggles the current state."""
    new_graph = deepcopy(graph_payload)
    for e in new_graph["edges"]:
        if e["id"] == edge_id:
            e["closed"] = (not e.get("closed", False)) if closed is None else bool(closed)
            return new_graph
    raise ValueError(f"Edge {edge_id} not found")


def reset_graph(graph_payload: dict) -> dict:
    new_graph = deepcopy(graph_payload)
    for e in new_graph["edges"]:
        e["weight"] = float(e["original_weight"])
        e["closed"] = False
    return new_graph


def edge_map(graph_payload: dict) -> Dict[str, dict]:
    return {e["id"]: e for e in graph_payload["edges"]}
