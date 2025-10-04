'use client'

import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { BenchmarkRecord } from '@/lib/types'

interface ThroughputChartProps {
  records: BenchmarkRecord[]
}

export function ThroughputChart({ records }: ThroughputChartProps) {
  // Guard against undefined/empty records
  if (!records || records.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        No throughput data available
      </div>
    )
  }

  // Calculate rolling throughput
  const windowSize = 10
  const data = []

  for (let i = windowSize; i < Math.min(records.length, 200); i++) {
    const windowRecords = records.slice(i - windowSize, i)
    const startTime = windowRecords[0]?.metadata?.timestamp_ns || 0
    const endTime = windowRecords[windowRecords.length - 1]?.metadata?.timestamp_ns || 0
    const duration = (endTime - startTime) / 1e9 // Convert to seconds

    const throughput = duration > 0 ? windowSize / duration : 0

    // Calculate token throughput
    const totalTokens = windowRecords.reduce((sum, r) => {
      const osl = r?.metrics?.output_sequence_length?.value || 0
      return sum + (typeof osl === 'number' ? osl : 0)
    }, 0)
    const tokenThroughput = duration > 0 ? totalTokens / duration : 0

    data.push({
      index: i,
      requestThroughput: throughput,
      tokenThroughput: tokenThroughput,
    })
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data}>
        <defs>
          <linearGradient id="colorRequest" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#76B900" stopOpacity={0.8} />
            <stop offset="95%" stopColor="#76B900" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="colorToken" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.8} />
            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#333" />
        <XAxis
          dataKey="index"
          stroke="#666"
          label={{ value: 'Request Index', position: 'insideBottom', offset: -5, fill: '#999' }}
        />
        <YAxis
          yAxisId="left"
          stroke="#666"
          label={{ value: 'Requests/s', angle: -90, position: 'insideLeft', fill: '#999' }}
        />
        <YAxis
          yAxisId="right"
          orientation="right"
          stroke="#666"
          label={{ value: 'Tokens/s', angle: 90, position: 'insideRight', fill: '#999' }}
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
        <Area
          yAxisId="left"
          type="monotone"
          dataKey="requestThroughput"
          name="Request Throughput"
          stroke="#76B900"
          fillOpacity={1}
          fill="url(#colorRequest)"
        />
        <Area
          yAxisId="right"
          type="monotone"
          dataKey="tokenThroughput"
          name="Token Throughput"
          stroke="#3b82f6"
          fillOpacity={1}
          fill="url(#colorToken)"
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
