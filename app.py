import heapq
import random
import statistics
import time

import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
import streamlit as st

st.set_page_config(page_title="DynamicRouteLab", page_icon="🚦", layout="wide")

st.title("🚦 DynamicRouteLab")
st.caption("A reproducible research prototype for shortest-path algorithms under changing road travel times.")

with st.sidebar:
    st.header("Experiment controls")
    grid_size = st.slider("Grid width / height", 4, 18, 8)
    trials = st.slider("Timing repetitions", 3, 30, 10)
    seed = st.number_input("Random seed", min_value=0, max_value=999999, value=42)
    congestion_pct = st.slider("Roads affected by congestion (%)", 5, 60, 20, 5)
    congestion_factor = st.slider("Congestion multiplier", 1.5, 8.0, 3.0, 0.5)
    st.caption("Synthetic grid network; edge weights are estimated travel-time units.")

def build_grid(n, seed):
    rng = random.Random(int(seed))
    G = nx.grid_2d_graph(n, n)
    # Make roads bidirectional and assign a stable positive weight per undirected edge.
    for u, v in G.edges():
        w = rng.randint(2, 12)
        G[u][v]["weight"] = float(w)
    return G

def copy_graph(G):
    H = nx.Graph()
    H.add_nodes_from(G.nodes(data=True))
    H.add_edges_from((u, v, data.copy()) for u, v, data in G.edges(data=True))
    return H

def dijkstra_path(G, source, target):
    dist = {v: float("inf") for v in G}
    parent = {}
    dist[source] = 0.0
    pq = [(0.0, source)]
    settled = set()
    relaxations = 0
    while pq:
        cost, u = heapq.heappop(pq)
        if cost != dist[u] or u in settled:
            continue
        settled.add(u)
        if u == target:
            break
        for v, data in G[u].items():
            relaxations += 1
            nd = cost + data["weight"]
            if nd < dist[v]:
                dist[v] = nd
                parent[v] = u
                heapq.heappush(pq, (nd, v))
    return reconstruct(source, target, parent, dist[target]), dist[target], len(settled), relaxations

def astar_path(G, source, target):
    # Manhattan distance multiplied by the global minimum edge weight is admissible
    # on this grid because every move changes one coordinate by one.
    min_w = min((d["weight"] for _, _, d in G.edges(data=True)), default=0.0)
    def h(v):
        return min_w * (abs(v[0] - target[0]) + abs(v[1] - target[1]))
    g = {v: float("inf") for v in G}
    parent = {}
    g[source] = 0.0
    pq = [(h(source), 0.0, source)]
    expanded = set()
    relaxations = 0
    while pq:
        f, cost, u = heapq.heappop(pq)
        if cost != g[u] or u in expanded:
            continue
        expanded.add(u)
        if u == target:
            break
        for v, data in G[u].items():
            relaxations += 1
            nd = g[u] + data["weight"]
            if nd < g[v]:
                g[v] = nd
                parent[v] = u
                heapq.heappush(pq, (nd + h(v), nd, v))
    return reconstruct(source, target, parent, g[target]), g[target], len(expanded), relaxations

def bellman_ford_path(G, source, target):
    dist = {v: float("inf") for v in G}
    parent = {}
    dist[source] = 0.0
    edges = list(G.edges(data=True))
    # Graph is undirected, so relax both directions.
    directed_edges = []
    for u, v, data in edges:
        directed_edges.append((u, v, data["weight"]))
        directed_edges.append((v, u, data["weight"]))
    passes = 0
    relaxations = 0
    for _ in range(max(0, len(G) - 1)):
        changed = False
        passes += 1
        for u, v, w in directed_edges:
            relaxations += 1
            if dist[u] != float("inf") and dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
                parent[v] = u
                changed = True
        if not changed:
            break
    return reconstruct(source, target, parent, dist[target]), dist[target], passes, relaxations

def reconstruct(source, target, parent, cost):
    if cost == float("inf"):
        return [], cost
    path = [target]
    while path[-1] != source:
        if path[-1] not in parent:
            return [], float("inf")
        path.append(parent[path[-1]])
    path.reverse()
    return path, cost

ALGORITHMS = {
    "Dijkstra": dijkstra_path,
    "A* Search": astar_path,
    "Bellman–Ford": bellman_ford_path,
}

def benchmark(G, source, target, trials):
    rows = []
    paths = {}
    costs = {}
    for name, algo in ALGORITHMS.items():
        durations = []
        last = None
        for _ in range(trials):
            t0 = time.perf_counter_ns()
            result = algo(G, source, target)
            durations.append((time.perf_counter_ns() - t0) / 1e6)
            last = result
        path, cost, processed, relaxations = last
        paths[name], costs[name] = path, cost
        rows.append({
            "Algorithm": name,
            "Path cost": round(cost, 4),
            "Median runtime (ms)": round(statistics.median(durations), 5),
            "Processed count": processed,
            "Edge relaxations": relaxations,
        })
    return pd.DataFrame(rows), paths, costs

def draw_graph(G, paths, title, source, target):
    fig, ax = plt.subplots(figsize=(8, 6))
    pos = {(r, c): (c, -r) for r, c in G.nodes()}
    nx.draw_networkx_edges(G, pos, ax=ax, edge_color="#a8b0bd", width=0.8, alpha=0.55)
    nx.draw_networkx_nodes(G, pos, ax=ax, node_size=18, node_color="#8a94a6")
    if source in G:
        nx.draw_networkx_nodes(G, pos, nodelist=[source], ax=ax, node_size=130, node_color="#22c55e", label="Source")
    if target in G:
        nx.draw_networkx_nodes(G, pos, nodelist=[target], ax=ax, node_size=130, node_color="#ef4444", label="Target")
    palette = {"Dijkstra": "#2563eb", "A* Search": "#9333ea", "Bellman–Ford": "#f59e0b"}
    # Show the A* route for a clean visual; all algorithm costs are in the table.
    chosen = paths.get("A* Search", [])
    if len(chosen) > 1:
        route_edges = list(zip(chosen[:-1], chosen[1:]))
        nx.draw_networkx_edges(G, pos, edgelist=route_edges, ax=ax, edge_color=palette["A* Search"], width=3.2)
        nx.draw_networkx_nodes(G, pos, nodelist=chosen, ax=ax, node_size=35, node_color=palette["A* Search"])
    ax.set_title(title + " — highlighted route: A*")
    ax.axis("off")
    ax.legend(loc="upper right")
    fig.tight_layout()
    return fig

# Session state keeps the congestion scenario stable across Streamlit reruns.
if "base_graph" not in st.session_state or st.session_state.get("seed") != int(seed) or st.session_state.get("n") != grid_size:
    st.session_state.base_graph = build_grid(grid_size, int(seed))
    st.session_state.seed = int(seed)
    st.session_state.n = grid_size
    st.session_state.congested_graph = None
    st.session_state.congestion_edges = []

base_graph = copy_graph(st.session_state.base_graph)
source, target = (0, 0), (grid_size - 1, grid_size - 1)

if st.button("🚧 Apply congestion update", type="primary"):
    changed = copy_graph(base_graph)
    edge_list = list(changed.edges())
    rng = random.Random(int(seed) + 1000 + int(congestion_pct * 10) + int(congestion_factor * 10))
    count = max(1, round(len(edge_list) * congestion_pct / 100))
    chosen_edges = rng.sample(edge_list, min(count, len(edge_list)))
    for u, v in chosen_edges:
        changed[u][v]["weight"] *= congestion_factor
    st.session_state.congested_graph = changed
    st.session_state.congestion_edges = chosen_edges

scenario = st.radio("Network state", ["Normal traffic", "After congestion"], horizontal=True)
if scenario == "After congestion":
    if st.session_state.congested_graph is None:
        st.info("Click **Apply congestion update** to generate the updated network.")
        active_graph = base_graph
        scenario_title = "Normal traffic (no update applied yet)"
    else:
        active_graph = copy_graph(st.session_state.congested_graph)
        scenario_title = "After congestion update"
else:
    active_graph = base_graph
    scenario_title = "Normal traffic"

with st.spinner("Benchmarking algorithms..."):
    results_df, paths, costs = benchmark(active_graph, source, target, int(trials))

finite_costs = [v for v in costs.values() if v != float("inf")]
correct = bool(finite_costs) and max(finite_costs) - min(finite_costs) < 1e-8

m1, m2, m3, m4 = st.columns(4)
m1.metric("Intersections", f"{active_graph.number_of_nodes():,}")
m2.metric("Road segments", f"{active_graph.number_of_edges():,}")
m3.metric("Algorithms agree on cost", "Yes" if correct else "Check results")
m4.metric("Timing repetitions", int(trials))

left, right = st.columns([1.2, 1])
with left:
    st.subheader("🗺️ Road network and selected route")
    st.pyplot(draw_graph(active_graph, paths, scenario_title, source, target), use_container_width=True)
    st.caption("The highlighted route is the A* route. The visualization is a synthetic grid, not a geographic map.")
with right:
    st.subheader("📊 Benchmark results")
    st.dataframe(results_df, hide_index=True, use_container_width=True)
    st.subheader("Runtime comparison")
    st.bar_chart(results_df.set_index("Algorithm")[["Median runtime (ms)"]])
    st.subheader("Edge-relaxation comparison")
    st.bar_chart(results_df.set_index("Algorithm")[["Edge relaxations"]])

st.subheader("🧪 Research interpretation")
if correct:
    st.success("Correctness check passed: all three algorithms returned the same shortest-path cost for this graph.")
else:
    st.warning("The reported costs do not all agree. Check the graph and implementation before drawing conclusions.")

if scenario == "After congestion" and st.session_state.congested_graph is not None:
    st.write(f"Congestion affected **{len(st.session_state.congestion_edges)}** road segments. Compare the selected route and path cost with Normal traffic.")
else:
    st.write("Use **Apply congestion update**, then select **After congestion** to observe how higher travel times can change the best route.")

st.info(
    "Research note: this app uses synthetic non-negative edge weights. "
    "Runtime results on small graphs are noisy; use larger networks, repeated trials, "
    "and multiple seeds before making general performance claims. "
    "The Bellman–Ford processed count is relaxation passes; edge relaxations are reported separately."
)

csv = results_df.to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Download benchmark table (CSV)", data=csv, file_name="dynamicroutelab_results.csv", mime="text/csv")

with st.expander("Reproducibility details"):
    st.markdown(f"""
    - Random seed: `{int(seed)}`
    - Grid size: `{grid_size} × {grid_size}`
    - Timing repetitions per algorithm: `{int(trials)}`
    - Source: `{source}`
    - Target: `{target}`
    - Weight model: deterministic integer travel-time weights from 2 to 12
    - Traffic update: selected road weights multiplied by `{congestion_factor}`
    - A* heuristic: Manhattan distance multiplied by the current minimum edge weight
    """)
