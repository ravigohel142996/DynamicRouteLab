import random
from typing import Dict, List, Tuple
import math

NodeId = str

def node_id(r: int, c: int) -> str:
    return f"{r}_{c}"

def parse_node_id(nid: str) -> Tuple[int, int]:
    r, c = nid.split("_")
    return int(r), int(c)

def generate_grid(n: int, seed: int, topology: str = "grid", weight_min: int = 2, weight_max: int = 12, extra_edge_prob: float = 0.12):
    """
    Generate synthetic road network.
    topology: grid | grid_diagonal | random_geometric_like (we implement extra edges)
    """
    if weight_min > weight_max:
        raise ValueError(f"weight_min ({weight_min}) must be <= weight_max ({weight_max})")
    if n < 2 or n > 30:
        raise ValueError(f"n must be in [2, 30], got {n}")
    if topology not in ("grid", "grid_diagonal", "random_extra"):
        raise ValueError(f"Unknown topology {topology!r}; choose from grid, grid_diagonal, random_extra")
    rng = random.Random(int(seed))
    nodes = []
    edges = []
    positions = {}  # node_id -> (x,y) for visualization (using grid coordinates)
    for r in range(n):
        for c in range(n):
            nid = node_id(r, c)
            nodes.append({"id": nid, "r": r, "c": c, "x": c, "y": -r})  # y inverted for display
            positions[nid] = (c, -r)

    # base grid edges (4-neighbor)
    for r in range(n):
        for c in range(n):
            nid = node_id(r, c)
            if r + 1 < n:
                nid2 = node_id(r+1, c)
                w = float(rng.randint(weight_min, weight_max))
                edges.append({"source": nid, "target": nid2, "weight": w, "original_weight": w, "closed": False, "id": f"{nid}__{nid2}"})
            if c + 1 < n:
                nid2 = node_id(r, c+1)
                w = float(rng.randint(weight_min, weight_max))
                edges.append({"source": nid, "target": nid2, "weight": w, "original_weight": w, "closed": False, "id": f"{nid}__{nid2}"})

    if topology == "grid_diagonal":
        # add diagonal edges with higher cost
        for r in range(n-1):
            for c in range(n-1):
                if rng.random() < 0.5:
                    # diagonal one direction
                    nid = node_id(r, c)
                    nid2 = node_id(r+1, c+1)
                    w = float(rng.randint(weight_min+2, weight_max+4))
                    edges.append({"source": nid, "target": nid2, "weight": w, "original_weight": w, "closed": False, "id": f"{nid}__{nid2}"})
                else:
                    nid = node_id(r, c+1)
                    nid2 = node_id(r+1, c)
                    w = float(rng.randint(weight_min+2, weight_max+4))
                    edges.append({"source": nid, "target": nid2, "weight": w, "original_weight": w, "closed": False, "id": f"{nid}__{nid2}"})
    elif topology == "random_extra":
        # add random extra edges
        for r in range(n):
            for c in range(n):
                if rng.random() < extra_edge_prob:
                    # pick a random other node not already neighbor, within distance 2-3
                    candidates = []
                    for dr in range(-2, 3):
                        for dc in range(-2, 3):
                            nr, nc = r+dr, c+dc
                            if 0 <= nr < n and 0 <= nc < n:
                                if abs(dr)+abs(dc) > 1:  # not immediate orthogonal already connected
                                    candidates.append(node_id(nr, nc))
                    if candidates:
                        target = rng.choice(candidates)
                        nid = node_id(r, c)
                        # avoid duplicate
                        exists = any((e["source"]==nid and e["target"]==target) or (e["source"]==target and e["target"]==nid) for e in edges)
                        if not exists:
                            w = float(rng.randint(weight_min+1, weight_max+6))
                            edges.append({"source": nid, "target": target, "weight": w, "original_weight": w, "closed": False, "id": f"{nid}__{target}"})

    return {"nodes": nodes, "edges": edges, "positions": positions, "meta": {"n": n, "seed": seed, "topology": topology}}

def graph_to_adjacency(payload: dict):
    """Convert payload to adjacency dict for algorithms, skipping closed edges."""
    adj = {}
    for node in payload["nodes"]:
        adj[node["id"]] = []
    for e in payload["edges"]:
        if e.get("closed"):
            continue
        w = e["weight"]
        adj[e["source"]].append((e["target"], w, e["id"]))
        adj[e["target"]].append((e["source"], w, e["id"]))  # undirected
    return adj

def get_positions(payload: dict):
    # positions as dict node_id -> (x,y) but we already have x,y per node; also support for heuristic
    pos = {}
    for n in payload["nodes"]:
        # use r,c for Manhattan heuristic
        pos[n["id"]] = (n["r"], n["c"])
    return pos
