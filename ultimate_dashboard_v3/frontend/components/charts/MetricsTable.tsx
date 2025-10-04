'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ArrowUp, ArrowDown, Minus, Trophy, TrendingUp, TrendingDown, ChevronDown, ChevronUp } from 'lucide-react'
import { ComparisonResult } from '@/lib/types'
import { formatNumber } from '@/lib/utils'

interface MetricsTableProps {
  comparison: ComparisonResult
  metrics: string[]
}

export function MetricsTable({ comparison, metrics }: MetricsTableProps) {
  const [sortMetric, setSortMetric] = useState<string | null>(null)
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc')
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())

  // Handle column sort
  const handleSort = (metricKey: string) => {
    if (sortMetric === metricKey) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortMetric(metricKey)
      setSortDirection('desc')
    }
  }

  // Sort benchmarks
  const sortedBenchmarks = [...comparison.benchmarks].sort((a, b) => {
    if (!sortMetric) return 0

    const aValue = comparison.data[a]?.[sortMetric]?.mean || 0
    const bValue = comparison.data[b]?.[sortMetric]?.mean || 0

    const isLatencyMetric = sortMetric.includes('latency') || sortMetric.includes('ttft')
    const multiplier = sortDirection === 'asc' ? 1 : -1

    // For latency, lower is better
    if (isLatencyMetric) {
      return (aValue - bValue) * multiplier
    }

    return (bValue - aValue) * multiplier
  })

  // Toggle row expansion
  const toggleRow = (benchmarkId: string) => {
    const newExpanded = new Set(expandedRows)
    if (newExpanded.has(benchmarkId)) {
      newExpanded.delete(benchmarkId)
    } else {
      newExpanded.add(benchmarkId)
    }
    setExpandedRows(newExpanded)
  }

  // Get winner for metric
  const getWinner = (metricKey: string) => {
    const values = comparison.benchmarks.map(id => ({
      id,
      value: comparison.data[id]?.[metricKey]?.mean || 0
    }))

    const isLatencyMetric = metricKey.includes('latency') || metricKey.includes('ttft')
    values.sort((a, b) => isLatencyMetric ? a.value - b.value : b.value - a.value)

    return values[0]?.id
  }

  // Get performance indicator
  const getPerformanceIndicator = (benchmarkId: string, metricKey: string) => {
    const value = comparison.data[benchmarkId]?.[metricKey]?.mean || 0
    const allValues = comparison.benchmarks.map(id => comparison.data[id]?.[metricKey]?.mean || 0)
    const avg = allValues.reduce((a, b) => a + b, 0) / allValues.length

    if (value === 0 || avg === 0) return null

    const isLatencyMetric = metricKey.includes('latency') || metricKey.includes('ttft')
    const percentDiff = ((value - avg) / avg) * 100

    const isBetter = isLatencyMetric ? percentDiff < 0 : percentDiff > 0
    const color = isBetter ? 'text-green-400' : 'text-red-400'
    const icon = isBetter ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />

    return { icon, color, percentDiff: Math.abs(percentDiff) }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-xl font-bold text-white">Comprehensive Metrics Table</h3>
        <div className="text-sm text-gray-400">
          {sortMetric ? `Sorted by ${sortMetric.replace(/_/g, ' ')}` : 'Click column to sort'}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          {/* Header */}
          <thead className="border-b-2 border-nvidia-green/50">
            <tr>
              <th className="px-4 py-4 text-gray-400 font-bold">Benchmark</th>
              {metrics.map(metricKey => (
                <th
                  key={metricKey}
                  onClick={() => handleSort(metricKey)}
                  className="px-4 py-4 text-gray-400 font-bold text-center cursor-pointer hover:text-nvidia-green transition-colors"
                >
                  <div className="flex items-center justify-center gap-2">
                    <span>{metricKey.replace(/_/g, ' ').substring(0, 12)}</span>
                    {sortMetric === metricKey && (
                      <motion.div
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                      >
                        {sortDirection === 'asc' ? (
                          <ArrowUp className="w-4 h-4 text-nvidia-green" />
                        ) : (
                          <ArrowDown className="w-4 h-4 text-nvidia-green" />
                        )}
                      </motion.div>
                    )}
                  </div>
                </th>
              ))}
              <th className="px-4 py-4 text-gray-400 font-bold text-center">Details</th>
            </tr>
          </thead>

          {/* Body */}
          <tbody>
            {sortedBenchmarks.map((benchmarkId, index) => {
              const isExpanded = expandedRows.has(benchmarkId)

              return (
                <motion.tr
                  key={benchmarkId}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.05 }}
                  className="border-b border-white/5 hover:bg-white/5 transition-colors"
                >
                  <td className="px-4 py-4">
                    <div className="font-semibold text-white truncate max-w-[200px]">
                      {benchmarkId}
                    </div>
                  </td>

                  {metrics.map(metricKey => {
                    const metricData = comparison.data[benchmarkId]?.[metricKey]
                    const winner = getWinner(metricKey)
                    const isWinner = winner === benchmarkId
                    const indicator = getPerformanceIndicator(benchmarkId, metricKey)

                    return (
                      <td
                        key={metricKey}
                        className={`px-4 py-4 text-center ${isWinner ? 'bg-nvidia-green/10' : ''}`}
                      >
                        <div className="flex flex-col items-center gap-1">
                          <div className={`font-bold ${isWinner ? 'text-nvidia-green text-lg' : 'text-white'}`}>
                            {metricData?.mean ? formatNumber(metricData.mean, 2) : 'N/A'}
                            {isWinner && ' 🏆'}
                          </div>
                          {indicator && (
                            <div className={`flex items-center gap-1 text-xs ${indicator.color}`}>
                              {indicator.icon}
                              <span>{indicator.percentDiff.toFixed(1)}%</span>
                            </div>
                          )}
                        </div>
                      </td>
                    )
                  })}

                  <td className="px-4 py-4 text-center">
                    <button
                      onClick={() => toggleRow(benchmarkId)}
                      className="px-3 py-1 bg-white/10 hover:bg-white/20 rounded-lg transition-colors flex items-center gap-1 mx-auto"
                    >
                      {isExpanded ? (
                        <>
                          <ChevronUp className="w-4 h-4" />
                          <span className="text-xs">Hide</span>
                        </>
                      ) : (
                        <>
                          <ChevronDown className="w-4 h-4" />
                          <span className="text-xs">Show</span>
                        </>
                      )}
                    </button>
                  </td>
                </motion.tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Expanded Details - Will add percentile distributions later */}
      <AnimatePresence>
        {sortedBenchmarks.map(benchmarkId => {
          const isExpanded = expandedRows.has(benchmarkId)
          if (!isExpanded) return null

          return (
            <motion.div
              key={`expanded-${benchmarkId}`}
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="bg-gradient-to-r from-nvidia-green/5 to-blue-500/5 border border-nvidia-green/20 rounded-xl p-6 overflow-hidden"
            >
              <h4 className="text-lg font-bold text-white mb-4">
                Detailed Statistics: {benchmarkId}
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {metrics.map(metricKey => {
                  const metricData = comparison.data[benchmarkId]?.[metricKey]
                  if (!metricData) return null

                  return (
                    <div key={metricKey} className="bg-black/30 rounded-lg p-4">
                      <div className="text-sm font-semibold text-gray-400 mb-3">
                        {metricKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                      </div>
                      <div className="space-y-2 text-xs">
                        <div className="flex justify-between">
                          <span className="text-gray-400">Mean:</span>
                          <span className="text-white font-bold">{formatNumber(metricData.mean, 2)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-400">Min:</span>
                          <span className="text-white">{formatNumber(metricData.min, 2)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-400">Max:</span>
                          <span className="text-white">{formatNumber(metricData.max, 2)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-400">Std Dev:</span>
                          <span className="text-white">{formatNumber(metricData.std, 2)}</span>
                        </div>
                        {metricData.p50 > 0 && (
                          <>
                            <div className="flex justify-between">
                              <span className="text-gray-400">P50:</span>
                              <span className="text-green-400">{formatNumber(metricData.p50, 2)}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-400">P90:</span>
                              <span className="text-yellow-400">{formatNumber(metricData.p90, 2)}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-400">P99:</span>
                              <span className="text-red-400">{formatNumber(metricData.p99, 2)}</span>
                            </div>
                          </>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}
