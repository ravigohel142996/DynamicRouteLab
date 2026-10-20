"""Streamlit entry point for the DynamicRouteLab research platform.

The Streamlit deployment calls the same algorithms, graph generator, traffic model, and
benchmark runner as the FastAPI/React app in backend/server. This keeps the existing
Streamlit Cloud URL usable without running a separate API process.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import networkx as nx
import pandas as pd
import streamlit as st


# Streamlit Cloud starts at the repository root, while the shared research engine lives in
# backend/server. Adding backend/ to the import path lets this app reuse that tested code.
BACKEND_DIR = str(Path(__file__).resolve().parent / "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from server import __version__  # noqa: E402
from server.benchmark import (  # noqa: E402
    ALGORITHMS,
    LABELS,
    PROCESSED_KIND,
    benchmark_snapshot,
    run_experiment,
    run_snapshot,
)
from server.graph.generator import generate_grid  # noqa: E402
from server.graph.traffic import (  # noqa: E402
    CONGESTION_SEED_OFFSET,
    apply_congestion,
    reset_graph,
    set_edge_weight,
    set_road_closed,
)


st.set_page_config(
    page_title="DynamicRouteLab",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded",
)

TOPOLOGIES = {
    "grid": "Orthogonal grid",
    "grid_diagonal": "Grid + diagonal roads",
    "random_extra": "Grid + random extra roads",
}
ALGORITHM_LABELS = {key: LABELS[key] for key in ALGORITHMS}


def _cost_text(cost: Any) -> str:
    if cost is None:
        return "Unreachable"
    try:
        return f"{float(cost):,.3f}"
    except (TypeError, ValueError):
        return "Unreachable"


def _snapshot_frame(snapshot: dict) -> pd.DataFrame:
    rows = []
    for name in ALGORITHMS:
        result = snapshot["results"][name]
        processed_key = PROCESSED_KIND[name]
        rows.append({
            "Algorithm": LABELS[name],
            "Path cost": result["cost"],
            "Runtime (ms, single run)": result.get("runtime_ms", 0.0),
            f"{processed_key.title()} count": result.get(processed_key, 0),
            "Edge relaxations": result.get("relaxations", 0),
            "Correctness": result["correctness"]["status"],
        })
    return pd.DataFrame(rows)


def _benchmark_frame(benchmark: dict) -> pd.DataFrame:
    rows = []
    for name in ALGORITHMS:
        summary = benchmark["summary"][name]
        rows.append({
            "Algorithm": LABELS[name],
            "Path cost": summary["path_cost"],
            "Median runtime (ms)": summary["median_runtime_ms"],
            "Mean runtime (ms)": summary["mean_runtime_ms"],
            "Std. dev. (ms)": summary["stdev_runtime_ms"],
            "Min (ms)": summary["min_runtime_ms"],
            "Max (ms)": summary["max_runtime_ms"],
            "Processed median": summary["processed_median"],
            "Relaxations median": summary["relaxations_median"],
            "Correctness rate": summary["correctness_pass_rate"],
        })
    return pd.DataFrame(rows)


def _experiment_frame(experiment: dict) -> pd.DataFrame:
    rows = []
    scenarios = [("Normal", experiment.get("normal"))]
    if experiment.get("congested") is not None:
        scenarios.append(("Congested", experiment["congested"]))
    for scenario, summaries in scenarios:
        for name in ALGORITHMS:
            summary = summaries[name]
            rows.append({
                "Scenario": scenario,
                "Algorithm": LABELS[name],
                "Path cost": summary["path_cost"],
                "Median runtime (ms)": summary["median_runtime_ms"],
                "Mean runtime (ms)": summary["mean_runtime_ms"],
                "Std. dev. (ms)": summary["stdev_runtime_ms"],
                "Processed median": summary["processed_median"],
                "Relaxations median": summary["relaxations_median"],
                "Correctness rate": summary["correctness_pass_rate"],
            })
    return pd.DataFrame(rows)


def _trial_frame(experiment: dict) -> pd.DataFrame:
    rows = []
    scenarios = [("normal", experiment.get("normal"))]
    if experiment.get("congested") is not None:
        scenarios.append(("congested", experiment["congested"]))
    for scenario, summaries in scenarios:
        for name in ALGORITHMS:
            for trial in summaries[name]["trials_raw"]:
                rows.append({
                    "scenario": scenario,
                    "algorithm": LABELS[name],
                    **trial,
                })
    return pd.DataFrame(rows)


def _graph_fingerprint(graph: dict, source: str, target: str, trials: int) -> str:
    payload = json.dumps(
        {"graph": graph, "source": source, "target": target, "trials": trials},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@st.cache_data(show_spinner=False)
def _cached_snapshot(graph: dict, source: str, target: str) -> dict:
    """Keep the single-run diagnostic stable across ordinary Streamlit reruns."""
    return run_snapshot(graph, source, target)


def _draw_graph(graph: dict, path: list[str], source: str, target: str, title: str) -> None:
    network = nx.Graph()
    positions = {}
    for node in graph["nodes"]:
        network.add_node(node["id"])
        positions[node["id"]] = (node["x"], node["y"])

    open_edges, modified_edges, closed_edges = [], [], []
    labels = {}
    for edge in graph["edges"]:
        pair = (edge["source"], edge["target"])
        network.add_edge(*pair, **edge)
        if edge.get("closed", False):
            closed_edges.append(pair)
        elif abs(float(edge["weight"]) - float(edge["original_weight"])) > 1e-9:
            modified_edges.append(pair)
        else:
            open_edges.append(pair)
        labels[pair] = f"{float(edge['weight']):g}"

    route_edges = list(zip(path[:-1], path[1:])) if len(path) > 1 else []
    fig, ax = plt.subplots(figsize=(9, 7))
    nx.draw_networkx_edges(
        network, positions, edgelist=open_edges, ax=ax,
        edge_color="#aeb8c5", width=0.9, alpha=0.75,
    )
    nx.draw_networkx_edges(
        network, positions, edgelist=modified_edges, ax=ax,
        edge_color="#f59e0b", width=1.8, alpha=0.9,
    )
    nx.draw_networkx_edges(
        network, positions, edgelist=closed_edges, ax=ax,
        edge_color="#ef4444", width=1.3, style="dashed", alpha=0.85,
    )
    if route_edges:
        nx.draw_networkx_edges(
            network, positions, edgelist=route_edges, ax=ax,
            edge_color="#2563eb", width=3.2, alpha=0.95,
        )

    nx.draw_networkx_nodes(
        network, positions, ax=ax, node_size=23, node_color="#64748b",
        linewidths=0.25, edgecolors="white",
    )
    if path:
        nx.draw_networkx_nodes(
            network, positions, nodelist=path, ax=ax, node_size=35,
            node_color="#60a5fa", linewidths=0.3, edgecolors="white",
        )
    if source in network:
        nx.draw_networkx_nodes(
            network, positions, nodelist=[source], ax=ax, node_size=125,
            node_color="#22c55e", edgecolors="white", linewidths=0.7,
        )
    if target in network:
        nx.draw_networkx_nodes(
            network, positions, nodelist=[target], ax=ax, node_size=125,
            node_color="#ef4444", edgecolors="white", linewidths=0.7,
        )
    if graph.get("meta", {}).get("n", 99) <= 6:
        nx.draw_networkx_edge_labels(
            network, positions, edge_labels=labels, ax=ax,
            font_size=6, font_color="#475569", rotate=False,
        )

    legend = [
        Line2D([0], [0], color="#aeb8c5", lw=1.4, label="Open road"),
        Line2D([0], [0], color="#f59e0b", lw=2, label="Changed travel time"),
        Line2D([0], [0], color="#ef4444", lw=1.5, linestyle="--", label="Closed road"),
        Line2D([0], [0], color="#2563eb", lw=3, label="Selected route"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#22c55e", label="Source"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#ef4444", label="Target"),
    ]
    ax.legend(handles=legend, loc="upper left", frameon=False, ncol=2, fontsize=8)
    ax.set_title(title)
    ax.set_axis_off()
    ax.set_aspect("equal", adjustable="datalim")
    fig.tight_layout()
    st.pyplot(fig, width="stretch")
    plt.close(fig)


def _experiment_csv_frame(experiment: dict) -> pd.DataFrame:
    frame = _trial_frame(experiment)
    if frame.empty:
        return pd.DataFrame(columns=["scenario", "algorithm", "trial", "runtime_ms", "cost", "processed", "relaxations", "correct"])
    return frame


# --------------------------------------------------------------------------- configuration and session state

st.title("🚦 DynamicRouteLab")
st.caption(
    "A reproducible laboratory for shortest-path algorithms on synthetic road networks. "
    "The Streamlit app uses the same validated research engine as the API edition."
)

with st.sidebar:
    st.header("Experiment controls")
    grid_size = st.slider("Grid width / height", min_value=4, max_value=18, value=8)
    seed = int(st.number_input("Random seed", min_value=0, max_value=2**31 - 1, value=42, step=1))
    topology = st.selectbox(
        "Network topology",
        options=list(TOPOLOGIES),
        format_func=lambda value: TOPOLOGIES[value],
    )
    weight_min, weight_max = st.slider(
        "Original road-weight range", min_value=1, max_value=30, value=(2, 12),
    )
    trials = st.slider("Timing repetitions", min_value=1, max_value=30, value=10)
    updates = st.slider("Traffic updates per experiment", min_value=1, max_value=10, value=2)
    congestion_pct = st.slider("Roads affected by congestion (%)", min_value=0, max_value=100, value=20, step=5)
    congestion_factor = st.slider("Congestion multiplier", min_value=1.0, max_value=10.0, value=3.0, step=0.5)
    st.caption("All coordinates and travel times are synthetic; they do not represent real streets.")

graph_config = (grid_size, seed, topology, weight_min, weight_max)
if st.session_state.get("_graph_config") != graph_config:
    generated = generate_grid(
        grid_size,
        seed,
        topology=topology,
        weight_min=weight_min,
        weight_max=weight_max,
    )
    st.session_state["_graph_config"] = graph_config
    st.session_state["original_graph"] = generated
    st.session_state["normal_graph"] = copy.deepcopy(generated)
    st.session_state["congested_graph"] = None
    st.session_state["traffic_changes"] = []
    st.session_state["affected_edge_ids"] = []
    st.session_state["source_node"] = "0_0"
    st.session_state["selected_road_edge"] = generated["edges"][0]["id"]
    st.session_state["target_node"] = f"{grid_size - 1}_{grid_size - 1}"
    st.session_state["scenario"] = "Normal traffic"
    st.session_state["benchmark_result"] = None
    st.session_state["benchmark_key"] = None
    st.session_state["experiment_result"] = None
    st.session_state["scale_sweep"] = None

node_ids = [node["id"] for node in st.session_state["normal_graph"]["nodes"]]
with st.sidebar:
    st.divider()
    st.subheader("Route endpoints")
    st.selectbox("Source intersection", node_ids, key="source_node")
    st.selectbox("Target intersection", node_ids, key="target_node")
    st.radio(
        "Network state",
        options=["Normal traffic", "After congestion"],
        key="scenario",
    )
    st.caption("Congestion can be applied and roads edited in the Traffic Simulator tab.")

source = st.session_state["source_node"]
target = st.session_state["target_node"]
scenario = st.session_state["scenario"]
normal_graph = st.session_state["normal_graph"]
congested_graph = st.session_state.get("congested_graph")
if scenario == "After congestion" and congested_graph is not None:
    active_graph = congested_graph
    active_label = "After congestion"
else:
    active_graph = normal_graph
    active_label = "Normal traffic"
active_snapshot = _cached_snapshot(active_graph, source, target)

overview_tab, traffic_tab, experiment_tab, evidence_tab = st.tabs(
    ["Overview & graph", "Traffic simulator", "Experiment runner", "Evidence & export"]
)


# --------------------------------------------------------------------------- overview and graph

with overview_tab:
    open_roads = sum(not edge.get("closed", False) for edge in active_graph["edges"])
    metric_cols = st.columns(4)
    metric_cols[0].metric("Intersections", f"{len(active_graph['nodes']):,}")
    metric_cols[1].metric("Road segments", f"{len(active_graph['edges']):,}")
    metric_cols[2].metric("Traversable roads", f"{open_roads:,}")
    metric_cols[3].metric("Network state", active_label)

    left, right = st.columns([1.15, 1])
    with left:
        st.subheader("🗺️ Road network and selected route")
        route_algorithm = st.selectbox(
            "Route to highlight",
            options=ALGORITHMS,
            format_func=lambda name: LABELS[name],
            key="route_algorithm",
        )
        selected_result = active_snapshot["results"][route_algorithm]
        _draw_graph(
            active_graph,
            selected_result.get("path", []),
            source,
            target,
            f"{active_label} — highlighted route: {LABELS[route_algorithm]}",
        )
        st.caption("Synthetic grid coordinates only; this is not a geographic map.")

    with right:
        st.subheader("Algorithm comparison — identical graph snapshot")
        st.dataframe(_snapshot_frame(active_snapshot), hide_index=True, width="stretch")
        if active_snapshot["agreement"] and all(
            active_snapshot["results"][name]["correctness"]["status"] == "pass"
            for name in ALGORITHMS
        ):
            st.success(f"All algorithms agree with the independent reference. Reference cost: {_cost_text(active_snapshot['reference_cost'])}.")
        else:
            st.error("Correctness check failed or algorithms disagree. Do not use this result without investigating it.")
        st.caption(
            "Single-call runtimes are noisy. Settled/expanded vertices and Bellman–Ford passes "
            "are algorithm-specific; edge relaxations are reported separately."
        )

    st.subheader("Repeated timing benchmark")
    st.write(
        f"Run {trials} round-robin trials per algorithm with a warm-up. "
        "Graph generation, reference checks, and rendering are outside the timed calls."
    )
    current_benchmark_key = _graph_fingerprint(active_graph, source, target, trials)
    if st.button("Run fresh repeated benchmark", type="primary", key="run_fresh_benchmark"):
        with st.spinner("Running interleaved algorithm trials…"):
            st.session_state["benchmark_result"] = benchmark_snapshot(
                active_graph, source, target, trials,
            )
            st.session_state["benchmark_key"] = current_benchmark_key

    benchmark = st.session_state.get("benchmark_result")
    if benchmark is not None and st.session_state.get("benchmark_key") == current_benchmark_key:
        benchmark_df = _benchmark_frame(benchmark)
        st.dataframe(benchmark_df, hide_index=True, width="stretch")
        chart = benchmark_df.set_index("Algorithm")[["Median runtime (ms)"]]
        st.bar_chart(chart, width="stretch")
        if any(row["Correctness rate"] < 1.0 for _, row in benchmark_df.iterrows()):
            st.error("At least one algorithm failed a repeated-trial correctness check.")
    else:
        st.info("No repeated benchmark is saved for this exact graph and endpoint pair yet.")


# --------------------------------------------------------------------------- traffic simulator

with traffic_tab:
    st.subheader("Dynamic traffic and road editing")
    st.write(
        "Apply seeded congestion to a percentage of open roads, compare the route before and after, "
        "or manually change/close a road. Every algorithm uses the same updated graph."
    )
    col_apply, col_reset = st.columns(2)
    with col_apply:
        if st.button("🚧 Apply congestion update", type="primary", key="apply_congestion"):
            updated, changes, affected = apply_congestion(
                st.session_state["normal_graph"],
                congestion_pct,
                congestion_factor,
                seed + CONGESTION_SEED_OFFSET,
            )
            st.session_state["congested_graph"] = updated
            st.session_state["traffic_changes"] = changes
            st.session_state["affected_edge_ids"] = affected
            st.success(f"Updated {len(changes)} open roads. Select ‘After congestion’ in the sidebar to inspect the new route.")
    with col_reset:
        if st.button("Reset all roads to generated weights", key="reset_all_roads"):
            st.session_state["normal_graph"] = reset_graph(st.session_state["original_graph"])
            st.session_state["congested_graph"] = None
            st.session_state["traffic_changes"] = []
            st.session_state["affected_edge_ids"] = []
            st.session_state["benchmark_result"] = None
            st.session_state["benchmark_key"] = None
            st.info("Road weights and closures were reset. Select Normal traffic in the sidebar if needed.")

    if congested_graph is not None:
        before = _cached_snapshot(normal_graph, source, target)
        after = _cached_snapshot(congested_graph, source, target)
        before_cost = before["results"]["dijkstra"]["cost"]
        after_cost = after["results"]["dijkstra"]["cost"]
        before_path = before["results"]["dijkstra"]["path"]
        after_path = after["results"]["dijkstra"]["path"]
        delta = (after_cost - before_cost) if before_cost is not None and after_cost is not None else None
        comparison_cols = st.columns(4)
        comparison_cols[0].metric("Normal route cost", _cost_text(before_cost))
        comparison_cols[1].metric("Updated route cost", _cost_text(after_cost), delta=f"{delta:+.3f}" if delta is not None else None)
        comparison_cols[2].metric("Route changed", "Yes" if before_path != after_path else "No")
        comparison_cols[3].metric("Roads changed", len(st.session_state.get("traffic_changes", [])))
        changes = st.session_state.get("traffic_changes", [])
        if changes:
            st.dataframe(pd.DataFrame(changes), hide_index=True, width="stretch")
        else:
            st.caption("The current congested snapshot has no weight changes (for example, congestion may be set to 0%).")
    else:
        st.info("No congestion scenario has been generated. Use ‘Apply congestion update’ above.")

    st.divider()
    st.markdown(f"**Editing:** {active_label} · **Selected route:** `{source}` → `{target}`")
    edit_graph = active_graph
    edge_lookup = {edge["id"]: edge for edge in edit_graph["edges"]}
    edge_ids = list(edge_lookup)

    def _edge_option(edge_id: str) -> str:
        edge = edge_lookup[edge_id]
        state = "closed" if edge.get("closed", False) else "open"
        return (
            f"{edge['source']} ↔ {edge['target']} · {float(edge['weight']):g} · {state}"
        )

    selected_edge_id = st.selectbox(
        "Road segment to edit",
        options=edge_ids,
        format_func=_edge_option,
        key="selected_road_edge",
    )
    selected_edge = edge_lookup[selected_edge_id]
    edit_col, close_col = st.columns([1, 1])
    with edit_col:
        new_weight = st.number_input(
            "Travel-time weight",
            min_value=0.0,
            max_value=1_000_000.0,
            value=float(selected_edge["weight"]),
            step=0.5,
            key=f"weight_{selected_edge_id}",
        )
        if st.button("Set road weight", key="set_road_weight"):
            updated = set_edge_weight(edit_graph, selected_edge_id, new_weight)
            if active_label == "After congestion" and congested_graph is not None:
                st.session_state["congested_graph"] = updated
            else:
                st.session_state["normal_graph"] = updated
                st.session_state["congested_graph"] = None
                st.session_state["traffic_changes"] = []
            st.session_state["benchmark_result"] = None
            st.session_state["benchmark_key"] = None
            st.success("Road weight updated.")
    with close_col:
        st.write("Road closure")
        action_label = "Reopen selected road" if selected_edge.get("closed", False) else "Close selected road"
        if st.button(action_label, key="toggle_road_closure"):
            updated = set_road_closed(edit_graph, selected_edge_id, None)
            if active_label == "After congestion" and congested_graph is not None:
                st.session_state["congested_graph"] = updated
            else:
                st.session_state["normal_graph"] = updated
                st.session_state["congested_graph"] = None
                st.session_state["traffic_changes"] = []
            st.session_state["benchmark_result"] = None
            st.session_state["benchmark_key"] = None
            st.success("Road closure state updated.")

    st.caption("Manual edits affect the selected traffic state. Editing the normal graph clears any older congestion snapshot.")


# --------------------------------------------------------------------------- reproducible experiment runner

with experiment_tab:
    st.subheader("Seeded repeated experiment")
    st.caption("The settings below are for the next run; prior results remain labeled with their saved configuration.")
    st.write(
        "The runner creates a fresh synthetic graph from the sidebar configuration, benchmarks all "
        "three algorithms on the same baseline, then applies independent seeded congestion draws."
    )
    st.code(
        f"n={grid_size}, seed={seed}, topology={topology}, trials={trials}, updates={updates}, "
        f"congestion={congestion_pct}% × {congestion_factor:g}, endpoints={source} → {target}",
        language="text",
    )
    if st.button("Run reproducible experiment", type="primary", key="run_full_experiment"):
        try:
            with st.spinner("Running baseline and traffic-update trials…"):
                experiment_result = run_experiment(
                    n=grid_size,
                    seed=seed,
                    topology=topology,
                    trials=trials,
                    congestion_pct=congestion_pct,
                    congestion_factor=congestion_factor,
                    source=source,
                    target=target,
                    updates=updates,
                    weight_min=weight_min,
                    weight_max=weight_max,
                )
                experiment_result["env"]["packages"].update({
                    "streamlit": st.__version__,
                    "networkx": nx.__version__,
                    "matplotlib": matplotlib.__version__,
                    "pandas": pd.__version__,
                })
                st.session_state["experiment_result"] = experiment_result
        except ValueError as exc:
            st.error(str(exc))

    experiment = st.session_state.get("experiment_result")
    if experiment is not None:
        experiment_df = _experiment_frame(experiment)
        comparison = experiment["comparison"]
        exp_cols = st.columns(4)
        exp_cols[0].metric("Baseline route cost", _cost_text(comparison["normal_cost"]))
        exp_cols[1].metric("First update cost", _cost_text(comparison["congested_cost"]))
        exp_cols[2].metric("First route changed", "Yes" if comparison["route_changed"] else "No")
        frequency = experiment.get("route_change_frequency")
        exp_cols[3].metric("Route-change frequency", f"{frequency:.0%}" if frequency is not None else "—")

        st.dataframe(experiment_df, hide_index=True, width="stretch")
        chart_df = experiment_df.pivot(
            index="Algorithm", columns="Scenario", values="Median runtime (ms)"
        )
        st.bar_chart(chart_df, width="stretch")
        st.subheader("Traffic update outcomes")
        updates_df = pd.DataFrame(experiment["updates"])
        if not updates_df.empty:
            st.dataframe(
                updates_df[[
                    "index", "congestion_seed", "affected_count", "cost_before", "cost_after",
                    "cost_delta", "route_changed", "cost_unchanged", "all_correct",
                ]],
                hide_index=True,
                width="stretch",
            )
        with st.expander("Experiment configuration and environment"):
            st.json({
                "config": experiment["config"],
                "environment": experiment["env"],
                "timestamp_utc": experiment["timestamp_iso"],
                "wall_clock_ms": experiment["wall_clock_ms"],
            })

    st.divider()
    st.subheader("Runtime-versus-size sweep")
    st.caption("Optional: compares baseline median runtime at fixed sizes 4, 6, 8, 10, 12, and 14. Sweep trials are capped at 10.")
    if st.button("Run size sweep", key="run_size_sweep"):
        sizes = [4, 6, 8, 10, 12, 14]
        sweep_rows = []
        sweep_progress = st.progress(0, text="Preparing size sweep…")
        try:
            for index, size in enumerate(sizes, start=1):
                result = run_experiment(
                    n=size,
                    seed=seed,
                    topology=topology,
                    trials=min(trials, 10),
                    congestion_pct=congestion_pct,
                    congestion_factor=congestion_factor,
                    source=None,
                    target=None,
                    updates=1,
                    weight_min=weight_min,
                    weight_max=weight_max,
                )
                for name in ALGORITHMS:
                    sweep_rows.append({
                        "Grid side": size,
                        "Intersections": size * size,
                        "Algorithm": LABELS[name],
                        "Median runtime (ms)": result["normal"][name]["median_runtime_ms"],
                    })
                sweep_progress.progress(index / len(sizes), text=f"Completed grid {size} × {size}")
            st.session_state["scale_sweep"] = sweep_rows
        except ValueError as exc:
            st.error(str(exc))

    sweep_rows = st.session_state.get("scale_sweep")
    if sweep_rows:
        sweep_df = pd.DataFrame(sweep_rows)
        sweep_chart = sweep_df.pivot(
            index="Intersections", columns="Algorithm", values="Median runtime (ms)"
        )
        st.line_chart(sweep_chart, width="stretch")
        st.dataframe(sweep_df, hide_index=True, width="stretch")


# --------------------------------------------------------------------------- evidence and export

with evidence_tab:
    st.subheader("Research evidence and exports")
    st.write("Download the exact graph snapshot, settings, correctness results, environment, and trial measurements used in this session.")

    snapshot_csv = _snapshot_frame(active_snapshot).to_csv(index=False).encode("utf-8")
    snapshot_export = {
        "application": "DynamicRouteLab Streamlit",
        "software_version": __version__,
        "exported_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "config": {
            "grid_size": grid_size,
            "seed": seed,
            "topology": topology,
            "weight_min": weight_min,
            "weight_max": weight_max,
            "source": source,
            "target": target,
            "scenario": active_label,
            "timing_repetitions": trials,
        },
        "graph": active_graph,
        "snapshot": active_snapshot,
    }
    json_col, csv_col = st.columns(2)
    with json_col:
        st.download_button(
            "Download graph + results (JSON)",
            data=json.dumps(snapshot_export, indent=2, ensure_ascii=False, allow_nan=False),
            file_name="dynamicroutelab_snapshot.json",
            mime="application/json",
            width="stretch",
        )
    with csv_col:
        st.download_button(
            "Download snapshot table (CSV)",
            data=snapshot_csv,
            file_name="dynamicroutelab_snapshot.csv",
            mime="text/csv",
            width="stretch",
        )

    if benchmark is not None and st.session_state.get("benchmark_key") == current_benchmark_key:
        st.download_button(
            "Download repeated benchmark (CSV)",
            data=_benchmark_frame(benchmark).to_csv(index=False).encode("utf-8"),
            file_name="dynamicroutelab_repeated_benchmark.csv",
            mime="text/csv",
            width="stretch",
        )

    if experiment is not None:
        exp_json = json.dumps(experiment, indent=2, ensure_ascii=False, allow_nan=False)
        trial_csv = _experiment_csv_frame(experiment).to_csv(index=False).encode("utf-8")
        exp_cols = st.columns(2)
        with exp_cols[0]:
            st.download_button(
                "Download full experiment (JSON)",
                data=exp_json,
                file_name="dynamicroutelab_experiment.json",
                mime="application/json",
                width="stretch",
            )
        with exp_cols[1]:
            st.download_button(
                "Download trial measurements (CSV)",
                data=trial_csv,
                file_name="dynamicroutelab_experiment_trials.csv",
                mime="text/csv",
                width="stretch",
            )

    with st.expander("Metric definitions and research limitations"):
        st.markdown(
            """
            - **Path cost:** sum of open-road weights along the returned path; independently checked.
            - **Runtime:** wall time for an algorithm call using `perf_counter_ns`; graph creation,
              traffic updates, reference checks, and rendering are excluded from repeated timings.
            - **Dijkstra settled / A* expanded / Bellman–Ford passes:** algorithm-specific processing
              counters. They are not interchangeable; edge relaxations are reported separately.
            - **Correctness:** each result is checked against an independent Dijkstra reference and
              the returned path is recomputed against open roads.
            - **Traffic:** each update samples roads deterministically from its recorded seed and
              multiplies original weights, so congestion does not compound across updates.
            - **Limitations:** networks and weights are synthetic; small-graph timings are noisy and
              depend on the host's CPU share. Run multiple seeds and topologies before generalizing.
            """
        )
        st.json({
            "software_version": __version__,
            "python": experiment["env"]["python_version"] if experiment else __import__("sys").version.split()[0],
            "timing_repetitions": trials,
            "warmup_calls_per_algorithm": 1,
            "trial_order": "round-robin across algorithms",
            "traffic_seed_offset": CONGESTION_SEED_OFFSET,
        })

st.caption(
    f"DynamicRouteLab v{__version__} · Synthetic data only · No measurements are retained by the app after the session."
)
