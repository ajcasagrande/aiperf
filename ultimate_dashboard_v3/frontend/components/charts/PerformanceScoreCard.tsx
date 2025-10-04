'use client'

import { motion } from 'framer-motion'
import { Trophy, Zap, Target, TrendingUp } from 'lucide-react'
import { ComparisonResult } from '@/lib/types'

interface PerformanceScoreCardProps {
  comparison: ComparisonResult
  benchmarkId: string
  rank: number
}

export function PerformanceScoreCard({ comparison, benchmarkId, rank }: PerformanceScoreCardProps) {
  // Calculate overall performance score
  const calculateOverallScore = () => {
    const metrics = Object.keys(comparison.data[benchmarkId] || {})
    if (metrics.length === 0) return 0

    let totalScore = 0
    let count = 0

    metrics.forEach(metricKey => {
      const allValues = comparison.benchmarks.map(id => {
        const metricData = comparison.data[id]?.[metricKey]
        return metricData?.mean || 0
      })
      const max = Math.max(...allValues)
      const min = Math.min(...allValues)

      if (max === min) return

      const value = comparison.data[benchmarkId]?.[metricKey]?.mean || 0

      // Normalize to 0-100
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

    return count > 0 ? totalScore / count : 0
  }

  const score = calculateOverallScore()
  const grade = score >= 90 ? 'S' : score >= 80 ? 'A' : score >= 70 ? 'B' : score >= 60 ? 'C' : score >= 50 ? 'D' : 'F'
  const gradeColor = score >= 90 ? 'from-yellow-400 to-yellow-600' :
                      score >= 80 ? 'from-green-400 to-green-600' :
                      score >= 70 ? 'from-blue-400 to-blue-600' :
                      score >= 60 ? 'from-purple-400 to-purple-600' :
                      score >= 50 ? 'from-orange-400 to-orange-600' : 'from-red-400 to-red-600'

  const medalColor = rank === 1 ? 'text-yellow-400' : rank === 2 ? 'text-gray-300' : rank === 3 ? 'text-orange-400' : 'text-gray-600'

  return (
    <motion.div
      initial={{ scale: 0.9, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ duration: 0.3, delay: rank * 0.1 }}
      className={`relative bg-gradient-to-br ${rank === 1 ? 'from-yellow-500/10 to-yellow-600/5 border-yellow-500/30' : 'from-white/5 to-white/0 border-white/10'} border rounded-xl p-6 overflow-hidden`}
    >
      {/* Background glow effect */}
      {rank === 1 && (
        <div className="absolute inset-0 bg-gradient-radial from-yellow-500/10 via-transparent to-transparent animate-pulse" />
      )}

      <div className="relative z-10">
        {/* Rank Badge */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Trophy className={`w-6 h-6 ${medalColor}`} />
            <span className="text-2xl font-bold text-white">#{rank}</span>
          </div>
          <div className={`text-4xl font-black bg-gradient-to-br ${gradeColor} bg-clip-text text-transparent`}>
            {grade}
          </div>
        </div>

        {/* Benchmark Name */}
        <h3 className="text-lg font-bold text-white mb-4 truncate">
          {benchmarkId}
        </h3>

        {/* Score Gauge */}
        <div className="mb-4">
          <div className="flex items-center justify-between text-sm mb-2">
            <span className="text-gray-400">Overall Score</span>
            <span className="text-white font-bold">{score.toFixed(1)}%</span>
          </div>
          <div className="relative h-4 bg-black/50 rounded-full overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${score}%` }}
              transition={{ duration: 1, delay: rank * 0.1 }}
              className={`absolute inset-y-0 left-0 bg-gradient-to-r ${gradeColor} rounded-full`}
            />
            {/* Glowing effect */}
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${score}%` }}
              transition={{ duration: 1, delay: rank * 0.1 }}
              className={`absolute inset-y-0 left-0 bg-gradient-to-r ${gradeColor} rounded-full blur-sm opacity-50`}
            />
          </div>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-3 gap-2">
          <div className="bg-black/30 rounded-lg p-2 text-center">
            <Zap className="w-4 h-4 text-nvidia-green mx-auto mb-1" />
            <div className="text-xs text-gray-400">Speed</div>
            <div className="text-sm font-bold text-white">
              {(comparison.data[benchmarkId]?.request_throughput?.mean || 0).toFixed(1)}
            </div>
          </div>
          <div className="bg-black/30 rounded-lg p-2 text-center">
            <Target className="w-4 h-4 text-blue-400 mx-auto mb-1" />
            <div className="text-xs text-gray-400">Latency</div>
            <div className="text-sm font-bold text-white">
              {(comparison.data[benchmarkId]?.request_latency?.mean || 0).toFixed(0)}ms
            </div>
          </div>
          <div className="bg-black/30 rounded-lg p-2 text-center">
            <TrendingUp className="w-4 h-4 text-purple-400 mx-auto mb-1" />
            <div className="text-xs text-gray-400">Goodput</div>
            <div className="text-sm font-bold text-white">
              {(comparison.data[benchmarkId]?.goodput?.mean || 0).toFixed(2)}
            </div>
          </div>
        </div>

        {/* Winner Badge */}
        {rank === 1 && (
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: "spring", delay: 0.5 }}
            className="mt-4 bg-gradient-to-r from-yellow-400 to-yellow-600 text-black font-bold text-center py-2 rounded-lg flex items-center justify-center gap-2"
          >
            <Trophy className="w-5 h-5" />
            CHAMPION
          </motion.div>
        )}
      </div>
    </motion.div>
  )
}
