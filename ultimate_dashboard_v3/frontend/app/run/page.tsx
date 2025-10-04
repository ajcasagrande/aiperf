'use client'

import { useState, useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import { Play, Square, Zap, Server, Activity, TrendingUp, Clock, CheckCircle, XCircle, Terminal as TerminalIcon, Save, FolderOpen, Trash2 } from 'lucide-react'
import { apiClient } from '@/lib/api'
import toast from 'react-hot-toast'
import dynamic from 'next/dynamic'

// Dynamically import TerminalViewer to avoid SSR issues
const TerminalViewer = dynamic(() => import('@/components/TerminalViewer'), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-full bg-black/50 border border-white/10 rounded-lg">
      <div className="text-gray-400">Loading terminal...</div>
    </div>
  ),
})

export default function RunBenchmarkPage() {
  const [isRunning, setIsRunning] = useState(false)
  const [benchmarkId, setBenchmarkId] = useState<string | null>(null)
  const [status, setStatus] = useState<'idle' | 'starting' | 'running' | 'completed' | 'failed' | 'stopped'>('idle')
  const [metrics, setMetrics] = useState<any>({})
  const [interactiveMode, setInteractiveMode] = useState(true)
  const [configExpanded, setConfigExpanded] = useState(true)
  const [savedConfigs, setSavedConfigs] = useState<any[]>([])
  const [showSaveDialog, setShowSaveDialog] = useState(false)
  const [showLoadDialog, setShowLoadDialog] = useState(false)
  const [configName, setConfigName] = useState('')
  const wsRef = useRef<WebSocket | null>(null)
  const benchmarkIdRef = useRef<string | null>(null)

  // Form state
  const [config, setConfig] = useState({
    model: 'openai/gpt-oss-20b',
    url: 'http://localhost:9000',
    endpoint_type: 'chat' as 'chat' | 'completions' | 'embeddings' | 'rankings' | 'responses',
    custom_endpoint: false,
    custom_endpoint_path: '',
    concurrency: 10,
    request_rate: undefined as number | undefined,
    request_count: 100,
    input_tokens: 256,
    output_tokens: 128,
    num_workers: 10,
    max_tokens: undefined as number | undefined,
    streaming: true,
  })

  // WebSocket connection - connect early and keep alive
  useEffect(() => {
    console.log('Setting up WebSocket connection')
    const ws = apiClient.createWebSocket()
    let reconnectAttempts = 0
    const maxReconnectAttempts = 3
    let reconnectTimeout: NodeJS.Timeout

    ws.onopen = () => {
      console.log('✓ WebSocket connected')
      wsRef.current = ws
      reconnectAttempts = 0

      // Subscribe to benchmark if one is running
      if (benchmarkId) {
        console.log('Subscribing to benchmark:', benchmarkId)
        ws.send(JSON.stringify({
          type: 'subscribe',
          benchmark_id: benchmarkId
        }))
      }
    }

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)

      if (data.benchmark_id === benchmarkIdRef.current || !data.benchmark_id) {
        // Update status
        if (data.status) {
          setStatus(data.status)
        }

        // Write ANSI data to terminal
        if (data.ansi_data) {
          const terminal = (window as any).xterm

          if (terminal) {
            try {
              terminal.write(data.ansi_data)
            } catch (e) {
              console.error('Failed to write to terminal:', e)
            }
          } else {
            // Queue data for when terminal is ready
            if (!(window as any).xtermQueue) {
              (window as any).xtermQueue = []
            }
            (window as any).xtermQueue.push(data.ansi_data)
          }
        }

        // Handle old format (fallback)
        if (data.output && (window as any).xterm) {
          const terminal = (window as any).xterm
          try {
            terminal.write(data.output + '\r\n')
          } catch (e) {
            console.warn('Failed to write output:', e)
          }
        }

        if (data.message && !data.ansi_data && (window as any).xterm) {
          const terminal = (window as any).xterm
          const statusColor =
            data.status === 'completed' ? '\x1b[32m' :
            data.status === 'failed' || data.status === 'error' ? '\x1b[31m' :
            data.status === 'running' ? '\x1b[36m' : '\x1b[37m'
          try {
            terminal.write(`${statusColor}[${data.status?.toUpperCase()}]\x1b[0m ${data.message}\r\n`)
          } catch (e) {
            console.warn('Failed to write message:', e)
          }
        }

        // Handle completion
        if (data.status === 'completed') {
          setIsRunning(false)
          toast.success('Benchmark completed successfully!')
        } else if (data.status === 'failed' || data.status === 'error') {
          setIsRunning(false)
          toast.error('Benchmark failed')
        }
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)

      // Only show toast if benchmark is running (not on initial connection failure)
      if (isRunning && benchmarkId) {
        toast.error('Connection lost. Attempting to reconnect...')
      }
    }

    ws.onclose = (event) => {
      console.log('WebSocket disconnected:', event.code, event.reason)
      wsRef.current = null

      // Attempt to reconnect if benchmark is still running
      if (isRunning && reconnectAttempts < maxReconnectAttempts) {
        reconnectAttempts++
        console.log(`Reconnection attempt ${reconnectAttempts}/${maxReconnectAttempts}`)

        reconnectTimeout = setTimeout(() => {
          console.log('Attempting to reconnect...')
          // Trigger re-render to reconnect
          setStatus((prev) => prev)
        }, 2000 * reconnectAttempts) // Exponential backoff
      } else if (reconnectAttempts >= maxReconnectAttempts) {
        toast.error('Connection lost. Please refresh the page.')
      }
    }

    return () => {
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout)
      }
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close()
      }
      wsRef.current = null
    }
  }, []) // Empty deps - connect once on mount

  // Subscribe to benchmark when ID becomes available
  useEffect(() => {
    if (benchmarkId && wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      console.log('Subscribing to benchmark:', benchmarkId)
      wsRef.current.send(JSON.stringify({
        type: 'subscribe',
        benchmark_id: benchmarkId
      }))
    }
  }, [benchmarkId])

  // Load saved configs on mount
  useEffect(() => {
    loadSavedConfigs()
  }, [])

  const loadSavedConfigs = async () => {
    try {
      const configs = await apiClient.listConfigs()
      setSavedConfigs(configs)
    } catch (error) {
      console.error('Failed to load configs:', error)
    }
  }

  const handleSaveConfig = async () => {
    if (!configName.trim()) {
      toast.error('Please enter a config name')
      return
    }

    try {
      await apiClient.saveConfig(configName, config)
      toast.success(`Configuration '${configName}' saved`)
      setShowSaveDialog(false)
      setConfigName('')
      loadSavedConfigs()
    } catch (error: any) {
      toast.error('Failed to save configuration')
    }
  }

  const handleLoadConfig = (savedConfig: any) => {
    setConfig(savedConfig.config)
    setShowLoadDialog(false)
    toast.success(`Loaded configuration '${savedConfig.name}'`)
  }

  const handleDeleteConfig = async (name: string) => {
    try {
      await apiClient.deleteConfig(name)
      toast.success(`Deleted configuration '${name}'`)
      loadSavedConfigs()
    } catch (error: any) {
      toast.error('Failed to delete configuration')
    }
  }

  // Handle terminal resize
  const handleTerminalResize = (rows: number, cols: number) => {
    if (wsRef.current && benchmarkId && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(JSON.stringify({
          type: 'resize',
          benchmark_id: benchmarkId,
          rows,
          cols,
        }))
        console.log(`✓ Sent terminal resize: ${rows}x${cols}`)
      } catch (error) {
        console.warn('Failed to send resize:', error)
      }
    }
  }

  // Handle terminal input (keyboard and mouse) - only if interactive mode enabled
  const handleTerminalInput = (data: string) => {
    if (!interactiveMode) {
      console.log('⚠️  Interactive mode disabled, ignoring input')
      return
    }

    if (wsRef.current && benchmarkId && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(JSON.stringify({
          type: 'input',
          benchmark_id: benchmarkId,
          data: data,
        }))
      } catch (error) {
        console.warn('Failed to send input:', error)
      }
    } else if (benchmarkId) {
      console.warn('Cannot send input: WebSocket not connected')
    }
  }

  const handleStart = async () => {
    try {
      setIsRunning(true)
      setStatus('starting')
      setConfigExpanded(false) // Collapse config when starting

      // DON'T clear terminal - let ANSI codes from aiperf handle display
      if ((window as any).xterm) {
        const terminal = (window as any).xterm
        try {
          console.log('📝 Terminal ready for benchmark output')
        } catch (e) {
          console.warn('Terminal check failed:', e)
        }
      }

      // Construct API payload
      const payload = {
        model: config.model,
        url: config.url,
        endpoint_type: config.endpoint_type,
        ...(config.custom_endpoint && { custom_endpoint: config.custom_endpoint_path }),
        concurrency: config.concurrency,
        request_rate: config.request_rate,
        request_count: config.request_count,
        input_tokens: config.input_tokens,
        output_tokens: config.output_tokens,
        num_workers: config.num_workers,
        ...(config.max_tokens && { max_tokens: config.max_tokens }),
        streaming: config.streaming,
      }

      const result = await apiClient.runBenchmark(payload as any)

      setBenchmarkId(result.benchmark_id)
      benchmarkIdRef.current = result.benchmark_id

      if ((window as any).xterm) {
        const terminal = (window as any).xterm
        try {
          terminal.write(`\x1b[90mBenchmark ID: \x1b[37m${result.benchmark_id}\x1b[0m\r\n`)
          terminal.write('\r\n')
          // Focus terminal for immediate interaction
          terminal.focus()
        } catch (e) {
          console.warn('Failed to write to terminal:', e)
        }
      }

      toast.success('Benchmark started!')
    } catch (error: any) {
      console.error('Failed to start benchmark:', error)
      toast.error(`Failed to start: ${error.message}`)
      setIsRunning(false)
      setStatus('failed')

      if ((window as any).xterm) {
        const terminal = (window as any).xterm
        terminal.write(`\x1b[31m✗ Failed to start: ${error.message}\x1b[0m\r\n`)
      }
    }
  }

  const handleStop = async () => {
    if (!benchmarkId) return

    try {
      await apiClient.stopBenchmark(benchmarkId)
      setIsRunning(false)
      setStatus('stopped')

      if ((window as any).xterm) {
        const terminal = (window as any).xterm
        terminal.writeln('\r\n\x1b[33m⏹  Benchmark stopped by user\x1b[0m')
      }

      toast.success('Benchmark stopped')
    } catch (error: any) {
      console.error('Failed to stop benchmark:', error)
      toast.error('Failed to stop benchmark')
    }
  }

  const getStatusIcon = () => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-6 h-6 text-green-400" />
      case 'failed':
      case 'stopped':
        return <XCircle className="w-6 h-6 text-red-400" />
      case 'running':
        return <Activity className="w-6 h-6 text-nvidia-green animate-pulse" />
      default:
        return <Activity className="w-6 h-6 text-gray-400" />
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-black via-nvidia-darkGray to-black p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <motion.div
          initial={{ y: -20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          className="mb-8"
        >
          <div className="flex items-center gap-4 mb-2">
            <div className="relative">
              <Play className="w-10 h-10 text-nvidia-green" />
              <motion.div
                animate={{ scale: [1, 1.2, 1] }}
                transition={{ duration: 2, repeat: Infinity }}
                className="absolute inset-0 bg-nvidia-green/20 rounded-full blur-xl"
              />
            </div>
            <div>
              <h1 className="text-4xl font-black bg-gradient-to-r from-nvidia-green to-green-400 bg-clip-text text-transparent">
                Run New Benchmark
              </h1>
              <p className="text-gray-400">Execute benchmarks and watch results in real-time</p>
            </div>
          </div>
        </motion.div>

        {/* Configuration Panel - Top */}
        <motion.div
          initial={{ y: -20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          className="bg-white/5 border border-white/10 rounded-2xl p-6 mb-8"
        >
            <div className="flex items-center justify-between mb-6">
              <button
                onClick={() => setConfigExpanded(!configExpanded)}
                className="flex items-center gap-2 hover:text-nvidia-green transition-colors"
              >
                <h2 className="text-2xl font-bold text-white flex items-center gap-2">
                  <Server className="w-6 h-6 text-nvidia-green" />
                  Benchmark Configuration
                  <span className="text-lg">{configExpanded ? '▼' : '▶'}</span>
                </h2>
              </button>
              <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold ${
                status === 'running' ? 'bg-nvidia-green/20 text-nvidia-green' :
                status === 'completed' ? 'bg-green-500/20 text-green-400' :
                status === 'failed' || status === 'stopped' ? 'bg-red-500/20 text-red-400' :
                'bg-gray-500/20 text-gray-400'
              }`}>
                {getStatusIcon()}
                <span>Status: {status.toUpperCase()}</span>
              </div>
            </div>

            {configExpanded && (
            <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Model */}
              <div>
                <label className="block text-sm font-semibold text-gray-400 mb-2">Model</label>
                <input
                  type="text"
                  value={config.model}
                  onChange={(e) => setConfig({ ...config, model: e.target.value })}
                  className="w-full px-4 py-3 bg-black/50 border border-white/10 rounded-lg text-white focus:border-nvidia-green focus:outline-none"
                  placeholder="gpt-3.5-turbo"
                  disabled={isRunning}
                />
              </div>

              {/* URL */}
              <div>
                <label className="block text-sm font-semibold text-gray-400 mb-2">Server URL</label>
                <input
                  type="text"
                  value={config.url}
                  onChange={(e) => setConfig({ ...config, url: e.target.value })}
                  className="w-full px-4 py-3 bg-black/50 border border-white/10 rounded-lg text-white focus:border-nvidia-green focus:outline-none"
                  placeholder="http://localhost:9000"
                  disabled={isRunning}
                />
              </div>

              {/* Endpoint Type */}
              <div>
                <label className="block text-sm font-semibold text-gray-400 mb-2">Endpoint Type</label>
                <select
                  value={config.endpoint_type}
                  onChange={(e) => setConfig({ ...config, endpoint_type: e.target.value as any })}
                  className="w-full px-4 py-3 bg-black/50 border border-white/10 rounded-lg text-white focus:border-nvidia-green focus:outline-none"
                  disabled={isRunning}
                >
                  <option value="chat">Chat</option>
                  <option value="completions">Completions</option>
                  <option value="embeddings">Embeddings</option>
                  <option value="rankings">Rankings</option>
                  <option value="responses">Responses</option>
                </select>
              </div>

              {/* Concurrency */}
              <div>
                <label className="block text-sm font-semibold text-gray-400 mb-2">Concurrency</label>
                <input
                  type="number"
                  value={config.concurrency}
                  onChange={(e) => setConfig({ ...config, concurrency: parseInt(e.target.value) })}
                  className="w-full px-4 py-3 bg-black/50 border border-white/10 rounded-lg text-white focus:border-nvidia-green focus:outline-none"
                  min={1}
                  disabled={isRunning}
                />
              </div>

              {/* Request Count */}
              <div>
                <label className="block text-sm font-semibold text-gray-400 mb-2">Request Count</label>
                <input
                  type="number"
                  value={config.request_count}
                  onChange={(e) => setConfig({ ...config, request_count: parseInt(e.target.value) })}
                  className="w-full px-4 py-3 bg-black/50 border border-white/10 rounded-lg text-white focus:border-nvidia-green focus:outline-none"
                  min={1}
                  disabled={isRunning}
                />
              </div>

              {/* Input Tokens */}
              <div>
                <label className="block text-sm font-semibold text-gray-400 mb-2">Input Tokens</label>
                <input
                  type="number"
                  value={config.input_tokens}
                  onChange={(e) => setConfig({ ...config, input_tokens: parseInt(e.target.value) })}
                  className="w-full px-4 py-3 bg-black/50 border border-white/10 rounded-lg text-white focus:border-nvidia-green focus:outline-none"
                  min={1}
                  disabled={isRunning}
                />
              </div>

              {/* Output Tokens */}
              <div>
                <label className="block text-sm font-semibold text-gray-400 mb-2">Output Tokens</label>
                <input
                  type="number"
                  value={config.output_tokens}
                  onChange={(e) => setConfig({ ...config, output_tokens: parseInt(e.target.value) })}
                  className="w-full px-4 py-3 bg-black/50 border border-white/10 rounded-lg text-white focus:border-nvidia-green focus:outline-none"
                  min={1}
                  disabled={isRunning}
                />
              </div>

              {/* Request Rate (Optional) */}
              <div>
                <label className="block text-sm font-semibold text-gray-400 mb-2">Request Rate (req/s)</label>
                <input
                  type="number"
                  value={config.request_rate || ''}
                  onChange={(e) => setConfig({ ...config, request_rate: e.target.value ? parseFloat(e.target.value) : undefined })}
                  className="w-full px-4 py-3 bg-black/50 border border-white/10 rounded-lg text-white focus:border-nvidia-green focus:outline-none"
                  placeholder="Optional"
                  min={0.1}
                  step={0.1}
                  disabled={isRunning}
                />
              </div>

              {/* Num Workers */}
              <div>
                <label className="block text-sm font-semibold text-gray-400 mb-2">Workers</label>
                <input
                  type="number"
                  value={config.num_workers}
                  onChange={(e) => setConfig({ ...config, num_workers: parseInt(e.target.value) })}
                  className="w-full px-4 py-3 bg-black/50 border border-white/10 rounded-lg text-white focus:border-nvidia-green focus:outline-none"
                  min={1}
                  disabled={isRunning}
                />
              </div>

              {/* Max Tokens (Optional) */}
              <div>
                <label className="block text-sm font-semibold text-gray-400 mb-2">Max Tokens</label>
                <input
                  type="number"
                  value={config.max_tokens || ''}
                  onChange={(e) => setConfig({ ...config, max_tokens: e.target.value ? parseInt(e.target.value) : undefined })}
                  className="w-full px-4 py-3 bg-black/50 border border-white/10 rounded-lg text-white focus:border-nvidia-green focus:outline-none"
                  placeholder="Optional"
                  min={1}
                  disabled={isRunning}
                />
              </div>

              {/* Streaming Toggle */}
              <div className="flex items-center">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={config.streaming}
                    onChange={(e) => setConfig({ ...config, streaming: e.target.checked })}
                    className="w-5 h-5 bg-black/50 border border-white/10 rounded text-nvidia-green focus:ring-nvidia-green"
                    disabled={isRunning}
                  />
                  <span className="text-sm font-semibold text-gray-300">Enable Streaming</span>
                </label>
              </div>
            </div>

            {/* Custom Endpoint - Full Width Row */}
            <div className="mt-4">
              <label className="flex items-center gap-2 cursor-pointer mb-2">
                <input
                  type="checkbox"
                  checked={config.custom_endpoint}
                  onChange={(e) => setConfig({ ...config, custom_endpoint: e.target.checked })}
                  className="w-4 h-4 bg-black/50 border border-white/10 rounded text-nvidia-green focus:ring-nvidia-green"
                  disabled={isRunning}
                />
                <span className="text-sm font-semibold text-gray-400">Use Custom Endpoint Path</span>
              </label>
              {config.custom_endpoint && (
                <input
                  type="text"
                  value={config.custom_endpoint_path}
                  onChange={(e) => setConfig({ ...config, custom_endpoint_path: e.target.value })}
                  className="w-full px-4 py-3 bg-black/50 border border-white/10 rounded-lg text-white focus:border-nvidia-green focus:outline-none"
                  placeholder="/v1/custom/endpoint"
                  disabled={isRunning}
                />
              )}
            </div>
            </>
            )}

            {/* Control Buttons */}
            <div className="mt-6 flex gap-3 justify-between">
              <div className="flex gap-3">
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={() => setShowSaveDialog(true)}
                  disabled={isRunning}
                  className="px-4 py-2 bg-white/5 border border-white/10 text-white rounded-lg flex items-center gap-2 hover:border-nvidia-green disabled:opacity-50"
                >
                  <Save className="w-4 h-4" />
                  Save Config
                </motion.button>
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={() => setShowLoadDialog(true)}
                  disabled={isRunning}
                  className="px-4 py-2 bg-white/5 border border-white/10 text-white rounded-lg flex items-center gap-2 hover:border-nvidia-green disabled:opacity-50"
                >
                  <FolderOpen className="w-4 h-4" />
                  Load Config
                </motion.button>
              </div>

              <div className="flex gap-3">
                {!isRunning ? (
                  <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={handleStart}
                    className="px-8 py-4 bg-gradient-to-r from-nvidia-green to-green-500 text-black font-bold rounded-xl shadow-lg shadow-nvidia-green/50 flex items-center justify-center gap-2"
                  >
                    <Play className="w-5 h-5" />
                    Start Benchmark
                  </motion.button>
                ) : (
                  <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={handleStop}
                    className="px-8 py-4 bg-gradient-to-r from-red-500 to-red-600 text-white font-bold rounded-xl shadow-lg flex items-center justify-center gap-2"
                  >
                    <Square className="w-5 h-5" />
                    Stop Benchmark
                  </motion.button>
                )}
              </div>
            </div>
        </motion.div>

        {/* Live Terminal Panel - Full Width Below */}
        <motion.div
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          className="bg-white/5 border border-white/10 rounded-2xl p-6 flex flex-col"
          style={{ height: 'calc(100vh - 400px)', minHeight: '500px' }}
        >
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-2xl font-bold text-white flex items-center gap-2">
              <TerminalIcon className="w-6 h-6 text-nvidia-green" />
              AIPerf Live Dashboard
            </h2>

            {/* Interactive Mode Toggle */}
            <label className={`flex items-center gap-3 px-4 py-3 rounded-lg cursor-pointer transition-all ${
              interactiveMode
                ? 'bg-nvidia-green/20 border-2 border-nvidia-green'
                : 'bg-black/30 border-2 border-white/10 hover:border-white/20'
            }`}>
              <input
                type="checkbox"
                checked={interactiveMode}
                onChange={(e) => setInteractiveMode(e.target.checked)}
                className="w-5 h-5 bg-black/50 border border-white/10 rounded text-nvidia-green focus:ring-nvidia-green"
                disabled={isRunning}
              />
              <div className="flex flex-col">
                <span className={`font-bold ${interactiveMode ? 'text-nvidia-green' : 'text-gray-300'}`}>
                  {interactiveMode ? '🎮 Interactive Terminal' : '📺 Read-Only Terminal'}
                </span>
                <span className="text-xs text-gray-400">
                  {interactiveMode ? 'Keyboard & mouse enabled' : 'Display only'}
                </span>
              </div>
            </label>
          </div>

          {/* Terminal Viewer - Full height */}
          <div className="flex-1 rounded-lg overflow-hidden border border-white/10">
            <TerminalViewer
              interactive={interactiveMode}
              onResize={handleTerminalResize}
              onData={interactiveMode ? handleTerminalInput : undefined}
            />
          </div>
        </motion.div>

        {/* Save Config Dialog */}
        {showSaveDialog && (
          <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50" onClick={() => setShowSaveDialog(false)}>
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-nvidia-darkGray border border-white/10 rounded-2xl p-6 w-full max-w-md"
            >
              <h3 className="text-2xl font-bold text-white mb-4">Save Configuration</h3>
              <input
                type="text"
                value={configName}
                onChange={(e) => setConfigName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSaveConfig()}
                placeholder="Enter config name..."
                className="w-full px-4 py-3 bg-black/50 border border-white/10 rounded-lg text-white focus:border-nvidia-green focus:outline-none mb-4"
                autoFocus
              />
              <div className="flex gap-3 justify-end">
                <button
                  onClick={() => setShowSaveDialog(false)}
                  className="px-4 py-2 bg-white/5 border border-white/10 text-gray-300 rounded-lg hover:border-white/20"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveConfig}
                  className="px-4 py-2 bg-nvidia-green text-black font-bold rounded-lg hover:bg-nvidia-green/80"
                >
                  Save
                </button>
              </div>
            </motion.div>
          </div>
        )}

        {/* Load Config Dialog */}
        {showLoadDialog && (
          <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50" onClick={() => setShowLoadDialog(false)}>
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-nvidia-darkGray border border-white/10 rounded-2xl p-6 w-full max-w-2xl max-h-[80vh] overflow-auto"
            >
              <h3 className="text-2xl font-bold text-white mb-4">Load Configuration</h3>
              {savedConfigs.length === 0 ? (
                <p className="text-gray-400 text-center py-8">No saved configurations found</p>
              ) : (
                <div className="space-y-2">
                  {savedConfigs.map((savedConfig) => (
                    <div
                      key={savedConfig.name}
                      className="flex items-center justify-between p-4 bg-black/30 border border-white/10 rounded-lg hover:border-nvidia-green/50 transition-colors"
                    >
                      <div className="flex-1">
                        <h4 className="font-bold text-white">{savedConfig.name}</h4>
                        <p className="text-sm text-gray-400">
                          {savedConfig.config.model} • Concurrency: {savedConfig.config.concurrency} • Requests: {savedConfig.config.request_count}
                        </p>
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleLoadConfig(savedConfig)}
                          className="px-4 py-2 bg-nvidia-green text-black font-bold rounded-lg hover:bg-nvidia-green/80"
                        >
                          Load
                        </button>
                        <button
                          onClick={() => handleDeleteConfig(savedConfig.name)}
                          className="px-3 py-2 bg-red-500/20 text-red-400 rounded-lg hover:bg-red-500/30"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              <div className="flex justify-end mt-4">
                <button
                  onClick={() => setShowLoadDialog(false)}
                  className="px-4 py-2 bg-white/5 border border-white/10 text-gray-300 rounded-lg hover:border-white/20"
                >
                  Close
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </div>
    </div>
  )
}
