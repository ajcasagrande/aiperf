'use client'

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { BenchmarkRecord } from '@/lib/types'

interface LatencyChartProps {
  records: BenchmarkRecord[]
}

export function LatencyChart({ records }: LatencyChartProps) {
  // Guard against undefined/empty records
  if (!records || records.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        No latency data available
      </div>
    )
  }

  // Process data for chart
  const data = records
    .slice(0, 100) // Limit to first 100 points for performance
    .map((record, index) => ({
      index,
      latency: record.metrics?.request_latency?.value || 0,
      ttft: record.metrics?.ttft?.value || 0,
      itl: record.metrics?.inter_token_latency?.value || 0,
    }))

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#333" />
        <XAxis
          dataKey="index"
          stroke="#666"
          label={{ value: 'Request Index', position: 'insideBottom', offset: -5, fill: '#999' }}
        />
        <YAxis
          stroke="#666"
          label={{ value: 'Latency (ms)', angle: -90, position: 'insideLeft', fill: '#999' }}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: '#1a1a1a',
            border: '1px solid #333',
            borderRadius: '8px',
          }}
          labelStyle={{ color: '#999' }}
        />
        <Legend />
        <Line
          type="monotone"
          dataKey="latency"
          name="Request Latency"
          stroke="#3b82f6"
          strokeWidth={2}
          dot={false}
        />
        <Line
          type="monotone"
          dataKey="ttft"
          name="TTFT"
          stroke="#10b981"
          strokeWidth={2}
          dot={false}
        />
        <Line
          type="monotone"
          dataKey="itl"
          name="Inter-Token Latency"
          stroke="#f59e0b"
          strokeWidth={2}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
