'use client'

import { ComparisonResult } from '@/lib/types'

interface HeatmapChartProps {
  comparison: ComparisonResult
  metrics: string[]
}

export function HeatmapChart({ comparison, metrics }: HeatmapChartProps) {
  if (!comparison || !comparison.benchmarks || !comparison.data) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        No comparison data available
      </div>
    )
  }

  // Calculate normalized scores for color intensity (0-100)
  const getNormalizedScore = (benchmarkId: string, metricKey: string) => {
    const allValues = comparison.benchmarks.map(id => {
      const metricData = comparison.data[id]?.[metricKey]
      return metricData?.mean || 0
    })
    const max = Math.max(...allValues)
    const min = Math.min(...allValues)

    if (max === min) return 50

    const value = comparison.data[benchmarkId]?.[metricKey]?.mean || 0

    // For latency metrics, lower is better (invert scale)
    const isLatencyMetric = metricKey.includes('latency') || metricKey.includes('ttft')
    if (isLatencyMetric) {
      return ((max - value) / (max - min)) * 100
    }

    // For throughput/goodput, higher is better
    return ((value - min) / (max - min)) * 100
  }

  // Get color based on score
  const getColor = (score: number) => {
    if (score >= 80) return 'bg-green-500'
    if (score >= 60) return 'bg-green-400'
    if (score >= 40) return 'bg-yellow-400'
    if (score >= 20) return 'bg-orange-400'
    return 'bg-red-400'
  }

  const getOpacity = (score: number) => {
    return Math.max(0.2, score / 100)
  }

  return (
    <div className="w-full overflow-x-auto">
      <div className="min-w-[600px]">
        {/* Header */}
        <div className="flex border-b border-white/10 mb-2">
          <div className="w-48 px-3 py-2 text-sm font-bold text-gray-400">Benchmark</div>
          {metrics.map(metric => (
            <div key={metric} className="flex-1 px-2 py-2 text-xs font-bold text-gray-400 text-center">
              {metric.replace(/_/g, ' ').substring(0, 15)}
            </div>
          ))}
        </div>

        {/* Heatmap Grid */}
        <div className="space-y-1">
          {comparison.benchmarks.map(benchmarkId => (
            <div key={benchmarkId} className="flex items-center hover:bg-white/5 rounded-lg transition-colors">
              <div className="w-48 px-3 py-2 text-sm text-white font-semibold truncate">
                {benchmarkId.substring(0, 20)}
              </div>
              <div className="flex-1 flex gap-1">
                {metrics.map(metricKey => {
                  const score = getNormalizedScore(benchmarkId, metricKey)
                  const color = getColor(score)
                  const opacity = getOpacity(score)
                  const value = comparison.data[benchmarkId]?.[metricKey]?.mean || 0

                  return (
                    <div
                      key={metricKey}
                      className="flex-1 group relative"
                    >
                      <div
                        className={`${color} h-12 rounded flex items-center justify-center text-xs font-bold text-white transition-all hover:scale-105 cursor-pointer`}
                        style={{ opacity }}
                      >
                        {score.toFixed(0)}
                      </div>
                      {/* Tooltip on hover */}
                      <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-2 bg-black border border-white/20 rounded-lg text-xs text-white whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
                        <div className="font-bold">{metricKey.replace(/_/g, ' ')}</div>
                        <div className="text-gray-400">Value: {value.toFixed(2)}</div>
                        <div className="text-gray-400">Score: {score.toFixed(1)}%</div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>

        {/* Legend */}
        <div className="mt-6 flex items-center justify-center gap-4 text-xs">
          <span className="text-gray-400">Performance Score:</span>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-red-400 rounded"></div>
            <span className="text-gray-400">Poor</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-yellow-400 rounded"></div>
            <span className="text-gray-400">Fair</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-green-400 rounded"></div>
            <span className="text-gray-400">Good</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-green-500 rounded"></div>
            <span className="text-gray-400">Excellent</span>
          </div>
        </div>
      </div>
    </div>
  )
}
