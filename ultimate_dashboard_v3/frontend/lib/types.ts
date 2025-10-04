/**
 * TypeScript types for AIPerf Dashboard
 */

export interface Benchmark {
  id: string
  name: string
  timestamp: string
  summary: {
    total_requests?: number
    avg_latency?: number
    throughput?: number
    goodput?: number
  }
  metadata?: Record<string, any>
  statistics?: BenchmarkStatistics
}

export interface BenchmarkStatistics {
  [metric: string]: MetricStats
}

export interface MetricStats {
  count: number
  mean: number
  std: number
  min: number
  max: number
  p1: number
  p5: number
  p25: number
  p50: number
  p75: number
  p90: number
  p95: number
  p99: number
}

export interface BenchmarkData {
  id: string
  metadata: Record<string, any>
  records: BenchmarkRecord[]
  aggregate: Record<string, any>
  statistics: BenchmarkStatistics
}

export interface BenchmarkRecord {
  metadata: {
    x_request_id: string
    timestamp_ns: number
    worker_id: string
    record_processor_id: string
    credit_phase: string
  }
  metrics: Record<string, MetricValue>
  error?: string | null
}

export interface MetricValue {
  value: number | number[]
  unit: string
}

export interface ComparisonResult {
  benchmarks: string[]
  metrics: string[]
  data: Record<string, Record<string, MetricStats>>
  analysis: ComparisonAnalysis
}

export interface ComparisonAnalysis {
  [metric: string]: {
    best: { benchmark: string; value: number }
    worst: { benchmark: string; value: number }
    spread: number
    relative_diff: number
  }
}

export interface AIInsights {
  summary: string
  key_findings: Finding[]
  recommendations: Recommendation[]
  alerts: Alert[]
  score: number
  trends?: TrendData
  context?: ContextData
}

export interface Finding {
  type: 'error' | 'warning' | 'info' | 'success'
  metric: string
  message: string
  severity: 'high' | 'medium' | 'low'
}

export interface Recommendation {
  category: string
  title: string
  description: string
  priority: 'high' | 'medium' | 'low'
}

export interface Alert {
  type: string
  message: string
  severity: 'high' | 'medium' | 'low'
  action_required: boolean
}

export interface TrendData {
  direction: string
  confidence: number
  prediction: string
}

export interface ContextData {
  industry_benchmark: string
  recommendations_count: number
  critical_issues: number
}

export interface LeaderboardEntry {
  benchmark_id: string
  score: number
  key_metrics: {
    throughput: number
    latency_p50: number
    latency_p99: number
  }
}

export interface TrendPoint {
  timestamp: string
  benchmark_id: string
  value: number
}

export interface UploadProgress {
  percent: number
  status: 'idle' | 'uploading' | 'processing' | 'complete' | 'error'
  message?: string
}
