const API_BASE = import.meta.env.VITE_API_URL || ''

async function post(path: string, body: any) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
  if (!res.ok) {
    const txt = await res.text()
    throw new Error(`${res.status} ${res.statusText}: ${txt}`)
  }
  return res.json()
}

async function get(path: string) {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`${res.status}`)
  return res.json()
}

export const api = {
  health: () => get('/api/health'),
  generateGraph: (params: any) => post('/api/graph/generate', params),
  runAlgorithms: (graph: any, source: string, target: string) => post('/api/algorithms/run', { graph, source, target }),
  applyTraffic: (graph: any, congestion_pct: number, congestion_factor: number, seed: number, affected_edge_ids?: string[]) =>
    post('/api/traffic/apply', { graph, congestion_pct, congestion_factor, seed, affected_edge_ids }),
  editEdge: (graph: any, edge_id: string, new_weight?: number, closed?: boolean, action?: string) =>
    post('/api/traffic/edit_edge', { graph, edge_id, new_weight, closed, action }),
  resetGraph: (graph: any) => post('/api/traffic/reset', graph),
  runExperiment: (params: any) => post('/api/experiments/run', params),
}
