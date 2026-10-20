"""Benchmark integrity, validation, reproducibility, and API contract tests."""

import pytest
from fastapi.testclient import TestClient

from server.benchmark import ALGORITHMS, run_experiment, run_snapshot, validate_graph
from server.graph.generator import generate_grid
from server.main import app

client = TestClient(app)


# ----------------------------------------------------------------- validation

def test_validate_graph_rejects_negative_weight():
    g = generate_grid(3, 1)
    g["edges"][0]["weight"] = -2
    with pytest.raises(ValueError, match="negative"):
        validate_graph(g)


def test_validate_graph_rejects_dangling_edge():
    g = generate_grid(3, 1)
    g["edges"][0]["target"] = "ghost"
    with pytest.raises(ValueError, match="unknown node"):
        validate_graph(g)


def test_run_snapshot_rejects_unknown_endpoint():
    with pytest.raises(ValueError, match="not an intersection"):
        run_snapshot(generate_grid(3, 1), "0_0", "9_9")


# ----------------------------------------------------------------- benchmark integrity

def test_snapshot_results_pass_correctness_and_keep_counts_separate():
    snap = run_snapshot(generate_grid(8, 42), "0_0", "7_7")
    assert snap["agreement"]
    for name in ALGORITHMS:
        assert snap["results"][name]["correctness"]["status"] == "pass", name
    assert "settled" in snap["results"]["dijkstra"]
    assert "expanded" in snap["results"]["astar"]
    assert "passes" in snap["results"]["bellman_ford"]


def test_experiment_counts_and_costs_are_reproducible_for_same_config():
    kwargs = dict(n=6, seed=7, topology="grid", trials=3, congestion_pct=25,
                  congestion_factor=3.0, source=None, target=None, updates=2)
    a = run_experiment(**kwargs)
    b = run_experiment(**kwargs)
    for name in ALGORITHMS:
        sa, sb = a["normal"][name], b["normal"][name]
        assert sa["path"] == sb["path"]
        assert sa["path_cost"] == sb["path_cost"]
        assert sa["processed_median"] == sb["processed_median"]
        assert sa["relaxations_median"] == sb["relaxations_median"]
        assert sa["counts_consistent"] and sa["correctness_pass_rate"] == 1.0
    assert [u["affected_count"] for u in a["updates"]] == [u["affected_count"] for u in b["updates"]]
    assert [u["cost_after"] for u in a["updates"]] == [u["cost_after"] for u in b["updates"]]


def test_experiment_reports_timing_statistics_from_trials():
    res = run_experiment(n=5, seed=3, topology="grid_diagonal", trials=4, congestion_pct=20,
                         congestion_factor=2.0, source=None, target=None, updates=1)
    for name in ALGORITHMS:
        s = res["normal"][name]
        assert len(s["trials_raw"]) == 4
        assert s["min_runtime_ms"] <= s["median_runtime_ms"] <= s["max_runtime_ms"]
    assert 0.0 <= res["route_change_frequency"] <= 1.0
    assert res["env"]["timer"].startswith("time.perf_counter_ns")


# ----------------------------------------------------------------- API contract

def test_api_health_returns_json_not_spa_shell():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert r.json()["algorithms"] == ALGORITHMS


def test_api_generate_then_run_roundtrip():
    g = client.post("/api/graph/generate", json={"n": 5, "seed": 2, "topology": "grid"}).json()
    r = client.post("/api/algorithms/run", json={"graph": g, "source": "0_0", "target": "4_4"})
    assert r.status_code == 200
    body = r.json()
    assert body["agreement"] is True
    assert body["results"]["dijkstra"]["correctness"]["status"] == "pass"


def test_api_bad_endpoint_gives_400_with_message():
    g = client.post("/api/graph/generate", json={"n": 4, "seed": 2}).json()
    r = client.post("/api/algorithms/run", json={"graph": g, "source": "bogus", "target": "3_3"})
    assert r.status_code == 400
    assert "bogus" in r.json()["detail"]


def test_api_rejects_out_of_range_parameters():
    r = client.post("/api/experiments/run", json={"n": 4, "trials": 999})
    assert r.status_code == 422


def test_api_traffic_apply_then_edit_then_reset():
    g = client.post("/api/graph/generate", json={"n": 4, "seed": 9}).json()
    t = client.post("/api/traffic/apply", json={"graph": g, "congestion_pct": 30, "congestion_factor": 3.0, "seed": 1}).json()
    assert t["affected_edge_ids"] and t["changes"]
    eid = t["affected_edge_ids"][0]
    e = client.post("/api/traffic/edit_edge", json={"graph": t["graph"], "edge_id": eid, "action": "toggle_close"}).json()
    closed = [x for x in e["graph"]["edges"] if x["id"] == eid][0]
    assert closed["closed"] is True
    reset = client.post("/api/traffic/reset", json=e["graph"]).json()
    assert all(not x["closed"] and x["weight"] == x["original_weight"] for x in reset["graph"]["edges"])


def test_api_experiment_returns_summary_and_timing_boundary():
    r = client.post("/api/experiments/run", json={"n": 4, "seed": 5, "trials": 2, "updates": 2})
    assert r.status_code == 200
    body = r.json()
    assert set(body["normal"].keys()) == set(ALGORITHMS)
    assert len(body["updates"]) == 2
    assert "perf_counter_ns" in body["env"]["timer"]
