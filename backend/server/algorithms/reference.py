import heapq

def reference_dijkstra(adj, source, target):
    """Independent trusted reference implementation (simple, clearly correct) for validation."""
    if source not in adj or target not in adj:
        return float("inf"), []
    if source == target:
        return 0.0, [source]
    dist = {n: float("inf") for n in adj}
    prev = {}
    dist[source]=0
    pq=[(0, source)]
    visited=set()
    while pq:
        d,u = heapq.heappop(pq)
        if u in visited:
            continue
        visited.add(u)
        if u==target:
            break
        for v,w,_ in adj[u]:
            nd=d+w
            if nd < dist[v]:
                dist[v]=nd
                prev[v]=u
                heapq.heappush(pq,(nd,v))
    if dist[target]==float("inf"):
        return float("inf"), []
    path=[target]
    cur=target
    while cur!=source:
        cur=prev[cur]
        path.append(cur)
    path.reverse()
    return dist[target], path
