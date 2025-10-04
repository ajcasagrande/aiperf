'use client'

import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useQuery } from '@tanstack/react-query'
import {
  Activity,
  Zap,
  TrendingUp,
  Clock,
  Database,
  CheckCircle,
  AlertCircle,
  BarChart3,
  Brain,
  Upload,
  Download,
  RefreshCw
} from 'lucide-react'
import { apiClient } from '@/lib/api'
import { useDashboardStore } from '@/lib/store'
import { BenchmarkUpload } from '@/components/BenchmarkUpload'
import { LatencyChart, ThroughputChart, DistributionChart } from '@/components/charts'
import { formatNumber, getMetricValue } from '@/lib/utils'
import toast from 'react-hot-toast'

export default function DashboardPage() {
  const [showUpload, setShowUpload] = useState(false)
  const { currentBenchmarkId, setCurrentBenchmarkId, selectedBenchmark, setSelectedBenchmark, setInsights, insights } = useDashboardStore()

  // Fetch benchmarks list
  const { data: benchmarksData, refetch: refetchBenchmarks } = useQuery({
    queryKey: ['benchmarks'],
    queryFn: () => apiClient.listBenchmarks(),
    refetchInterval: 30000, // Refetch every 30s
    refetchOnMount: true,
    staleTime: 0,
  })

  // Fetch current benchmark data
  const { data: benchmarkData, isLoading, refetch } = useQuery({
    queryKey: ['benchmark', currentBenchmarkId],
    queryFn: () => currentBenchmarkId ? apiClient.getBenchmark(currentBenchmarkId) : null,
    enabled: !!currentBenchmarkId,
    refetchOnMount: true,
    staleTime: 0,
  })

  // Fetch AI insights
  const { data: insightsData } = useQuery({
    queryKey: ['insights', currentBenchmarkId],
    queryFn: () => currentBenchmarkId ? apiClient.getInsights(currentBenchmarkId) : null,
    enabled: !!currentBenchmarkId,
    refetchOnMount: true,
    staleTime: 0,
  })

  useEffect(() => {
    if (benchmarkData) {
      setSelectedBenchmark(benchmarkData)
    }
  }, [benchmarkData, setSelectedBenchmark])

  useEffect(() => {
    if (insightsData) {
      setInsights(insightsData)
    }
  }, [insightsData, setInsights])

  // Auto-select first benchmark if none selected
  useEffect(() => {
    if (!currentBenchmarkId && benchmarksData?.length > 0) {
      setCurrentBenchmarkId(benchmarksData[0].id)
    }
  }, [benchmarksData, currentBenchmarkId, setCurrentBenchmarkId])

  const stats = selectedBenchmark?.statistics || {}
  const records = selectedBenchmark?.records || []

  // Verify data structure for charts
  if (selectedBenchmark && records.length > 0) {
    const firstRecord = records[0]
    if (!firstRecord?.metrics || !firstRecord?.metadata) {
      console.error('❌ Record structure invalid:', firstRecord)
    }
  }

  const handleUploadSuccess = (benchmarkId: string) => {
    setCurrentBenchmarkId(benchmarkId)
    refetchBenchmarks()
    toast.success('Benchmark loaded successfully!')
  }

  const handleExport = async () => {
    if (!currentBenchmarkId) return
    try {
      const data = await apiClient.exportBenchmark(currentBenchmarkId, 'json')
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${currentBenchmarkId}.json`
      a.click()
      URL.revokeObjectURL(url)
      toast.success('Exported successfully!')
    } catch (error) {
      toast.error('Export failed')
    }
  }

  if (!currentBenchmarkId || !stats) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-black via-nvidia-darkGray to-black flex items-center justify-center">
        <div className="text-center">
          <Activity className="w-16 h-16 text-nvidia-green mx-auto mb-4 animate-pulse" />
          <h2 className="text-2xl font-bold text-white mb-2">No Benchmark Selected</h2>
          <p className="text-gray-400 mb-6">Upload a benchmark to get started</p>
          <button
            onClick={() => setShowUpload(true)}
            className="px-6 py-3 bg-nvidia-green text-black font-bold rounded-lg hover:bg-nvidia-green/90"
          >
            <Upload className="w-5 h-5 inline mr-2" />
            Upload Benchmark
          </button>
        </div>

        <AnimatePresence>
          {showUpload && (
            <BenchmarkUpload
              onClose={() => setShowUpload(false)}
              onSuccess={handleUploadSuccess}
            />
          )}
        </AnimatePresence>
      </div>
    )
  }

  // Calculate KPIs - ensure stats is defined
  const requestThroughput = getMetricValue(stats, 'request_throughput', [], 'mean')
  const tokenThroughput = getMetricValue(stats, 'output_token_throughput', ['output_token_throughput_per_user'], 'mean')
  const p50Latency = getMetricValue(stats, 'request_latency', [], 'p50')
  const goodput = getMetricValue(stats, 'goodput', [], 'mean')
  const ttftP50 = getMetricValue(stats, 'ttft', [], 'p50')

  return (
    <div className="min-h-screen bg-gradient-to-br from-black via-nvidia-darkGray to-black">
      {/* Header */}
      <div className="border-b border-white/10 bg-black/50 backdrop-blur-lg sticky top-0 z-50">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Activity className="w-8 h-8 text-nvidia-green" />
              <div>
                <h1 className="text-2xl font-bold text-white">Performance Dashboard</h1>
                {benchmarksData && (
                  <select
                    value={currentBenchmarkId || ''}
                    onChange={(e) => setCurrentBenchmarkId(e.target.value)}
                    className="mt-1 text-sm bg-white/10 text-white border border-white/20 rounded px-2 py-1"
                  >
                    {benchmarksData.map((b: any) => (
                      <option key={b.id} value={b.id} className="bg-nvidia-darkGray">
                        {b.name} ({new Date(b.timestamp).toLocaleDateString()})
                      </option>
                    ))}
                  </select>
                )}
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() => refetch()}
                className="px-4 py-2 bg-white/10 text-white rounded-lg hover:bg-white/20 flex items-center gap-2"
              >
                <RefreshCw className="w-4 h-4" />
                Refresh
              </button>
              <button
                onClick={handleExport}
                className="px-4 py-2 bg-white/10 text-white rounded-lg hover:bg-white/20 flex items-center gap-2"
              >
                <Download className="w-4 h-4" />
                Export
              </button>
              <button
                onClick={() => setShowUpload(true)}
                className="px-4 py-2 bg-nvidia-green text-black font-semibold rounded-lg hover:bg-nvidia-green/90 flex items-center gap-2"
              >
                <Upload className="w-4 h-4" />
                Upload
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-4 py-8">
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="w-12 h-12 border-4 border-nvidia-green border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <>
            {/* KPI Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6 mb-8">
              <KPICard
                icon={<Zap className="w-6 h-6" />}
                title="Request Throughput"
                value={formatNumber(requestThroughput, 2)}
                unit="req/s"
                color="green"
              />
              <KPICard
                icon={<Activity className="w-6 h-6" />}
                title="Token Throughput"
                value={formatNumber(tokenThroughput, 0)}
                unit="tok/s"
                color="blue"
              />
              <KPICard
                icon={<Clock className="w-6 h-6" />}
                title="P50 Latency"
                value={formatNumber(p50Latency, 0)}
                unit="ms"
                color="purple"
              />
              <KPICard
                icon={<CheckCircle className="w-6 h-6" />}
                title="Goodput"
                value={formatNumber(goodput, 2)}
                unit="req/s"
                color="orange"
              />
              <KPICard
                icon={<TrendingUp className="w-6 h-6" />}
                title="TTFT P50"
                value={formatNumber(ttftP50, 0)}
                unit="ms"
                color="pink"
              />
            </div>

            {/* Main Charts Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
              <ChartCard title="Latency Over Time" description="Request, TTFT, and ITL latencies">
                <div className="h-80">
                  <LatencyChart records={records} />
                </div>
              </ChartCard>

              <ChartCard title="Throughput Trends" description="Request and token throughput">
                <div className="h-80">
                  <ThroughputChart records={records} />
                </div>
              </ChartCard>
            </div>

            {/* AI Insights Section */}
            {insights && (
              <div className="mb-8">
                <div className="bg-gradient-to-r from-purple-500/10 to-blue-500/10 border border-purple-500/20 rounded-xl p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <Brain className="w-6 h-6 text-purple-400" />
                    <h2 className="text-xl font-bold text-white">AI-Powered Insights</h2>
                    <div className="ml-auto">
                      <div className="text-3xl font-bold text-nvidia-green">{formatNumber(insights.score ?? 0, 0)}</div>
                      <div className="text-xs text-gray-400">Performance Score</div>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {(insights.key_findings || []).slice(0, 3).map((finding, i) => (
                      <InsightCard key={i} finding={finding} />
                    ))}
                  </div>

                  {(insights.recommendations || []).length > 0 && (
                    <div className="mt-4 pt-4 border-t border-white/10">
                      <h3 className="text-sm font-semibold text-white mb-2">Top Recommendations:</h3>
                      <ul className="space-y-2">
                        {(insights.recommendations || []).slice(0, 3).map((rec, i) => (
                          <li key={i} className="text-sm text-gray-300 flex items-start gap-2">
                            <span className="text-nvidia-green mt-0.5">▸</span>
                            <span><strong>{rec.title}:</strong> {rec.description}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Distribution Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
              <ChartCard title="Latency Distribution" description="Percentile breakdown">
                <div className="h-80">
                  {stats?.request_latency ? (
                    <DistributionChart stats={stats.request_latency} metricName="Latency (ms)" />
                  ) : (
                    <div className="flex items-center justify-center h-full text-gray-400">
                      Loading latency data...
                    </div>
                  )}
                </div>
              </ChartCard>

              <ChartCard title="TTFT Distribution" description="Time to first token percentiles">
                <div className="h-80">
                  {stats?.ttft ? (
                    <DistributionChart stats={stats.ttft} metricName="TTFT (ms)" />
                  ) : (
                    <div className="flex items-center justify-center h-full text-gray-400">
                      Loading TTFT data...
                    </div>
                  )}
                </div>
              </ChartCard>
            </div>

            {/* Detailed Metrics Table */}
            <ChartCard title="Detailed Metrics" description="Complete performance breakdown">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-white/10">
                    <tr>
                      <th className="px-4 py-3 text-gray-400">Metric</th>
                      <th className="px-4 py-3 text-gray-400 text-right">P50</th>
                      <th className="px-4 py-3 text-gray-400 text-right">P90</th>
                      <th className="px-4 py-3 text-gray-400 text-right">P99</th>
                      <th className="px-4 py-3 text-gray-400 text-right">Mean</th>
                    </tr>
                  </thead>
                  <tbody className="text-white">
                    <MetricRow name="Request Latency" stats={stats.request_latency} unit="ms" />
                    <MetricRow name="TTFT" stats={stats.ttft} unit="ms" />
                    <MetricRow name="Inter-Token Latency" stats={stats.inter_token_latency} unit="ms" />
                    <MetricRow name="Output Tokens/Req" stats={stats.output_sequence_length} unit="tokens" />
                  </tbody>
                </table>
              </div>
            </ChartCard>
          </>
        )}
      </div>

      <AnimatePresence>
        {showUpload && (
          <BenchmarkUpload
            onClose={() => setShowUpload(false)}
            onSuccess={handleUploadSuccess}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

function KPICard({ icon, title, value, unit, color }: any) {
  const colorClasses = {
    green: 'text-green-400',
    blue: 'text-blue-400',
    purple: 'text-purple-400',
    orange: 'text-orange-400',
    pink: 'text-pink-400',
  }

  return (
    <motion.div
      whileHover={{ scale: 1.02 }}
      className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl p-6 hover:border-nvidia-green/50 transition-colors"
    >
      <div className={`${colorClasses[color as keyof typeof colorClasses]} mb-4`}>
        {icon}
      </div>
      <div className="text-3xl font-bold text-white mb-1">
        {value}
        <span className="text-lg text-gray-400 ml-2">{unit}</span>
      </div>
      <div className="text-sm text-gray-400">{title}</div>
    </motion.div>
  )
}

function ChartCard({ title, description, children }: any) {
  return (
    <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl p-6">
      <div className="mb-4">
        <h3 className="text-lg font-bold text-white mb-1">{title}</h3>
        <p className="text-sm text-gray-400">{description}</p>
      </div>
      {children}
    </div>
  )
}

function InsightCard({ finding }: any) {
  const icons = {
    success: <CheckCircle className="w-5 h-5 text-green-400" />,
    warning: <AlertCircle className="w-5 h-5 text-yellow-400" />,
    info: <BarChart3 className="w-5 h-5 text-blue-400" />,
    error: <AlertCircle className="w-5 h-5 text-red-400" />,
  }

  return (
    <div className="bg-white/5 border border-white/10 rounded-lg p-4">
      <div className="flex items-start gap-3">
        {icons[finding.type as keyof typeof icons]}
        <div>
          <h4 className="font-semibold text-white mb-1 text-sm">{finding.metric}</h4>
          <p className="text-xs text-gray-400">{finding.message}</p>
        </div>
      </div>
    </div>
  )
}

function MetricRow({ name, stats, unit }: any) {
  if (!stats) return null
  return (
    <tr className="border-b border-white/5 hover:bg-white/5">
      <td className="px-4 py-3">{name}</td>
      <td className="px-4 py-3 text-right">{formatNumber(stats.p50, 2)} {unit}</td>
      <td className="px-4 py-3 text-right">{formatNumber(stats.p90, 2)} {unit}</td>
      <td className="px-4 py-3 text-right">{formatNumber(stats.p99, 2)} {unit}</td>
      <td className="px-4 py-3 text-right">{formatNumber(stats.mean, 2)} {unit}</td>
    </tr>
  )
}
