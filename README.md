# DynamicRouteLab

Interactive research prototype for comparing Dijkstra, A* Search, and Bellman–Ford on synthetic dynamic road networks.

## Run locally

1. Install Python 3.10 or newer.
2. Open a terminal in this folder.
3. Install dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

4. Launch the dashboard:

   ```bash
   streamlit run app.py
   ```

## Features

- Configurable synthetic grid graph
- Deterministic road weights using a selected random seed
- Dijkstra, A*, and Bellman–Ford
- Repeated runtime trials and median runtime
- Path cost, processing count, and edge-relaxation count
- Congestion update simulation
- Route visualization and benchmark charts
- CSV export

## Research integrity notes

This prototype uses synthetic data, not live traffic. The app's results should be described as measurements on the tested synthetic graphs only. Run multiple seeds and graph sizes before making general claims. Runtime on small graphs is sensitive to measurement noise. The `Processed count` is algorithm-specific: settled vertices for Dijkstra, expanded vertices for A*, and relaxation passes for Bellman–Ford. Use edge-relaxation counts as a more comparable work metric, while noting that even this metric does not capture every implementation cost.

A* uses Manhattan distance multiplied by the minimum current edge weight, which is admissible on this grid because every road edge changes one coordinate by one. All generated weights remain non-negative.
