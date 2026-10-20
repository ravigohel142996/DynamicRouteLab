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
