export interface GraphNode {
  id: string
  r: number
  c: number
  x: number
  y: number
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  weight: number
  original_weight: number
  closed: boolean
}

export interface GraphPayload {
  nodes: GraphNode[]
  edges: GraphEdge[]
  meta?: any
  source?: string
  target?: string
  positions?: any
}

export interface AlgorithmResult {
  path: string[]
  cost: number | null
  settled?: number
  expanded?: number
  passes?: number
  relaxations: number
  explored_order: string[]
  success: boolean
  runtime_ms: number
  correctness: {
    ref_cost: number | null
    cost_match: boolean
    valid_path: boolean
    status: string
  }
  has_negative_cycle?: boolean
}

export interface RunResponse {
  results: {
    dijkstra: AlgorithmResult
    astar: AlgorithmResult
    bellman_ford: AlgorithmResult
  }
  reference_cost: number | null
  agreement: boolean
  heuristic_scale: number | null
}

export interface ExperimentResult {
  config: any
  source: string
  target: string
  normal: Record<string, any>
  congested: Record<string, any> | null
  congested_graph: GraphPayload | null
  base_graph: GraphPayload
  traffic_changes: any[]
  affected_edge_ids: string[]
  comparison: {
    route_changed: boolean
    cost_delta: number | null
    normal_cost: number | null
    congested_cost: number | null
  }
  env: any
  wall_clock_ms: number
  timestamp: number
  route_change_frequency: number | null
  recompute_total_ms: number
  updates: any[]
}
