'use client'

import { useMemo } from 'react'

interface TimelineChartProps {
  traces: any[]
}

export default function TimelineChart({ traces }: TimelineChartProps) {
  const timelineData = useMemo(() => {
    if (!traces || traces.length === 0) return { events: [], maxTime: 0, minTime: 0 }

    const allEvents: any[] = []

    traces.forEach((trace) => {
      const metadata = trace.metadata || {}
      const metrics = trace.metrics || {}
      const baseTime = metadata.timestamp_ns || 0
      const requestId = metadata.x_request_id || 'unknown'

      // Request start
      allEvents.push({
        type: 'request_start',
        requestId,
        time: baseTime / 1_000_000, // Convert to ms
        label: 'Request Start',
        color: '#76b900',
      })

      // TTFT
      if (metrics.ttft?.value) {
        allEvents.push({
          type: 'ttft',
          requestId,
          time: (baseTime / 1_000_000) + metrics.ttft.value,
          label: 'First Token',
          color: '#f9ca24',
        })
      }

      // Request complete
      if (metrics.request_latency?.value) {
        allEvents.push({
          type: 'request_complete',
          requestId,
          time: (baseTime / 1_000_000) + metrics.request_latency.value,
          label: 'Complete',
          color: metadata.error ? '#ff6b6b' : '#1dd1a1',
        })
      }
    })

    allEvents.sort((a, b) => a.time - b.time)

    const times = allEvents.map(e => e.time)
    const minTime = Math.min(...times)
    const maxTime = Math.max(...times)

    return { events: allEvents, maxTime, minTime }
  }, [traces])

  if (traces.length === 0) {
    return (
      <div className="flex items-center justify-center h-96 text-gray-400">
        No traces available
      </div>
    )
  }

  const { events, maxTime, minTime } = timelineData
  const duration = maxTime - minTime

  return (
    <div className="w-full">
      {/* Timeline header */}
      <div className="mb-4">
        <h3 className="text-lg font-bold text-white mb-2">Request Lifecycle Timeline</h3>
        <div className="text-sm text-gray-400">
          Total duration: {duration.toFixed(2)}ms • {events.length} events • {traces.length} requests
        </div>
      </div>

      {/* Timeline visualization */}
      <div className="relative bg-black/30 rounded-xl p-6 overflow-auto" style={{ maxHeight: '600px' }}>
        {/* Time axis */}
        <div className="flex justify-between mb-4 text-xs font-mono text-gray-500">
          <span>{minTime.toFixed(0)}ms</span>
          <span>{((minTime + maxTime) / 2).toFixed(0)}ms</span>
          <span>{maxTime.toFixed(0)}ms</span>
        </div>

        {/* Events */}
        <div className="relative h-96">
          {/* Timeline line */}
          <div className="absolute top-0 bottom-0 left-0 right-0 flex items-center">
            <div className="w-full h-0.5 bg-white/10"></div>
          </div>

          {/* Event markers */}
          {events.map((event, idx) => {
            const position = ((event.time - minTime) / duration) * 100

            return (
              <div
                key={idx}
                className="absolute"
                style={{
                  left: `${position}%`,
                  top: `${(idx % 20) * 20}px`, // Stagger vertically to prevent overlap
                }}
              >
                {/* Event dot */}
                <div
                  className="w-3 h-3 rounded-full border-2 border-white/20 cursor-pointer hover:scale-150 transition-transform"
                  style={{ backgroundColor: event.color }}
                  title={`${event.label} - ${event.requestId} @ ${event.time.toFixed(2)}ms`}
                />

                {/* Event label (show first/last and errors) */}
                {(idx < 3 || idx > events.length - 3 || event.type === 'request_complete' && event.color === '#ff6b6b') && (
                  <div
                    className="absolute top-4 left-0 text-xs whitespace-nowrap bg-black/80 px-2 py-1 rounded border border-white/10"
                    style={{ transform: 'translateX(-50%)' }}
                  >
                    <div className="font-mono text-white">{event.requestId.substring(0, 8)}</div>
                    <div className="text-gray-400">{event.label}</div>
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Legend */}
        <div className="flex items-center gap-6 mt-8 pt-4 border-t border-white/10">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: '#76b900' }}></div>
            <span className="text-xs text-gray-400">Request Start</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: '#f9ca24' }}></div>
            <span className="text-xs text-gray-400">First Token</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: '#1dd1a1' }}></div>
            <span className="text-xs text-gray-400">Success</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: '#ff6b6b' }}></div>
            <span className="text-xs text-gray-400">Error</span>
          </div>
        </div>
      </div>
    </div>
  )
}
