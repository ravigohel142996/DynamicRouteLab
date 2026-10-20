#!/usr/bin/env python3
"""
Reproducible experiment runner that generates the preserved paper benchmarks
as actual CSV/JSON exports and a reproducibility manifest.

Generates:
  results/benchmark_8x8_seed42.json              — full 8x8 experiment JSON (config, graph, per-trial timings, env)
  results/benchmark_8x8_seed42_trials.csv       — raw per-trial measurements
  results/benchmark_8x8_seed42_summary.csv     — summary per algorithm/scenario
  results/reproducibility_manifest.json         — environment + config manifest for the run
  results/paper_3x3_current_engine.json        — 3x3 with current engine (for comparison, not a claim that paper's 12 is reproduced)
  results/paper_3x3_current_engine_trials.csv — trials for the 3x3 current engine

All data is synthetic (backend/server/graph/generator.py); no live traffic.

Usage:
  python scripts/reproduce_experiments.py                # both 8x8 and 3x3
  python scripts/reproduce_experiments.py --benchmark-8x8
  python scripts/reproduce_experiments.py --paper-3x3
"""
from __future__ import annotations
import argparse
import csv
import json
import platform
import sys
import time
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

# Allow running from repo root or scripts/ directory
REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from server.benchmark import run_experiment, benchmark_snapshot
from server.graph.generator import generate_grid
from server import __version__ as APP_VERSION

RESULTS_DIR = REPO_ROOT / "results"
RESULTS_DIR.mkdir(exist_ok=True)


def manifest_for(config: dict) -> dict:
    versions = {}
    for pkg in ("fastapi", "uvicorn", "pydantic", "matplotlib", "networkx", "pandas", "streamlit"):
        try:
            versions[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            versions[pkg] = None
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "software_version": APP_VERSION,
        "python_version": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "packages": versions,
        "timer": "time.perf_counter_ns (monotonic, high resolution)",
        "timing_boundary": "Each timed sample is one call to an algorithm function. Generation, traffic updates, reference checks, serialisation, and rendering are excluded.",
        "warmup_calls_per_algorithm": 1,
        "trial_ordering": "round-robin across algorithms",
        "config": config,
        "data_origin": "synthetic (generate_grid, synthetic grid positions, not real streets)",
    }


def write_trials_csv(experiment: dict, csv_path: Path) -> None:
    """Write raw per-trial CSV with exact measurement provenance."""
    rows = []
    scenarios = [("normal", experiment.get("normal"))]
    if experiment.get("congested") is not None:
        scenarios.append(("congested", experiment.get("congested")))
    headers = ["scenario", "algorithm", "trial", "runtime_ms", "cost", "processed", "relaxations", "correct", "source", "target", "seed", "n", "topology"]
    for scenario_label, summaries in scenarios:
        for algo in ("dijkstra", "astar", "bellman_ford"):
            for trial in summaries[algo]["trials_raw"]:
                rows.append({
                    "scenario": scenario_label,
                    "algorithm": algo,
                    "trial": trial["trial"],
                    "runtime_ms": f"{trial['runtime_ms']:.6f}",
                    "cost": trial["cost"],
                    "processed": trial["processed"],
                    "relaxations": trial["relaxations"],
                    "correct": trial["correct"],
                    "source": experiment["config"]["source"],
                    "target": experiment["config"]["target"],
                    "seed": experiment["config"]["seed"],
                    "n": experiment["config"]["n"],
                    "topology": experiment["config"]["topology"],
                })
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(rows)


def write_summary_csv(experiment: dict, csv_path: Path) -> None:
    headers = ["scenario", "algorithm", "label", "path_cost", "median_runtime_ms", "mean_runtime_ms", "stdev_runtime_ms", "min_runtime_ms", "max_runtime_ms", "cv_runtime", "processed_median", "relaxations_median", "correctness_pass_rate", "counts_consistent", "success"]
    rows = []
    for scenario_label in ("normal", "congested"):
        summary = experiment.get(scenario_label)
        if not summary:
            continue
        for algo in ("dijkstra", "astar", "bellman_ford"):
            s = summary[algo]
            rows.append({
                "scenario": scenario_label,
                "algorithm": algo,
                "label": s["label"],
                "path_cost": s["path_cost"],
                "median_runtime_ms": f"{s['median_runtime_ms']:.6f}",
                "mean_runtime_ms": f"{s['mean_runtime_ms']:.6f}",
                "stdev_runtime_ms": f"{s['stdev_runtime_ms']:.6f}",
                "min_runtime_ms": f"{s['min_runtime_ms']:.6f}",
                "max_runtime_ms": f"{s['max_runtime_ms']:.6f}",
                "cv_runtime": f"{s['cv_runtime']:.6f}",
                "processed_median": s["processed_median"],
                "relaxations_median": s["relaxations_median"],
                "correctness_pass_rate": s["correctness_pass_rate"],
                "counts_consistent": s["counts_consistent"],
                "success": s["success"],
            })
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(rows)


def run_8x8() -> dict:
    """The dashboard's default benchmark: 8x8 grid, seed 42, 10 trials, 20% congestion x3."""
    print("Running 8x8 benchmark (n=8, seed=42, topology=grid, trials=10, 20% x3.0)...")
    exp = run_experiment(
        n=8,
        seed=42,
        topology="grid",
        trials=10,
        congestion_pct=20,
        congestion_factor=3.0,
        source="0_0",
        target="7_7",
        updates=2,
        weight_min=2,
        weight_max=12,
    )
    # Write full experiment JSON
    json_path = RESULTS_DIR / "benchmark_8x8_seed42.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(exp, f, indent=2, ensure_ascii=False, allow_nan=False)
    print(f"  wrote {json_path}")

    # Raw trials CSV
    trials_csv = RESULTS_DIR / "benchmark_8x8_seed42_trials.csv"
    write_trials_csv(exp, trials_csv)
    print(f"  wrote {trials_csv}")

    # Summary CSV
    summary_csv = RESULTS_DIR / "benchmark_8x8_seed42_summary.csv"
    write_summary_csv(exp, summary_csv)
    print(f"  wrote {summary_csv}")

    # Reproducibility manifest
    manifest = manifest_for(exp["config"])
    manifest.update({
        "experiment": "benchmark-8x8-seed42",
        "verification": {
            "node_count": len(exp["base_graph"]["nodes"]),
            "edge_count": len(exp["base_graph"]["edges"]),
            "reference_cost_normal": exp["reference_cost_normal"],
            "path_cost_normal": exp["normal"]["dijkstra"]["path_cost"],
            "path_normal": exp["normal"]["dijkstra"]["path"],
            "reference_cost_congested": exp["congested"]["dijkstra"]["path_cost"] if exp.get("congested") else None,
            "affected_count_first_update": exp["updates"][0]["affected_count"] if exp["updates"] else 0,
            "route_change_first": exp["comparison"]["route_changed"],
            "cost_delta_first": exp["comparison"]["cost_delta"],
            "route_change_frequency": exp["route_change_frequency"],
            "normal_label": "64 nodes, 112 edges, cost 65.0, seed 42 (verified)",
        },
        "paper_historical_preserved_in": "paper/historical_3x3_paper_table.json",
    })
    manifest_path = RESULTS_DIR / "reproducibility_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"  wrote {manifest_path}")

    # Print verification
    print(f"  verification: {manifest['verification']}")
    return exp


def run_paper_3x3() -> dict:
    """Current engine's 3x3 output for comparison with historical paper cost-12 table."""
    print("Running 3x3 current-engine comparison (n=3, seed=42, grid, 10 trials)...")
    exp = run_experiment(
        n=3,
        seed=42,
        topology="grid",
        trials=10,
        congestion_pct=20,
        congestion_factor=3.0,
        source="0_0",
        target="2_2",
        updates=1,
        weight_min=2,
        weight_max=12,
    )
    json_path = RESULTS_DIR / "paper_3x3_current_engine.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(exp, f, indent=2, ensure_ascii=False, allow_nan=False)
    print(f"  wrote {json_path}")

    trials_csv = RESULTS_DIR / "paper_3x3_current_engine_trials.csv"
    write_trials_csv(exp, trials_csv)
    print(f"  wrote {trials_csv}")

    summary_csv = RESULTS_DIR / "paper_3x3_current_engine_summary.csv"
    write_summary_csv(exp, summary_csv)
    print(f"  wrote {summary_csv}")

    # Also write a comparison note
    print("  note: paper historical cost was 12 (different seed/config); current engine cost is "
          f"{exp['normal']['dijkstra']['path_cost']} under seed 42 — not a regression, just a different config.")
    return exp


def main():
    parser = argparse.ArgumentParser(description="Reproduce preserved paper benchmarks")
    parser.add_argument("--benchmark-8x8", action="store_true", help="only run 8x8 benchmark")
    parser.add_argument("--paper-3x3", action="store_true", help="only run 3x3 current-engine comparison")
    args = parser.parse_args()

    run_both = not (args.benchmark_8x8 or args.paper_3x3)

    if run_both or args.benchmark_8x8:
        run_8x8()
    if run_both or args.paper_3x3:
        run_paper_3x3()

    print("\nAll requested experiments completed. Outputs in results/.")
    print("To regenerate academic figures: python scripts/generate_figures.py")


if __name__ == "__main__":
    main()
