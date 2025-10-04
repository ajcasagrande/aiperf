'use client'

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { MetricStats } from '@/lib/types'

interface DistributionChartProps {
  stats: MetricStats
  metricName: string
}

export function DistributionChart({ stats, metricName }: DistributionChartProps) {
  // Guard against undefined/invalid stats
  if (!stats) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        No distribution data available
      </div>
    )
  }

  const data = [
    { name: 'Min', value: stats.min || 0 },
    { name: 'P25', value: stats.p25 || 0 },
    { name: 'P50', value: stats.p50 || 0 },
    { name: 'P75', value: stats.p75 || 0 },
    { name: 'P90', value: stats.p90 || 0 },
    { name: 'P95', value: stats.p95 || 0 },
    { name: 'P99', value: stats.p99 || 0 },
    { name: 'Max', value: stats.max || 0 },
  ]

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#333" />
        <XAxis dataKey="name" stroke="#666" />
        <YAxis
          stroke="#666"
          label={{ value: metricName, angle: -90, position: 'insideLeft', fill: '#999' }}
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
        <Bar dataKey="value" fill="#76B900" radius={[8, 8, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
