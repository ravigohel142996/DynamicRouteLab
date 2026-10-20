"""A* search with an admissible, consistent Manhattan-based heuristic.

Heuristic
---------
Let P(v) = (r, c) be the grid position of node v and let L(u, v) = |r_u - r_v| + |c_u - c_v|
be the Manhattan length of the road (u, v). Define the per-unit cost scale

    c* = min over open roads e of  w(e) / L(e)

and the heuristic  h(v) = c* * Manhattan(P(v), P(target)).

Admissibility: every road costs w(e) >= c* * L(e). Along any path from v to the target,
the Manhattan lengths sum to at least Manhattan(P(v), P(target)) (triangle inequality on the
Manhattan metric), hence every path costs at least h(v). Consistency follows because
h(u) - h(v) <= c* * L(u, v) <= w(u, v) for every road (u, v).

For plain 4-neighbour grids L(e) = 1 for every road, so c* = min road weight, the classic
bound. For diagonal or long-range roads (L(e) = 2..4) the bound is recomputed from the
current weights, so the heuristic stays valid after congestion and closures. Closed roads are
excluded from c*, which keeps the bound valid for the traversable graph only.

The scale is computed inside the timed region because it is part of A*'s work.
"""

import heapq
import time
from typing import Dict, List, Optional, Tuple

Adjacency = Dict[str, List[Tuple[str, float, str]]]


def manhattan(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def heuristic_scale(adj: Adjacency, positions: Dict[str, Tuple[int, int]]) -> float:
    """Return c* = min_e w(e)/L(e) over the traversable (open) roads. 0.0 if no roads."""
    best = float("inf")
    for u, nbrs in adj.items():
        pu = positions[u]
        for v, w, _eid in nbrs:
            length = manhattan(pu, positions[v])
            if length <= 0:
                continue  # defensive: zero-length roads cannot tighten the bound
            ratio = w / length
            if ratio < best:
                best = ratio
    return 0.0 if best == float("inf") else best


def astar(
    adj: Adjacency,
    source: str,
    target: str,
    positions: Dict[str, Tuple[int, int]],
    scale: Optional[float] = None,
) -> dict:
    """Shortest path from source to target.

    `scale` (c*) may be supplied for experiments that want to exclude precomputation, but the
    default (None) recomputes it from the current adjacency inside the timed region.
    """
    if source not in adj or target not in adj:
        return {"path": [], "cost": float("inf"), "expanded": 0, "relaxations": 0,
                "explored_order": [], "success": False, "error": "Source or target not in graph"}

    if source == target:
        return {"path": [source], "cost": 0.0, "expanded": 1, "relaxations": 0,
                "explored_order": [source], "success": True, "runtime_ms": 0.0}

    start = time.perf_counter_ns()
    c_star = heuristic_scale(adj, positions) if scale is None else float(scale)
    tr_pos = positions[target]

    def h(node: str) -> float:
        return c_star * manhattan(positions[node], tr_pos)

    g = {node: float("inf") for node in adj}
    parent: Dict[str, str] = {}
    g[source] = 0.0
    pq = [(h(source), 0.0, source)]
    expanded = set()
    explored_order: List[str] = []
    relaxations = 0

    while pq:
        _f, cost, u = heapq.heappop(pq)
        if cost != g[u] or u in expanded:
            continue
        expanded.add(u)
        explored_order.append(u)
        if u == target:
            break
        for v, w, _eid in adj[u]:
            relaxations += 1
            nd = g[u] + w
            if nd < g[v] - 1e-9:
                g[v] = nd
                parent[v] = u
                heapq.heappush(pq, (nd + h(v), nd, v))

    runtime_ms = (time.perf_counter_ns() - start) / 1e6
    cost = g[target]
    base = {"expanded": len(expanded), "relaxations": relaxations,
            "explored_order": explored_order, "runtime_ms": runtime_ms,
            "heuristic_scale": c_star}
    if cost == float("inf"):
        return {"path": [], "cost": float("inf"), "success": False, **base}

    path = [target]
    cur = target
    while cur != source:
        if cur not in parent:
            return {"path": [], "cost": float("inf"), "success": False, **base}
        cur = parent[cur]
        path.append(cur)
    path.reverse()
    return {"path": path, "cost": cost, "success": True, **base}
