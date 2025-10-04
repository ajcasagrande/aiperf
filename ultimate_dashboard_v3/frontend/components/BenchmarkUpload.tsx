'use client'

import { useState, useCallback } from 'react'
import { motion } from 'framer-motion'
import { Upload, File, CheckCircle, AlertCircle, X } from 'lucide-react'
import { apiClient } from '@/lib/api'
import { useDashboardStore } from '@/lib/store'
import toast from 'react-hot-toast'

interface UploadState {
  jsonlFile: File | null
  aggregateFile: File | null
  uploading: boolean
  progress: number
  error: string | null
}

export function BenchmarkUpload({ onClose, onSuccess }: { onClose: () => void; onSuccess?: (benchmarkId: string) => void }) {
  const [state, setState] = useState<UploadState>({
    jsonlFile: null,
    aggregateFile: null,
    uploading: false,
    progress: 0,
    error: null,
  })

  const { setLoading } = useDashboardStore()

  const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>, type: 'jsonl' | 'aggregate') => {
    e.preventDefault()
    e.stopPropagation()

    const files = Array.from(e.dataTransfer.files)
    const file = files[0]

    if (!file) return

    // Validate file type
    if (type === 'jsonl' && !file.name.endsWith('.jsonl')) {
      toast.error('Please upload a .jsonl file')
      return
    }

    if (type === 'aggregate' && !file.name.endsWith('.json')) {
      toast.error('Please upload a .json file')
      return
    }

    setState((prev) => ({
      ...prev,
      [type === 'jsonl' ? 'jsonlFile' : 'aggregateFile']: file,
      error: null,
    }))
  }, [])

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>, type: 'jsonl' | 'aggregate') => {
    const files = e.target.files
    if (!files || files.length === 0) return

    const file = files[0]

    setState((prev) => ({
      ...prev,
      [type === 'jsonl' ? 'jsonlFile' : 'aggregateFile']: file,
      error: null,
    }))
  }

  const handleUpload = async () => {
    if (!state.jsonlFile) {
      toast.error('Please select a JSONL file')
      return
    }

    setState((prev) => ({ ...prev, uploading: true, progress: 0, error: null }))
    setLoading(true)

    try {
      const result = await apiClient.uploadBenchmark(
        state.jsonlFile,
        state.aggregateFile || undefined
      )

      setState((prev) => ({ ...prev, progress: 100 }))

      toast.success('Benchmark uploaded successfully!')

      setTimeout(() => {
        onSuccess?.(result.benchmark_id)
        onClose()
      }, 1000)
    } catch (error: any) {
      console.error('Upload error:', error)
      const errorMessage = error.response?.data?.detail || error.message || 'Upload failed'
      setState((prev) => ({ ...prev, error: errorMessage }))
      toast.error(errorMessage)
    } finally {
      setState((prev) => ({ ...prev, uploading: false }))
      setLoading(false)
    }
  }

  const removeFile = (type: 'jsonl' | 'aggregate') => {
    setState((prev) => ({
      ...prev,
      [type === 'jsonl' ? 'jsonlFile' : 'aggregateFile']: null,
    }))
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        className="bg-nvidia-darkGray border border-white/10 rounded-2xl p-8 max-w-2xl w-full"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold text-white mb-1">Upload Benchmark</h2>
            <p className="text-gray-400">Upload your benchmark data files</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* JSONL File Upload */}
        <div className="mb-6">
          <label className="block text-sm font-semibold text-white mb-2">
            JSONL File <span className="text-red-400">*</span>
          </label>
          <div
            onDrop={(e) => handleDrop(e, 'jsonl')}
            onDragOver={(e) => e.preventDefault()}
            className="border-2 border-dashed border-white/20 rounded-xl p-8 text-center hover:border-nvidia-green/50 transition-colors cursor-pointer"
          >
            {state.jsonlFile ? (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <File className="w-8 h-8 text-nvidia-green" />
                  <div className="text-left">
                    <p className="text-white font-semibold">{state.jsonlFile.name}</p>
                    <p className="text-sm text-gray-400">
                      {(state.jsonlFile.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => removeFile('jsonl')}
                  className="text-gray-400 hover:text-red-400 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            ) : (
              <>
                <Upload className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                <p className="text-white mb-1">Drop JSONL file here or click to browse</p>
                <p className="text-sm text-gray-400">profile_export.jsonl</p>
                <input
                  type="file"
                  accept=".jsonl"
                  onChange={(e) => handleFileSelect(e, 'jsonl')}
                  className="hidden"
                  id="jsonl-input"
                />
                <label
                  htmlFor="jsonl-input"
                  className="inline-block mt-4 px-4 py-2 bg-white/10 text-white rounded-lg hover:bg-white/20 cursor-pointer transition-colors"
                >
                  Select File
                </label>
              </>
            )}
          </div>
        </div>

        {/* Aggregate File Upload (Optional) */}
        <div className="mb-6">
          <label className="block text-sm font-semibold text-white mb-2">
            Aggregate JSON File <span className="text-gray-500">(Optional)</span>
          </label>
          <div
            onDrop={(e) => handleDrop(e, 'aggregate')}
            onDragOver={(e) => e.preventDefault()}
            className="border-2 border-dashed border-white/20 rounded-xl p-6 text-center hover:border-nvidia-green/50 transition-colors cursor-pointer"
          >
            {state.aggregateFile ? (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <File className="w-8 h-8 text-blue-400" />
                  <div className="text-left">
                    <p className="text-white font-semibold">{state.aggregateFile.name}</p>
                    <p className="text-sm text-gray-400">
                      {(state.aggregateFile.size / 1024).toFixed(2)} KB
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => removeFile('aggregate')}
                  className="text-gray-400 hover:text-red-400 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            ) : (
              <>
                <Upload className="w-10 h-10 text-gray-400 mx-auto mb-2" />
                <p className="text-white text-sm mb-1">Drop JSON file or click to browse</p>
                <p className="text-xs text-gray-400">profile_export_aiperf.json</p>
                <input
                  type="file"
                  accept=".json"
                  onChange={(e) => handleFileSelect(e, 'aggregate')}
                  className="hidden"
                  id="aggregate-input"
                />
                <label
                  htmlFor="aggregate-input"
                  className="inline-block mt-3 px-3 py-1.5 text-sm bg-white/10 text-white rounded-lg hover:bg-white/20 cursor-pointer transition-colors"
                >
                  Select File
                </label>
              </>
            )}
          </div>
        </div>

        {/* Progress Bar */}
        {state.uploading && (
          <div className="mb-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-white">Uploading...</span>
              <span className="text-sm text-nvidia-green">{state.progress}%</span>
            </div>
            <div className="w-full bg-white/10 rounded-full h-2">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${state.progress}%` }}
                className="bg-nvidia-green h-2 rounded-full"
              />
            </div>
          </div>
        )}

        {/* Error Message */}
        {state.error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/50 rounded-lg flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-red-400">Upload Failed</p>
              <p className="text-sm text-red-300">{state.error}</p>
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3">
          <button
            onClick={handleUpload}
            disabled={!state.jsonlFile || state.uploading}
            className="flex-1 px-6 py-3 bg-nvidia-green text-black font-bold rounded-lg hover:bg-nvidia-green/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
          >
            {state.uploading ? (
              <>
                <div className="w-5 h-5 border-2 border-black/20 border-t-black rounded-full animate-spin" />
                Uploading...
              </>
            ) : (
              <>
                <Upload className="w-5 h-5" />
                Upload Benchmark
              </>
            )}
          </button>
          <button
            onClick={onClose}
            disabled={state.uploading}
            className="px-6 py-3 bg-white/10 text-white font-semibold rounded-lg hover:bg-white/20 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Cancel
          </button>
        </div>
      </motion.div>
    </motion.div>
  )
}
