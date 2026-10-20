"""Traffic engine semantics: congestion, closures, edits, reset."""

import pytest

from server.benchmark import run_snapshot
from server.graph.generator import generate_grid
from server.graph.traffic import (
    CONGESTION_SEED_OFFSET, apply_congestion, edge_map, reset_graph, set_edge_weight, set_road_closed,
)


def base():
    return generate_grid(6, 5)


def test_congestion_multiplies_original_weight_and_is_deterministic():
    g = base()
    a, changes_a, ids_a = apply_congestion(g, 25, 3.0, 9)
    b, changes_b, ids_b = apply_congestion(g, 25, 3.0, 9)
    assert ids_a == ids_b and changes_a == changes_b
    em = edge_map(a)
    for eid in ids_a:
        assert em[eid]["weight"] == pytest.approx(em[eid]["original_weight"] * 3.0)
    untouched = [e for e in a["edges"] if e["id"] not in set(ids_a)]
    assert all(e["weight"] == e["original_weight"] for e in untouched)


def test_reapplying_congestion_does_not_compound():
    g = base()
    once, _, ids = apply_congestion(g, 30, 2.0, 1)
    twice, _, _ = apply_congestion(once, 30, 2.0, 1)
    for eid in ids:
        assert edge_map(twice)[eid]["weight"] == pytest.approx(edge_map(g)[eid]["weight"] * 2.0)


def test_congestion_sample_size_matches_percentage_of_open_roads():
    g = base()
    total = len(g["edges"])
    _, _, ids = apply_congestion(g, 20, 2.0, 3)
    assert len(ids) == round(total * 0.20)


def test_congestion_factor_below_one_is_rejected():
    with pytest.raises(ValueError):
        apply_congestion(base(), 10, 0.5, 1)


def test_unknown_edge_id_is_rejected():
    with pytest.raises(ValueError):
        apply_congestion(base(), 0, 2.0, 1, affected_edge_ids=["nope"])


def test_closure_changes_every_algorithm_consistently_and_reopen_restores():
    g = base()
    s, t = "0_0", "5_5"
    before = run_snapshot(g, s, t)
    first_edge = before["results"]["dijkstra"]["path"][:2]
    eid = next(e["id"] for e in g["edges"]
               if {e["source"], e["target"]} == set(first_edge))
    closed = set_road_closed(g, eid, True)
    after = run_snapshot(closed, s, t)
    costs = {r["cost"] for r in after["results"].values()}
    assert len(costs) == 1, "all algorithms must agree on the closed graph"
    assert after["reference_cost"] >= before["reference_cost"]
    for r in after["results"].values():
        for u, v in zip(r["path"][:-1], r["path"][1:]):
            assert {u, v} != set(first_edge)
    reopened = set_road_closed(closed, eid, False)
    assert run_snapshot(reopened, s, t)["reference_cost"] == before["reference_cost"]


def test_manual_edit_changes_weight_but_keeps_original():
    g = base()
    eid = g["edges"][0]["id"]
    edited = set_edge_weight(g, eid, 99)
    e = edge_map(edited)[eid]
    assert e["weight"] == 99 and e["original_weight"] == g["edges"][0]["original_weight"]


def test_negative_or_nonfinite_weights_are_rejected():
    g = base()
    eid = g["edges"][0]["id"]
    for bad in (-1, float("inf"), float("nan")):
        with pytest.raises(ValueError):
            set_edge_weight(g, eid, bad)


def test_reset_restores_original_weights_and_reopens_roads():
    g = base()
    changed, _, _ = apply_congestion(g, 50, 4.0, 2)
    changed = set_road_closed(changed, changed["edges"][0]["id"], True)
    restored = reset_graph(changed)
    assert all(e["weight"] == e["original_weight"] and not e["closed"] for e in restored["edges"])


def test_congestion_seed_offset_is_documented_constant():
    assert CONGESTION_SEED_OFFSET == 9999
