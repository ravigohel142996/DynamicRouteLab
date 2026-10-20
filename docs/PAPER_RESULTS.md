# Paper Results — Historical vs Reproducible Benchmarks

This document preserves two distinct experiments referenced in the research paper
**“Shortest Path Algorithms for Dynamic Road Networks: A Comparative Study”**
(Ravi Gohel, Yesha Santoki, Marwadi University).
The two experiments must never be mixed; their datasets, configurations, and
measurement contexts are different.

## Configuration A — Historical Paper Experiment (3×3 Grid)

> **Status: Historical record. Preserved verbatim. Not a claim about the current codebase.**

The paper reports the following measurements for a **3×3 grid (9 nodes, 12 edges)**
experiment. The original measurement environment (hardware, Python version, timer
resolution, single-run vs repeated trials) is not fully documented in the
paper draft, so these numbers are reproduced here **exactly as printed** for
archival integrity.

| Scenario    | Algorithm      | Path Cost | Displayed Runtime | Displayed Count* |
|-------------|---------------|-----------|-------------------|------------------|
| Normal      | Dijkstra       | 12        | 0.6000 ms         | 9                |
| Normal      | A* Search      | 12        | 0.4000 ms         | 9                |
| Normal      | Bellman–Ford   | 12        | 0.0000 ms         | 2                |
| Congestion  | Dijkstra       | 12        | 0.1000 ms         | 8                |
| Congestion  | A* Search      | 12        | 0.0000 ms         | 7                |
| Congestion  | Bellman–Ford   | 12        | 0.2000 ms         | 2                |

\* `Count` in the paper conflates different algorithm-specific counters:
- Dijkstra `settled vertices`
- A* `expanded vertices`
- Bellman–Ford `relaxation passes`

These counters are **not comparable across algorithms** and must not be placed
on a single shared axis as though they measure the same work. The current
dashboard reports them separately with explicit labels and also reports the
cross-algorithm `edge relaxations` counter.

### Known limitations of the historical 0.0000 ms entries

- `0.0000 ms` indicates the measurement was **below the timer resolution or
  was rounded to 4 decimal places**, not that the algorithm took zero time.
- Single-run wall-clock on small graphs is dominated by Python interpreter
  overhead and OS scheduling noise; do not use single sub-millisecond samples
  to claim one algorithm is fastest.
- The current codebase uses `time.perf_counter_ns()` (monotonic, high
  resolution) and reports **medians over repeated round-robin trials** with
  warm-up, plus min/max/stdev and raw per-trial CSV. The historical single-run
  table is retained for archival transparency only.

### Reproducibility note for 3×3

Running the current generator with `n=3, seed=42, topology=grid,
weight_min=2, weight_max=12, source=0_0, target=2_2` produces:

- **Cost 19.0** (not 12) — because the paper's 3×3 used a different seed and/or
  weight range and/or endpoint choice that is not recorded in the draft.
- `settled = 9` for Dijkstra on a 3×3 fully-connected traversal is expected
  (all 9 vertices may be settled when the target is the last remaining node).
- `passes = 2` for Bellman–Ford on a 3×3 with 12 undirected edges (24 directed)
  is typical; the exact pass count depends on edge ordering and early-exit
  optimisation.

**Do not silently replace the paper's cost 12 with the current engine's cost
19, and do not overwrite the paper to claim 19.** Keep this section as the
archival record and refer to the new 8×8 benchmark (Configuration B) for
current reproducible evidence.

The 3×3 historical values are also available as a machine-readable fixture:

- `paper/historical_3x3_paper_table.json` — verbatim transcription of the
  reported table (no measurements are recomputed).
- Run `python scripts/reproduce_experiments.py --paper-3x3` to generate the
  **current engine's** 3×3 output for comparison (cost 19 under seed 42).
  That output is written to `results/paper_3x3_current_engine.json` and
  `results/paper_3x3_current_engine_trials.csv`.

---

## Configuration B — Current Dashboard Benchmark (8×8 Grid)

> **Status: Reproducible, verified against actual exports. The dashboard's
> default view (`n=8, seed=42, topology=grid, trials=10`).**

This is the newer experiment shown in the dashboard before these upgrades:

- **Grid:** 8×8 → **64 nodes, 112 undirected edges** (224 directed relaxations
  before heuristic work)
- **Seed:** 42, topology `grid`, `weight_min=2, weight_max=12`
- **Endpoints:** `0_0 → 7_7` (opposite corners; Manhattan distance 14)
- **Trials:** 10 per algorithm, round-robin interleaving, 1 warm-up call
- **Congestion scenario:** `congestion_pct=20, congestion_factor=3.0`,
  seed `seed + 9999` (deterministic sample of 22 open roads, 20% of 112)

### Verified baseline results (Normal traffic, seed 42)

All three algorithms agree on the optimal cost, verified against the
independent reference implementation:

- **Path cost (all algorithms): 65.0** — recomputed from open-road weights,
  cross-checked with `reference_dijkstra`, correctness `pass` for every
  algorithm.
- **Single-run snapshot (timing noise, not for claims):**
  - Dijkstra `settled = 64`, `relaxations = 222`, `runtime ≈ 0.06–0.07 ms`
  - A* `expanded = 64`, `relaxations = 222`, `heuristic_scale = 2.0`, `runtime ≈ 0.12–0.15 ms`
  - Bellman–Ford `passes = 3`, `relaxations = 896`, `runtime ≈ 0.14–0.16 ms`
  - On this 8×8 grid with the heuristic scale `c* = 2.0`, A* and Dijkstra
    settle/expand the same number of vertices; cost agreement holds, but
    `expanded < settled` does not hold for this particular pair (hypothesis H1
    is not supported on this snapshot; see hypotheses tracking below).

- **Repeated benchmark (median over 10 trials, `results/benchmark_8x8_seed42.json`):**
  - Median runtimes are of the same order as single-run timings (all < 0.2 ms);
    variability is dominated by OS scheduling and Python overhead. See the raw
    per-trial CSV for the full distribution; do not claim statistical
    significance from this single-host sample.

### Congestion comparison

After applying the deterministic congestion sample (seed 42+9999):

- **New path cost: 71.0** (Dijkstra reference cost after congestion)
- **Affected roads: 22** (20% of 112 open roads, sampled deterministically)
- **Route changed: Yes** — the optimal path differs from the baseline path
- **Cost delta: +6.0** (increase, but not assumed to always increase; equal-cost
  alternatives could keep cost unchanged — see H3)

Full exports for the 8×8 run are stored in:

- `results/benchmark_8x8_seed42.json` — full experiment JSON with config,
  graph, traffic changes, per-trial timings, environment, wall-clock time
- `results/benchmark_8x8_seed42_trials.csv` — raw per-trial measurements
  (scenario, algorithm, trial, runtime_ms, cost, processed, relaxations, correct)
- `results/benchmark_8x8_seed42_summary.csv` — summary per algorithm/scenario

All numeric results in this section are generated from code and match the
dashboard when loaded with `n=8, seed=42, topology=grid`. See
`scripts/reproduce_experiments.py` for the generation command.

---

## Hypotheses — Measurable outcomes and verdicts on current data

| Hypothesis | Measurable outcome | Comparison in this dataset | Verdict on `8×8 seed 42` |
|------------|--------------------|----------------------------|---------------------------|
| **H1** A* expands fewer vertices than Dijkstra while returning same optimal cost | `expanded (A*) < settled (Dijkstra)` and `cost(A*) == cost(Dijkstra)` | Single snapshot `n=8 seed 42 0_0→7_7`: `expanded=64, settled=64, cost=65` equal | **Not supported** on this pair (equal). Supported on other pairs (e.g. `n=12 seed 42` yields `expanded=~60 < settled=~140`). See sweep. |
| **H2** Relative runtime depends on topology, heuristic quality, graph size | Median runtimes across topologies and `n=4…14` sweep | 8×8 grid: BF slowest; diagonal/random_extra increase relaxations; sweep shows BF O(VE) growth | **Supported** — BF median grows faster with `n`; A* heuristic strength varies by topology |
| **H3** Congestion can change route even when optimal cost unchanged | `route_changed == true` and `cost_delta == 0` exists across updates | Synthetic equal-cost fixture in tests proves the mechanism; 8×8 seed42 shows cost increase, not this case | **Mechanism demonstrated** via unit test; not observed in 8×8 seed42 (cost increased). Needs multi-seed scan. |
| **H4** Recomputation has measurable cost | `recompute_total_ms = sum(median_runtime per algorithm) > 0` | 8×8 seed42: `recompute_total_ms ≈ 0.4 ms` (measurable but dominated by noise) | **Inconclusive** at small `n`; meaningful at larger `n` after scaling sweep |

Verdicts above refer only to the specific synthetic graphs measured. Broader
claims require multi-seed, multi-topology experiments; the runner supports
`updates` independent congestion draws and `route_change_frequency`.

---

## How to reproduce

```bash
# 1. Install backend dependencies
python -m pip install -r backend/requirements.txt

# 2. Run both preserved benchmarks and save exports
python scripts/reproduce_experiments.py                # 8×8 default + 3×3 current-engine comparison
python scripts/reproduce_experiments.py --paper-3x3     # only the 3×3 comparison
python scripts/reproduce_experiments.py --benchmark-8x8 # only the 8×8 benchmark

# 3. Regenerate academic figures from saved exports (requires matplotlib)
pip install matplotlib  # if not already present
python scripts/generate_figures.py                     # reads results/benchmark_8x8_seed42*.json/csv
```

All outputs are written to `results/` (CSV/JSON) and `figures/` (PNG at 300 DPI + PDF + SVG where applicable).
The dashboard can be cross-checked by loading `n=8, seed=42, topology=grid,
source=0_0, target=7_7, trials=10` and comparing the displayed cost `65` with
`results/benchmark_8x8_seed42_summary.csv`.

---

## Limitations and integrity notes

- All graphs and weights are synthetic; no live traffic provider is integrated.
- Sub-millisecond timings are noisy and depend on the host's CPU share; do not
  treat cloud-demo timings as hardware-independent results. Record deployed
  commit SHA, platform, and plan/CPU allocation alongside any reported timing.
- Medians and IQR are descriptive only; no significance tests are computed.
- A* heuristic `h(v) = c* · Manhattan(v, target)` with `c* = min_e w(e)/L(e)`
  is admissible and consistent on all three topologies (verified by tests).
  On diagonal/random_extra graphs the bound is looser, so A* may expand more
  than on a plain grid (see Methodology §4.1 correction note).
- Bellman–Ford pass counts are not comparable to Dijkstra/A* vertex counts;
  compare `edge relaxations` for work, noting it still omits heap-operation
  cost.

## References

- Methodology, assumptions, metric definitions, and traffic model details:
  `docs/METHODOLOGY.md`
- Algorithm source: `backend/server/algorithms/`
- Tests that guard these experiments: `backend/tests/`
- Sample configuration (no measurements): `examples/sample_experiment.json`
