"""DynamicRouteLab HTTP API (FastAPI).

The server is stateless: every request carries the graph snapshot it operates on, so the
client and the benchmark runner always agree on which graph version was used.
"""

from __future__ import annotations

import platform
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from server import __version__
from server.benchmark import (
    ALGORITHMS, environment_info, run_experiment, run_snapshot, validate_endpoints, validate_graph,
)
from server.graph.generator import generate_grid
from server.graph.traffic import apply_congestion, reset_graph, set_edge_weight, set_road_closed

app = FastAPI(title="DynamicRouteLab API", version=__version__)

# The Vite dev server proxies /api to this process, so CORS is only needed for direct API use.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


# --------------------------------------------------------------------------- request models

class GenerateRequest(BaseModel):
    n: int = Field(8, ge=2, le=30, description="Grid side length (n × n intersections)")
    seed: int = Field(42, ge=0, le=2**31 - 1)
    topology: str = Field("grid", pattern="^(grid|grid_diagonal|random_extra)$")
    weight_min: int = Field(2, ge=1, le=60)
    weight_max: int = Field(12, ge=1, le=120)
    weight_min_max_check: Optional[str] = None  # placeholder for validator

    def model_post_init(self, __context):
        if self.weight_min > self.weight_max:
            raise ValueError(f"weight_min ({self.weight_min}) must be <= weight_max ({self.weight_max})")


class SnapshotRequest(BaseModel):
    graph: Dict[str, Any]
    source: str
    target: str


class TrafficRequest(BaseModel):
    graph: Dict[str, Any]
    congestion_pct: float = Field(20, ge=0, le=100)
    congestion_factor: float = Field(3.0, ge=1.0, le=10.0)
    seed: int = Field(1000, ge=0)
    affected_edge_ids: Optional[List[str]] = None


class EditEdgeRequest(BaseModel):
    graph: Dict[str, Any]
    edge_id: str
    action: str = Field(..., pattern="^(set_weight|toggle_close|set_closed)$")
    new_weight: Optional[float] = None
    closed: Optional[bool] = None


class ExperimentRequest(BaseModel):
    n: int = Field(8, ge=2, le=18)
    seed: int = Field(42, ge=0, le=2**31 - 1)
    topology: str = Field("grid", pattern="^(grid|grid_diagonal|random_extra)$")
    trials: int = Field(10, ge=1, le=30)
    updates: int = Field(1, ge=1, le=10)
    congestion_pct: float = Field(20, ge=0, le=100)
    congestion_factor: float = Field(3.0, ge=1.0, le=10.0)
    source: Optional[str] = None
    target: Optional[str] = None
    weight_min: Optional[int] = Field(None, ge=1, le=60)
    weight_max: Optional[int] = Field(None, ge=1, le=120)

    def model_post_init(self, __context):
        if self.weight_min is not None and self.weight_max is not None:
            if self.weight_min > self.weight_max:
                raise ValueError(f"weight_min ({self.weight_min}) must be <= weight_max ({self.weight_max})")


def _bad_request(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


# --------------------------------------------------------------------------- endpoints

@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": __version__,
        "algorithms": ALGORITHMS,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "environment": environment_info(),
    }


@app.post("/api/graph/generate")
def generate_graph(req: GenerateRequest) -> dict:
    graph = generate_grid(req.n, req.seed, topology=req.topology,
                          weight_min=req.weight_min, weight_max=req.weight_max)
    source, target = "0_0", f"{req.n - 1}_{req.n - 1}"
    graph["source"], graph["target"] = source, target
    return graph


@app.post("/api/algorithms/run")
def run_algorithms(req: SnapshotRequest) -> dict:
    try:
        return run_snapshot(req.graph, req.source, req.target)
    except ValueError as exc:
        raise _bad_request(exc)


@app.post("/api/traffic/apply")
def traffic_apply(req: TrafficRequest) -> dict:
    try:
        validate_graph(req.graph)
        new_graph, changes, affected = apply_congestion(
            req.graph, req.congestion_pct, req.congestion_factor, req.seed, req.affected_edge_ids)
    except ValueError as exc:
        raise _bad_request(exc)
    return {"graph": new_graph, "changes": changes, "affected_edge_ids": affected}


@app.post("/api/traffic/edit_edge")
def edit_edge(req: EditEdgeRequest) -> dict:
    try:
        validate_graph(req.graph)
        if req.action == "set_weight":
            if req.new_weight is None:
                raise ValueError("new_weight is required for action 'set_weight'")
            new_graph = set_edge_weight(req.graph, req.edge_id, req.new_weight)
        elif req.action == "toggle_close":
            new_graph = set_road_closed(req.graph, req.edge_id, None)
        else:
            if req.closed is None:
                raise ValueError("'closed' is required for action 'set_closed'")
            new_graph = set_road_closed(req.graph, req.edge_id, req.closed)
    except ValueError as exc:
        raise _bad_request(exc)
    return {"graph": new_graph}


@app.post("/api/traffic/reset")
def traffic_reset(req: Dict[str, Any]) -> dict:
    try:
        validate_graph(req)
    except ValueError as exc:
        raise _bad_request(exc)
    return {"graph": reset_graph(req)}


@app.post("/api/experiments/run")
def experiments_run(req: ExperimentRequest) -> dict:
    try:
        return run_experiment(
            n=req.n, seed=req.seed, topology=req.topology, trials=req.trials,
            congestion_pct=req.congestion_pct, congestion_factor=req.congestion_factor,
            source=req.source, target=req.target, updates=req.updates,
            weight_min=req.weight_min or 2, weight_max=req.weight_max or 12,
        )
    except ValueError as exc:
        raise _bad_request(exc)


# --------------------------------------------------------------------------- SPA (production)

# Mounted last so that its catch-all route never shadows /api/* routes.
try:
    from server.static_mount import mount_frontend

    _DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if (_DIST / "index.html").exists():
        mount_frontend(app, str(_DIST))
except Exception as _exc:  # pragma: no cover - optional production path
    print(f"Static frontend mount skipped: {_exc}")
