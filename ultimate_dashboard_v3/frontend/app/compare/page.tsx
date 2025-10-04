'use client'

import { useState, useEffect, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useQuery } from '@tanstack/react-query'
import {
  GitCompare,
  Plus,
  TrendingUp,
  Zap,
  X,
  CheckCircle,
  AlertTriangle,
  BarChart2,
  Target,
  Activity,
  Sparkles,
  Filter,
  Download
} from 'lucide-react'
import { apiClient } from '@/lib/api'
import { useDashboardStore } from '@/lib/store'
import {
  ComparisonChart,
  RadarChart,
  HeatmapChart,
  PerformanceScoreCard,
  WinnerPodium,
  StatisticalAnalysisSection,
  MetricsTable
} from '@/components/charts'
import { formatNumber, calculatePerformanceGrade } from '@/lib/utils'
import toast from 'react-hot-toast'

export default function ComparePage() {
  const { comparisonBenchmarks, addToComparison, removeFromComparison, clearComparison } = useDashboardStore()
  const [selectedMetrics, setSelectedMetrics] = useState(['request_latency', 'output_token_throughput', 'ttft', 'goodput', 'request_throughput', 'inter_token_latency'])
  const [activeView, setActiveView] = useState<'overview' | 'detailed' | 'statistical'>('overview')

  // Fetch benchmarks list
  const { data: benchmarksData } = useQuery({
    queryKey: ['benchmarks'],
    queryFn: () => apiClient.listBenchmarks(),
  })

  // Fetch comparison result
  const { data: comparisonData, isLoading, refetch } = useQuery({
    queryKey: ['comparison', comparisonBenchmarks, selectedMetrics],
    queryFn: () => {
      if (comparisonBenchmarks.length < 2) return null
      return apiClient.compareBenchmarks(comparisonBenchmarks, selectedMetrics)
    },
    enabled: comparisonBenchmarks.length >= 2,
  })

  const availableBenchmarks = benchmarksData || []
  const availableMetrics = [
    { key: 'request_latency', label: 'Request Latency', category: 'latency' },
    { key: 'ttft', label: 'Time to First Token', category: 'latency' },
    { key: 'inter_token_latency', label: 'Inter-Token Latency', category: 'latency' },
    { key: 'output_token_throughput', label: 'Token Throughput', category: 'throughput' },
    { key: 'request_throughput', label: 'Request Throughput', category: 'throughput' },
    { key: 'goodput', label: 'Goodput', category: 'quality' },
  ]

  // Calculate overall rankings
  const rankedBenchmarks = useMemo(() => {
    if (!comparisonData) return []

    const rankings = comparisonBenchmarks.map(benchmarkId => {
      const metrics = Object.keys(comparisonData.data[benchmarkId] || {})
      let totalScore = 0
      let count = 0

      metrics.forEach(metricKey => {
        const allValues = comparisonBenchmarks.map(id => {
          const metricData = comparisonData.data[id]?.[metricKey]
          return metricData?.mean || 0
        })
        const max = Math.max(...allValues)
        const min = Math.min(...allValues)

        if (max === min) return

        const value = comparisonData.data[benchmarkId]?.[metricKey]?.mean || 0
        const isLatencyMetric = metricKey.includes('latency') || metricKey.includes('ttft')

        let score = 0
        if (isLatencyMetric) {
          score = ((max - value) / (max - min)) * 100
        } else {
          score = ((value - min) / (max - min)) * 100
        }

        totalScore += score
        count++
      })

      return {
        benchmarkId,
        score: count > 0 ? totalScore / count : 0
      }
    })

    return rankings.sort((a, b) => b.score - a.score)
  }, [comparisonData, comparisonBenchmarks])

  const handleAddBenchmark = (benchmarkId: string) => {
    addToComparison(benchmarkId)
    toast.success('Benchmark added to comparison', {
      icon: '🚀',
      style: {
        background: '#10b981',
        color: 'white',
      },
    })
    setTimeout(refetch, 100)
  }

  const handleRemoveBenchmark = (benchmarkId: string) => {
    removeFromComparison(benchmarkId)
    toast.success('Benchmark removed from comparison')
    setTimeout(refetch, 100)
  }

  const toggleMetric = (metricKey: string) => {
    setSelectedMetrics((prev) => {
      if (prev.includes(metricKey)) {
        if (prev.length === 1) {
          toast.error('At least one metric must be selected')
          return prev
        }
        return prev.filter((m) => m !== metricKey)
      } else {
        return [...prev, metricKey]
      }
    })
  }

  const getWinner = (metric: string) => {
    if (!comparisonData?.analysis?.[metric]) return null
    return comparisonData.analysis[metric].best
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-black via-nvidia-darkGray to-black">
      {/* Epic Header with Gradient */}
      <div className="border-b border-white/10 bg-gradient-to-r from-black via-nvidia-darkGray to-black backdrop-blur-lg sticky top-0 z-50 shadow-2xl">
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center justify-between">
            <motion.div
              initial={{ x: -50, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              className="flex items-center gap-4"
            >
              <div className="relative">
                <GitCompare className="w-10 h-10 text-nvidia-green" />
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
                  className="absolute -inset-2 bg-nvidia-green/20 rounded-full blur-xl"
                />
              </div>
              <div>
                <h1 className="text-3xl font-black bg-gradient-to-r from-nvidia-green via-green-400 to-nvidia-green bg-clip-text text-transparent">
                  ULTIMATE BENCHMARK COMPARISON
                </h1>
                <p className="text-sm text-gray-400 flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-nvidia-green" />
                  {comparisonBenchmarks.length} benchmark{comparisonBenchmarks.length !== 1 ? 's' : ''} • {selectedMetrics.length} metrics
                </p>
              </div>
            </motion.div>

            <div className="flex items-center gap-3">
              {comparisonBenchmarks.length > 0 && (
                <>
                  <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={clearComparison}
                    className="px-4 py-2 bg-red-500/20 text-red-400 border border-red-500/50 rounded-lg hover:bg-red-500/30 transition-colors flex items-center gap-2 font-semibold"
                  >
                    <X className="w-4 h-4" />
                    Clear All
                  </motion.button>
                </>
              )}
            </div>
          </div>

          {/* View Switcher */}
          {comparisonBenchmarks.length >= 2 && (
            <motion.div
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              className="flex items-center gap-2 mt-4"
            >
              <button
                onClick={() => setActiveView('overview')}
                className={`px-4 py-2 rounded-lg font-semibold transition-all ${
                  activeView === 'overview'
                    ? 'bg-nvidia-green text-black shadow-lg shadow-nvidia-green/50'
                    : 'bg-white/10 text-white hover:bg-white/20'
                }`}
              >
                <div className="flex items-center gap-2">
                  <Target className="w-4 h-4" />
                  Overview
                </div>
              </button>
              <button
                onClick={() => setActiveView('detailed')}
                className={`px-4 py-2 rounded-lg font-semibold transition-all ${
                  activeView === 'detailed'
                    ? 'bg-nvidia-green text-black shadow-lg shadow-nvidia-green/50'
                    : 'bg-white/10 text-white hover:bg-white/20'
                }`}
              >
                <div className="flex items-center gap-2">
                  <BarChart2 className="w-4 h-4" />
                  Detailed Analysis
                </div>
              </button>
              <button
                onClick={() => setActiveView('statistical')}
                className={`px-4 py-2 rounded-lg font-semibold transition-all ${
                  activeView === 'statistical'
                    ? 'bg-nvidia-green text-black shadow-lg shadow-nvidia-green/50'
                    : 'bg-white/10 text-white hover:bg-white/20'
                }`}
              >
                <div className="flex items-center gap-2">
                  <Activity className="w-4 h-4" />
                  Statistical
                </div>
              </button>
            </motion.div>
          )}
        </div>
      </div>

      <div className="container mx-auto px-4 py-8">
        {/* Benchmark Selection Grid */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-2xl font-bold text-white flex items-center gap-2">
              <Filter className="w-6 h-6 text-nvidia-green" />
              Select Benchmarks
            </h2>
            <div className="text-sm text-gray-400">
              {availableBenchmarks.length} available
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {availableBenchmarks.map((benchmark: any) => (
              <BenchmarkCard
                key={benchmark.id}
                benchmark={benchmark}
                isSelected={comparisonBenchmarks.includes(benchmark.id)}
                onToggle={() => {
                  if (comparisonBenchmarks.includes(benchmark.id)) {
                    handleRemoveBenchmark(benchmark.id)
                  } else {
                    handleAddBenchmark(benchmark.id)
                  }
                }}
              />
            ))}
          </div>
        </div>

        {/* Metric Selection */}
        {comparisonBenchmarks.length >= 2 && (
          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            className="mb-8"
          >
            <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-2">
              <BarChart2 className="w-6 h-6 text-nvidia-green" />
              Select Metrics
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
              {availableMetrics.map((metric) => (
                <motion.button
                  key={metric.key}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={() => toggleMetric(metric.key)}
                  className={`px-4 py-3 rounded-xl font-semibold transition-all ${
                    selectedMetrics.includes(metric.key)
                      ? 'bg-gradient-to-r from-nvidia-green to-green-500 text-black shadow-lg shadow-nvidia-green/50'
                      : 'bg-white/10 text-white hover:bg-white/20 border border-white/20'
                  }`}
                >
                  <div className="text-center">
                    <div className="font-bold">{metric.label}</div>
                    <div className="text-xs opacity-75">{metric.category}</div>
                  </div>
                </motion.button>
              ))}
            </div>
          </motion.div>
        )}

        {/* Main Content Area */}
        {comparisonBenchmarks.length >= 2 && comparisonData && (
          <AnimatePresence mode="wait">
            {activeView === 'overview' && (
              <motion.div
                key="overview"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="space-y-8"
              >
                {/* Winner Podium */}
                <WinnerPodium comparison={comparisonData} rankedBenchmarks={rankedBenchmarks} />

                {/* Performance Score Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {rankedBenchmarks.map((item, index) => (
                    <PerformanceScoreCard
                      key={item.benchmarkId}
                      comparison={comparisonData}
                      benchmarkId={item.benchmarkId}
                      rank={index + 1}
                    />
                  ))}
                </div>

                {/* Radar Chart - Multi-dimensional View */}
                <div className="bg-white/5 border border-white/10 rounded-2xl p-8">
                  <h3 className="text-2xl font-bold text-white mb-6 flex items-center gap-3">
                    <Target className="w-7 h-7 text-nvidia-green" />
                    Multi-Dimensional Performance Radar
                  </h3>
                  <div className="h-[600px]">
                    <RadarChart comparison={comparisonData} metrics={selectedMetrics} />
                  </div>
                </div>

                {/* Heatmap */}
                <div className="bg-white/5 border border-white/10 rounded-2xl p-8">
                  <h3 className="text-2xl font-bold text-white mb-6 flex items-center gap-3">
                    <Activity className="w-7 h-7 text-nvidia-green" />
                    Performance Heatmap
                  </h3>
                  <HeatmapChart comparison={comparisonData} metrics={selectedMetrics} />
                </div>
              </motion.div>
            )}

            {activeView === 'detailed' && (
              <motion.div
                key="detailed"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="space-y-8"
              >
                {/* Comparison Charts Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {selectedMetrics.map((metricKey) => (
                    <div key={metricKey} className="bg-white/5 border border-white/10 rounded-2xl p-6 hover:border-nvidia-green/30 transition-colors">
                      <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                        <BarChart2 className="w-5 h-5 text-nvidia-green" />
                        {availableMetrics.find((m) => m.key === metricKey)?.label || metricKey}
                      </h3>
                      <div className="h-80">
                        {isLoading ? (
                          <div className="flex items-center justify-center h-full">
                            <div className="w-8 h-8 border-4 border-nvidia-green border-t-transparent rounded-full animate-spin" />
                          </div>
                        ) : (
                          <ComparisonChart comparison={comparisonData} metric={metricKey} />
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Comprehensive Metrics Table */}
                <div className="bg-white/5 border border-white/10 rounded-2xl p-8">
                  <MetricsTable comparison={comparisonData} metrics={selectedMetrics} />
                </div>
              </motion.div>
            )}

            {activeView === 'statistical' && (
              <motion.div
                key="statistical"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="space-y-8"
              >
                <div className="bg-white/5 border border-white/10 rounded-2xl p-8">
                  <StatisticalAnalysisSection comparison={comparisonData} metrics={selectedMetrics} />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        )}

        {/* Empty State */}
        {comparisonBenchmarks.length < 2 && (
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="flex flex-col items-center justify-center h-96 text-center"
          >
            <div className="relative mb-8">
              <GitCompare className="w-24 h-24 text-gray-600" />
              <motion.div
                animate={{
                  scale: [1, 1.2, 1],
                  opacity: [0.5, 0.8, 0.5]
                }}
                transition={{
                  duration: 2,
                  repeat: Infinity,
                  ease: "easeInOut"
                }}
                className="absolute inset-0 bg-nvidia-green/20 rounded-full blur-2xl"
              />
            </div>
            <h3 className="text-3xl font-bold text-white mb-4">Ready to Compare?</h3>
            <p className="text-gray-400 text-lg mb-8 max-w-md">
              Select at least 2 benchmarks from the grid above to unlock powerful comparison analytics
            </p>
            <div className="flex items-center gap-6 text-sm text-gray-500">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-nvidia-green" />
                <span>Multi-dimensional Analysis</span>
              </div>
              <div className="flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-nvidia-green" />
                <span>Statistical Insights</span>
              </div>
              <div className="flex items-center gap-2">
                <Activity className="w-5 h-5 text-nvidia-green" />
                <span>Performance Rankings</span>
              </div>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  )
}

function BenchmarkCard({ benchmark, isSelected, onToggle }: any) {
  return (
    <motion.div
      whileHover={{ scale: 1.02, y: -5 }}
      whileTap={{ scale: 0.98 }}
      className={`relative bg-gradient-to-br rounded-2xl p-5 cursor-pointer transition-all overflow-hidden ${
        isSelected
          ? 'from-nvidia-green/20 to-green-600/10 border-2 border-nvidia-green shadow-2xl shadow-nvidia-green/30'
          : 'from-white/5 to-white/0 border border-white/10 hover:border-nvidia-green/30'
      }`}
      onClick={onToggle}
    >
      {/* Glow effect for selected */}
      {isSelected && (
        <motion.div
          animate={{ opacity: [0.3, 0.6, 0.3] }}
          transition={{ duration: 2, repeat: Infinity }}
          className="absolute inset-0 bg-nvidia-green/10 blur-xl"
        />
      )}

      <div className="relative z-10">
        <div className="flex items-start justify-between mb-3">
          <div className="flex-1">
            <h3 className="text-white font-bold text-base truncate mb-1">{benchmark.name}</h3>
            <p className="text-xs text-gray-400">{new Date(benchmark.timestamp).toLocaleString()}</p>
          </div>
          <motion.div
            animate={isSelected ? { rotate: [0, 360] } : {}}
            transition={{ duration: 0.5 }}
            className={`w-10 h-10 rounded-full border-2 flex items-center justify-center transition-all ${
              isSelected
                ? 'bg-nvidia-green border-nvidia-green shadow-lg shadow-nvidia-green/50'
                : 'bg-transparent border-white/30'
            }`}
          >
            {isSelected && <CheckCircle className="w-6 h-6 text-black" />}
          </motion.div>
        </div>

        {benchmark.summary && (
          <div className="space-y-2 pt-3 border-t border-white/10">
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-400 flex items-center gap-1">
                <Zap className="w-3 h-3 text-nvidia-green" />
                Throughput
              </span>
              <span className="text-white font-bold">
                {formatNumber(benchmark.summary.throughput || 0, 2)} req/s
              </span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-400 flex items-center gap-1">
                <TrendingUp className="w-3 h-3 text-blue-400" />
                Latency
              </span>
              <span className="text-white font-bold">
                {formatNumber(benchmark.summary.avg_latency || 0, 0)} ms
              </span>
            </div>
          </div>
        )}
      </div>
    </motion.div>
  )
}
