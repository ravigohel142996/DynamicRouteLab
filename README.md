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
app.py, requirements.txt  Streamlit Cloud entry point; reuses the shared backend research engine
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

- Results describe the tested synthetic graphs only. Run several seeds, topologies, and sizes
  before making general claims.
- Small-graph runtimes are dominated by timer noise and interpreter overhead.
- The A* heuristic is admissible and consistent on every topology, verified by tests.
  During development an earlier version was found to be inadmissible on diagonal and
  random-extra roads and was corrected. The details are in `docs/METHODOLOGY.md` §4.1.
