'use client'

import { Radar, RadarChart as RechartsRadar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, Legend, Tooltip } from 'recharts'
import { ComparisonResult } from '@/lib/types'

interface RadarChartProps {
  comparison: ComparisonResult
  metrics: string[]
}

export function RadarChart({ comparison, metrics }: RadarChartProps) {
  if (!comparison || !comparison.benchmarks || !comparison.data) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        No comparison data available
      </div>
    )
  }

  // Normalize data to 0-100 scale for radar visualization
  const normalizeValue = (value: number, metricKey: string) => {
    // Get all values for this metric across benchmarks
    const allValues = comparison.benchmarks.map(id => {
      const metricData = comparison.data[id]?.[metricKey]
      return metricData?.mean || 0
    })
    const max = Math.max(...allValues)
    const min = Math.min(...allValues)

    if (max === min) return 50

    // For latency metrics, lower is better (invert scale)
    const isLatencyMetric = metricKey.includes('latency') || metricKey.includes('ttft')
    if (isLatencyMetric) {
      return ((max - value) / (max - min)) * 100
    }

    // For throughput/goodput, higher is better
    return ((value - min) / (max - min)) * 100
  }

  // Transform data for radar chart
  const data = metrics.map(metricKey => {
    const metricLabel = metricKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
    const point: any = { metric: metricLabel }

    comparison.benchmarks.forEach(benchmarkId => {
      const metricData = comparison.data[benchmarkId]?.[metricKey]
      const value = metricData?.mean || 0
      point[benchmarkId] = normalizeValue(value, metricKey)
    })

    return point
  })

  const colors = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899']

  return (
    <ResponsiveContainer width="100%" height="100%">
      <RechartsRadar data={data}>
        <PolarGrid stroke="#333" />
        <PolarAngleAxis
          dataKey="metric"
          stroke="#999"
          tick={{ fill: '#999', fontSize: 12 }}
        />
        <PolarRadiusAxis
          angle={90}
          domain={[0, 100]}
          stroke="#666"
          tick={{ fill: '#666' }}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: '#1a1a1a',
            border: '1px solid #333',
            borderRadius: '8px',
          }}
          labelStyle={{ color: '#76b900' }}
          formatter={(value: number) => `${value.toFixed(1)}%`}
        />
        <Legend
          wrapperStyle={{ paddingTop: '20px' }}
          formatter={(value) => value.substring(0, 25) + '...'}
        />
        {comparison.benchmarks.map((benchmarkId, idx) => (
          <Radar
            key={benchmarkId}
            name={benchmarkId}
            dataKey={benchmarkId}
            stroke={colors[idx % colors.length]}
            fill={colors[idx % colors.length]}
            fillOpacity={0.25}
            strokeWidth={2}
          />
        ))}
      </RechartsRadar>
    </ResponsiveContainer>
  )
}
