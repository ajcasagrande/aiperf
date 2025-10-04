'use client'

import { motion } from 'framer-motion'
import { TrendingUp, TrendingDown, Minus, Activity, BarChart3, PieChart } from 'lucide-react'
import { ComparisonResult } from '@/lib/types'

interface StatisticalAnalysisSectionProps {
  comparison: ComparisonResult
  metrics: string[]
}

export function StatisticalAnalysisSection({ comparison, metrics }: StatisticalAnalysisSectionProps) {
  // Calculate coefficient of variation for each metric
  const calculateCV = (metricKey: string) => {
    const values = comparison.benchmarks.map(id => {
      const metricData = comparison.data[id]?.[metricKey]
      return metricData?.mean || 0
    })

    const mean = values.reduce((a, b) => a + b, 0) / values.length
    const variance = values.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / values.length
    const stdDev = Math.sqrt(variance)

    return mean > 0 ? (stdDev / mean) * 100 : 0
  }

  // Calculate performance spread
  const calculateSpread = (metricKey: string) => {
    const values = comparison.benchmarks.map(id => {
      const metricData = comparison.data[id]?.[metricKey]
      return metricData?.mean || 0
    })

    const max = Math.max(...values)
    const min = Math.min(...values)

    return max > 0 ? ((max - min) / max) * 100 : 0
  }

  // Determine consistency rating
  const getConsistencyRating = (cv: number) => {
    if (cv < 10) return { label: 'Highly Consistent', color: 'text-green-400', icon: <Activity className="w-5 h-5" /> }
    if (cv < 25) return { label: 'Moderately Consistent', color: 'text-blue-400', icon: <Activity className="w-5 h-5" /> }
    if (cv < 50) return { label: 'Variable', color: 'text-yellow-400', icon: <Activity className="w-5 h-5" /> }
    return { label: 'Highly Variable', color: 'text-red-400', icon: <Activity className="w-5 h-5" /> }
  }

  // Calculate statistical insights
  const insights = metrics.map(metricKey => {
    const cv = calculateCV(metricKey)
    const spread = calculateSpread(metricKey)
    const consistency = getConsistencyRating(cv)

    // Get best and worst performers
    const values = comparison.benchmarks.map(id => ({
      id,
      value: comparison.data[id]?.[metricKey]?.mean || 0
    }))

    const isLatencyMetric = metricKey.includes('latency') || metricKey.includes('ttft')
    values.sort((a, b) => isLatencyMetric ? a.value - b.value : b.value - a.value)

    const best = values[0]
    const worst = values[values.length - 1]
    const improvement = worst.value > 0 ? ((Math.abs(worst.value - best.value) / worst.value) * 100) : 0

    return {
      metricKey,
      cv,
      spread,
      consistency,
      best,
      worst,
      improvement
    }
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <BarChart3 className="w-8 h-8 text-nvidia-green" />
        <div>
          <h2 className="text-2xl font-bold text-white">Statistical Analysis</h2>
          <p className="text-sm text-gray-400">Deep dive into performance metrics and variance</p>
        </div>
      </div>

      {/* Summary Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className="bg-gradient-to-br from-blue-500/10 to-blue-600/5 border border-blue-500/20 rounded-xl p-6"
        >
          <div className="flex items-center gap-3 mb-2">
            <PieChart className="w-6 h-6 text-blue-400" />
            <h3 className="text-sm font-semibold text-gray-400">Total Benchmarks</h3>
          </div>
          <div className="text-4xl font-black text-white">{comparison.benchmarks.length}</div>
        </motion.div>

        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.1 }}
          className="bg-gradient-to-br from-green-500/10 to-green-600/5 border border-green-500/20 rounded-xl p-6"
        >
          <div className="flex items-center gap-3 mb-2">
            <BarChart3 className="w-6 h-6 text-green-400" />
            <h3 className="text-sm font-semibold text-gray-400">Metrics Analyzed</h3>
          </div>
          <div className="text-4xl font-black text-white">{metrics.length}</div>
        </motion.div>

        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.2 }}
          className="bg-gradient-to-br from-purple-500/10 to-purple-600/5 border border-purple-500/20 rounded-xl p-6"
        >
          <div className="flex items-center gap-3 mb-2">
            <TrendingUp className="w-6 h-6 text-purple-400" />
            <h3 className="text-sm font-semibold text-gray-400">Avg Performance Spread</h3>
          </div>
          <div className="text-4xl font-black text-white">
            {(insights.reduce((sum, i) => sum + i.spread, 0) / insights.length).toFixed(1)}%
          </div>
        </motion.div>

        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="bg-gradient-to-br from-yellow-500/10 to-yellow-600/5 border border-yellow-500/20 rounded-xl p-6"
        >
          <div className="flex items-center gap-3 mb-2">
            <Activity className="w-6 h-6 text-yellow-400" />
            <h3 className="text-sm font-semibold text-gray-400">Avg Variability (CV)</h3>
          </div>
          <div className="text-4xl font-black text-white">
            {(insights.reduce((sum, i) => sum + i.cv, 0) / insights.length).toFixed(1)}%
          </div>
        </motion.div>
      </div>

      {/* Detailed Metric Analysis */}
      <div className="space-y-4">
        <h3 className="text-xl font-bold text-white mb-4">Metric-by-Metric Breakdown</h3>
        {insights.map((insight, index) => (
          <motion.div
            key={insight.metricKey}
            initial={{ x: -50, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            transition={{ delay: index * 0.05 }}
            className="bg-white/5 border border-white/10 rounded-xl p-6 hover:bg-white/10 transition-colors"
          >
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Metric Info */}
              <div>
                <h4 className="text-lg font-bold text-white mb-3">
                  {insight.metricKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                </h4>
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    {insight.consistency.icon}
                    <span className={`text-sm font-semibold ${insight.consistency.color}`}>
                      {insight.consistency.label}
                    </span>
                  </div>
                  <div className="text-xs text-gray-400">
                    Coefficient of Variation: <span className="text-white font-semibold">{insight.cv.toFixed(1)}%</span>
                  </div>
                  <div className="text-xs text-gray-400">
                    Performance Spread: <span className="text-white font-semibold">{insight.spread.toFixed(1)}%</span>
                  </div>
                </div>
              </div>

              {/* Best Performer */}
              <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <TrendingUp className="w-4 h-4 text-green-400" />
                  <span className="text-sm font-semibold text-green-400">Best Performer</span>
                </div>
                <div className="text-white font-semibold text-sm truncate mb-1">
                  {insight.best.id.substring(0, 25)}...
                </div>
                <div className="text-2xl font-bold text-green-400">
                  {insight.best.value.toFixed(2)}
                </div>
              </div>

              {/* Worst Performer */}
              <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <TrendingDown className="w-4 h-4 text-red-400" />
                  <span className="text-sm font-semibold text-red-400">Needs Improvement</span>
                </div>
                <div className="text-white font-semibold text-sm truncate mb-1">
                  {insight.worst.id.substring(0, 25)}...
                </div>
                <div className="text-2xl font-bold text-red-400">
                  {insight.worst.value.toFixed(2)}
                </div>
                <div className="text-xs text-gray-400 mt-2">
                  {insight.improvement.toFixed(1)}% gap from best
                </div>
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  )
}
