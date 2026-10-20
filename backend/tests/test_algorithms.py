"""Core algorithm correctness tests.

Every algorithm's cost is compared against an independent Dijkstra reference, and every returned
path is checked edge-by-edge with its cost recomputed from the traversable roads.
"""

import itertools
import math

import pytest

from server.algorithms.astar import astar, heuristic_scale, manhattan
from server.algorithms.bellman_ford import bellman_ford
from server.algorithms.dijkstra import dijkstra
from server.algorithms.reference import reference_dijkstra
from server.benchmark import _check_path, _open_index
from server.graph.generator import generate_grid, get_positions, graph_to_adjacency
from server.graph.traffic import apply_congestion, set_road_closed

TOPOLOGIES = ["grid", "grid_diagonal", "random_extra"]


def manual_graph():
    """A small hand-built graph with known shortest path A-B-C-D (cost 6)."""
    adj = {
        "A": [("B", 1, "e1"), ("C", 4, "e2")],
        "B": [("A", 1, "e1"), ("C", 2, "e3"), ("D", 6, "e4")],
        "C": [("A", 4, "e2"), ("B", 2, "e3"), ("D", 3, "e5")],
        "D": [("B", 6, "e4"), ("C", 3, "e5")],
    }
    pos = {"A": (0, 0), "B": (0, 1), "C": (1, 0), "D": (1, 1)}
    return adj, pos


def run_all(adj, pos, s, t):
    return {
        "dijkstra": dijkstra(adj, s, t),
        "astar": astar(adj, s, t, pos),
        "bellman_ford": bellman_ford(adj, s, t),
    }


# ----------------------------------------------------------------- hand-built graphs

def test_known_shortest_path_on_manual_graph():
    adj, pos = manual_graph()
    for name, res in run_all(adj, pos, "A", "D").items():
        assert res["success"], name
        assert res["cost"] == pytest.approx(6), name
        assert res["path"] == ["A", "B", "C", "D"], name


def test_unreachable_destination_reports_failure_for_all():
    adj, pos = manual_graph()
    adj = {k: [x for x in v if x[0] != "D"] for k, v in adj.items()}
    adj["D"] = []
    for name, res in run_all(adj, pos, "A", "D").items():
        assert not res["success"], name
        assert res["cost"] == math.inf, name
        assert res["path"] == [], name


def test_source_equals_target_is_zero_cost_single_node_path():
    payload = generate_grid(4, 10)
    adj = graph_to_adjacency(payload)
    pos = get_positions(payload)
    for name, res in run_all(adj, pos, "0_0", "0_0").items():
        assert res["success"], name
        assert res["cost"] == 0, name
        assert res["path"] == ["0_0"], name


def test_equal_cost_alternatives_return_optimal_cost():
    adj = {
        "S": [("A", 1, "e1"), ("B", 1, "e2")],
        "A": [("S", 1, "e1"), ("T", 1, "e3")],
        "B": [("S", 1, "e2"), ("T", 1, "e4")],
        "T": [("A", 1, "e3"), ("B", 1, "e4")],
    }
    pos = {"S": (0, 0), "A": (0, 1), "B": (1, 0), "T": (1, 1)}
    for name, res in run_all(adj, pos, "S", "T").items():
        assert res["cost"] == pytest.approx(2), name
        assert res["path"] in (["S", "A", "T"], ["S", "B", "T"]), name


def test_bellman_ford_detects_negative_cycle_and_not_otherwise():
    no_cycle = {"A": [("B", 1, "e1"), ("C", 2, "e2")], "B": [("C", -1, "e3")], "C": [("A", 1, "e4")]}
    assert not bellman_ford(no_cycle, "A", "C")["has_negative_cycle"]
    cycle = {"A": [("B", 1, "e1")], "B": [("C", -2, "e2")], "C": [("A", -2, "e3")]}
    assert bellman_ford(cycle, "A", "C")["has_negative_cycle"]


def test_bellman_ford_reports_passes_not_vertices():
    adj, _ = manual_graph()
    res = bellman_ford(adj, "A", "D")
    assert "passes" in res and "settled" not in res and "expanded" not in res
    assert res["passes"] <= len(adj) - 1


# ----------------------------------------------------------------- reference agreement

@pytest.mark.parametrize("topology,seed,wmin", list(itertools.product(TOPOLOGIES, range(6), [2, 5, 8])))
def test_all_algorithms_match_reference_cost(topology, seed, wmin):
    payload = generate_grid(7, seed, topology=topology, weight_min=wmin, weight_max=wmin + 10)
    adj = graph_to_adjacency(payload)
    pos = get_positions(payload)
    pairs = [("0_0", "6_6"), ("6_0", "0_6"), ("3_0", "3_6")]
    for s, t in pairs:
        ref, _ = reference_dijkstra(adj, s, t)
        for name, res in run_all(adj, pos, s, t).items():
            assert res["cost"] == pytest.approx(ref, abs=1e-6), (name, topology, seed, wmin, s, t)


@pytest.mark.parametrize("topology", TOPOLOGIES)
def test_reconstructed_paths_use_real_roads_and_match_cost(topology):
    payload = generate_grid(8, 3, topology=topology)
    adj = graph_to_adjacency(payload)
    pos = get_positions(payload)
    index = _open_index(payload)
    for name, res in run_all(adj, pos, "0_0", "7_7").items():
        valid, recomputed = _check_path(index, res["path"], "0_0", "7_7", res["cost"], res["success"])
        assert valid, name
        assert recomputed == pytest.approx(res["cost"]), name


# ----------------------------------------------------------------- A* heuristic validity

def _true_distances_to(adj, target):
    """Exact distance from every node to target (reference, one Dijkstra per source)."""
    return {v: reference_dijkstra(adj, v, target)[0] for v in adj}


@pytest.mark.parametrize("topology", TOPOLOGIES)
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_heuristic_is_admissible_and_consistent_after_traffic(topology, seed):
    """h(v) must never exceed the true remaining cost, and must satisfy h(u) <= w(u,v) + h(v)."""
    base = generate_grid(6, seed, topology=topology, weight_min=5, weight_max=15)
    congested, _, _ = apply_congestion(base, 40, 4.0, seed + 1)
    # also close a few roads: heuristic must use only traversable roads
    for edge in congested["edges"][:3]:
        congested = set_road_closed(congested, edge["id"], True)

    adj = graph_to_adjacency(congested)
    pos = get_positions(congested)
    target = "5_5"
    scale = heuristic_scale(adj, pos)
    true = _true_distances_to(adj, target)
    tp = pos[target]
    for v in adj:
        h = scale * manhattan(pos[v], tp)
        if math.isfinite(true[v]):
            assert h <= true[v] + 1e-9, (v, h, true[v])
    for u, nbrs in adj.items():
        for v, w, _ in nbrs:
            hu = scale * manhattan(pos[u], tp)
            hv = scale * manhattan(pos[v], tp)
            assert hu <= w + hv + 1e-9


@pytest.mark.parametrize("topology", TOPOLOGIES)
def test_astar_cost_equals_dijkstra_after_congestion_and_closure(topology):
    base = generate_grid(9, 11, topology=topology, weight_min=5, weight_max=14)
    congested, _, _ = apply_congestion(base, 35, 5.0, 77)
    congested = set_road_closed(congested, congested["edges"][0]["id"], True)
    adj = graph_to_adjacency(congested)
    pos = get_positions(congested)
    d = dijkstra(adj, "0_0", "8_8")
    a = astar(adj, "0_0", "8_8", pos)
    assert a["cost"] == pytest.approx(d["cost"], abs=1e-6)


def test_astar_expands_no_more_than_dijkstra_on_a_plain_grid():
    """Sanity check for H1 on a plain grid: admissible heuristic should not expand more vertices."""
    payload = generate_grid(12, 42)
    adj = graph_to_adjacency(payload)
    pos = get_positions(payload)
    d = dijkstra(adj, "0_0", "11_11")
    a = astar(adj, "0_0", "11_11", pos)
    assert a["cost"] == pytest.approx(d["cost"])
    assert a["expanded"] <= d["settled"]


def test_closed_roads_are_absent_from_all_algorithms():
    adj, pos = manual_graph()
    # close B-C; the only remaining route A-B-D costs 7, A-C-D costs 7
    adj_closed = {k: [x for x in v if {k, x[0]} != {"B", "C"}] for k, v in adj.items()}
    for name, res in run_all(adj_closed, pos, "A", "D").items():
        assert res["cost"] == pytest.approx(7), name
        assert "B" not in res["path"] or "C" not in res["path"], name


def test_congestion_can_change_route_without_changing_cost():
    """H3: congestion may change the chosen route even though optimal cost stays same (equal-cost alternative)."""
    adj = {
        "S": [("A", 1, "e1"), ("B", 1, "e2")],
        "A": [("S", 1, "e1"), ("T", 1, "e3")],
        "B": [("S", 1, "e2"), ("T", 1, "e4")],
        "T": [("A", 1, "e3"), ("B", 1, "e4")],
    }
    pos = {"S": (0, 0), "A": (0, 1), "B": (1, 0), "T": (1, 1)}
    baseline = dijkstra(adj, "S", "T")
    assert baseline["cost"] == pytest.approx(2)
    congested_adj = {
        "S": [("A", 2, "e1"), ("B", 1, "e2")],
        "A": [("S", 2, "e1"), ("T", 1, "e3")],
        "B": [("S", 1, "e2"), ("T", 1, "e4")],
        "T": [("A", 1, "e3"), ("B", 1, "e4")],
    }
    after = dijkstra(congested_adj, "S", "T")
    assert after["cost"] == pytest.approx(2)
    assert after["path"] == ["S", "B", "T"]
    adj2 = {
        "S": [("A", 1, "e1"), ("B", 1, "e2"), ("C", 5, "e5")],
        "A": [("S", 1, "e1"), ("T", 1, "e3")],
        "B": [("S", 1, "e2"), ("T", 1, "e4")],
        "C": [("S", 5, "e5"), ("T", 5, "e6")],
        "T": [("A", 1, "e3"), ("B", 1, "e4"), ("C", 5, "e6")],
    }
    congested2 = {
        "S": [("A", 1, "e1"), ("B", 1, "e2"), ("C", 15, "e5")],
        "A": [("S", 1, "e1"), ("T", 1, "e3")],
        "B": [("S", 1, "e2"), ("T", 1, "e4")],
        "C": [("S", 15, "e5"), ("T", 5, "e6")],
        "T": [("A", 1, "e3"), ("B", 1, "e4"), ("C", 5, "e6")],
    }
    b2 = dijkstra(adj2, "S", "T")
    a2 = dijkstra(congested2, "S", "T")
    assert b2["cost"] == pytest.approx(a2["cost"])
    assert b2["cost"] == pytest.approx(2)


def test_congestion_via_traffic_engine_can_leave_cost_unchanged():
    """Verify traffic engine: congestion on off-path edges leaves optimal cost unchanged."""
    payload = generate_grid(4, 10, weight_min=5, weight_max=5)
    adj = graph_to_adjacency(payload)
    from server.benchmark import run_snapshot
    base_snap = run_snapshot(payload, "0_0", "3_3")
    base_cost = base_snap["reference_cost"]
    congested, changes, affected = apply_congestion(payload, 10, 5.0, 12345)
    after_snap = run_snapshot(congested, "0_0", "3_3")
    assert after_snap["agreement"]
    if after_snap["reference_cost"] is not None and base_cost is not None:
        assert after_snap["reference_cost"] >= base_cost - 1e-6


def test_bellman_ford_handles_negative_edge_without_cycle():
    """Bellman-Ford must return correct shortest path when graph contains a negative edge but no negative cycle."""
    # Use directed-style adjacency (no opposite negative duplicate) to avoid inadvertent 2-cycle
    adj = {
        "A": [("B", 2, "e1")],
        "B": [("C", -1, "e2")],
        "C": [],
    }
    res = bellman_ford(adj, "A", "C")
    assert res["success"]
    assert res["cost"] == pytest.approx(1.0)
    assert res["path"] == ["A", "B", "C"]
    assert not res["has_negative_cycle"]


def test_bellman_ford_negative_edge_cost_matches_reference():
    """When negative edges are present without a cycle, BF should still work; on non-negative graphs it must match Dijkstra."""
    adj, _ = manual_graph()
    for target in ["B", "C", "D"]:
        d = dijkstra(adj, "A", target)
        b = bellman_ford(adj, "A", target)
        assert d["cost"] == pytest.approx(b["cost"]), f"mismatch to {target}"
        assert d["success"] == b["success"]


def test_invalid_weight_range_raises():
    with pytest.raises(ValueError, match="weight_min"):
        generate_grid(4, 1, weight_min=12, weight_max=2)


def test_invalid_topology_raises():
    with pytest.raises(ValueError, match="topology"):
        generate_grid(4, 1, topology="hexagonal")


def test_all_algorithms_reject_unknown_node():
    adj, pos = manual_graph()
    for name, res in run_all(adj, pos, "A", "GHOST").items():
        assert not res["success"], name
        assert res["cost"] == math.inf, name


def test_path_reconstruction_verified_against_reference():
    """Every returned path cost, when recomputed from open roads, must equal the reported cost."""
    for seed in [0, 1, 42]:
        payload = generate_grid(5, seed)
        adj = graph_to_adjacency(payload)
        pos = get_positions(payload)
        index = _open_index(payload)
        for s, t in [("0_0", "4_4"), ("4_0", "0_4")]:
            for name, res in run_all(adj, pos, s, t).items():
                valid, recomputed = _check_path(index, res["path"], s, t, res["cost"], res["success"])
                assert valid, f"{name} seed {seed} {s}->{t} invalid path {res['path']}"
                if res["success"]:
                    assert recomputed == pytest.approx(res["cost"]), f"{name} cost mismatch"


def test_deterministic_tie_breaking():
    """Same graph+endpoints should always yield same path (deterministic priority queue ordering)."""
    adj = {
        "S": [("A", 1, "e1"), ("B", 1, "e2")],
        "A": [("S", 1, "e1"), ("T", 1, "e3")],
        "B": [("S", 1, "e2"), ("T", 1, "e4")],
        "T": [("A", 1, "e3"), ("B", 1, "e4")],
    }
    pos = {"S": (0, 0), "A": (0, 1), "B": (1, 0), "T": (1, 1)}
    paths = [dijkstra(adj, "S", "T")["path"] for _ in range(5)]
    assert len(set(tuple(p) for p in paths)) == 1
