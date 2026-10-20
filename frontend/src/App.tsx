import { useEffect, useMemo, useState } from 'react'
import { api } from './api'
import type { GraphPayload, RunResponse, ExperimentResult } from './types'
import CytoscapeGraph from './components/CytoscapeGraph'
import {
  Activity, Beaker, Map, FlaskConical, BarChart3, Download, Info,
  Play, RefreshCw, AlertTriangle, CheckCircle2, XCircle, Clock, Route, Eye,
  Settings2, Zap, Timer, Network
} from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  LineChart, Line, ScatterChart, Scatter
} from 'recharts'

type Tab = 'overview' | 'lab' | 'compare' | 'traffic' | 'experiments' | 'visuals' | 'evidence'

export default function App() {
  // global experiment config
  const [n, setN] = useState(8)
  const [seed, setSeed] = useState(42)
  const [topology, setTopology] = useState<'grid' | 'grid_diagonal' | 'random_extra'>('grid')
  const [trials, setTrials] = useState(10)
  const [updates, setUpdates] = useState(1)
  const [congestionPct, setCongestionPct] = useState(20)
  const [congestionFactor, setCongestionFactor] = useState(3.0)
  const [source, setSource] = useState('0_0')
  const [target, setTarget] = useState('7_7')
  const [scenarioTraffic, setScenarioTraffic] = useState<'normal' | 'congested'>('normal')

  const [graph, setGraph] = useState<GraphPayload | null>(null)
  const [baseGraph, setBaseGraph] = useState<GraphPayload | null>(null)
  const [congestedGraph, setCongestedGraph] = useState<GraphPayload | null>(null)
  const [activeGraph, setActiveGraph] = useState<GraphPayload | null>(null)
  const [runResult, setRunResult] = useState<RunResponse | null>(null)
  const [prevRunResult, setPrevRunResult] = useState<RunResponse | null>(null)
  const [experimentResult, setExperimentResult] = useState<ExperimentResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [expLoading, setExpLoading] = useState(false)
  const [hoverNode, setHoverNode] = useState<string | null>(null)
  const [hoverEdge, setHoverEdge] = useState<string | null>(null)
  const [selectedEdge, setSelectedEdge] = useState<string | null>(null)
  const [editWeight, setEditWeight] = useState('')
  const [showExplored, setShowExplored] = useState(false)
  const [selectedAlgoForViz, setSelectedAlgoForViz] = useState<'dijkstra' | 'astar' | 'bellman_ford'>('dijkstra')
  const [health, setHealth] = useState<any>(null)
  const [tab, setTab] = useState<Tab>('overview')
  const [lastChanges, setLastChanges] = useState<any[]>([])
  const [beforeCost, setBeforeCost] = useState<number | null>(null)
  const [afterCost, setAfterCost] = useState<number | null>(null)
  const [routeChangedFlag, setRouteChangedFlag] = useState(false)
  const [dark, setDark] = useState(false)

  // scale experiments
  const [scaleResults, setScaleResults] = useState<any[]>([])
  const [scaleLoading, setScaleLoading] = useState(false)

  const activePayload = useMemo(() => {
    if (scenarioTraffic === 'congested' && congestedGraph) return congestedGraph
    return graph
  }, [graph, congestedGraph, scenarioTraffic])

  // keep activeGraph synced
  useEffect(() => {
    setActiveGraph(activePayload)
  }, [activePayload])

  useEffect(() => {
    api.health().then(setHealth).catch(() => { })
    generate()
  }, [])

  useEffect(() => {
    // update source/target when n changes
    setSource('0_0')
    setTarget(`${n - 1}_${n - 1}`)
  }, [n])

  async function generate() {
    setLoading(true)
    try {
      const g = await api.generateGraph({ n, seed, topology, weight_min: 2, weight_max: 12, source: `0_0`, target: `${n - 1}_${n - 1}` })
      // ensure source/target exist
      const newSource = source && g.nodes.find((x: any) => x.id === source) ? source : g.source
      const newTarget = target && g.nodes.find((x: any) => x.id === target) ? target : g.target
      setGraph(g)
      setBaseGraph(JSON.parse(JSON.stringify(g)))
      setCongestedGraph(null)
      setScenarioTraffic('normal')
      setSource(newSource)
      setTarget(newTarget)
      setRunResult(null)
      setPrevRunResult(null)
      setExperimentResult(null)
      setLastChanges([])
      setBeforeCost(null)
      setAfterCost(null)
      // auto-run algorithms after generation
      setTimeout(() => runAlgorithmsFor(g, newSource, newTarget, false), 100)
    } catch (e: any) {
      alert(e.message)
    } finally { setLoading(false) }
  }

  async function runAlgorithmsFor(g: GraphPayload | null, src: string, tgt: string, preservePrev = true) {
    if (!g) return
    setLoading(true)
    try {
      const res: RunResponse = await api.runAlgorithms(g, src, tgt)
      if (preservePrev && runResult) setPrevRunResult(runResult)
      else if (preservePrev && scenarioTraffic === 'congested' && runResult) {
        // keep before snapshot
      }
      setRunResult(res)
      // update before/after cost tracking
      if (scenarioTraffic === 'normal') {
        setBeforeCost(res.results.dijkstra.cost)
      } else {
        setAfterCost(res.results.dijkstra.cost)
        // compare route changed
        if (prevRunResult) {
          const beforePath = prevRunResult.results.dijkstra.path.join(',')
          const afterPath = res.results.dijkstra.path.join(',')
          setRouteChangedFlag(beforePath !== afterPath)
        }
      }
    } catch (e: any) {
      console.error(e)
      alert('Run failed: ' + e.message)
    } finally { setLoading(false) }
  }

  async function handleRun() {
    if (!activeGraph) return
    await runAlgorithmsFor(activeGraph, source, target, true)
  }

  async function handleApplyCongestion() {
    if (!graph) return
    setLoading(true)
    try {
      // save before cost
      const beforeRes = runResult
      const res = await api.applyTraffic(graph, congestionPct, congestionFactor, seed + 9999)
      setCongestedGraph(res.graph)
      setLastChanges(res.changes)
      setScenarioTraffic('congested')
      // run algorithms on new graph
      const runRes: RunResponse = await api.runAlgorithms(res.graph, source, target)
      setPrevRunResult(beforeRes)
      setRunResult(runRes)
      if (beforeRes) {
        setBeforeCost(beforeRes.results.dijkstra.cost)
        setAfterCost(runRes.results.dijkstra.cost)
        setRouteChangedFlag(beforeRes.results.dijkstra.path.join(',') !== runRes.results.dijkstra.path.join(','))
      }
    } catch (e: any) { alert(e.message) }
    finally { setLoading(false) }
  }

  async function handleEditEdgeWeight() {
    if (!activeGraph || !selectedEdge) return
    const w = parseFloat(editWeight)
    if (isNaN(w) || w < 0) { alert('Enter non-negative weight'); return }
    setLoading(true)
    try {
      const res = await api.editEdge(activeGraph, selectedEdge, w, undefined, 'set_weight')
      if (scenarioTraffic === 'congested') setCongestedGraph(res.graph)
      else setGraph(res.graph)
      // re-run
      await runAlgorithmsFor(res.graph, source, target, false)
    } catch (e: any) { alert(e.message) }
    finally { setLoading(false) }
  }

  async function handleToggleClosure() {
    if (!activeGraph || !selectedEdge) return
    setLoading(true)
    try {
      const res = await api.editEdge(activeGraph, selectedEdge, undefined, undefined, 'toggle_close')
      if (scenarioTraffic === 'congested') setCongestedGraph(res.graph)
      else setGraph(res.graph)
      await runAlgorithmsFor(res.graph, source, target, false)
    } catch (e: any) { alert(e.message) }
    finally { setLoading(false) }
  }

  async function handleResetGraph() {
    if (!baseGraph) return
    setLoading(true)
    try {
      const res = await api.resetGraph(baseGraph)
      // Actually baseGraph already is original; we can just reset to baseGraph
      setGraph(baseGraph)
      setCongestedGraph(null)
      setLastChanges([])
      setBeforeCost(null); setAfterCost(null); setRouteChangedFlag(false)
      setScenarioTraffic('normal')
      await runAlgorithmsFor(res.graph, source, target, false)
    } catch (e: any) { alert(e.message) }
    finally { setLoading(false) }
  }

  async function handleSwapScenario(to: 'normal' | 'congested') {
    setScenarioTraffic(to)
    // when switching, run algorithms for that snapshot
    const g = to === 'congested' ? congestedGraph : graph
    if (g) await runAlgorithmsFor(g, source, target, false)
  }

  async function handleExperimentBoth() {
    setExpLoading(true)
    try {
      const res: ExperimentResult = await api.runExperiment({
        n, seed, topology, trials, congestion_pct: congestionPct, congestion_factor: congestionFactor,
        source, target, updates
      })
      setExperimentResult(res)
    } catch (e: any) { alert(e.message) }
    finally { setExpLoading(false) }
  }

  async function handleScaleExperiment() {
    setScaleLoading(true)
    setScaleResults([])
    try {
      const sizes = [4, 6, 8, 10, 12, 14]
      const out: any[] = []
      for (const sz of sizes) {
        const res: ExperimentResult = await api.runExperiment({
          n: sz, seed, topology, trials: 7, congestion_pct: congestionPct, congestion_factor: congestionFactor,
          source: `0_0`, target: `${sz - 1}_${sz - 1}`, scenario: 'normal'
        })
        out.push({
          n: sz,
          nodes: sz * sz,
          edges: res.base_graph.edges.length,
          dijkstra_ms: res.normal['dijkstra'].median_runtime_ms,
          astar_ms: res.normal['astar'].median_runtime_ms,
          bellman_ms: res.normal['bellman_ford'].median_runtime_ms,
          dijkstra_relax: res.normal['dijkstra'].relaxations_median,
          astar_relax: res.normal['astar'].relaxations_median,
          bellman_relax: res.normal['bellman_ford'].relaxations_median,
          dijkstra_expanded: res.normal['dijkstra'].processed_median,
          astar_expanded: res.normal['astar'].processed_median,
        })
      }
      setScaleResults(out)
    } catch (e: any) { alert(e.message) }
    finally { setScaleLoading(false) }
  }

  const congestedEdgeIds = useMemo(() => {
    if (!activeGraph) return new Set<string>()
    const s = new Set<string>()
    activeGraph.edges.forEach(e => {
      if (e.weight !== e.original_weight) s.add(e.id)
    })
    return s
  }, [activeGraph])

  const closedEdgeIds = useMemo(() => {
    if (!activeGraph) return new Set<string>()
    const s = new Set<string>()
    activeGraph.edges.forEach(e => { if (e.closed) s.add(e.id) })
    return s
  }, [activeGraph])

  const highlightedPath = useMemo(() => {
    if (!runResult) return null
    // choose path from selected algorithm for viz
    const r = runResult.results[selectedAlgoForViz]
    return r?.path || runResult.results.dijkstra.path
  }, [runResult, selectedAlgoForViz])

  const exploredNodes = useMemo(() => {
    if (!runResult || !showExplored) return []
    const r = runResult.results[selectedAlgoForViz]
    // @ts-ignore
    return r.explored_order || []
  }, [runResult, selectedAlgoForViz, showExplored])

  const metricsCards = useMemo(() => {
    if (!runResult) return null
    const d = runResult.results.dijkstra
    const a = runResult.results.astar
    const b = runResult.results.bellman_ford
    const nodes = activeGraph?.nodes.length || 0
    const edges = activeGraph?.edges.length || 0

    return { d, a, b, nodes, edges }
  }, [runResult, activeGraph])

  // chart data
  const chartDataMedian = useMemo(() => {
    if (!runResult) return []
    const r = runResult.results
    return [
      { algo: 'Dijkstra', runtime: r.dijkstra.runtime_ms, relax: r.dijkstra.relaxations, expanded: (r.dijkstra as any).settled },
      { algo: 'A*', runtime: r.astar.runtime_ms, relax: r.astar.relaxations, expanded: (r.astar as any).expanded },
      { algo: 'Bellman–Ford', runtime: r.bellman_ford.runtime_ms, relax: r.bellman_ford.relaxations, expanded: (r.bellman_ford as any).passes },
    ]
  }, [runResult])

  const expChartData = useMemo(() => {
    if (!experimentResult?.normal) return []
    const nrm = experimentResult.normal
    const cng = experimentResult.congested
    const make = (algo: string, src: any) => ({
      algo: algo === 'dijkstra' ? 'Dijkstra' : algo === 'astar' ? 'A*' : 'Bellman–Ford',
      median: src[algo].median_runtime_ms,
      mean: src[algo].mean_runtime_ms,
      relax: src[algo].relaxations_median,
      expanded: src[algo].processed_median,
      cost: src[algo].path_cost,
    })
    const rows = ['dijkstra', 'astar', 'bellman_ford'].map(k => make(k, nrm))
    const rowsCong: any[] = cng ? ['dijkstra', 'astar', 'bellman_ford'].map(k => make(k, cng)).map(r => ({ ...r, algo: r.algo + ' (cong)' })) : []
    return { normal: rows, congested: rowsCong }
  }, [experimentResult])

  // hover details
  const hoverEdgeData = useMemo(() => {
    if (!hoverEdge || !activeGraph) return null
    return activeGraph.edges.find(e => e.id === hoverEdge)
  }, [hoverEdge, activeGraph])

  const hoverNodeData = useMemo(() => {
    if (!hoverNode || !activeGraph) return null
    return activeGraph.nodes.find(n => n.id === hoverNode)
  }, [hoverNode, activeGraph])

  const selectedEdgeData = useMemo(() => {
    if (!selectedEdge || !activeGraph) return null
    return activeGraph.edges.find(e => e.id === selectedEdge)
  }, [selectedEdge, activeGraph])

  // export helpers
  function exportCSV() {
    if (!runResult || !activeGraph) return
    const rows = [
      ['Algorithm', 'Path cost', 'Runtime (ms)', 'Processed', 'Relaxations', 'Success', 'Correctness', 'Path'],
    ]
    const map: any = {
      'Dijkstra': runResult.results.dijkstra,
      'A* Search': runResult.results.astar,
      'Bellman-Ford': runResult.results.bellman_ford,
    }
    for (const [name, r] of Object.entries(map) as any) {
      const proc = r.settled ?? r.expanded ?? r.passes ?? ''
      rows.push([name, r.cost ?? '∞', r.runtime_ms, proc, r.relaxations, r.success, r.correctness.status, (r.path || []).join(' -> ')])
    }
    const csv = rows.map(r => r.map(v => `"${v}"`).join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `dynamicroutelab_${n}x${n}_seed${seed}.csv`; a.click()
    URL.revokeObjectURL(url)
  }

  function exportExperimentCSV() {
    if (!experimentResult) return
    const headers = ['scenario', 'algorithm', 'median_ms', 'mean_ms', 'stdev_ms', 'min_ms', 'max_ms', 'path_cost', 'processed_median', 'relax_median', 'success']
    const rows: any[] = [headers]
    const pushScenario = (label: string, data: any) => {
      if (!data) return
      for (const algo of ['dijkstra', 'astar', 'bellman_ford']) {
        const s = data[algo]
        rows.push([label, algo, s.median_runtime_ms, s.mean_runtime_ms, s.stdev_runtime_ms, s.min_runtime_ms, s.max_runtime_ms, s.path_cost, s.processed_median, s.relaxations_median, s.success])
      }
    }
    pushScenario('normal', experimentResult.normal)
    pushScenario('congested', experimentResult.congested)
    const csv = rows.map(r => r.join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `experiment_${n}x${n}_seed${seed}_trials${trials}.csv`; a.click()
    URL.revokeObjectURL(url)
  }

  function exportJSON() {
    const data = {
      config: { n, seed, topology, trials, congestionPct, congestionFactor, source, target, scenarioTraffic },
      runResult,
      experimentResult,
      graph: activeGraph,
      timestamp: new Date().toISOString(),
      env: health || experimentResult?.env,
      methodology: "Synthetic grid, non-negative travel-time weights 2-12, A* heuristic h(v) = c* · Manhattan(v, target), where c* = min over open roads of weight/Manhattan road length; admissible and consistent."
    }
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = `dynamicroutelab_export_${Date.now()}.json`; a.click(); URL.revokeObjectURL(url)
  }

  return (
    <div className={`min-h-screen ${dark ? 'bg-[#0f1115] text-[#e5e7eb]' : 'bg-[#fdfbf7] text-[#111827]'} flex flex-col`}>
      {/* Top bar */}
      <header className={`${dark ? 'bg-[#111317] border-[#22252b]' : 'bg-white border-[#e7e5e0]'} border-b sticky top-0 z-30`}>
        <div className="max-w-[1440px] mx-auto px-5 h-[56px] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded bg-[#1d4ed8] flex items-center justify-center text-white">
              <Network size={16} />
            </div>
            <div>
              <div className={`text-[13px] font-semibold tracking-tight leading-none ${dark ? 'text-white' : 'text-[#111827]'}`}>DynamicRouteLab</div>
              <div className="text-[10px] tracking-widest text-[#6b7280] font-medium">RESEARCH PLATFORM — v1.0.0</div>
            </div>
            <span className="hidden md:inline-flex ml-3 px-2 py-0.5 rounded bg-[#eef2ff] text-[#1d4ed8] text-[10px] font-semibold border border-[#dbeafe]">SYNTHETIC DATA • DETERMINISTIC</span>
          </div>
          <div className="flex items-center gap-2">
            <div className={`hidden lg:flex items-center gap-2 text-[11px] mono ${dark ? 'text-[#9ca3af]' : 'text-[#6b7280]'} border ${dark ? 'border-[#22252b] bg-[#1a1d22]' : 'border-[#e7e5e0] bg-[#fdfbf7]'} px-2.5 py-1 rounded`}>
              <span className={`w-2 h-2 rounded-full ${health ? 'bg-emerald-500' : 'bg-amber-400'} animate-pulse`}></span>
              API {health ? 'OK' : 'connecting'} • {activeGraph ? `${activeGraph.nodes.length} nodes • ${activeGraph.edges.length} edges` : '—'}
            </div>
            <button onClick={() => setDark(!dark)} className={`w-8 h-8 rounded border text-xs ${dark ? 'bg-[#1a1d22] border-[#2a2e36] text-white' : 'bg-white border-[#e7e5e0]'}`} title="Toggle theme">{dark ? '☀' : '☾'}</button>
            <a href="#method" onClick={(e) => { e.preventDefault(); setTab('evidence'); document.getElementById('method')?.scrollIntoView() }} className={`hidden md:inline-flex items-center gap-1.5 px-3 h-8 rounded border text-xs font-medium ${dark ? 'bg-[#1a1d22] border-[#2a2e36] text-white' : 'bg-white border-[#e7e5e0] hover:bg-[#fdfbf7]'}`}><Info size={12} /> Methodology</a>
          </div>
        </div>
        {/* experiment meta strip */}
        <div className={`border-t ${dark ? 'border-[#1f232b] bg-[#0f1115]' : 'border-[#e7e5e0] bg-[#fdfbf7]'} `}>
          <div className="max-w-[1440px] mx-auto px-5 h-[42px] flex items-center gap-3 overflow-x-auto">
            <div className="flex items-center gap-2 shrink-0">
              <label className="text-[11px] font-semibold tracking-wide text-[#6b7280]">GRAPH</label>
              <select value={topology} onChange={e => setTopology(e.target.value as any)} className={`h-7 rounded border px-2 text-xs ${dark ? 'bg-[#1a1d22] border-[#2a2e36] text-white' : 'bg-white border-[#e7e5e0]'}`}>
                <option value="grid">Grid (4-nbr)</option>
                <option value="grid_diagonal">Grid + Diagonal</option>
                <option value="random_extra">Grid + Random Extra</option>
              </select>
              <div className={`flex items-center gap-1.5 text-xs ${dark ? 'text-[#9ca3af]' : 'text-[#374151]'} `}>
                <span className="mono">{n}×{n}</span>
                <input type="range" min={4} max={18} value={n} onChange={e => setN(parseInt(e.target.value))} className="w-20" />
              </div>
            </div>
            <div className="h-5 w-px bg-[#e7e5e0] shrink-0" />
            <div className="flex items-center gap-2 shrink-0">
              <label className="text-[11px] font-semibold tracking-wide text-[#6b7280]">SEED</label>
              <input type="number" value={seed} onChange={e => setSeed(parseInt(e.target.value) || 0)} className={`w-20 h-7 rounded border px-2 text-xs mono ${dark ? 'bg-[#1a1d22] border-[#2a2e36] text-white' : 'bg-white border-[#e7e5e0]'}`} />
              <button onClick={generate} className="h-7 px-3 rounded bg-[#111827] text-white text-xs font-medium hover:bg-black flex items-center gap-1"><RefreshCw size={12} /> Generate</button>
            </div>
            <div className="h-5 w-px bg-[#e7e5e0] shrink-0" />
            <div className="flex items-center gap-2 shrink-0">
              <label className="text-[11px] font-semibold tracking-wide text-[#6b7280]">SRC</label>
              <select value={source} onChange={e => setSource(e.target.value)} className={`h-7 rounded border px-2 text-xs mono max-w-[110px] ${dark ? 'bg-[#1a1d22] border-[#2a2e36] text-white' : 'bg-white border-[#e7e5e0]'}`}>
                {activeGraph?.nodes.slice(0, 100).map(n => <option key={n.id} value={n.id}>{n.id}</option>)}
              </select>
              <span className="text-[#9ca3af] text-xs">→</span>
              <label className="text-[11px] font-semibold tracking-wide text-[#6b7280]">DST</label>
              <select value={target} onChange={e => setTarget(e.target.value)} className={`h-7 rounded border px-2 text-xs mono max-w-[110px] ${dark ? 'bg-[#1a1d22] border-[#2a2e36] text-white' : 'bg-white border-[#e7e5e0]'}`}>
                {activeGraph?.nodes.slice(0, 100).map(n => <option key={n.id} value={n.id}>{n.id}</option>)}
              </select>
              <button onClick={handleRun} disabled={loading || !activeGraph} className="h-7 px-3 rounded bg-[#1d4ed8] text-white text-xs font-medium hover:bg-[#1e40af] disabled:opacity-50 flex items-center gap-1"><Play size={12} /> Run</button>
            </div>
            <div className="ml-auto hidden xl:flex items-center gap-2 shrink-0">
              <span className={`px-2 py-1 rounded border text-[11px] mono ${dark ? 'bg-[#1a1d22] border-[#2a2e36] text-white' : 'bg-white border-[#e7e5e0]'}`}>Seed: <b>{seed}</b> • {topology} • {n}×{n} • {trials} trials</span>
            </div>
          </div>
        </div>
        {/* Tabs */}
        <div className={`px-5 max-w-[1440px] mx-auto flex items-center gap-1 h-[40px] border-t ${dark ? 'border-[#1f232b] bg-[#0f1115]' : 'border-[#e7e5e0] bg-[#f8f6f1]'} -mb-px overflow-x-auto`}>
          {[
            { id: 'overview', label: 'Overview', icon: Beaker },
            { id: 'lab', label: 'Laboratory', icon: Map },
            { id: 'compare', label: 'Algorithm Comparison', icon: Activity },
            { id: 'traffic', label: 'Traffic Simulator', icon: Zap },
            { id: 'experiments', label: 'Experiment Runner', icon: FlaskConical },
            { id: 'visuals', label: 'Visualizations', icon: BarChart3 },
            { id: 'evidence', label: 'Evidence & Export', icon: Download },
          ].map(t => (
            <button key={t.id} onClick={() => setTab(t.id as Tab)} className={`h-7 px-3 rounded-full text-xs font-medium inline-flex items-center gap-1.5 whitespace-nowrap border transition ${tab === t.id ? 'bg-[#111827] text-white border-[#111827]' : dark ? 'bg-[#1a1d22] text-[#9ca3af] border-[#2a2e36] hover:text-white' : 'bg-white text-[#374151] border-[#e7e5e0] hover:bg-[#fdfbf7]'}`}>
              <t.icon size={12} /> {t.label}
            </button>
          ))}
          <div className="ml-auto flex items-center gap-1.5 text-[11px] mono text-[#6b7280]">
            <Clock size={12} /> Reproducible • {new Date().toLocaleDateString()}
          </div>
        </div>
      </header>

      <main className="max-w-[1440px] mx-auto w-full px-5 py-6 flex-1">
        {tab === 'overview' && (
          <div className="grid grid-cols-12 gap-5">
            {/* Left: Overview metrics */}
            <div className="col-span-12 lg:col-span-8 space-y-5">
              <div className={`${dark ? 'bg-[#1a1d22] border-[#2a2e36]' : 'bg-white border-[#e7e5e0]'} border rounded-[10px] p-5`}>
                <div className="flex items-start justify-between">
                  <div>
                    <h1 className={`text-[18px] font-semibold tracking-tight ${dark ? 'text-white' : 'text-[#111827]'}`}>Shortest Path Algorithms for Dynamic Road Networks</h1>
                    <p className={`text-[13px] leading-5 ${dark ? 'text-[#9ca3af]' : 'text-[#6b7280]'} mt-1 max-w-[680px]`}>A comparative research platform for Dijkstra, A* Search, and Bellman–Ford under traffic congestion, road closures, and travel-time changes. Every measurement is computed on the current synthetic snapshot — no fabricated data.</p>
                  </div>
                  <div className={`hidden md:flex flex-col items-end text-[11px] mono ${dark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}`}>
                    <span>Graph: <b className={dark ? 'text-white' : 'text-[#111827]'}>{activeGraph?.nodes.length ?? 0} nodes</b> • <b className={dark ? 'text-white' : 'text-[#111827]'}>{activeGraph?.edges.length ?? 0} edges</b></span>
                    <span>Traffic: <b className={dark ? 'text-white' : 'text-[#111827]'}>{closedEdgeIds.size > 0 ? `${closedEdgeIds.size} closed` : congestedEdgeIds.size > 0 ? `${congestedEdgeIds.size} congested` : 'normal'}</b> • Seed: <b className={dark ? 'text-white' : 'text-[#111827]'}>{seed}</b></span>
                    <span className="text-[10px]">Timer: perf_counter_ns • UI excluded</span>
                  </div>
                </div>

                {/* metric cards */}
                {!metricsCards ? (
                  <div className={`mt-5 p-8 text-center rounded border border-dashed ${dark ? 'border-[#2a2e36] text-[#9ca3af]' : 'border-[#e7e5e0] text-[#6b7280]'} `}>
                    <Beaker size={20} className="mx-auto mb-2 opacity-60" />
                    <div className="text-sm font-medium">No experiment yet</div>
                    <div className="text-xs mt-1">Click <b>Run</b> to compute optimal path cost, runtime, expanded vertices, relaxations, and correctness.</div>
                  </div>
                ) : (
                  <div className="mt-5 grid grid-cols-2 md:grid-cols-5 gap-3">
                    <div className={`rounded border p-3 ${dark ? 'bg-[#111317] border-[#2a2e36]' : 'bg-[#fdfbf7] border-[#e7e5e0]'}`}>
                      <div className="text-[11px] font-semibold tracking-wide text-[#6b7280]">OPTIMAL PATH COST</div>
                      <div className={`text-[22px] font-semibold mono mt-1 ${dark ? 'text-white' : 'text-[#111827]'}`}>{metricsCards.d.cost ?? '∞'}</div>
                      <div className="text-[11px] text-[#6b7280]">travel-time units</div>
                      <div className="text-[10px] text-emerald-600 mt-1 flex items-center gap-1"><CheckCircle2 size={10} /> {runResult?.agreement ? 'All algorithms agree' : 'Mismatch'}</div>
                    </div>
                    <div className={`rounded border p-3 ${dark ? 'bg-[#111317] border-[#2a2e36]' : 'bg-[#fdfbf7] border-[#e7e5e0]'}`}>
                      <div className="text-[11px] font-semibold tracking-wide text-[#6b7280]">MEDIAN RUNTIME</div>
                      <div className={`text-[22px] font-semibold mono mt-1 ${dark ? 'text-white' : 'text-[#111827]'}`}>{metricsCards.d.runtime_ms.toFixed(3)}<span className="text-[12px] font-normal text-[#6b7280]"> ms</span></div>
                      <div className="text-[11px] text-[#6b7280]">Dijkstra • {trials} trials</div>
                      <div className="text-[10px] text-[#6b7280] mt-1">A*: {metricsCards.a.runtime_ms.toFixed(3)} ms • BF: {metricsCards.b.runtime_ms.toFixed(3)} ms</div>
                    </div>
                    <div className={`rounded border p-3 ${dark ? 'bg-[#111317] border-[#2a2e36]' : 'bg-[#fdfbf7] border-[#e7e5e0]'}`}>
                      <div className="text-[11px] font-semibold tracking-wide text-[#6b7280]">EXPANDED VERTICES</div>
                      <div className={`text-[22px] font-semibold mono mt-1 ${dark ? 'text-white' : 'text-[#111827]'}`}>{(metricsCards.d as any).settled}<span className="text-[12px] font-normal text-[#6b7280]"> / {(metricsCards.a as any).expanded}</span></div>
                      <div className="text-[11px] text-[#6b7280]">Dijkstra / A*</div>
                      <div className="text-[10px] text-[#6b7280] mt-1">BF passes: {(metricsCards.b as any).passes}</div>
                    </div>
                    <div className={`rounded border p-3 ${dark ? 'bg-[#111317] border-[#2a2e36]' : 'bg-[#fdfbf7] border-[#e7e5e0]'}`}>
                      <div className="text-[11px] font-semibold tracking-wide text-[#6b7280]">EDGE RELAXATIONS</div>
                      <div className={`text-[22px] font-semibold mono mt-1 ${dark ? 'text-white' : 'text-[#111827]'}`}>{metricsCards.d.relaxations}</div>
                      <div className="text-[11px] text-[#6b7280]">Dijkstra • comparable work</div>
                      <div className="text-[10px] text-[#6b7280] mt-1">A*: {metricsCards.a.relaxations} • BF: {metricsCards.b.relaxations}</div>
                    </div>
                    <div className={`rounded border p-3 ${dark ? 'bg-[#111317] border-[#2a2e36]' : 'bg-[#fdfbf7] border-[#e7e5e0]'}`}>
                      <div className="text-[11px] font-semibold tracking-wide text-[#6b7280]">CORRECTNESS</div>
                      <div className={`text-[14px] font-semibold mono mt-1 flex items-center gap-1 ${dark ? 'text-white' : 'text-[#111827]'}`}>{runResult?.results.dijkstra.correctness.status === 'pass' && runResult?.results.astar.correctness.status === 'pass' ? <><CheckCircle2 size={14} className="text-emerald-600" /> PASS</> : <><XCircle size={14} className="text-red-600" /> FAIL</>}</div>
                      <div className="text-[11px] text-[#6b7280]">vs. trusted reference</div>
                      <div className="text-[10px] text-[#6b7280] mt-1">Valid edges • cost match</div>
                    </div>
                  </div>
                )}

                {/* hypotheses */}
                <div className={`mt-5 grid md:grid-cols-2 gap-3 text-xs leading-4 ${dark ? 'text-[#9ca3af]' : 'text-[#374151]'}`}>
                  <div className={`rounded border p-3 ${dark ? 'bg-[#111317] border-[#2a2e36]' : 'bg-[#f8f6f1] border-[#e7e5e0]'}`}>
                    <div className="font-semibold text-[#111827] dark:text-white text-[11px] tracking-wide">H1 — A* EFFICIENCY</div>
                    <div className="mt-1">A* with admissible heuristic will expand fewer vertices than Dijkstra on at least some pairs while returning same optimal cost. <span className="mono bg-white border border-[#e7e5e0] px-1 rounded text-[10px]">{metricsCards ? `${(metricsCards.a as any).expanded} < ${(metricsCards.d as any).settled} ? ${(metricsCards.a as any).expanded < (metricsCards.d as any).settled ? '✓ supports' : '✗ not this pair'}` : 'run to test'}</span></div>
                  </div>
                  <div className={`rounded border p-3 ${dark ? 'bg-[#111317] border-[#2a2e36]' : 'bg-[#f8f6f1] border-[#e7e5e0]'}`}>
                    <div className="font-semibold text-[#111827] dark:text-white text-[11px] tracking-wide">H2 — TOPOLOGY DEPENDENCE</div>
                    <div className="mt-1">Relative performance depends on topology, heuristic quality, size. <span className="mono bg-white border border-[#e7e5e0] px-1 rounded text-[10px]">Test grid vs diagonal vs random_extra and 4→14 scaling</span></div>
                  </div>
                  <div className={`rounded border p-3 ${dark ? 'bg-[#111317] border-[#2a2e36]' : 'bg-[#f8f6f1] border-[#e7e5e0]'}`}>
                    <div className="font-semibold text-[#111827] dark:text-white text-[11px] tracking-wide">H3 — TRAFFIC RE-ROUTING</div>
                    <div className="mt-1">Traffic may change optimal route even when cost unchanged (equal-cost alternatives). <span className="mono bg-white border border-[#e7e5e0] px-1 rounded text-[10px]">{experimentResult ? (experimentResult.comparison.route_changed ? 'route changed' : 'route unchanged') : routeChangedFlag ? 'route changed' : 'test via simulator'}</span></div>
                  </div>
                  <div className={`rounded border p-3 ${dark ? 'bg-[#111317] border-[#2a2e36]' : 'bg-[#f8f6f1] border-[#e7e5e0]'}`}>
                    <div className="font-semibold text-[#111827] dark:text-white text-[11px] tracking-wide">H4 — RECOMPUTATION COST</div>
                    <div className="mt-1">Repeated full recomputation has measurable cost. <span className="mono bg-white border border-[#e7e5e0] px-1 rounded text-[10px]">{experimentResult ? `${experimentResult.recompute_total_ms.toFixed(2)} ms recompute total` : 'run experiment to measure'}</span></div>
                  </div>
                </div>
              </div>

              {/* mini lab preview */}
              <div className={`${dark ? 'bg-[#1a1d22] border-[#2a2e36]' : 'bg-white border-[#e7e5e0]'} border rounded-[10px] overflow-hidden`}>
                <div className={`h-9 flex items-center justify-between px-4 border-b ${dark ? 'border-[#2a2e36] bg-[#111317]' : 'border-[#e7e5e0] bg-[#f8f6f1]'}`}>
                  <div className="text-xs font-semibold flex items-center gap-2"><Map size={14} /> Interactive Road-Network Laboratory — Preview</div>
                  <button onClick={() => setTab('lab')} className={`px-2.5 py-1 rounded border text-xs font-medium ${dark ? 'bg-[#1a1d22] border-[#2a2e36] text-white' : 'bg-white border-[#e7e5e0]'}`}><Eye size={12} className="inline mr-1" /> Open Lab</button>
                </div>
                {activeGraph && <CytoscapeGraph graph={activeGraph} source={source} target={target} highlightedPath={highlightedPath} exploredNodes={exploredNodes} congestedEdgeIds={congestedEdgeIds} closedEdgeIds={closedEdgeIds} showExplored={showExplored} />}
                {!activeGraph && <div className="h-[400px] flex items-center justify-center text-sm text-[#6b7280]">No graph yet</div>}
              </div>
            </div>

            {/* Right column */}
            <div className="col-span-12 lg:col-span-4 space-y-5">
              <div className={`${dark ? 'bg-[#1a1d22] border-[#2a2e36]' : 'bg-white border-[#e7e5e0]'} border rounded-[10px] p-4`}>
                <h3 className={`text-xs font-semibold tracking-wide ${dark ? 'text-white' : 'text-[#111827]'} flex items-center gap-2`}><Settings2 size={14} /> EXPERIMENT CONFIGURATION</h3>
                <div className="mt-3 space-y-3">
                  <div>
                    <label className="text-[11px] font-medium text-[#6b7280]">Trials per algorithm</label>
                    <div className="flex items-center gap-2 mt-1">
                      <input type="range" min={3} max={30} value={trials} onChange={e => setTrials(parseInt(e.target.value))} className="flex-1" />
                      <span className={`px-2 py-1 rounded border text-xs mono ${dark ? 'bg-[#111317] border-[#2a2e36] text-white' : 'bg-[#fdfbf7] border-[#e7e5e0]'}`}>{trials}</span>
                    </div>
                    <div className="text-[10px] text-[#9ca3af] mt-1">High-res perf_counter_ns • graph gen excluded</div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-[11px] font-medium text-[#6b7280]">Congestion %</label>
                      <div className="flex items-center gap-2 mt-1">
                        <input type="range" min={5} max={60} step={5} value={congestionPct} onChange={e => setCongestionPct(parseInt(e.target.value))} className="flex-1" />
                        <span className={`px-2 py-1 rounded border text-xs mono ${dark ? 'bg-[#111317] border-[#2a2e36] text-white' : 'bg-[#fdfbf7] border-[#e7e5e0]'}`}>{congestionPct}%</span>
                      </div>
                    </div>
                    <div>
                      <label className="text-[11px] font-medium text-[#6b7280]">Multiplier</label>
                      <div className="flex items-center gap-2 mt-1">
                        <input type="range" min={1.5} max={8} step={0.5} value={congestionFactor} onChange={e => setCongestionFactor(parseFloat(e.target.value))} className="flex-1" />
                        <span className={`px-2 py-1 rounded border text-xs mono ${dark ? 'bg-[#111317] border-[#2a2e36] text-white' : 'bg-[#fdfbf7] border-[#e7e5e0]'}`}>{congestionFactor}×</span>
                      </div>
                    </div>
                  </div>
                  <button onClick={handleApplyCongestion} disabled={loading || !graph} className="w-full h-8 rounded bg-[#f59e0b] text-white text-xs font-semibold hover:bg-[#d97706] disabled:opacity-50 flex items-center justify-center gap-1.5"><Zap size={12} /> Apply Congestion Update</button>
                  <div className="flex gap-2">
                    <button onClick={() => handleSwapScenario('normal')} className={`flex-1 h-7 rounded border text-xs font-medium ${scenarioTraffic === 'normal' ? 'bg-[#111827] text-white border-[#111827]' : dark ? 'bg-[#111317] border-[#2a2e36] text-white' : 'bg-white border-[#e7e5e0]'}`}>Normal</button>
                    <button onClick={() => handleSwapScenario('congested')} disabled={!congestedGraph} className={`flex-1 h-7 rounded border text-xs font-medium disabled:opacity-50 ${scenarioTraffic === 'congested' ? 'bg-[#1d4ed8] text-white border-[#1d4ed8]' : dark ? 'bg-[#111317] border-[#2a2e36] text-white' : 'bg-white border-[#e7e5e0]'}`}>After congestion</button>
                  </div>
                  <div className={`rounded border p-2.5 text-[11px] leading-4 ${dark ? 'bg-[#111317] border-[#2a2e36] text-[#9ca3af]' : 'bg-[#fdfbf7] border-[#e7e5e0] text-[#374151]'}`}>
                    <div className="font-semibold text-[#111827] dark:text-white">Current snapshot</div>
                    <div className="mono text-[10px] mt-1">
                      <div>Source: {source} → Target: {target}</div>
                      <div>Heuristic scale c* = {runResult?.heuristic_scale != null ? runResult.heuristic_scale.toFixed(3) : '—'} (h = c* × Manhattan)</div>
                      <div>c* = min(w / Manhattan length) over open roads, so h never overestimates after congestion or closures.</div>
                    </div>
                  </div>
                </div>
              </div>

              <div className={`${dark ? 'bg-[#1a1d22] border-[#2a2e36]' : 'bg-white border-[#e7e5e0]'} border rounded-[10px] p-4`}>
                <h3 className={`text-xs font-semibold tracking-wide ${dark ? 'text-white' : 'text-[#111827]'} flex items-center gap-2`}><Timer size={14} /> LATEST RESULTS</h3>
                {!runResult ? <div className="text-xs text-[#6b7280] mt-3">Run an experiment to see results.</div> : (
                  <div className="mt-3 space-y-2">
                    {[
                      { key: 'dijkstra', label: 'Dijkstra', color: '#1d4ed8', desc: 'settled vertices' },
                      { key: 'astar', label: 'A* Search', color: '#7c3aed', desc: 'expanded vertices' },
                      { key: 'bellman_ford', label: 'Bellman–Ford', color: '#d97706', desc: 'relaxation passes' },
                    ].map(item => {
                      const r = (runResult.results as any)[item.key]
                      const processed = r.settled ?? r.expanded ?? r.passes
                      return (
                        <div key={item.key} className={`rounded border p-2.5 ${dark ? 'bg-[#111317] border-[#2a2e36]' : 'bg-[#fdfbf7] border-[#e7e5e0]'}`}>
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="w-2 h-2 rounded-full" style={{ background: item.color }}></span>
                              <span className="text-xs font-semibold">{item.label}</span>
                              <span className="text-[10px] text-[#6b7280]">{item.desc}</span>
                            </div>
                            <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${r.correctness.status === 'pass' ? 'bg-emerald-50 border-emerald-200 text-emerald-700' : 'bg-red-50 border-red-200 text-red-700'}`}>{r.correctness.status.toUpperCase()}</span>
                          </div>
                          <div className="grid grid-cols-3 gap-2 mt-2 text-[11px] mono">
                            <div><div className="text-[#6b7280] text-[10px]">COST</div><div className={`font-semibold ${dark ? 'text-white' : 'text-[#111827]'}`}>{r.cost ?? '∞'}</div></div>
                            <div><div className="text-[#6b7280] text-[10px]">TIME</div><div className={`font-semibold ${dark ? 'text-white' : 'text-[#111827]'}`}>{r.runtime_ms.toFixed(2)} ms</div></div>
                            <div><div className="text-[#6b7280] text-[10px]">PROC / RELAX</div><div className={`font-semibold ${dark ? 'text-white' : 'text-[#111827]'}`}>{processed} / {r.relaxations}</div></div>
                          </div>
                          <div className="text-[10px] text-[#6b7280] mt-1 truncate mono">Path: {r.path.length ? r.path.join(' → ') : 'no path'}</div>
                        </div>
                      )
                    })}
                    <div className="flex gap-2 pt-1">
                      <button onClick={exportCSV} className={`flex-1 h-7 rounded border text-xs font-medium flex items-center justify-center gap-1 ${dark ? 'bg-[#111317] border-[#2a2e36] text-white' : 'bg-white border-[#e7e5e0]'}`}><Download size={12} /> CSV</button>
                      <button onClick={exportJSON} className={`flex-1 h-7 rounded border text-xs font-medium flex items-center justify-center gap-1 ${dark ? 'bg-[#111317] border-[#2a2e36] text-white' : 'bg-white border-[#e7e5e0]'}`}><Download size={12} /> JSON</button>
                    </div>
                  </div>
                )}
              </div>

              <div className={`rounded border p-3 text-[11px] leading-4 ${dark ? 'bg-[#111317] border-[#2a2e36] text-[#9ca3af]' : 'bg-[#fffbeb] border-[#fde68a] text-[#92400e]'}`}>
                <div className="font-semibold flex items-center gap-1.5"><AlertTriangle size={12} /> Research integrity</div>
                <div className="mt-1">Synthetic non-negative weights. Small-graph runtimes are noisy; use larger n, repeated trials, multiple seeds. <b>Processed count</b> is algorithm-specific; compare <b>edge relaxations</b> for work, noting not all costs equal.</div>
              </div>
            </div>
          </div>
        )}

        {tab === 'lab' && (
          <div className="grid grid-cols-12 gap-5">
            <div className="col-span-12 lg:col-span-9 space-y-4">
              <div className={`${dark ? 'bg-[#1a1d22] border-[#2a2e36]' : 'bg-white border-[#e7e5e0]'} border rounded-[10px] overflow-hidden`}>
                <div className={`h-10 flex items-center justify-between px-4 border-b ${dark ? 'border-[#2a2e36] bg-[#111317]' : 'border-[#e7e5e0] bg-[#f8f6f1]'}`}>
                  <div className="text-xs font-semibold flex items-center gap-2"><Map size={14} /> ROAD NETWORK LABORATORY</div>
                  <div className="flex items-center gap-2">
                    <label className="flex items-center gap-1.5 text-xs"><input type="checkbox" checked={showExplored} onChange={e => setShowExplored(e.target.checked)} /> Show explored</label>
                    <select value={selectedAlgoForViz} onChange={e => setSelectedAlgoForViz(e.target.value as any)} className={`h-7 rounded border px-2 text-xs ${dark ? 'bg-[#1a1d22] border-[#2a2e36] text-white' : 'bg-white border-[#e7e5e0]'}`}>
                      <option value="dijkstra">Dijkstra route</option>
                      <option value="astar">A* route</option>
                      <option value="bellman_ford">Bellman–Ford route</option>
                    </select>
                    <button onClick={handleRun} className="h-7 px-3 rounded bg-[#1d4ed8] text-white text-xs font-medium">Recompute</button>
                  </div>
                </div>
                {activeGraph ? (
                  <CytoscapeGraph
                    graph={activeGraph}
                    source={source}
                    target={target}
                    highlightedPath={highlightedPath}
                    exploredNodes={exploredNodes}
                    congestedEdgeIds={congestedEdgeIds}
                    closedEdgeIds={closedEdgeIds}
                    showExplored={showExplored}
                    onNodeClick={(nid) => {
                      // first click sets source, second sets target? We'll alternate: if source==nid -> pick target, else set source/target via prompt
                      // Simple: click to set source, shift-click to set target not possible, so we use buttons below
                      // We'll just select node for inspection
                      setHoverNode(nid)
                    }}
                    onEdgeClick={(eid) => { setSelectedEdge(eid); setEditWeight(activeGraph.edges.find(e => e.id === eid)?.weight.toString() || '') }}
                    onHoverNode={setHoverNode}
                    onHoverEdge={setHoverEdge}
                  />
                ) : <div className="h-[560px] grid place-items-center text-sm text-[#6b7280]">No graph</div>}
                <div className={`px-4 py-2.5 border-t text-[11px] flex items-center justify-between ${dark ? 'border-[#2a2e36] bg-[#111317] text-[#9ca3af]' : 'border-[#e7e5e0] bg-[#f8f6f1] text-[#6b7280]'}`}>
                  <span className="mono">Click nodes/edges to inspect • Use zoom/pan/fit controls • Routes highlight {selectedAlgoForViz}</span>
                  <span className="mono">{activeGraph?.nodes.length} intersections • {activeGraph?.edges.length} roads • {congestedEdgeIds.size} congested • {closedEdgeIds.size} closed</span>
                </div>
              </div>
            </div>

            <div className="col-span-12 lg:col-span-3 space-y-4">
              <div className={`${dark ? 'bg-[#1a1d22] border-[#2a2e36]' : 'bg-white border-[#e7e5e0]'} border rounded-[10px] p-4`}>
                <h3 className={`text-xs font-semibold tracking-wide ${dark ? 'text-white' : 'text-[#111827]'}`}>SELECT SOURCE & DESTINATION</h3>
                <div className="mt-3 space-y-3">
                  <div>
                    <label className="text-[11px] text-[#6b7280]">Source</label>
                    <select value={source} onChange={e => { setSource(e.target.value); setTimeout(() => activeGraph && runAlgorithmsFor(activeGraph, e.target.value, target, false), 0) }} className={`w-full mt-1 h-8 rounded border px-2 text-xs mono ${dark ? 'bg-[#111317] border-[#2a2e36] text-white' : 'bg-white border-[#e7e5e0]'}`}>
                      {activeGraph?.nodes.map(n => <option key={n.id} value={n.id}>{n.id} (r{n.r},c{n.c})</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="text-[11px] text-[#6b7280]">Destination</label>
                    <select value={target} onChange={e => { setTarget(e.target.value); setTimeout(() => activeGraph && runAlgorithmsFor(activeGraph, source, e.target.value, false), 0) }} className={`w-full mt-1 h-8 rounded border px-2 text-xs mono ${dark ? 'bg-[#111317] border-[#2a2e36] text-white' : 'bg-white border-[#e7e5e0]'}`}>
                      {activeGraph?.nodes.map(n => <option key={n.id} value={n.id}>{n.id} (r{n.r},c{n.c})</option>)}
                    </select>
                  </div>
                  <div className={`rounded p-2.5 text-[11px] leading-4 border ${dark ? 'bg-[#111317] border-[#2a2e36] text-[#9ca3af]' : 'bg-[#fdfbf7] border-[#e7e5e0] text-[#374151]'}`}>
                    <div className="font-semibold">Hover details</div>
                    {hoverNodeData && <div className="mono mt-1">Node <b>{hoverNodeData.id}</b> • row {hoverNodeData.r}, col {hoverNodeData.c} • position ({hoverNodeData.x}, {hoverNodeData.y})</div>}
                    {hoverEdgeData && <div className="mono mt-1">Road <b>{hoverEdgeData.id}</b><br />{hoverEdgeData.source} ↔ {hoverEdgeData.target}<br />weight {hoverEdgeData.weight} {hoverEdgeData.weight !== hoverEdgeData.original_weight ? `(original ${hoverEdgeData.original_weight})` : ''} {hoverEdgeData.closed ? '• CLOSED' : ''}</div>}
                    {!hoverNodeData && !hoverEdgeData && <div className="text-[#9ca3af] mt-1">Hover a node or edge in the graph to inspect.</div>}
                  </div>
                </div>
              </div>

              <div className={`${dark ? 'bg-[#1a1d22] border-[#2a2e36]' : 'bg-white border-[#e7e5e0]'} border rounded-[10px] p-4`}>
                <h3 className={`text-xs font-semibold tracking-wide ${dark ? 'text-white' : 'text-[#111827]'}`}>EDIT ROAD</h3>
                <div className="mt-3">
                  <label className="text-[11px] text-[#6b7280]">Selected road (click edge)</label>
                  <div className={`mt-1 h-8 rounded border px-2 flex items-center text-xs mono ${dark ? 'bg-[#111317] border-[#2a2e36] text-white' : 'bg-[#fdfbf7] border-[#e7e5e0]'}`}>{selectedEdge || '— none —'}</div>
                  {selectedEdgeData && (
                    <>
                      <div className="mt-2 text-[11px] text-[#374151] mono">
                        <div>{selectedEdgeData.source} ↔ {selectedEdgeData.target}</div>
                        <div>Current: <b>{selectedEdgeData.weight}</b> • Original: {selectedEdgeData.original_weight} • {selectedEdgeData.closed ? 'CLOSED' : 'open'}</div>
                      </div>
                      <div className="flex gap-2 mt-2">
                        <input value={editWeight} onChange={e => setEditWeight(e.target.value)} placeholder="New weight" className={`flex-1 h-8 rounded border px-2 text-xs mono ${dark ? 'bg-[#111317] border-[#2a2e36] text-white' : 'bg-white border-[#e7e5e0]'}`} />
                        <button onClick={handleEditEdgeWeight} className="h-8 px-3 rounded bg-[#111827] text-white text-xs">Set</button>
                      </div>
                      <button onClick={handleToggleClosure} className={`w-full mt-2 h-8 rounded border text-xs font-medium ${selectedEdgeData.closed ? 'bg-emerald-600 text-white border-emerald-600' : 'bg-white border-[#e7e5e0] text-[#111827]'}`}>{selectedEdgeData.closed ? 'Reopen road' : 'Close road'}</button>
                    </>
                  )}
                  <div className="mt-3 flex gap-2">
                    <button onClick={handleResetGraph} className="flex-1 h-7 rounded border text-xs bg-white border-[#e7e5e0] hover:bg-gray-50">Reset to original</button>
                    <button onClick={handleRun} className="flex-1 h-7 rounded bg-[#1d4ed8] text-white text-xs">Recompute</button>
                  </div>
                  <p className="text-[10px] text-[#6b7280] mt-2 leading-3">Edge-weight edits change actual graph weights and affect all algorithms consistently. Closures remove traversable edge.</p>
                </div>
              </div>

              <div className={`${dark ? 'bg-[#1a1d22] border-[#2a2e36]' : 'bg-white border-[#e7e5e0]'} border rounded-[10px] p-4`}>
                <h3 className={`text-xs font-semibold ${dark ? 'text-white' : 'text-[#111827]'}`}>LEGEND & STATES</h3>
                <div className="mt-2 space-y-1.5 text-xs">
                  <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-[#8a94a6]"></span> Normal intersection & road (#d1d5db)</div>
                  <div className="flex items-center gap-2"><span className="w-4 h-1 bg-[#1d4ed8]"></span> Optimal route</div>
                  <div className="flex items-center gap-2"><span className="w-4 h-1 bg-[#f59e0b]"></span> Congested (×{congestionFactor})</div>
                  <div className="flex items-center gap-2"><span className="w-4 h-1 border-t border-dashed border-[#ef4444]"></span> Closed (unavailable)</div>
                  <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-[#f59e0b]"></span> Explored (when enabled)</div>
                </div>
                <div className="mt-3 text-[11px] mono text-[#6b7280]">Synthetic coordinates, not real streets.</div>
              </div>
            </div>
          </div>
        )}

        {tab === 'compare' && (
          <div className="space-y-5">
            <div className={`${dark ? 'bg-[#1a1d22] border-[#2a2e36]' : 'bg-white border-[#e7e5e0]'} border rounded-[10px] p-5`}>
              <h2 className={`text-sm font-semibold flex items-center gap-2 ${dark ? 'text-white' : 'text-[#111827]'}`}><Activity size={16} /> Algorithm Comparison — Identical Snapshot</h2>
              <p className="text-xs text-[#6b7280] mt-1">All algorithms run on the same graph snapshot, source, destination, and weights for fair comparison. Timing excludes graph generation and rendering.</p>
              {!runResult ? <div className="mt-6 text-center text-sm text-[#6b7280] border border-dashed rounded p-8">No run yet. Click <b>Run</b> in the header or Laboratory.</div> : (
                <div className="mt-5 grid lg:grid-cols-3 gap-4">
                  {[
                    { key: 'dijkstra', title: 'Dijkstra', subtitle: 'Priority queue • non-negative weights', color: '#1d4ed8', bg: dark ? '#111317' : '#eff6ff', border: '#dbeafe', metricLabel: 'SETTLED', getMetric: (r: any) => r.settled },
                    { key: 'astar', title: 'A* Search', subtitle: 'c* × Manhattan (admissible, consistent)', color: '#7c3aed', bg: dark ? '#111317' : '#f5f3ff', border: '#ede9fe', metricLabel: 'EXPANDED', getMetric: (r: any) => r.expanded },
                    { key: 'bellman_ford', title: 'Bellman–Ford', subtitle: 'Edge relaxation • negative-cycle detection', color: '#d97706', bg: dark ? '#111317' : '#fffbeb', border: '#fde68a', metricLabel: 'PASSES', getMetric: (r: any) => r.passes },
                  ].map(col => {
                    const r = (runResult.results as any)[col.key]
                    const processed = col.getMetric(r)
                    return (
                      <div key={col.key} className={`rounded-[10px] border overflow-hidden ${dark ? 'border-[#2a2e36]' : 'border-[#e7e5e0]'}`} style={{ background: col.bg, borderColor: dark ? undefined : col.border }}>
                        <div className="px-4 py-3 border-b flex items-center justify-between" style={{ background: dark ? '#0f1115' : 'white', borderColor: col.border }}>
                          <div>
                            <div className="text-xs font-semibold flex items-center gap-2"><span className="w-2 h-2 rounded-full" style={{ background: col.color }}></span>{col.title}</div>
                            <div className="text-[11px] text-[#6b7280]">{col.subtitle}</div>
                          </div>
                          <span className={`text-[10px] px-1.5 py-0.5 rounded border font-semibold ${r.correctness.status === 'pass' ? 'bg-emerald-50 border-emerald-200 text-emerald-700' : 'bg-red-50 border-red-200 text-red-700'}`}>{r.correctness.status.toUpperCase()}</span>
                        </div>
                        <div className="p-4 space-y-3">
                          <div className="grid grid-cols-2 gap-2">
                            <div className={`rounded border p-2.5 ${dark ? 'bg-[#1a1d22] border-[#2a2e36]' : 'bg-white border-[#e7e5e0]'}`}>
                              <div className="text-[10px] tracking-wide font-semibold text-[#6b7280]">PATH COST</div>
                              <div className={`text-lg font-semibold mono ${dark ? 'text-white' : 'text-[#111827]'}`}>{r.cost ?? '∞'}</div>
                              <div className="text-[10px] text-[#6b7280]">ref: {r.correctness.ref_cost ?? '∞'} • {r.correctness.cost_match ? 'match ✓' : 'mismatch ✗'}</div>
                            </div>
                            <div className={`rounded border p-2.5 ${dark ? 'bg-[#1a1d22] border-[#2a2e36]' : 'bg-white border-[#e7e5e0]'}`}>
                              <div className="text-[10px] tracking-wide font-semibold text-[#6b7280]">RUNTIME</div>
                              <div className={`text-lg font-semibold mono ${dark ? 'text-white' : 'text-[#111827]'}`}>{r.runtime_ms.toFixed(3)}<span className="text-[10px] font-normal text-[#6b7280]"> ms</span></div>
                              <div className="text-[10px] text-[#6b7280]">perf_counter_ns</div>
                            </div>
                          </div>
                          <div className="grid grid-cols-2 gap-2">
                            <div className={`rounded border p-2.5 ${dark ? 'bg-[#1a1d22] border-[#2a2e36]' : 'bg-white border-[#e7e5e0]'}`}>
                              <div className="text-[10px] tracking-wide font-semibold text-[#6b7280]">{col.metricLabel}</div>
                              <div className={`text-lg font-semibold mono ${dark ? 'text-white' : 'text-[#111827]'}`}>{processed}</div>
                              <div className="text-[10px] text-[#6b7280]">{col.key === 'dijkstra' ? 'settled vertices' : col.key === 'astar' ? 'expanded vertices' : 'relaxation passes'}</div>
                            </div>
                            <div className={`rounded border p-2.5 ${dark ? 'bg-[#1a1d22] border-[#2a2e36]' : 'bg-white border-[#e7e5e0]'}`}>
                              <div className="text-[10px] tracking-wide font-semibold text-[#6b7280]">EDGE RELAXATIONS</div>
                              <div className={`text-lg font-semibold mono ${dark ? 'text-white' : 'text-[#111827]'}`}>{r.relaxations}</div>
                              <div className="text-[10px] text-[#6b7280]">comparable work metric</div>
                            </div>
                          </div>
                          <div className={`rounded border p-2.5 text-xs leading-4 ${dark ? 'bg-[#1a1d22] border-[#2a2e36] text-[#9ca3af]' : 'bg-white border-[#e7e5e0] text-[#374151]'}`}>
                            <div className="font-semibold text-[11px]">PATH</div>
                            <div className={`mono text-[11px] mt-1 break-all ${r.success ? (dark ? 'text-white' : 'text-[#111827]') : 'text-red-600'}`}>{r.success ? r.path.join(' → ') : `Failed • cost ∞ • ${r.path.length ? r.path.join('→') : 'unreachable or invalid'}`}</div>
                            <div className="text-[10px] text-[#6b7280] mt-1">Length: {r.path.length} nodes • Valid edges: {r.correctness.valid_path ? '✓' : '✗'} • Agreement: {runResult.agreement ? 'yes' : 'no'}</div>
                          </div>
                          {col.key === 'bellman_ford' && r.has_negative_cycle && <div className="text-[11px] bg-red-50 border border-red-200 text-red-700 rounded p-2">⚠ Negative cycle detected — path cost unreliable. (Not physically meaningful as travel time; algorithm supports detection.)</div>}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
              {runResult && (
                <div className={`mt-4 rounded border p-3 text-xs leading-4 ${dark ? 'bg-[#111317] border-[#2a2e36] text-[#9ca3af]' : 'bg-[#f8f6f1] border-[#e7e5e0] text-[#374151]'}`}>
                  <b>Metric semantics:</b> <span className="mono">Settled</span> = Dijkstra finalized nodes via priority queue; <span className="mono">Expanded</span> = A* nodes removed from open set; <span className="mono">Passes</span> = Bellman–Ford full edge-sweep iterations (not comparable to vertex counts). Use <b>edge relaxations</b> for cross-algorithm work comparison, noting implementation differences. Timing boundary: algorithm execution only.
                </div>
              )}
            </div>

            {runResult && (
              <div className="grid lg:grid-cols-2 gap-5">
                <div className={`${dark ? 'bg-[#1a1d22] border-[#2a2e36]' : 'bg-white border-[#e7e5e0]'} border rounded-[10px] p-4`}>
                  <h3 className="text-xs font-semibold">Median runtime by algorithm (current snapshot)</h3>
                  <div className="h-[220px] mt-3">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={chartDataMedian}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e7e5e0" />
                        <XAxis dataKey="algo" tick={{ fontSize: 11 }} />
                        <YAxis tick={{ fontSize: 11 }} label={{ value: 'ms', angle: -90, position: 'insideLeft', fontSize: 11 }} />
                        <Tooltip />
                        <Bar dataKey="runtime" fill="#1d4ed8" name="Runtime (ms)" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
                <div className={`${dark ? 'bg-[#1a1d22] border-[#2a2e36]' : 'bg-white border-[#e7e5e0]'} border rounded-[10px] p-4`}>
                  <h3 className="text-xs font-semibold">Edge relaxations vs. expanded vertices</h3>
                  <div className="h-[220px] mt-3">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={chartDataMedian}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e7e5e0" />
                        <XAxis dataKey="algo" tick={{ fontSize: 11 }} />
                        <YAxis tick={{ fontSize: 11 }} />
                        <Tooltip />
                        <Legend wrapperStyle={{ fontSize: 11 }} />
                        <Bar dataKey="relax" fill="#f59e0b" name="Relaxations" radius={[4, 4, 0, 0]} />
                        <Bar dataKey="expanded" fill="#7c3aed" name="Processed (settled/expanded/passes)" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {tab === 'traffic' && (
          <div className="grid grid-cols-12 gap-5">
            <div className="col-span-12 lg:col-span-8 space-y-4">
              <div className={`${dark ? 'bg-[#1a1d22] border-[#2a2e36]' : 'bg-white border-[#e7e5e0]'} border rounded-[10px] overflow-hidden`}>
                <div className={`h-10 flex items-center justify-between px-4 border-b ${dark ? 'border-[#2a2e36] bg-[#111317]' : 'border-[#e7e5e0] bg-[#f8f6f1]'}`}>
                  <div className="text-xs font-semibold flex items-center gap-2"><Zap size={14} /> DYNAMIC TRAFFIC SIMULATOR</div>
                  <div className="flex gap-2">
                    <button onClick={() => handleSwapScenario('normal')} className={`h-7 px-3 rounded border text-xs font-medium ${scenarioTraffic === 'normal' ? 'bg-[#111827] text-white border-[#111827]' : 'bg-white border-[#e7e5e0]'}`}>Normal traffic</button>
                    <button onClick={() => handleSwapScenario('congested')} disabled={!congestedGraph} className={`h-7 px-3 rounded border text-xs font-medium disabled:opacity-50 ${scenarioTraffic === 'congested' ? 'bg-[#1d4ed8] text-white border-[#1d4ed8]' : 'bg-white border-[#e7e5e0]'}`}>After congestion</button>
                  </div>
                </div>
                {activeGraph ? (
                  <CytoscapeGraph graph={activeGraph} source={source} target={target} highlightedPath={highlightedPath} congestedEdgeIds={congestedEdgeIds} closedEdgeIds={closedEdgeIds} showExplored={false} onEdgeClick={(eid) => { setSelectedEdge(eid); setEditWeight(activeGraph.edges.find(e => e.id === eid)?.weight.toString() || '') }} />
                ) : <div className="h-[560px] grid place-items-center text-sm text-[#6b7280]">No graph</div>}
              </div>

              {lastChanges.length > 0 && (
                <div className={`${dark ? 'bg-[#1a1d22] border-[#2a2e36]' : 'bg-white border-[#e7e5e0]'} border rounded-[10px] p-4`}>
                  <h3 className="text-xs font-semibold">Which roads changed</h3>
                  <div className="mt-2 max-h-[180px] overflow-auto border rounded">
                    <table className="w-full text-[11px] mono">
                      <thead className="bg-[#f8f6f1] sticky top-0"><tr><th className="text-left p-2 border-b">Edge</th><th className="text-left p-2 border-b">Route</th><th className="text-right p-2 border-b">Old → New</th><th className="text-right p-2 border-b">Δ</th></tr></thead>
                      <tbody>
                        {lastChanges.map((ch: any) => (
                          <tr key={ch.edge_id} className="border-b last:border-0 hover:bg-[#fdfbf7]">
                            <td className="p-2">{ch.edge_id}</td>
                            <td className="p-2">{ch.source} ↔ {ch.target}</td>
                            <td className="p-2 text-right">{ch.old_weight} → {ch.new_weight}</td>
                            <td className="p-2 text-right text-amber-600">+{ch.delta}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>

            <div className="col-span-12 lg:col-span-4 space-y-4">
              <div className={`${dark ? 'bg-[#1a1d22] border-[#2a2e36]' : 'bg-white border-[#e7e5e0]'} border rounded-[10px] p-4`}>
                <h3 className="text-xs font-semibold">CONGESTION CONTROLS</h3>
                <div className="mt-3 space-y-3">
                  <div>
                    <label className="text-[11px] text-[#6b7280]">Roads affected</label>
                    <div className="flex items-center gap-2 mt-1">
                      <input type="range" min={5} max={60} step={5} value={congestionPct} onChange={e => setCongestionPct(parseInt(e.target.value))} className="flex-1" />
                      <span className="px-2 py-1 rounded border text-xs mono bg-[#fdfbf7] border-[#e7e5e0]">{congestionPct}%</span>
                    </div>
                  </div>
                  <div>
                    <label className="text-[11px] text-[#6b7280]">Travel-time multiplier</label>
                    <div className="flex items-center gap-2 mt-1">
                      <input type="range" min={1.5} max={8} step={0.5} value={congestionFactor} onChange={e => setCongestionFactor(parseFloat(e.target.value))} className="flex-1" />
                      <span className="px-2 py-1 rounded border text-xs mono bg-[#fdfbf7] border-[#e7e5e0]">{congestionFactor}×</span>
                    </div>
                    <div className="text-[10px] text-[#6b7280] mt-1">Selected roads: weight × multiplier (original preserved for reset).</div>
                  </div>
                  <button onClick={handleApplyCongestion} disabled={!graph} className="w-full h-9 rounded bg-[#f59e0b] text-white text-xs font-semibold hover:bg-[#d97706]">Apply congestion update</button>
                  <div className="grid grid-cols-2 gap-2">
                    <button onClick={handleResetGraph} className="h-8 rounded border text-xs bg-white border-[#e7e5e0]">Reset to original</button>
                    <button onClick={handleRun} className="h-8 rounded bg-[#1d4ed8] text-white text-xs">Recompute routes</button>
                  </div>
                  <div className="rounded border bg-[#fdfbf7] border-[#e7e5e0] p-2.5 text-[11px] leading-4">
                    <div className="font-semibold">Individual edge editing</div>
                    <div className="mono text-[10px] mt-1">Click an edge → set weight or toggle closure. Closure removes traversable edge for all algorithms consistently.</div>
                    <div className="flex gap-2 mt-2">
                      <input value={editWeight} onChange={e => setEditWeight(e.target.value)} placeholder="New weight" className="flex-1 h-7 rounded border px-2 text-xs mono bg-white border-[#e7e5e0]" />
                      <button onClick={handleEditEdgeWeight} disabled={!selectedEdge} className="px-3 h-7 rounded bg-[#111827] text-white text-xs disabled:opacity-50">Set</button>
                    </div>
                    <button onClick={handleToggleClosure} disabled={!selectedEdge} className="w-full mt-1.5 h-7 rounded border text-xs bg-white border-[#e7e5e0] disabled:opacity-50">{selectedEdge && activeGraph?.edges.find(e => e.id === selectedEdge)?.closed ? 'Reopen' : 'Close/Reopen'} selected road</button>
                  </div>
                </div>
              </div>

              <div className={`${dark ? 'bg-[#1a1d22] border-[#2a2e36]' : 'bg-white border-[#e7e5e0]'} border rounded-[10px] p-4`}>
                <h3 className="text-xs font-semibold">BEFORE vs AFTER COMPARISON</h3>
                {!runResult || !prevRunResult ? (
                  <div className="text-xs text-[#6b7280] mt-3">Apply congestion, then view comparison. Both results use identical source/destination; only weights differ.</div>
                ) : (
                  <div className="mt-3 space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div className="rounded border bg-[#fdfbf7] border-[#e7e5e0] p-2.5">
                        <div className="text-[11px] font-semibold text-[#6b7280]">BEFORE COST</div>
                        <div className="text-lg mono font-semibold">{beforeCost ?? prevRunResult.results.dijkstra.cost ?? '—'}</div>
                        <div className="text-[10px] text-[#6b7280] truncate mono">Path: {(prevRunResult.results.dijkstra.path || []).join(' → ')}</div>
                      </div>
                      <div className="rounded border bg-[#f0f9ff] border-[#bae6fd] p-2.5">
                        <div className="text-[11px] font-semibold text-[#0284c7]">AFTER COST</div>
                        <div className="text-lg mono font-semibold">{afterCost ?? runResult.results.dijkstra.cost ?? '—'}</div>
                        <div className="text-[10px] text-[#6b7280] truncate mono">Path: {(runResult.results.dijkstra.path || []).join(' → ')}</div>
                      </div>
                    </div>
                    <div className={`rounded border p-2.5 text-xs ${routeChangedFlag ? 'bg-amber-50 border-amber-200 text-amber-800' : 'bg-emerald-50 border-emerald-200 text-emerald-800'}`}>
                      <div className="font-semibold flex items-center gap-1.5">{routeChangedFlag ? <Route size={12} /> : <CheckCircle2 size={12} />} {routeChangedFlag ? 'Route changed' : 'Route unchanged'}</div>
                      <div className="text-[11px] mt-1">Δ cost = {beforeCost !== null && afterCost !== null ? (afterCost - beforeCost).toFixed(4) : '—'} • {routeChangedFlag ? 'Optimal route recomputed due to higher travel times.' : 'Same optimal route remains best despite congestion on other roads.'}</div>
                    </div>
                    <div className="text-[11px] text-[#6b7280]">How congestion affected cost: {prevRunResult && runResult ? (prevRunResult.results.dijkstra.cost === runResult.results.dijkstra.cost ? 'Cost unchanged — alternative roads avoided congestion.' : `Cost ${runResult.results.dijkstra.cost! > prevRunResult.results.dijkstra.cost! ? 'increased' : 'decreased'} (Δ ${(runResult.results.dijkstra.cost! - prevRunResult.results.dijkstra.cost!).toFixed(2)})`) : '—'}</div>
                    <div className="text-[10px] mono text-[#6b7280] border-t pt-2">H3 evidence: route may change even when final shortest-path cost remains unchanged if equal-cost alternative exists.</div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {tab === 'experiments' && (
          <div className="space-y-5">
            <div className={`${dark ? 'bg-[#1a1d22] border-[#2a2e36]' : 'bg-white border-[#e7e5e0]'} border rounded-[10px] p-5`}>
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold flex items-center gap-2"><FlaskConical size={16} /> Reproducible Benchmark Runner</h2>
                <span className="text-[11px] mono bg-[#fdfbf7] border border-[#e7e5e0] px-2 py-1 rounded">Timer: perf_counter_ns • graph gen excluded</span>
              </div>
              <div className="mt-4 grid lg:grid-cols-5 gap-4">
                <div className="lg:col-span-3 grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div>
                    <label className="text-[11px] text-[#6b7280]">Grid n</label>
                    <input type="number" min={4} max={18} value={n} onChange={e => setN(parseInt(e.target.value) || 8)} className="w-full mt-1 h-8 rounded border px-2 text-xs mono bg-white border-[#e7e5e0]" />
                  </div>
                  <div>
                    <label className="text-[11px] text-[#6b7280]">Seed</label>
                    <input type="number" value={seed} onChange={e => setSeed(parseInt(e.target.value) || 0)} className="w-full mt-1 h-8 rounded border px-2 text-xs mono bg-white border-[#e7e5e0]" />
                  </div>
                  <div>
                    <label className="text-[11px] text-[#6b7280]">Trials</label>
                    <input type="number" min={1} max={50} value={trials} onChange={e => setTrials(parseInt(e.target.value) || 5)} className="w-full mt-1 h-8 rounded border px-2 text-xs mono bg-white border-[#e7e5e0]" />
                  </div>
                  <div>
                    <label className="text-[11px] text-[#6b7280]">Topology</label>
                    <select value={topology} onChange={e => setTopology(e.target.value as any)} className="w-full mt-1 h-8 rounded border px-2 text-xs bg-white border-[#e7e5e0]">
                      <option value="grid">grid</option>
                      <option value="grid_diagonal">grid_diagonal</option>
                      <option value="random_extra">random_extra</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-[11px] text-[#6b7280]">Traffic updates</label>
                    <input type="number" min={1} max={10} value={updates} onChange={e => setUpdates(Math.min(10, Math.max(1, parseInt(e.target.value) || 1)))} className="w-full mt-1 h-8 rounded border px-2 text-xs mono bg-white border-[#e7e5e0]" />
                  </div>
                  <div>
                    <label className="text-[11px] text-[#6b7280]">Congestion %</label>
                    <input type="number" value={congestionPct} onChange={e => setCongestionPct(parseInt(e.target.value) || 0)} className="w-full mt-1 h-8 rounded border px-2 text-xs mono bg-white border-[#e7e5e0]" />
                  </div>
                  <div>
                    <label className="text-[11px] text-[#6b7280]">Factor</label>
                    <input type="number" step={0.5} value={congestionFactor} onChange={e => setCongestionFactor(parseFloat(e.target.value) || 1.5)} className="w-full mt-1 h-8 rounded border px-2 text-xs mono bg-white border-[#e7e5e0]" />
                  </div>
                  <div>
                    <label className="text-[11px] text-[#6b7280]">Source</label>
                    <input value={source} onChange={e => setSource(e.target.value)} className="w-full mt-1 h-8 rounded border px-2 text-xs mono bg-white border-[#e7e5e0]" />
                  </div>
                  <div>
                    <label className="text-[11px] text-[#6b7280]">Target</label>
                    <input value={target} onChange={e => setTarget(e.target.value)} className="w-full mt-1 h-8 rounded border px-2 text-xs mono bg-white border-[#e7e5e0]" />
                  </div>
                </div>
                <div className="lg:col-span-2 space-y-2">
                  <button onClick={handleExperimentBoth} disabled={expLoading} className="w-full h-10 rounded bg-[#111827] text-white text-sm font-semibold hover:bg-black disabled:opacity-50 flex items-center justify-center gap-2">
                    {expLoading ? <><RefreshCw size={14} className="animate-spin" /> Running {trials} trials × 2 scenarios…</> : <><Play size={14} /> Run Reproducible Experiment</>}
                  </button>
                  <button onClick={handleScaleExperiment} disabled={scaleLoading} className="w-full h-8 rounded border bg-white border-[#e7e5e0] text-xs font-medium flex items-center justify-center gap-2">
                    {scaleLoading ? <RefreshCw size={12} className="animate-spin" /> : <BarChart3 size={12} />} Runtime vs Graph Size (n=4..14)
                  </button>
                  <div className="text-[11px] text-[#6b7280] leading-4">Progress: {expLoading ? 'Benchmarking algorithms on identical snapshots…' : 'Idle. Results include median, mean, stdev, min, max, correctness, route-change frequency.'}</div>
                  <div className="text-[10px] mono text-[#6b7280]">Prevent double-submit: button disabled while running.</div>
                </div>
              </div>

              {experimentResult && (
                <div className="mt-6">
                  <div className="grid lg:grid-cols-2 gap-4">
                    <div className="rounded border bg-[#f8f6f1] border-[#e7e5e0] p-3">
                      <div className="text-xs font-semibold">Normal traffic — summary (median over {trials} trials)</div>
                      <div className="mt-2 overflow-auto">
                        <table className="w-full text-[11px] mono">
                          <thead><tr className="text-[#6b7280] text-[10px]"><th className="text-left p-1">Algorithm</th><th className="text-right p-1">Cost</th><th className="text-right p-1">Median ms</th><th className="text-right p-1">Mean ms</th><th className="text-right p-1">Relax</th><th className="text-right p-1">Proc</th></tr></thead>
                          <tbody>
                            {['dijkstra', 'astar', 'bellman_ford'].map(k => {
                              const s = (experimentResult.normal as any)[k]
                              return <tr key={k} className="border-t"><td className="p-1">{k}</td><td className="text-right p-1">{s.path_cost ?? '∞'}</td><td className="text-right p-1">{s.median_runtime_ms.toFixed(3)}</td><td className="text-right p-1">{s.mean_runtime_ms.toFixed(3)}</td><td className="text-right p-1">{s.relaxations_median}</td><td className="text-right p-1">{s.processed_median}</td></tr>
                            })}
                          </tbody>
                        </table>
                      </div>
                    </div>
                    {experimentResult.congested && (
                      <div className="rounded border bg-[#fffbeb] border-[#fde68a] p-3">
                        <div className="text-xs font-semibold">After congestion — summary</div>
                        <div className="mt-2 overflow-auto">
                          <table className="w-full text-[11px] mono">
                            <thead><tr className="text-[#6b7280] text-[10px]"><th className="text-left p-1">Algorithm</th><th className="text-right p-1">Cost</th><th className="text-right p-1">Median ms</th><th className="text-right p-1">Mean ms</th><th className="text-right p-1">Relax</th><th className="text-right p-1">Proc</th></tr></thead>
                            <tbody>
                              {['dijkstra', 'astar', 'bellman_ford'].map(k => {
                                const s = (experimentResult.congested as any)[k]
                                return <tr key={k} className="border-t"><td className="p-1">{k}</td><td className="text-right p-1">{s.path_cost ?? '∞'}</td><td className="text-right p-1">{s.median_runtime_ms.toFixed(3)}</td><td className="text-right p-1">{s.mean_runtime_ms.toFixed(3)}</td><td className="text-right p-1">{s.relaxations_median}</td><td className="text-right p-1">{s.processed_median}</td></tr>
                              })}
                            </tbody>
                          </table>
                        </div>
                        <div className="text-[11px] mt-2">Route changed (update 1): <b>{experimentResult.comparison.route_changed ? 'Yes' : 'No'}</b> • Δ cost: {experimentResult.comparison.cost_delta ?? '—'}</div>
                        <div className="text-[11px] mt-1">Route-change frequency: <b>{experimentResult.route_change_frequency != null ? `${(experimentResult.route_change_frequency * 100).toFixed(0)}%` : '—'}</b> over {experimentResult.updates?.length ?? 0} update(s) • Recompute cost (sum of median runtimes, all updates): <b>{experimentResult.recompute_total_ms?.toFixed(2) ?? '—'} ms</b></div>
                      </div>
                    )}
                  </div>

                  <div className="mt-4 grid lg:grid-cols-3 gap-3">
                    <div className="rounded border bg-white border-[#e7e5e0] p-3">
                      <div className="text-[11px] font-semibold text-[#6b7280]">RUNTIME VARIABILITY (normal)</div>
                      <div className="text-[11px] mono mt-1 space-y-1">
                        {['dijkstra', 'astar', 'bellman_ford'].map(k => {
                          const s = (experimentResult.normal as any)[k]
                          return <div key={k} className="flex justify-between"><span>{k}</span><span>median {s.median_runtime_ms.toFixed(2)} • mean {s.mean_runtime_ms.toFixed(2)} • stdev {s.stdev_runtime_ms.toFixed(2)} • [{s.min_runtime_ms.toFixed(2)}–{s.max_runtime_ms.toFixed(2)}]</span></div>
                        })}
                      </div>
                    </div>
                    <div className="rounded border bg-white border-[#e7e5e0] p-3">
                      <div className="text-[11px] font-semibold text-[#6b7280]">CORRECTNESS</div>
                      <div className="text-[11px] mono mt-1 space-y-1">
                        {['dijkstra', 'astar', 'bellman_ford'].map(k => {
                          const s = (experimentResult.normal as any)[k]
                          return <div key={k} className="flex justify-between"><span>{k}</span><span className={s.correctness_pass_rate === 1 ? 'text-emerald-600' : 'text-red-600'}>{(s.correctness_pass_rate * 100).toFixed(0)}% pass • {s.success ? 'success' : 'fail'}</span></div>
                        })}
                      </div>
                    </div>
                    <div className="rounded border bg-white border-[#e7e5e0] p-3">
                      <div className="text-[11px] font-semibold text-[#6b7280]">ENVIRONMENT</div>
                      <div className="text-[11px] mono mt-1 leading-4">
                        <div>Python: {experimentResult.env.python_version}</div>
                        <div>Timer: {experimentResult.env.timer}</div>
                        <div>Boundary: {experimentResult.env.timing_boundary}</div>
                        <div>Wall clock (incl. generation, not timed): {experimentResult.wall_clock_ms?.toFixed(2)} ms • Recompute total: {experimentResult.recompute_total_ms?.toFixed(2)} ms</div>
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 flex gap-2">
                    <button onClick={exportExperimentCSV} className="h-8 px-3 rounded border bg-white border-[#e7e5e0] text-xs flex items-center gap-1"><Download size={12} /> Export CSV (trials)</button>
                    <button onClick={exportJSON} className="h-8 px-3 rounded border bg-white border-[#e7e5e0] text-xs flex items-center gap-1"><Download size={12} /> Export JSON (full config)</button>
                  </div>
                </div>
              )}
            </div>

            {scaleResults.length > 0 && (
              <div className={`${dark ? 'bg-[#1a1d22] border-[#2a2e36]' : 'bg-white border-[#e7e5e0]'} border rounded-[10px] p-4`}>
                <h3 className="text-xs font-semibold">Runtime vs Graph Size (auto-sweep n=4..14, seed {seed}, trials 7)</h3>
                <div className="h-[260px] mt-3">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={scaleResults}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e7e5e0" />
                      <XAxis dataKey="nodes" tick={{ fontSize: 11 }} label={{ value: 'Nodes (n×n)', position: 'insideBottom', offset: -5, fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} label={{ value: 'Median ms (log scale?)', angle: -90, position: 'insideLeft', fontSize: 10 }} />
                      <Tooltip />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <Line type="monotone" dataKey="dijkstra_ms" stroke="#1d4ed8" name="Dijkstra" dot />
                      <Line type="monotone" dataKey="astar_ms" stroke="#7c3aed" name="A*" dot />
                      <Line type="monotone" dataKey="bellman_ms" stroke="#d97706" name="Bellman–Ford" dot />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                <div className="mt-2 text-[11px] text-[#6b7280]">Demonstrates H2: performance scaling depends on size; Bellman–Ford relaxations grow as O(VE).</div>
              </div>
            )}
          </div>
        )}

        {tab === 'visuals' && (
          <div className="space-y-5">
            {!runResult && !experimentResult ? (
              <div className="rounded border border-dashed p-10 text-center bg-white border-[#e7e5e0]">
                <BarChart3 size={20} className="mx-auto text-[#9ca3af]" />
                <div className="text-sm font-medium mt-2">No data yet</div>
                <div className="text-xs text-[#6b7280] mt-1">Run algorithms or experiments to generate scientific visualizations.</div>
              </div>
            ) : (
              <>
                <div className="grid lg:grid-cols-2 gap-5">
                  <div className={`${dark ? 'bg-[#1a1d22] border-[#2a2e36]' : 'bg-white border-[#e7e5e0]'} border rounded-[10px] p-4`}>
                    <h3 className="text-xs font-semibold">Median runtime by algorithm</h3>
                    <div className="h-[240px] mt-3">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={runResult ? chartDataMedian : (expChartData as any).normal}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#e7e5e0" />
                          <XAxis dataKey="algo" tick={{ fontSize: 11 }} />
                          <YAxis tick={{ fontSize: 11 }} label={{ value: 'ms', angle: -90, position: 'insideLeft', fontSize: 11 }} />
                          <Tooltip />
                          <Bar dataKey="runtime" fill="#1d4ed8" name="Runtime (ms)" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="text-[11px] text-[#6b7280] mt-1">Units: milliseconds • High-res monotonic timer • One snapshot; for claims use multi-trial experiment runner (median+mean+stdev).</div>
                  </div>

                  <div className={`${dark ? 'bg-[#1a1d22] border-[#2a2e36]' : 'bg-white border-[#e7e5e0]'} border rounded-[10px] p-4`}>
                    <h3 className="text-xs font-semibold">Edge relaxations by algorithm</h3>
                    <div className="h-[240px] mt-3">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={runResult ? chartDataMedian : (expChartData as any).normal}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#e7e5e0" />
                          <XAxis dataKey="algo" tick={{ fontSize: 11 }} />
                          <YAxis tick={{ fontSize: 11 }} />
                          <Tooltip />
                          <Bar dataKey="relax" fill="#d97706" name="Relaxations" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="text-[11px] text-[#6b7280] mt-1">Comparable work metric across algorithms (BF passes × edges).</div>
                  </div>

                  <div className={`${dark ? 'bg-[#1a1d22] border-[#2a2e36]' : 'bg-white border-[#e7e5e0]'} border rounded-[10px] p-4`}>
                    <h3 className="text-xs font-semibold">Expanded vertices by algorithm</h3>
                    <div className="h-[240px] mt-3">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={runResult ? chartDataMedian : []}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#e7e5e0" />
                          <XAxis dataKey="algo" tick={{ fontSize: 11 }} />
                          <YAxis tick={{ fontSize: 11 }} label={{ value: 'count', angle: -90, position: 'insideLeft', fontSize: 11 }} />
                          <Tooltip />
                          <Bar dataKey="expanded" fill="#7c3aed" name="Vertices / Passes" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="text-[11px] text-[#6b7280] mt-1">Distinct semantics: settled (Dijkstra), expanded (A*), passes (BF). Not directly comparable — use relaxations.</div>
                  </div>

                  <div className={`${dark ? 'bg-[#1a1d22] border-[#2a2e36]' : 'bg-white border-[#e7e5e0]'} border rounded-[10px] p-4`}>
                    <h3 className="text-xs font-semibold">Path cost before vs after traffic</h3>
                    {(beforeCost !== null || experimentResult) ? (
                      <div className="h-[240px] mt-3">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={[
                            { name: 'Before', cost: beforeCost ?? experimentResult?.comparison.normal_cost ?? 0 },
                            { name: 'After', cost: afterCost ?? experimentResult?.comparison.congested_cost ?? 0 },
                          ]}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#e7e5e0" />
                            <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                            <YAxis tick={{ fontSize: 11 }} label={{ value: 'travel-time', angle: -90, position: 'insideLeft', fontSize: 11 }} />
                            <Tooltip />
                            <Bar dataKey="cost" fill="#16a34a" radius={[4, 4, 0, 0]} name="Path cost" />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    ) : <div className="h-[240px] grid place-items-center text-xs text-[#6b7280]">Apply congestion to compare costs</div>}
                    <div className="text-[11px] text-[#6b7280] mt-1">Supports H3: route may change while cost stays same (equal-cost alternative).</div>
                  </div>
                </div>

                {experimentResult && (
                  <div className={`${dark ? 'bg-[#1a1d22] border-[#2a2e36]' : 'bg-white border-[#e7e5e0]'} border rounded-[10px] p-4`}>
                    <h3 className="text-xs font-semibold">Performance variability across trials (normal traffic)</h3>
                    <div className="h-[260px] mt-3">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={[
                          { algo: 'Dijkstra', median: experimentResult.normal['dijkstra'].median_runtime_ms, mean: experimentResult.normal['dijkstra'].mean_runtime_ms, min: experimentResult.normal['dijkstra'].min_runtime_ms, max: experimentResult.normal['dijkstra'].max_runtime_ms },
                          { algo: 'A*', median: experimentResult.normal['astar'].median_runtime_ms, mean: experimentResult.normal['astar'].mean_runtime_ms, min: experimentResult.normal['astar'].min_runtime_ms, max: experimentResult.normal['astar'].max_runtime_ms },
                          { algo: 'Bellman–Ford', median: experimentResult.normal['bellman_ford'].median_runtime_ms, mean: experimentResult.normal['bellman_ford'].mean_runtime_ms, min: experimentResult.normal['bellman_ford'].min_runtime_ms, max: experimentResult.normal['bellman_ford'].max_runtime_ms },
                        ]}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#e7e5e0" />
                          <XAxis dataKey="algo" tick={{ fontSize: 11 }} />
                          <YAxis tick={{ fontSize: 11 }} />
                          <Tooltip />
                          <Legend wrapperStyle={{ fontSize: 11 }} />
                          <Bar dataKey="median" fill="#1d4ed8" name="Median" />
                          <Bar dataKey="mean" fill="#60a5fa" name="Mean" />
                          <Bar dataKey="min" fill="#e5e7eb" name="Min" />
                          <Bar dataKey="max" fill="#f59e0b" name="Max" />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                )}

                {scaleResults.length > 0 && (
                  <div className={`${dark ? 'bg-[#1a1d22] border-[#2a2e36]' : 'bg-white border-[#e7e5e0]'} border rounded-[10px] p-4`}>
                    <h3 className="text-xs font-semibold">Runtime vs graph size</h3>
                    <div className="h-[260px] mt-3">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={scaleResults}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#e7e5e0" />
                          <XAxis dataKey="n" tick={{ fontSize: 11 }} label={{ value: 'Grid n (n×n)', position: 'insideBottom', offset: -5, fontSize: 11 }} />
                          <YAxis tick={{ fontSize: 11 }} />
                          <Tooltip />
                          <Legend wrapperStyle={{ fontSize: 11 }} />
                          <Line type="monotone" dataKey="dijkstra_ms" stroke="#1d4ed8" name="Dijkstra ms" dot />
                          <Line type="monotone" dataKey="astar_ms" stroke="#7c3aed" name="A* ms" dot />
                          <Line type="monotone" dataKey="bellman_ms" stroke="#d97706" name="BF ms" dot />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="text-[11px] text-[#6b7280] mt-1">Each point median of 7 trials. BF O(VE) scaling visible. Supports H2.</div>
                  </div>
                )}

                {experimentResult && (
                  <div className={`${dark ? 'bg-[#1a1d22] border-[#2a2e36]' : 'bg-white border-[#e7e5e0]'} border rounded-[10px] p-4`}>
                    <h3 className="text-xs font-semibold">Trials scatter: runtime vs relaxations</h3>
                    <div className="h-[260px] mt-3">
                      <ResponsiveContainer width="100%" height="100%">
                        <ScatterChart>
                          <CartesianGrid stroke="#e7e5e0" />
                          <XAxis type="number" dataKey="relaxations" name="Relaxations" tick={{ fontSize: 11 }} />
                          <YAxis type="number" dataKey="runtime_ms" name="Runtime ms" tick={{ fontSize: 11 }} />
                          <Tooltip cursor={{ strokeDasharray: '3 3' }} />
                          <Legend />
                          <Scatter name="Dijkstra trials" data={experimentResult.normal['dijkstra'].trials_raw} fill="#1d4ed8" />
                          <Scatter name="A* trials" data={experimentResult.normal['astar'].trials_raw} fill="#7c3aed" />
                          <Scatter name="BF trials" data={experimentResult.normal['bellman_ford'].trials_raw} fill="#d97706" />
                        </ScatterChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {tab === 'evidence' && (
          <div className="grid grid-cols-12 gap-5">
            <div className="col-span-12 lg:col-span-8 space-y-5">
              <div className={`${dark ? 'bg-[#1a1d22] border-[#2a2e36]' : 'bg-white border-[#e7e5e0]'} border rounded-[10px] p-5`}>
                <h2 className="text-sm font-semibold flex items-center gap-2"><Download size={16} /> Research Evidence & Export</h2>
                <div className="mt-4 grid md:grid-cols-3 gap-3">
                  <button onClick={exportCSV} disabled={!runResult} className="h-10 rounded bg-[#111827] text-white text-xs font-semibold disabled:opacity-50 flex items-center justify-center gap-2"><Download size={14} /> CSV — Latest Results</button>
                  <button onClick={exportExperimentCSV} disabled={!experimentResult} className="h-10 rounded bg-[#1d4ed8] text-white text-xs font-semibold disabled:opacity-50 flex items-center justify-center gap-2"><Download size={14} /> CSV — Experiment Trials</button>
                  <button onClick={exportJSON} className="h-10 rounded border bg-white border-[#e7e5e0] text-xs font-semibold flex items-center justify-center gap-2"><Download size={14} /> JSON — Config + Metadata</button>
                </div>
                <div className={`mt-4 rounded border p-3 text-xs leading-4 ${dark ? 'bg-[#111317] border-[#2a2e36] text-[#9ca3af]' : 'bg-[#f8f6f1] border-[#e7e5e0] text-[#374151]'}`}>
                  <div className="font-semibold">What’s included for reproducibility</div>
                  <ul className="list-disc ml-4 mt-1 space-y-1">
                    <li>Experiment timestamp: {experimentResult ? new Date(experimentResult.timestamp * 1000).toISOString() : new Date().toISOString()}</li>
                    <li>Random seed: {seed} • Grid: {n}×{n} • Topology: {topology} • Source: {source} • Target: {target} • Trials: {trials}</li>
                    <li>Traffic: {congestionPct}% roads ×{congestionFactor} multiplier • Affected edges: {lastChanges.length || experimentResult?.affected_edge_ids.length || 0}</li>
                    <li>Timing: perf_counter_ns, algorithm execution only (generation/serialization excluded) • Python {health?.python?.slice(0, 60) || '—'} • {health?.platform || experimentResult?.env.platform || ''}</li>
                    <li>Synthetic non-negative weights 2–12 • A* heuristic: c* × Manhattan, c* = min(w / road length) over open roads (admissible, consistent) • Bellman–Ford supports negative weights (not physically meaningful travel times)</li>
                  </ul>
                </div>
                {runResult && (
                  <div className="mt-4 overflow-auto border rounded">
                    <table className="w-full text-[11px] mono">
                      <thead className="bg-[#f8f6f1]"><tr><th className="text-left p-2 border-b">Algorithm</th><th className="text-right p-2 border-b">Cost</th><th className="text-right p-2 border-b">Runtime ms</th><th className="text-right p-2 border-b">Processed</th><th className="text-right p-2 border-b">Relax</th><th className="text-center p-2 border-b">Correctness</th></tr></thead>
                      <tbody>
                        {[
                          { name: 'Dijkstra', r: runResult.results.dijkstra, proc: (runResult.results.dijkstra as any).settled },
                          { name: 'A*', r: runResult.results.astar, proc: (runResult.results.astar as any).expanded },
                          { name: 'Bellman–Ford', r: runResult.results.bellman_ford, proc: (runResult.results.bellman_ford as any).passes },
                        ].map(row => (
                          <tr key={row.name} className="border-b last:border-0"><td className="p-2">{row.name}</td><td className="text-right p-2">{row.r.cost ?? '∞'}</td><td className="text-right p-2">{row.r.runtime_ms.toFixed(3)}</td><td className="text-right p-2">{row.proc}</td><td className="text-right p-2">{row.r.relaxations}</td><td className="text-center p-2"><span className={`px-1.5 py-0.5 rounded text-[10px] border ${row.r.correctness.status === 'pass' ? 'bg-emerald-50 border-emerald-200 text-emerald-700' : 'bg-red-50 border-red-200 text-red-700'}`}>{row.r.correctness.status}</span></td></tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              <div id="method" className={`${dark ? 'bg-[#1a1d22] border-[#2a2e36]' : 'bg-white border-[#e7e5e0]'} border rounded-[10px] p-5`}>
                <h3 className="text-sm font-semibold flex items-center gap-2"><Info size={16} /> Methodology — Assumptions, Metrics, Limitations, Reproducibility</h3>
                <div className="mt-3 space-y-4 text-xs leading-5 text-[#374151] dark:text-[#9ca3af]">
                  <div>
                    <div className="font-semibold text-[#111827] dark:text-white">Graph generation</div>
                    <p className="mt-1">Synthetic grid graph: n×n nodes, 4-neighbor edges (grid), optional diagonal or random extra edges. Deterministic integer weights 2–12 via seeded Random. Positions are grid coordinates (r,c) and (x=c, y=-r) for visualization; not geographic. Topology parameter controls heuristic strength. All weights non-negative representing travel-time units. Synthetic nature clearly labeled; not claimed as real streets.</p>
                  </div>
                  <div>
                    <div className="font-semibold text-[#111827] dark:text-white">Algorithms</div>
                    <ul className="list-disc ml-5 mt-1">
                      <li><b>Dijkstra:</b> binary heap priority queue, settled set, early exit on target, relaxations counted per edge examined.</li>
                      <li><b>A*:</b> same heap plus f = g + h, h = c* × Manhattan(v, target), where c* = min over open roads of w(e)/L(e) and L(e) is the Manhattan length of road e. Every path's cost is at least c* × Manhattan distance, so h is admissible and consistent. c* is recomputed from current weights, so it stays valid after congestion and closures. c* is computed inside A*'s timed region.</li>
                      <li><b>Bellman–Ford:</b> |V|-1 passes over directed edge list (undirected edges expanded both ways), early exit if no change, negative-cycle detection via one additional scan. Relaxations = passes × edges + detection checks. Processed count reported as passes, not vertices — distinguished from Dijkstra/A* expanded counts.</li>
                      <li><b>Reference:</b> independent Dijkstra reference for correctness: cost match within 1e-6 and reconstructed path edge-validity.</li>
                    </ul>
                  </div>
                  <div>
                    <div className="font-semibold text-[#111827] dark:text-white">Traffic update logic</div>
                    <p className="mt-1">Congestion: sample p% edges via seeded RNG, multiply their original_weight by factor (new_weight = original × factor). Original weight preserved for reset. Road closure: edge marked closed=true, excluded from adjacency for all algorithms consistently. Individual edge-weight editing supported. Reset restores original weights and opens closures. Before-vs-after route comparison shows which roads changed, weight deltas, route changed boolean, and cost delta.</p>
                  </div>
                  <div>
                    <div className="font-semibold text-[#111827] dark:text-white">Benchmarking & statistics</div>
                    <p className="mt-1">Per-algorithm runtime measured with high-resolution monotonic perf_counter_ns, excluding graph generation and UI rendering. Configurable trials; median, mean, stdev, min, max reported. Runtime variability chart and trials scatter included. Route-change frequency across scenarios reported. Environment disclosure: Python version, platform, timer, and boundary stated in export.</p>
                  </div>
                  <div>
                    <div className="font-semibold text-[#111827] dark:text-white">Limitations</div>
                    <ul className="list-disc ml-5 mt-1">
                      <li>Small graphs → noisy runtimes; use larger n (12–18) and ≥10 trials and multiple seeds before general claims.</li>
                      <li>On diagonal and random_extra topologies c* is set by the cheapest cost per unit of Manhattan distance, which is typically a weaker bound than on a plain grid, so A* may expand more vertices there (topology dependence, H2).</li>
                      <li>Negative weights supported only for Bellman–Ford demonstration; not meaningful as travel times; negative cycles flagged.</li>
                      <li>Real road networks (OSM, traffic APIs) not integrated; all data synthetic and labeled as such.</li>
                      <li>Browser rendering not included in timing; backend timing excludes serialization.</li>
                    </ul>
                  </div>
                  <div>
                    <div className="font-semibold text-[#111827] dark:text-white">Reproducibility</div>
                    <p className="mt-1">Every result export includes full config (n, seed, topology, source, target, congestion %, factor, trials), timestamp, software version, and affected edge IDs. Deterministic generation: same seed + topology + n yields identical graph. Traffic sampling seeded as seed+9999 for experiment reproducibility. A sample configuration is provided in examples/sample_experiment.json; the full methodology is in docs/METHODOLOGY.md.</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="col-span-12 lg:col-span-4 space-y-4">
              <div className={`${dark ? 'bg-[#1a1d22] border-[#2a2e36]' : 'bg-white border-[#e7e5e0]'} border rounded-[10px] p-4`}>
                <h3 className="text-xs font-semibold">Sample Experiment Configuration</h3>
                <pre className={`mt-3 p-3 rounded border text-[11px] mono leading-4 overflow-auto ${dark ? 'bg-[#111317] border-[#2a2e36] text-[#9ca3af]' : 'bg-[#fdfbf7] border-[#e7e5e0] text-[#111827]'}`}>{JSON.stringify({ n: 8, seed: 42, topology: 'grid', trials: 10, congestion_pct: 20, congestion_factor: 3.0, source: '0_0', target: '7_7', updates: 1 }, null, 2)}</pre>
                <div className="text-[11px] text-[#6b7280] mt-2">Clearly identified as sample data — load via Experiment Runner.</div>
              </div>
              <div className={`${dark ? 'bg-[#1a1d22] border-[#2a2e36]' : 'bg-white border-[#e7e5e0]'} border rounded-[10px] p-4`}>
                <h3 className="text-xs font-semibold">Software & Environment</h3>
                <div className="mt-2 text-[11px] mono leading-4">
                  <div>Frontend: React + TypeScript + Vite + Tailwind + Cytoscape.js + Recharts</div>
                  <div>Backend: Python + FastAPI + NetworkX (generation) + custom algorithms</div>
                  <div>API: {health ? `${health.python.slice(0, 80)}...` : 'loading…'}</div>
                  <div>Platform: {health?.platform || '—'}</div>
                  <div>Deploy: development = Vite :5173 + API :8000; production = FastAPI serves the built app on one port</div>
                </div>
              </div>
              <div className="rounded border bg-[#eff6ff] border-[#dbeafe] p-4">
                <div className="text-xs font-semibold text-[#1d4ed8] flex items-center gap-1.5"><CheckCircle2 size={12} /> Honest reporting</div>
                <div className="text-[11px] text-[#3730a3] mt-1 leading-4">No live traffic integration claimed. No fabricated rankings or statistical significance. Empty states shown before runs. All charts generated from actual executions. Tests validate correctness, unreachable, equal-cost, closure, source=target, and heuristic admissibility.</div>
              </div>
            </div>
          </div>
        )}
      </main>

      <footer className={`border-t mt-6 ${dark ? 'border-[#1f232b] bg-[#0f1115] text-[#9ca3af]' : 'border-[#e7e5e0] bg-[#f8f6f1] text-[#6b7280]'}`}>
        <div className="max-w-[1440px] mx-auto px-5 h-10 flex items-center justify-between text-[11px] mono">
          <span>© 2026 DynamicRouteLab — Synthetic data • Non-negative travel-time model • Reproducible science • No live traffic claimed</span>
          <span className="hidden md:inline">Methodology • Tests • Reproducibility • Accessibility • Honest metrics</span>
        </div>
      </footer>
    </div>
  )
}
