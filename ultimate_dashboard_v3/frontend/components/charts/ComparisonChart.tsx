'use client'

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { ComparisonResult } from '@/lib/types'

interface ComparisonChartProps {
  comparison: ComparisonResult
  metric: string
}

export function ComparisonChart({ comparison, metric }: ComparisonChartProps) {
  // Guard against undefined/invalid comparison data
  if (!comparison || !comparison.benchmarks || !comparison.data) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        No comparison data available
      </div>
    )
  }

  // Transform comparison data for chart
  const data = comparison.benchmarks.map((benchmarkId) => {
    const metricData = comparison.data[benchmarkId]?.[metric]

    // Check if this is an aggregate metric (no percentiles, only mean)
    const hasPercentiles = (metricData?.p50 || 0) > 0 ||
                           (metricData?.p90 || 0) > 0 ||
                           (metricData?.p99 || 0) > 0

    if (hasPercentiles) {
      // Use percentiles for record-level metrics
      return {
        name: benchmarkId.substring(0, 20), // Truncate long IDs
        p50: metricData?.p50 || 0,
        p90: metricData?.p90 || 0,
        p99: metricData?.p99 || 0,
      }
    } else {
      // For aggregate metrics (throughput, goodput), use mean value
      const meanValue = metricData?.mean || 0
      return {
        name: benchmarkId.substring(0, 20),
        p50: meanValue,
        p90: meanValue,
        p99: meanValue,
      }
    }
  })

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#333" />
        <XAxis dataKey="name" stroke="#666" angle={-45} textAnchor="end" height={80} />
        <YAxis
          stroke="#666"
          label={{ value: metric, angle: -90, position: 'insideLeft', fill: '#999' }}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: '#1a1a1a',
            border: '1px solid #333',
            borderRadius: '8px',
          }}
          labelStyle={{ color: '#999' }}
          formatter={(value: number) => value.toFixed(2)}
        />
        <Legend />
        <Bar dataKey="p50" name="P50" fill="#10b981" radius={[4, 4, 0, 0]} />
        <Bar dataKey="p90" name="P90" fill="#f59e0b" radius={[4, 4, 0, 0]} />
        <Bar dataKey="p99" name="P99" fill="#ef4444" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
