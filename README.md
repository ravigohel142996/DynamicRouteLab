# DynamicRouteLab

A research platform for comparing **Dijkstra**, **A\* Search**, and **Bellman–Ford** on synthetic
road networks under dynamic traffic: congestion, closures, and travel-time edits.

- Interactive road-network laboratory (zoom, pan, fit, hover, select, close and reopen roads)
- Algorithm comparison on identical graph snapshots, checked against an independent reference
- Dynamic traffic simulator that changes the actual graph (before/after route comparison)
- Reproducible benchmark runner (seeded, repeated trials, median/variability, route-change frequency)
- Charts generated only from executed results
- JSON and CSV exports with configuration, seeds, timestamps, and environment

**All data is synthetic.** Coordinates are grid positions, not real streets. No live traffic
provider is integrated. Methodology, assumptions, and limitations: [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md).

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
docs/METHODOLOGY.md      assumptions, metrics, limitations, reproducibility
examples/sample_experiment.json   sample configuration (sample data, no measurements)
app.py, requirements.txt  original Streamlit prototype, kept for reference (see below)
run_backend.sh, run_frontend.sh   development launch helpers
pytest.ini
```

## Requirements

- Python 3.10 or newer
- Node.js 20.19+ or 22.12+ (required by Vite 8) and npm

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
python3 -m pytest          # runs backend/tests (configured in pytest.ini)
cd frontend && npm run build   # type-checks the frontend and builds the bundle
```

The suite covers:

- Reference agreement on all three topologies, several seeds and weight ranges, and multiple
  endpoint pairs (`test_algorithms.py`)
- Reconstructed paths validated edge-by-edge, with cost recomputed from roads
- Unreachable destinations, source = destination, equal-cost alternatives, negative-cycle detection
- A* heuristic admissibility and consistency after congestion and closures, on every topology
- Traffic semantics: multipliers on original weights (no compounding), closures removed from every
  algorithm, reopen and reset, validation of bad input (`test_traffic.py`)
- Benchmark integrity: reproducible counts and costs for the same configuration, timing statistics,
  validation messages, API contract (`test_benchmark_and_api.py`)

## Production deployment

The backend serves the built frontend, so the platform runs as one process on one port.

```bash
cd frontend && npm ci && npm run build && cd ..          # creates frontend/dist
python3 -m pip install -r backend/requirements.txt
python3 -m uvicorn server.main:app --app-dir backend --host 0.0.0.0 --port "${PORT:-8000}"
```

Notes for a cloud host:

- Set the start command to the uvicorn line above and bind to `0.0.0.0` on the platform's `$PORT`.
- Run the build step during deployment, before the start command. Without `frontend/dist`, the
  API still works, but `/` returns 404.
- The API is stateless, so any number of instances can run behind a load balancer. Be aware that
  benchmark timings depend on the instance's CPU share. Keep one instance per benchmark to reduce noise.
- Experiments are synchronous HTTP requests. In the development sandbox, the largest configuration
  (n = 18, 30 trials, 10 updates, grid + random extra roads) completed in about 1 s. Your timings
  will vary with hardware. Keep the platform's request timeout comfortably above the expected run time.
- No authentication is implemented. Do not expose the instance publicly without an access layer.

## Using the platform

1. **Overview** — current configuration, graph size, traffic state, seed, and the latest results.
   Empty until you run something.
2. **Laboratory** — interactive graph. Click a road to select it and set its weight or close it.
   Hover for node and road details. Choose the route to highlight. Zoom, fit, and reset are in the
   top-left of the canvas.
3. **Algorithm Comparison** — per-algorithm cost, runtime, processing count, relaxations, path, and
   correctness, with the metric definitions shown.
4. **Traffic Simulator** — apply congestion (percentage, multiplier), then compare before and after:
   changed roads with old and new weights, route change, and cost delta. Reset returns to the
   original graph.
5. **Experiment Runner** — seeded repeated trials, traffic updates, median and variability, and the
   runtime-vs-size sweep (n = 4 to 14). The button is disabled while a run is in progress.
6. **Visualizations** — charts drawn from the executed results.
7. **Evidence & Export** — CSV and JSON exports, reproducibility details, and the methodology.

## Metric definitions

| Metric | Meaning |
|---|---|
| Path cost | Sum of traversable road weights on the returned path (recomputed and checked). |
| Runtime (ms) | Wall time of one call to an algorithm function (`perf_counter_ns`). Excludes generation, traffic updates, and checks. |
| Settled (Dijkstra) / Expanded (A*) | Vertices finalised / removed from the open set before the target. |
| Passes (Bellman–Ford) | Full edge-sweep iterations. **Not** a vertex count. |
| Edge relaxations | Directed edge examinations during the search. Cross-algorithm work counter. |
| Correctness | `pass` if the cost matches the reference and the path is valid. |
| Route-change frequency | Share of traffic updates where the Dijkstra route differs from the baseline route. |

## Legacy Streamlit prototype

The original single-file Streamlit prototype is still in the repository as `app.py`
(dependencies in the root `requirements.txt`). It uses its own A* heuristic, which is valid only
on plain grids. The platform above replaces it and should be used for research. Run it only if
needed: `python3 -m pip install -r requirements.txt && streamlit run app.py`.

## Research integrity notes

- Results describe the tested synthetic graphs only. Run several seeds, topologies, and sizes
  before making general claims.
- Small-graph runtimes are dominated by timer noise and interpreter overhead.
- The A* heuristic is admissible and consistent on every topology, verified by tests.
  During development an earlier version was found to be inadmissible on diagonal and
  random-extra roads and was corrected. The details are in `docs/METHODOLOGY.md` §4.1.
