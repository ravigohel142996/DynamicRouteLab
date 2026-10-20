import heapq
import time
from typing import Dict, List, Tuple

def dijkstra(adj: Dict[str, List[Tuple[str, float, str]]], source: str, target: str):
    """
    Returns dict with path, cost, settled, relaxations, explored_order, runtime_ms
    adj: node -> [(neighbor, weight, edge_id)]
    """
    if source not in adj or target not in adj:
        return {"path": [], "cost": float("inf"), "settled": 0, "relaxations": 0, "explored_order": [], "success": False, "error": "Source or target not in graph"}

    # handle source==target
    if source == target:
        return {"path": [source], "cost": 0.0, "settled": 1, "relaxations": 0, "explored_order": [source], "success": True}

    start = time.perf_counter_ns()
    dist = {node: float("inf") for node in adj}
    parent = {}
    dist[source] = 0.0
    pq = [(0.0, source)]
    settled = set()
    explored_order = []
    relaxations = 0
    visited_edges = set()

    while pq:
        cost, u = heapq.heappop(pq)
        if cost != dist[u] or u in settled:
            continue
        settled.add(u)
        explored_order.append(u)
        if u == target:
            break
        for v, w, eid in adj[u]:
            relaxations += 1
            nd = cost + w
            if nd < dist[v] - 1e-9:  # tolerance
                dist[v] = nd
                parent[v] = u
                heapq.heappush(pq, (nd, v))

    end = time.perf_counter_ns()
    runtime_ms = (end - start) / 1e6

    cost = dist[target]
    if cost == float("inf"):
        return {"path": [], "cost": float("inf"), "settled": len(settled), "relaxations": relaxations, "explored_order": explored_order, "success": False, "runtime_ms": runtime_ms}

    # reconstruct
    path = [target]
    cur = target
    while cur != source:
        if cur not in parent:
            return {"path": [], "cost": float("inf"), "settled": len(settled), "relaxations": relaxations, "explored_order": explored_order, "success": False, "runtime_ms": runtime_ms}
        cur = parent[cur]
        path.append(cur)
    path.reverse()

    return {"path": path, "cost": cost, "settled": len(settled), "relaxations": relaxations, "explored_order": explored_order, "success": True, "runtime_ms": runtime_ms}
