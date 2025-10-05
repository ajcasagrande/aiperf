'use client'

import { useMemo } from 'react'

interface WaterfallChartProps {
  traces: any[]
}

export default function WaterfallChart({ traces }: WaterfallChartProps) {
  const chartData = useMemo(() => {
    if (!traces || traces.length === 0) return { bars: [], maxTime: 0 }

    // Sort by timestamp
    const sorted = [...traces].sort((a, b) => {
      const aTime = a.metadata?.timestamp_ns || 0
      const bTime = b.metadata?.timestamp_ns || 0
      return aTime - bTime
    })

    const firstTimestamp = sorted[0]?.metadata?.timestamp_ns || 0

    const bars = sorted.map((trace, idx) => {
      const metadata = trace.metadata || {}
      const metrics = trace.metrics || {}

      const startTime = ((metadata.timestamp_ns || 0) - firstTimestamp) / 1_000_000 // Convert to ms
      const ttft = metrics.ttft?.value || 0
      const latency = metrics.request_latency?.value || 0
      const hasError = metadata.error !== undefined

      return {
        index: idx,
        requestId: metadata.x_request_id || `req_${idx}`,
        workerId: metadata.worker_id || 'unknown',
        startTime,
        ttft,
        latency,
        endTime: startTime + latency,
        hasError,
      }
    })

    const maxTime = Math.max(...bars.map(b => b.endTime))

    return { bars, maxTime }
  }, [traces])

  if (traces.length === 0) {
    return (
      <div className="flex items-center justify-center h-96 text-gray-400">
        No traces available
      </div>
    )
  }

  const { bars, maxTime } = chartData
  const barHeight = 24
  const spacing = 4
  const totalHeight = bars.length * (barHeight + spacing)

  return (
    <div className="w-full overflow-auto">
      <div className="min-w-[800px]">
        {/* Time axis */}
        <div className="flex items-center gap-2 mb-2 px-32">
          <div className="flex-1 flex justify-between text-xs text-gray-400 font-mono">
            <span>0ms</span>
            <span>{(maxTime / 4).toFixed(0)}ms</span>
            <span>{(maxTime / 2).toFixed(0)}ms</span>
            <span>{(3 * maxTime / 4).toFixed(0)}ms</span>
            <span>{maxTime.toFixed(0)}ms</span>
          </div>
        </div>

        {/* Waterfall */}
        <div style={{ height: totalHeight }}>
          {bars.map((bar, idx) => {
            const startPercent = (bar.startTime / maxTime) * 100
            const widthPercent = (bar.latency / maxTime) * 100
            const ttftPercent = (bar.ttft / maxTime) * 100

            return (
              <div
                key={bar.requestId}
                className="flex items-center gap-2 mb-1"
                style={{ height: barHeight }}
              >
                {/* Request ID */}
                <div className="w-28 text-xs font-mono text-gray-400 truncate">
                  {bar.requestId.substring(0, 12)}
                </div>

                {/* Worker ID */}
                <div className="w-20 text-xs text-gray-500 truncate">
                  {bar.workerId}
                </div>

                {/* Bar container */}
                <div className="flex-1 relative bg-white/5 rounded" style={{ height: barHeight }}>
                  {/* Full request bar */}
                  <div
                    className={`absolute h-full rounded transition-all ${
                      bar.hasError ? 'bg-red-500/40 border border-red-500/60' : 'bg-nvidia-green/40 border border-nvidia-green/60'
                    }`}
                    style={{
                      left: `${startPercent}%`,
                      width: `${widthPercent}%`,
                    }}
                  >
                    {/* TTFT marker */}
                    {bar.ttft > 0 && (
                      <div
                        className="absolute h-full w-1 bg-yellow-400/80"
                        style={{
                          left: `${(bar.ttft / bar.latency) * 100}%`,
                        }}
                        title={`TTFT: ${bar.ttft.toFixed(2)}ms`}
                      />
                    )}
                  </div>
                </div>

                {/* Latency label */}
                <div className="w-24 text-xs text-right font-mono text-white">
                  {bar.latency.toFixed(2)}ms
                </div>
              </div>
            )
          })}
        </div>

        {/* Legend */}
        <div className="flex items-center gap-6 mt-6 px-4 py-3 bg-black/30 rounded-lg">
          <div className="flex items-center gap-2">
            <div className="w-8 h-4 bg-nvidia-green/40 border border-nvidia-green/60 rounded"></div>
            <span className="text-xs text-gray-400">Successful Request</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-8 h-4 bg-red-500/40 border border-red-500/60 rounded"></div>
            <span className="text-xs text-gray-400">Failed Request</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-1 h-4 bg-yellow-400/80"></div>
            <span className="text-xs text-gray-400">Time to First Token</span>
          </div>
        </div>
      </div>
    </div>
  )
}
