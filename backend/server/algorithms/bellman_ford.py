import time
from typing import Dict, List, Tuple

def bellman_ford(adj: Dict[str, List[Tuple[str, float, str]]], source: str, target: str):
    if source not in adj or target not in adj:
        return {"path": [], "cost": float("inf"), "passes": 0, "relaxations": 0, "success": False, "error": "Source or target not in graph", "has_negative_cycle": False}

    if source == target:
        return {"path": [source], "cost": 0.0, "passes": 0, "relaxations": 0, "success": True, "runtime_ms": 0.0, "has_negative_cycle": False}

    # Build directed edge list
    directed_edges = []
    for u in adj:
        for v,w,eid in adj[u]:
            directed_edges.append((u, v, w))

    start = time.perf_counter_ns()
    dist = {node: float("inf") for node in adj}
    parent = {}
    dist[source] = 0.0
    n = len(adj)
    passes = 0
    relaxations = 0

    for i in range(n-1):
        changed = False
        passes += 1
        for u, v, w in directed_edges:
            relaxations += 1
            if dist[u] != float("inf") and dist[u] + w < dist[v] - 1e-9:
                dist[v] = dist[u] + w
                parent[v] = u
                changed = True
        if not changed:
            break

    # Negative cycle detection
    has_negative_cycle = False
    for u, v, w in directed_edges:
        # we count these checks as relaxations? No, keep separate to be precise
        # but we already counted? Actually detection loop is not counted in passes; we count separately but not add to relaxations for metric? We'll count as relaxations too for transparency
        # For metric consistency, we have relaxations = passes * edges, detection extra not counted previously. We'll add detection relaxations.
        relaxations += 1
        if dist[u] != float("inf") and dist[u] + w < dist[v] - 1e-9:
            has_negative_cycle = True
            break

    end = time.perf_counter_ns()
    runtime_ms = (end - start)/1e6

    cost = dist[target]
    if cost == float("inf"):
        return {"path": [], "cost": float("inf"), "passes": passes, "relaxations": relaxations, "success": False, "runtime_ms": runtime_ms, "has_negative_cycle": has_negative_cycle}

    # If negative cycle affects target, path not reliable - but our synthetic graphs are non-negative, so no negative cycle
    path = [target]
    cur = target
    max_iter = n+5
    iter_count = 0
    while cur != source:
        if cur not in parent:
            return {"path": [], "cost": float("inf"), "passes": passes, "relaxations": relaxations, "success": False, "runtime_ms": runtime_ms, "has_negative_cycle": has_negative_cycle}
        cur = parent[cur]
        path.append(cur)
        iter_count += 1
        if iter_count > max_iter:
            break
    path.reverse()

    return {"path": path, "cost": cost, "passes": passes, "relaxations": relaxations, "success": True, "runtime_ms": runtime_ms, "has_negative_cycle": has_negative_cycle}
