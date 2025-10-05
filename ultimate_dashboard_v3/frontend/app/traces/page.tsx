'use client'

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Activity, Search, Download, AlertCircle, Filter, GitBranch } from 'lucide-react'
import { apiClient } from '@/lib/api'
import { useDashboardStore } from '@/lib/store'
import toast from 'react-hot-toast'
import WaterfallChart from '@/components/charts/WaterfallChart'
import TimelineChart from '@/components/charts/TimelineChart'

export default function TracesPage() {
  const { currentBenchmarkId, benchmarks } = useDashboardStore()
  const [selectedBenchmark, setSelectedBenchmark] = useState(currentBenchmarkId || '')
  const [traces, setTraces] = useState<any[]>([])
  const [errorTraces, setErrorTraces] = useState<any[]>([])
  const [selectedTrace, setSelectedTrace] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [view, setView] = useState<'list' | 'timeline' | 'waterfall' | 'errors'>('list')

  // Filters
  const [searchTerm, setSearchTerm] = useState('')
  const [minLatency, setMinLatency] = useState<number | undefined>()
  const [maxLatency, setMaxLatency] = useState<number | undefined>()
  const [showErrorsOnly, setShowErrorsOnly] = useState(false)
  const [offset, setOffset] = useState(0)
  const [total, setTotal] = useState(0)
  const limit = 50

  useEffect(() => {
    if (selectedBenchmark) {
      loadTraces()
      if (view === 'errors') {
        loadErrorTraces()
      }
    }
  }, [selectedBenchmark, searchTerm, minLatency, maxLatency, showErrorsOnly, offset, view])

  const loadTraces = async () => {
    if (!selectedBenchmark) return

    setLoading(true)
    try {
      const response = await apiClient.client.get(`/api/v3/benchmarks/${selectedBenchmark}/traces`, {
        params: {
          limit,
          offset,
          search: searchTerm || undefined,
          min_latency: minLatency,
          max_latency: maxLatency,
          has_error: showErrorsOnly || undefined,
        }
      })
      setTraces(response.data.traces.items)
      setTotal(response.data.traces.total)
    } catch (error) {
      console.error('Failed to load traces:', error)
      toast.error('Failed to load traces')
    } finally {
      setLoading(false)
    }
  }

  const loadErrorTraces = async () => {
    if (!selectedBenchmark) return

    try {
      const response = await apiClient.client.get(`/api/v3/benchmarks/${selectedBenchmark}/traces/errors`)
      setErrorTraces(response.data.errors)
    } catch (error) {
      console.error('Failed to load error traces:', error)
      toast.error('Failed to load error traces')
    }
  }

  const loadTraceDetail = async (requestId: string) => {
    try {
      const response = await apiClient.client.get(`/api/v3/benchmarks/${selectedBenchmark}/traces/${requestId}`)
      setSelectedTrace(response.data)
    } catch (error) {
      console.error('Failed to load trace detail:', error)
      toast.error('Failed to load trace details')
    }
  }

  const exportTraces = async (format: string) => {
    try {
      const response = await apiClient.client.get(`/api/v3/benchmarks/${selectedBenchmark}/traces/export`, {
        params: { format }
      })

      const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `traces_${selectedBenchmark}.${format}`
      a.click()
      toast.success(`Exported ${total} traces`)
    } catch (error) {
      console.error('Failed to export traces:', error)
      toast.error('Failed to export traces')
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-black via-nvidia-darkGray to-black p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <motion.div
          initial={{ y: -20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          className="mb-8"
        >
          <div className="flex items-center gap-4 mb-4">
            <GitBranch className="w-10 h-10 text-nvidia-green" />
            <div>
              <h1 className="text-4xl font-black bg-gradient-to-r from-nvidia-green to-green-400 bg-clip-text text-transparent">
                Request Tracing
              </h1>
              <p className="text-gray-400">Deep dive into individual request traces</p>
            </div>
          </div>

          {/* Benchmark Selector */}
          <select
            value={selectedBenchmark}
            onChange={(e) => setSelectedBenchmark(e.target.value)}
            className="w-full max-w-md px-4 py-3 bg-black/50 border border-white/10 rounded-lg text-white focus:border-nvidia-green focus:outline-none"
          >
            <option value="">Select a benchmark...</option>
            {benchmarks.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        </motion.div>

        {selectedBenchmark && (
          <>
            {/* View Tabs */}
            <div className="flex gap-2 mb-6">
              {['list', 'timeline', 'waterfall', 'errors'].map((v) => (
                <button
                  key={v}
                  onClick={() => setView(v as any)}
                  className={`px-4 py-2 rounded-lg font-semibold transition-colors ${
                    view === v
                      ? 'bg-nvidia-green text-black'
                      : 'bg-white/5 text-gray-400 hover:text-white'
                  }`}
                >
                  {v.charAt(0).toUpperCase() + v.slice(1)}
                </button>
              ))}
            </div>

            {/* Filters */}
            <motion.div
              initial={{ y: -10, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              className="bg-white/5 border border-white/10 rounded-xl p-4 mb-6"
            >
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div>
                  <label className="block text-sm font-semibold text-gray-400 mb-2">
                    <Search className="w-4 h-4 inline mr-1" />
                    Search Request ID
                  </label>
                  <input
                    type="text"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    placeholder="req_12345..."
                    className="w-full px-3 py-2 bg-black/50 border border-white/10 rounded-lg text-white text-sm focus:border-nvidia-green focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-sm font-semibold text-gray-400 mb-2">
                    Min Latency (ms)
                  </label>
                  <input
                    type="number"
                    value={minLatency || ''}
                    onChange={(e) => setMinLatency(e.target.value ? parseFloat(e.target.value) : undefined)}
                    placeholder="0"
                    className="w-full px-3 py-2 bg-black/50 border border-white/10 rounded-lg text-white text-sm focus:border-nvidia-green focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-sm font-semibold text-gray-400 mb-2">
                    Max Latency (ms)
                  </label>
                  <input
                    type="number"
                    value={maxLatency || ''}
                    onChange={(e) => setMaxLatency(e.target.value ? parseFloat(e.target.value) : undefined)}
                    placeholder="10000"
                    className="w-full px-3 py-2 bg-black/50 border border-white/10 rounded-lg text-white text-sm focus:border-nvidia-green focus:outline-none"
                  />
                </div>

                <div className="flex items-end gap-2">
                  <label className="flex items-center gap-2 cursor-pointer px-3 py-2 bg-black/30 border border-white/10 rounded-lg">
                    <input
                      type="checkbox"
                      checked={showErrorsOnly}
                      onChange={(e) => setShowErrorsOnly(e.target.checked)}
                      className="w-4 h-4"
                    />
                    <AlertCircle className="w-4 h-4 text-red-400" />
                    <span className="text-sm text-gray-300">Errors Only</span>
                  </label>
                  <button
                    onClick={() => exportTraces('json')}
                    className="px-3 py-2 bg-nvidia-green/20 border border-nvidia-green rounded-lg text-nvidia-green hover:bg-nvidia-green/30"
                  >
                    <Download className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <div className="mt-3 text-sm text-gray-400">
                Showing {traces.length} of {total} traces
              </div>
            </motion.div>

            {/* Content based on view */}
            {view === 'list' && (
              <div className="bg-white/5 border border-white/10 rounded-xl overflow-hidden">
                <table className="w-full">
                  <thead className="bg-black/50">
                    <tr>
                      <th className="px-4 py-3 text-left text-sm font-semibold text-gray-400">Request ID</th>
                      <th className="px-4 py-3 text-left text-sm font-semibold text-gray-400">Worker</th>
                      <th className="px-4 py-3 text-right text-sm font-semibold text-gray-400">Latency (ms)</th>
                      <th className="px-4 py-3 text-right text-sm font-semibold text-gray-400">TTFT (ms)</th>
                      <th className="px-4 py-3 text-right text-sm font-semibold text-gray-400">Tokens In/Out</th>
                      <th className="px-4 py-3 text-center text-sm font-semibold text-gray-400">Status</th>
                      <th className="px-4 py-3 text-center text-sm font-semibold text-gray-400">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {traces.map((trace, idx) => {
                      const metadata = trace.metadata || {}
                      const metrics = trace.metrics || {}
                      const hasError = metadata.error !== undefined

                      return (
                        <tr
                          key={metadata.x_request_id || idx}
                          className="border-t border-white/10 hover:bg-white/5 transition-colors"
                        >
                          <td className="px-4 py-3 text-sm font-mono text-white">
                            {metadata.x_request_id || 'N/A'}
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-300">
                            {metadata.worker_id || 'N/A'}
                          </td>
                          <td className="px-4 py-3 text-sm text-right text-white">
                            {metrics.request_latency?.value?.toFixed(2) || '0'}
                          </td>
                          <td className="px-4 py-3 text-sm text-right text-white">
                            {metrics.ttft?.value?.toFixed(2) || 'N/A'}
                          </td>
                          <td className="px-4 py-3 text-sm text-right text-white">
                            {metrics.input_sequence_length?.value || 0} / {metrics.output_sequence_length?.value || 0}
                          </td>
                          <td className="px-4 py-3 text-center">
                            {hasError ? (
                              <span className="inline-flex items-center gap-1 px-2 py-1 bg-red-500/20 text-red-400 rounded text-xs font-bold">
                                <AlertCircle className="w-3 h-3" />
                                ERROR
                              </span>
                            ) : (
                              <span className="inline-flex px-2 py-1 bg-green-500/20 text-green-400 rounded text-xs font-bold">
                                SUCCESS
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-center">
                            <button
                              onClick={() => loadTraceDetail(metadata.x_request_id)}
                              className="px-3 py-1 bg-nvidia-green/20 text-nvidia-green rounded text-xs font-bold hover:bg-nvidia-green/30"
                            >
                              Details
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>

                {/* Pagination */}
                <div className="flex items-center justify-between px-4 py-3 bg-black/30 border-t border-white/10">
                  <button
                    onClick={() => setOffset(Math.max(0, offset - limit))}
                    disabled={offset === 0}
                    className="px-4 py-2 bg-white/5 border border-white/10 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Previous
                  </button>
                  <span className="text-gray-400">
                    Page {Math.floor(offset / limit) + 1} of {Math.ceil(total / limit)}
                  </span>
                  <button
                    onClick={() => setOffset(offset + limit)}
                    disabled={offset + limit >= total}
                    className="px-4 py-2 bg-white/5 border border-white/10 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}

            {view === 'errors' && (
              <div className="bg-white/5 border border-white/10 rounded-xl p-6">
                <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-2">
                  <AlertCircle className="w-6 h-6 text-red-400" />
                  Error Traces ({errorTraces.length})
                </h2>

                {errorTraces.length === 0 ? (
                  <div className="text-center py-12 text-gray-400">
                    No errors found in this benchmark
                  </div>
                ) : (
                  <div className="space-y-4">
                    {errorTraces.map((trace, idx) => (
                      <div key={idx} className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
                        <div className="flex items-start justify-between mb-3">
                          <div>
                            <div className="font-mono text-white text-sm">{trace.request_id}</div>
                            <div className="text-gray-400 text-xs">Worker: {trace.worker_id}</div>
                          </div>
                          <button
                            onClick={() => setSelectedTrace(trace)}
                            className="px-3 py-1 bg-white/10 text-white rounded text-xs font-bold hover:bg-white/20"
                          >
                            View Details
                          </button>
                        </div>

                        {/* Error message */}
                        <div className="bg-black/40 rounded p-3 mb-3">
                          <div className="text-red-400 text-sm font-semibold mb-1">Error:</div>
                          <pre className="text-red-300 text-xs overflow-auto max-h-32">
                            {typeof trace.error === 'string' ? trace.error : JSON.stringify(trace.error, null, 2)}
                          </pre>
                        </div>

                        {/* Metrics summary */}
                        <div className="grid grid-cols-4 gap-3">
                          <div>
                            <div className="text-gray-500 text-xs">Latency</div>
                            <div className="text-white font-mono text-sm">
                              {trace.metrics?.request_latency?.value?.toFixed(2) || 'N/A'}ms
                            </div>
                          </div>
                          <div>
                            <div className="text-gray-500 text-xs">TTFT</div>
                            <div className="text-white font-mono text-sm">
                              {trace.metrics?.ttft?.value?.toFixed(2) || 'N/A'}ms
                            </div>
                          </div>
                          <div>
                            <div className="text-gray-500 text-xs">Input Tokens</div>
                            <div className="text-white font-mono text-sm">
                              {trace.token_breakdown?.input || 0}
                            </div>
                          </div>
                          <div>
                            <div className="text-gray-500 text-xs">Output Tokens</div>
                            <div className="text-white font-mono text-sm">
                              {trace.token_breakdown?.output || 0}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {view === 'timeline' && (
              <div className="bg-white/5 border border-white/10 rounded-xl p-6">
                <TimelineChart traces={traces} />
              </div>
            )}

            {view === 'waterfall' && (
              <div className="bg-white/5 border border-white/10 rounded-xl p-6">
                <WaterfallChart traces={traces} />
              </div>
            )}
          </>
        )}

        {/* Trace Detail Modal */}
        {selectedTrace && (
          <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-8" onClick={() => setSelectedTrace(null)}>
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-nvidia-darkGray border border-white/10 rounded-2xl p-6 w-full max-w-4xl max-h-[90vh] overflow-auto"
            >
              <h3 className="text-2xl font-bold text-white mb-4">
                Trace: {selectedTrace.request_id}
              </h3>

              {/* Timeline */}
              <div className="mb-6">
                <h4 className="text-lg font-bold text-nvidia-green mb-3">Timeline</h4>
                <div className="space-y-2">
                  {selectedTrace.timeline?.map((event: any, idx: number) => (
                    <div key={idx} className="flex items-center gap-3 p-3 bg-black/30 rounded-lg">
                      <div className="w-2 h-2 bg-nvidia-green rounded-full"></div>
                      <div className="flex-1">
                        <span className="text-white font-semibold">{event.event}</span>
                      </div>
                      <span className="text-gray-400 font-mono text-sm">{event.relative_ms.toFixed(2)} ms</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Token Breakdown */}
              <div className="mb-6">
                <h4 className="text-lg font-bold text-nvidia-green mb-3">Token Breakdown</h4>
                <div className="grid grid-cols-3 gap-4">
                  <div className="p-4 bg-black/30 rounded-lg">
                    <div className="text-gray-400 text-sm">Input Tokens</div>
                    <div className="text-2xl font-bold text-white">{selectedTrace.token_breakdown?.input || 0}</div>
                  </div>
                  <div className="p-4 bg-black/30 rounded-lg">
                    <div className="text-gray-400 text-sm">Output Tokens</div>
                    <div className="text-2xl font-bold text-white">{selectedTrace.token_breakdown?.output || 0}</div>
                  </div>
                  <div className="p-4 bg-black/30 rounded-lg">
                    <div className="text-gray-400 text-sm">Total Tokens</div>
                    <div className="text-2xl font-bold text-nvidia-green">{selectedTrace.token_breakdown?.total || 0}</div>
                  </div>
                </div>
              </div>

              {/* Metrics */}
              <div className="mb-6">
                <h4 className="text-lg font-bold text-nvidia-green mb-3">Metrics</h4>
                <div className="grid grid-cols-2 gap-3">
                  {Object.entries(selectedTrace.metrics || {}).map(([key, value]: [string, any]) => (
                    <div key={key} className="p-3 bg-black/30 rounded-lg">
                      <div className="text-gray-400 text-xs mb-1">{key}</div>
                      <div className="text-white font-mono text-sm">
                        {value.value} {value.unit}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Error Details */}
              {selectedTrace.error && (
                <div className="mb-6">
                  <h4 className="text-lg font-bold text-red-400 mb-3 flex items-center gap-2">
                    <AlertCircle className="w-5 h-5" />
                    Error Details
                  </h4>
                  <pre className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg text-red-300 text-sm overflow-auto">
                    {JSON.stringify(selectedTrace.error, null, 2)}
                  </pre>
                </div>
              )}

              <button
                onClick={() => setSelectedTrace(null)}
                className="w-full px-4 py-2 bg-white/5 border border-white/10 text-gray-300 rounded-lg hover:border-white/20"
              >
                Close
              </button>
            </motion.div>
          </div>
        )}
      </div>
    </div>
  )
}
