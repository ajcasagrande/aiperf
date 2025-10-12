/**
 * API Client for NVIDIA AIPerf Dashboard v3
 * Handles all backend communication
 */

import axios, { AxiosInstance } from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

class APIClient {
  private client: AxiosInstance

  constructor() {
    this.client = axios.create({
      baseURL: API_URL,
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 30000,
    })
  }

  // Health check
  async health() {
    const response = await this.client.get('/')
    return response.data
  }

  // List all benchmarks
  async listBenchmarks() {
    const response = await this.client.get('/api/v3/benchmarks')
    return response.data.benchmarks
  }

  // Get specific benchmark
  async getBenchmark(benchmarkId: string) {
    const response = await this.client.get(`/api/v3/benchmarks/${benchmarkId}`)
    return response.data
  }

  // Upload benchmark
  async uploadBenchmark(jsonlFile: File, aggregateFile?: File) {
    const formData = new FormData()
    formData.append('jsonl_file', jsonlFile)
    if (aggregateFile) {
      formData.append('aggregate_file', aggregateFile)
    }

    const response = await this.client.post('/api/v3/benchmarks/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        const percentCompleted = Math.round(
          (progressEvent.loaded * 100) / (progressEvent.total || 100)
        )
        console.log(`Upload progress: ${percentCompleted}%`)
      },
    })
    return response.data
  }

  // Compare benchmarks
  async compareBenchmarks(benchmarkIds: string[], metrics: string[]) {
    const response = await this.client.post('/api/v3/compare', {
      benchmark_ids: benchmarkIds,
      metrics: metrics,
    })
    return response.data.comparison
  }

  // Get AI insights
  async getInsights(benchmarkId: string, focusArea?: string) {
    const response = await this.client.post('/api/v3/insights', {
      benchmark_id: benchmarkId,
      focus_area: focusArea,
    })
    return response.data.insights
  }

  // Query metrics
  async queryMetrics(params: {
    metric?: string
    start_time?: number
    end_time?: number
    filters?: Record<string, any>
  }) {
    const response = await this.client.post('/api/v3/query', params)
    return response.data
  }

  // Get summary stats
  async getSummaryStats() {
    const response = await this.client.get('/api/v3/stats/summary')
    return response.data
  }

  // Export data
  async exportBenchmark(benchmarkId: string, format: 'json' | 'csv' | 'parquet') {
    const response = await this.client.get(`/api/v3/export/${benchmarkId}/${format}`)
    return response.data
  }

  // Get leaderboard
  async getLeaderboard() {
    const response = await this.client.get('/api/v3/leaderboard')
    return response.data
  }

  // Get trends
  async getTrends(metric: string, window: number = 30) {
    const response = await this.client.get(`/api/v3/trends/${metric}`, {
      params: { window },
    })
    return response.data
  }

  // Run benchmark
  async runBenchmark(config: {
    model: string
    url?: string
    endpoint_type?: string
    custom_endpoint?: string
    concurrency?: number
    request_rate?: number
    request_count?: number
    input_tokens?: number
    output_tokens?: number
  }) {
    const response = await this.client.post('/api/v3/benchmarks/run', config)
    return response.data
  }

  // List active benchmark runs
  async listActiveRuns() {
    const response = await this.client.get('/api/v3/benchmarks/runs/active')
    return response.data.active_runs
  }

  // Stop a running benchmark
  async stopBenchmark(benchmarkId: string) {
    const response = await this.client.post(`/api/v3/benchmarks/runs/${benchmarkId}/stop`)
    return response.data
  }

  // Save configuration
  async saveConfig(name: string, config: any) {
    const response = await this.client.post('/api/v3/configs/save', { name, config })
    return response.data
  }

  // List saved configurations
  async listConfigs() {
    const response = await this.client.get('/api/v3/configs')
    return response.data.configs
  }

  // Delete configuration
  async deleteConfig(name: string) {
    const response = await this.client.delete(`/api/v3/configs/${name}`)
    return response.data
  }

  // Get traces
  async getTraces(
    benchmarkId: string,
    params?: {
      limit?: number
      offset?: number
      search?: string
      min_latency?: number
      max_latency?: number
      has_error?: boolean
    }
  ) {
    const response = await this.client.get(`/api/v3/benchmarks/${benchmarkId}/traces`, { params })
    return response.data.traces
  }

  // Get trace detail
  async getTraceDetail(benchmarkId: string, requestId: string) {
    const response = await this.client.get(`/api/v3/benchmarks/${benchmarkId}/traces/${requestId}`)
    return response.data
  }

  // Get error traces
  async getErrorTraces(benchmarkId: string) {
    const response = await this.client.get(`/api/v3/benchmarks/${benchmarkId}/traces/errors`)
    return response.data.errors
  }

  // Export traces
  async exportTraces(benchmarkId: string, format: string = 'json') {
    const response = await this.client.get(`/api/v3/benchmarks/${benchmarkId}/traces/export`, {
      params: { format }
    })
    return response.data
  }

  // WebSocket connection
  createWebSocket() {
    const wsUrl = API_URL.replace('http', 'ws') + '/ws/realtime'
    return new WebSocket(wsUrl)
  }
}

export const apiClient = new APIClient()
export default apiClient
