# DynamicRouteLab

A **research-grade, reproducible platform** for comparing **Dijkstra**, **A\* Search**, and **Bellman–Ford** on synthetic road networks under dynamic traffic: congestion, closures, and travel-time edits.

- Interactive road-network laboratory (zoom, pan, fit, hover, select, close and reopen roads)
- Algorithm comparison on **identical graph snapshots**, checked against an independent reference
- Dynamic traffic simulator that changes the actual graph (before/after route comparison)
- Reproducible benchmark runner (seeded, repeated trials, median/variability, route-change frequency)
- Charts generated only from executed results
- Raw per-trial **CSV** and summary **JSON** exports with configuration, seeds, timestamps, and environment
- Research-quality academic figures (Matplotlib, 300 DPI PNG + PDF/SVG) generated from saved data
- Two preserved experiments: historical 3×3 paper table and current 8×8 reproducible benchmark

**All data is synthetic.** Coordinates are grid positions, not real streets. No live traffic
provider is integrated. Methodology, assumptions, and limitations: [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md).
Paper results preservation: [`docs/PAPER_RESULTS.md`](docs/PAPER_RESULTS.md).

## Project layout

```
backend/
  server/
    main.py              FastAPI app: endpoints, request validation (no algorithm logic)
    benchmark.py         correctness checks, timed trials, statistics, experiment runner
    static_mount.py      serves frontend/dist in production (mounted last)
    algorithms/
      dijkstra.py        binary-heap Dijkstra (settled vertices, edge relaxations)
      astar.py           A* with per-road admissible Manhattan heuristic
      bellman_ford.py    edge-relaxation Bellman–Ford with negative-cycle detection
      reference.py       independent reference used only for validation
    graph/
      generator.py       deterministic synthetic grid / diagonal / random-extra graphs
      traffic.py         congestion, closures, edits, reset (real weight/closure changes)
  tests/                 pytest suite: algorithms, traffic semantics, benchmark, API
  requirements.txt
frontend/
  src/App.tsx            application shell, laboratory, comparison, simulator, runner, exports
  src/components/CytoscapeGraph.tsx   interactive graph (Cytoscape.js)
  src/api.ts, src/types.ts
docs/
  METHODOLOGY.md         assumptions, metrics, limitations, reproducibility
  PAPER_RESULTS.md       historical 3×3 paper table vs current 8×8 benchmark, hypothesis verdicts
paper/
  historical_3x3_paper_table.json   verbatim transcription of the paper's reported table
examples/
  sample_experiment.json sample configuration (sample data, no measurements)
results/                 generated experiment outputs (CSV, JSON, manifests)
  benchmark_8x8_seed42.json/.csv     8×8 reproducible benchmark (64 nodes, 112 edges, seed 42)
  paper_3x3_current_engine.json/.csv 3×3 current-engine comparison (cost 19 vs paper cost 12)
  reproducibility_manifest.json       environment, versions, config, verification
  size_sweep_seed42.json/.csv         runtime-vs-size sweep n=4..14
figures/                 academic figures (PNG 300 DPI + PDF + SVG) from saved results
  fig01_path_cost_comparison.png/pdf/svg
  fig02_runtime_distribution.png/pdf/svg
  fig03_relaxations_comparison.png/pdf/svg
  fig04_congestion_sensitivity.png/pdf/svg
  fig05_correctness_summary.png/pdf/svg
  fig06_runtime_vs_size.png/pdf/svg + fig06_relaxations_vs_size
  fig07_trials_scatter.png/pdf/svg
scripts/
  reproduce_experiments.py   run preserved benchmarks, write results/ CSV/JSON/manifest
  generate_figures.py        generate figures/ from results/ data
app.py, requirements.txt  Streamlit Cloud entry point; reuses the shared backend research engine
run_backend.sh, run_frontend.sh   development launch helpers
pytest.ini
```

## Requirements

- Python 3.10 or newer
- Node.js 20.19+ or 22.12+ (required by Vite 8) and npm
- `matplotlib` for academic figure generation (`pip install matplotlib`)

## Setup and run (development)

From the repository root:

```bash
# 1. Backend dependencies
python3 -m pip install -r backend/requirements.txt

# 2. Frontend dependencies
cd frontend && npm ci && cd ..
```

Run the API and the web app in two terminals:

```bash
# Terminal 1: API on port 8000
./run_backend.sh          # or: python3 -m uvicorn server.main:app --app-dir backend --port 8000

# Terminal 2: web app on port 5173 (proxies /api to :8000)
./run_frontend.sh         # or: cd frontend && npm run dev
```

Open <http://localhost:5173>. The API docs are at <http://localhost:8000/docs>.

## Tests

```bash
python3 -m pytest          # runs backend/tests (configured in pytest.ini) — 108 tests
cd frontend && npm run build   # type-checks the frontend and builds the bundle
```

The suite covers:

- Reference agreement on all three topologies, several seeds and weight ranges, and multiple
  endpoint pairs (`test_algorithms.py`)
- Reconstructed paths validated edge-by-edge, with cost recomputed from roads; deterministic
  tie-breaking; path validity across seeds
- Unreachable destinations, source = destination, equal-cost alternatives, negative-cycle detection
- A* heuristic admissibility and consistency after congestion and closures, on every topology
- Congestion route-change semantics (H3: route may change even when cost unchanged)
- Bellman–Ford on negative edges without a cycle, and correctness vs Dijkstra on non-negative graphs
- Input validation (weight range, topology, unknown nodes)
- Traffic semantics: multipliers on original weights (no compounding), closures removed from every
  algorithm, reopen and reset, validation of bad input (`test_traffic.py`)
- Benchmark integrity: reproducible counts and costs for the same configuration, timing statistics,
  validation messages, API contract (`test_benchmark_and_api.py`)

**Current status: 108 tests, 0 failures.**

## Reproducing the paper experiments

The project preserves **two distinct experiments** — see [`docs/PAPER_RESULTS.md`](docs/PAPER_RESULTS.md) for the full archival record.

### Configuration A — Historical 3×3 paper table (preserved verbatim)

The paper reports a small 3×3 grid (9 nodes, 12 edges) with cost **12** for all algorithms
in both normal and congestion scenarios. The table includes `0.0000 ms` runtimes, which are
**rounded/below-resolution artifacts, not true zero-time measurements**, and algorithm-specific
`count` values (9/9/2 normal; 8/7/2 congestion) that conflate settled/expanded/passes.

This table is preserved verbatim in:

- `paper/historical_3x3_paper_table.json`

**Do not claim the historical cost 12 is reproduced by `seed 42` with the current engine.**
The generating seed/weight-range for cost 12 is not recorded in the draft.
Run the comparison below to see what the current engine produces for `n=3, seed=42`:

```bash
python scripts/reproduce_experiments.py --paper-3x3
# Writes: results/paper_3x3_current_engine.json/.csv (cost 19.0 under seed 42)
# Compare with paper/historical_3x3_paper_table.json (cost 12, historical config)
```

### Configuration B — Current 8×8 reproducible benchmark (dashboard default)

The dashboard defaults to `n=8, seed=42, topology=grid, trials=10` (64 nodes, 112 edges, cost **65.0**):

```bash
python scripts/reproduce_experiments.py --benchmark-8x8
# Writes: results/benchmark_8x8_seed42.json (full experiment JSON)
#         results/benchmark_8x8_seed42_trials.csv (raw per-trial measurements)
#         results/benchmark_8x8_seed42_summary.csv (summary per algorithm/scenario)
#         results/reproducibility_manifest.json (environment, versions, verification)
```

Or reproduce both at once:

```bash
python scripts/reproduce_experiments.py
```

**Verification:** load `n=8, seed=42, topology=grid, source=0_0, target=7_7, trials=10` in
the dashboard and confirm the displayed cost `65.0` matches `results/benchmark_8x8_seed42_summary.csv`.
Congestion (`20% × 3.0`, seed `42+9999`) changes cost to `71.0` with `22` affected roads.

### Exporting raw results from the dashboard or API

- **Dashboard:** use the Download buttons in the **Evidence & Export** tab or **Experiment Runner** tab
  for CSV (per-trial) and JSON (full config + environment) downloads.
- **API:** `POST /api/experiments/run` returns the full experiment JSON (config, graph, traffic
  changes, per-trial timings, environment). `POST /api/graph/generate` and `POST /api/algorithms/run`
  return snapshot results with correctness status.
- **CLI:** `scripts/reproduce_experiments.py` is the ground truth for paper-compatible exports;
  it records `perf_counter_ns` timings with warm-up and round-robin interleaving.

## Regenerating academic figures

Figures are generated **directly from saved experimental data** — no fabricated distributions or
significance markers:

```bash
pip install matplotlib  # if not already installed (backend/requirements already includes it for local dev)
python scripts/generate_figures.py
# Reads:  results/benchmark_8x8_seed42.json/.csv + results/size_sweep_seed42.*
# Writes: figures/fig01_path_cost_comparison.{png,pdf,svg} (300 DPI PNG)
#         figures/fig02_runtime_distribution.{png,pdf,svg}
#         figures/fig03_relaxations_comparison.{png,pdf,svg}
#         figures/fig04_congestion_sensitivity.{png,pdf,svg}
#         figures/fig05_correctness_summary.{png,pdf,svg}
#         figures/fig06_runtime_vs_size.{png,pdf,svg} + fig06_relaxations_vs_size
#         figures/fig07_trials_scatter.{png,pdf,svg}
```

Figure catalogue and data provenance:

| Figure | Content | Source data |
|---|---|---|
| fig01 | Path cost per algorithm (normal vs congested) | `results/benchmark_8x8_seed42.json` |
| fig02 | Runtime distribution (median/mean/stdev/min-max) | `results/benchmark_8x8_seed42_trials.csv` |
| fig03 | Work: edge relaxations vs algorithm-specific counters | `results/benchmark_8x8_seed42_summary.csv` |
| fig04 | Congestion sensitivity (cost before/after, route changes) | `results/benchmark_8x8_seed42.json` updates |
| fig05 | Correctness pass rate (100% on this dataset) | `results/benchmark_8x8_seed42_summary.csv` |
| fig06 | Runtime vs graph size (n=4..14) + relaxations vs size | `results/size_sweep_seed42.csv` |
| fig07 | Per-trial runtime vs relaxations scatter | `results/benchmark_8x8_seed42_trials.csv` |

All figures use restrained accessible colours, legible scientific labels, and consistent units.
Error bars (stdev, min-max) are only shown when raw trial distributions support them.

## Production deployment

The backend serves the built frontend, so the app runs as one process on one port. A multi-stage
`Dockerfile` builds the Vite app and runs FastAPI; `render.yaml` is a Render Blueprint using that
image, with `/api/health` as its health check.

### Deploy a hosted demo on Render

1. Push or merge the reviewed source commit to the GitHub repository's `main` branch.
2. In Render, create a **New Blueprint**, connect the repository, and apply `render.yaml`.
3. After the image builds, open the service's assigned `*.onrender.com` URL and verify
   `/api/health` returns `{"status":"ok", ...}`. `autoDeploy: false` is set deliberately; deploy
   later revisions manually after reviewing and recording the commit.

The included Blueprint uses Render's free plan to avoid opting into a charge. Free instances sleep
when idle, so the first request after inactivity may be slow. For dependable reviewer access, select
an always-on plan in Render (which may incur a charge). The URL remains the same when the plan is
changed.

For a paper or supplement, record the deployed Git commit SHA, service URL, deployment date, and
experiment configuration. Keep one instance per benchmark run and document its plan/CPU allocation:
measured runtimes depend on the host's CPU share. Do not treat cloud demo timings as hardware-
independent results. The API is stateless; it does not persist experiment data.

### Other Docker hosts / manual run

Build and run from the repository root:

```bash
docker build -t dynamicroutelab .
docker run --rm -p 8000:8000 -e PORT=8000 dynamicroutelab
```

For a non-Docker deployment, build the frontend before starting the backend:

```bash
cd frontend && npm ci && npm run build && cd ..
python3 -m pip install -r backend/requirements.txt
python3 -m uvicorn server.main:app --app-dir backend --host 0.0.0.0 --port "${PORT:-8000}"
```

Verify the app starts and `/api/health` responds:

```bash
curl http://localhost:8000/api/health  # should return {"status":"ok","version":"1.0.0",...}
```

**Public-access warning:** no authentication or per-user resource limits are implemented. The API
accepts graph and benchmark requests from anyone who can reach it. Do not put sensitive data on the
service; before opening it broadly, add an access-control and abuse-protection layer at the host or
edge. All built-in data is synthetic, but benchmark requests still consume CPU.

## Using the platform

1. **Overview** — current configuration, graph size, traffic state, seed, and the latest results.
   Empty until you run something.
2. **Laboratory** — interactive graph. Click a road to select it and set its weight or close it.
   Hover for node and road details. Choose the route to highlight. Zoom, fit, and reset are in the
   top-left of the canvas.
3. **Algorithm Comparison** — per-algorithm cost, runtime, processing count, relaxations, path, and
   correctness, with the metric definitions shown. **Settled/expanded/passes are on separate axes**
   and labelled distinctly; use **edge relaxations** for cross-algorithm work comparison.
4. **Traffic Simulator** — apply congestion (percentage, multiplier), then compare before and after:
   changed roads with old and new weights, route change, and cost delta. Reset returns to the
   original graph.
5. **Experiment Runner** — seeded repeated trials, traffic updates, median and variability, and the
   runtime-vs-size sweep (n = 4 to 14). The button is disabled while a run is in progress.
6. **Visualizations** — charts drawn from the executed results (Recharts in the browser; Matplotlib
   for academic 300 DPI exports via `scripts/generate_figures.py`).
7. **Evidence & Export** — CSV and JSON exports, reproducibility details, and the methodology.

## Metric definitions

| Metric | Meaning | Unit / Notes |
|---|---|---|
| Path cost | Sum of traversable road weights on the returned path (recomputed and checked against `reference_dijkstra`). | travel-time units |
| Runtime (ms) | Wall time of one call to an algorithm function (`time.perf_counter_ns`). Excludes generation, traffic updates, and checks. Displayed with 6-decimal precision; do not interpret rounded zeros as zero time. | ms (high-resolution monotonic) |
| Settled (Dijkstra) | Vertices finalised / removed from the priority queue before the target is settled. | count — **not comparable** to passes |
| Expanded (A*) | Vertices removed from the open set before the target. | count — **not comparable** to passes |
| Passes (Bellman–Ford) | Full edge-sweep iterations over the directed edge list. **Not a vertex count.** | count — reported separately |
| Edge relaxations | Directed edge examinations during the search (tentative-distance comparisons). Cross-algorithm work counter (still implementation-dependent). | count |
| Correctness | `pass` if (a) cost matches the independent reference within 1e-6 (or both unreachable) and (b) the path is valid (edges exist, cost recomputed). Otherwise `fail`. | status |
| Route-change frequency | Share of traffic updates where the Dijkstra route differs from the baseline route. Dijkstra is canonical because it is deterministic. | fraction 0–1 |
| Recompute total | Sum of median runtimes across algorithms and updates — measurable recomputation cost (H4; meaningful at larger n). | ms |

**Important:** the dashboard never puts semantically different counters (`settled`, `expanded`, `passes`)
on a single shared comparison axis as though they were the same measure. Where a chart combines metrics,
processed counts are shown with distinct labels/hatching and the caption clarifies non-comparability.

## Streamlit Cloud deployment (existing URL)

`app.py` is the Streamlit deployment entry point and reuses the same graph generator, algorithms,
traffic model, correctness checks, and experiment runner as `backend/server/`. It does not need a
separate FastAPI process. Streamlit Cloud installs the root `requirements.txt`; do not also install
`backend/requirements.txt` into that environment. The latter is for the separate FastAPI deployment.

To update an existing Streamlit Community Cloud app while keeping its URL:

1. In the app settings, confirm the connected repository, deployment branch, and main file path
   (`app.py` at the repository root).
2. Push or merge the reviewed changes to that configured branch. Streamlit Cloud will rebuild the
   app from that commit; use **Reboot app** in its management page if a rebuild does not start.
3. Check the app's deployment logs if dependency installation or startup fails. The Python entry
   point imports shared code from `backend/server/`, so keep that directory in the repository.

For a paper, record the deployed commit SHA and date alongside the Streamlit URL and experiment
configuration. The demo remains synthetic and unauthenticated; do not submit sensitive data, and
consider host-level access/abuse controls before broad public sharing.

Run locally with: `python3 -m pip install -r requirements.txt && streamlit run app.py`.

## Research integrity notes

- All experiments are on the tested synthetic graphs only. Run several seeds, topologies, and sizes
  before making general claims.
- Small-graph runtimes are dominated by timer noise and interpreter overhead. Use medians over
  repeated trials and report variability; do not claim rankings from a single sub-millisecond run.
- The A* heuristic is admissible and consistent on every topology, verified by tests.
  During development an earlier version (`min_edge_weight × Manhattan`) was found to be
  inadmissible on diagonal and random-extra roads and was corrected. The details are in
  `docs/METHODOLOGY.md` §4.1. The corrected heuristic `h(v) = c* × Manhattan(v, target)` with
  `c* = min_e w(e)/L(e)` is verified by tests against `reference_dijkstra`.
- The historical 3×3 paper table is preserved verbatim in `paper/historical_3x3_paper_table.json`;
  its `0.0000 ms` entries are rounded artifacts, not true measurements. The current 8×8 benchmark
  (`results/benchmark_8x8_seed42.*`) is the reproducible evidence for the new platform.
  See `docs/PAPER_RESULTS.md` for hypothesis verdicts and integrity tracking.

## Hypotheses tracking

The platform treats the following as hypotheses, not findings (see `docs/PAPER_RESULTS.md` for
measurable outcomes and current-data verdicts):

- **H1:** A* may expand fewer vertices than Dijkstra on some configurations while returning the same optimal cost.
- **H2:** Relative runtime depends on graph size, topology, edge weights, heuristic quality, and implementation.
- **H3:** Congestion can change the selected route even when the optimal total cost remains unchanged.
- **H4:** Recomputing a shortest path after an update incurs measurable computational cost.

Each hypothesis is tested against actual exports; unsupported results are marked inconclusive.

---

*Authors: Ravi Gohel, Yesha Santoki — Dept. of CSE (AI & ML), Marwadi University, Gujarat, India.*
*All figures and tables in this README describe synthetic data generated by the code in this repository.*
