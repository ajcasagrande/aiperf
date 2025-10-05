'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import { Upload, FileText, CheckCircle, XCircle, ArrowRight } from 'lucide-react'
import { apiClient } from '@/lib/api'
import { useRouter } from 'next/navigation'
import toast from 'react-hot-toast'

export default function UploadPage() {
  const router = useRouter()
  const [jsonlFile, setJsonlFile] = useState<File | null>(null)
  const [aggregateFile, setAggregateFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadResult, setUploadResult] = useState<any>(null)

  const handleJsonlChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      if (!file.name.endsWith('.jsonl')) {
        toast.error('File must have .jsonl extension')
        return
      }
      setJsonlFile(file)
    }
  }

  const handleAggregateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      if (!file.name.endsWith('.json')) {
        toast.error('File must have .json extension')
        return
      }
      setAggregateFile(file)
    }
  }

  const handleUpload = async () => {
    if (!jsonlFile) {
      toast.error('Please select a JSONL file')
      return
    }

    setUploading(true)
    setUploadResult(null)

    try {
      const formData = new FormData()
      formData.append('jsonl_file', jsonlFile)
      if (aggregateFile) {
        formData.append('aggregate_file', aggregateFile)
      }

      const response = await apiClient.client.post('/api/v3/benchmarks/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })

      setUploadResult(response.data)
      toast.success('Benchmark uploaded successfully!')

      // Redirect to dashboard after 2 seconds
      setTimeout(() => {
        router.push(`/dashboard`)
      }, 2000)
    } catch (error: any) {
      console.error('Upload failed:', error)
      toast.error(error.response?.data?.detail || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const handleDrop = (e: React.DragEvent, type: 'jsonl' | 'aggregate') => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file) {
      if (type === 'jsonl') {
        if (file.name.endsWith('.jsonl')) {
          setJsonlFile(file)
        } else {
          toast.error('File must have .jsonl extension')
        }
      } else {
        if (file.name.endsWith('.json')) {
          setAggregateFile(file)
        } else {
          toast.error('File must have .json extension')
        }
      }
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-black via-nvidia-darkGray to-black p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <motion.div
          initial={{ y: -20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          className="mb-8"
        >
          <div className="flex items-center gap-4 mb-2">
            <Upload className="w-10 h-10 text-nvidia-green" />
            <div>
              <h1 className="text-4xl font-black bg-gradient-to-r from-nvidia-green to-green-400 bg-clip-text text-transparent">
                Upload Benchmark
              </h1>
              <p className="text-gray-400">Import benchmark data from JSONL files</p>
            </div>
          </div>
        </motion.div>

        {/* Upload Form */}
        <motion.div
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          className="bg-white/5 border border-white/10 rounded-2xl p-8 mb-8"
        >
          {/* JSONL File */}
          <div className="mb-6">
            <label className="block text-lg font-semibold text-white mb-3">
              Benchmark Records (JSONL) *
            </label>
            <div
              onDrop={(e) => handleDrop(e, 'jsonl')}
              onDragOver={(e) => e.preventDefault()}
              className={`border-2 border-dashed rounded-xl p-8 transition-colors cursor-pointer ${
                jsonlFile
                  ? 'border-nvidia-green bg-nvidia-green/10'
                  : 'border-white/20 hover:border-nvidia-green/50 bg-white/5'
              }`}
              onClick={() => document.getElementById('jsonl-input')?.click()}
            >
              <input
                id="jsonl-input"
                type="file"
                accept=".jsonl"
                onChange={handleJsonlChange}
                className="hidden"
              />

              {jsonlFile ? (
                <div className="flex items-center justify-center gap-3">
                  <CheckCircle className="w-8 h-8 text-nvidia-green" />
                  <div>
                    <div className="text-white font-semibold">{jsonlFile.name}</div>
                    <div className="text-gray-400 text-sm">
                      {(jsonlFile.size / 1024).toFixed(2)} KB
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center">
                  <FileText className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                  <div className="text-gray-300 font-semibold mb-1">
                    Drop JSONL file here or click to browse
                  </div>
                  <div className="text-gray-500 text-sm">
                    Required: records.jsonl from AIPerf benchmark
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Aggregate File (Optional) */}
          <div className="mb-6">
            <label className="block text-lg font-semibold text-white mb-3">
              Aggregate Metrics (JSON) <span className="text-gray-500 text-sm">Optional</span>
            </label>
            <div
              onDrop={(e) => handleDrop(e, 'aggregate')}
              onDragOver={(e) => e.preventDefault()}
              className={`border-2 border-dashed rounded-xl p-8 transition-colors cursor-pointer ${
                aggregateFile
                  ? 'border-nvidia-green bg-nvidia-green/10'
                  : 'border-white/20 hover:border-nvidia-green/50 bg-white/5'
              }`}
              onClick={() => document.getElementById('aggregate-input')?.click()}
            >
              <input
                id="aggregate-input"
                type="file"
                accept=".json"
                onChange={handleAggregateChange}
                className="hidden"
              />

              {aggregateFile ? (
                <div className="flex items-center justify-center gap-3">
                  <CheckCircle className="w-8 h-8 text-nvidia-green" />
                  <div>
                    <div className="text-white font-semibold">{aggregateFile.name}</div>
                    <div className="text-gray-400 text-sm">
                      {(aggregateFile.size / 1024).toFixed(2)} KB
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center">
                  <FileText className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                  <div className="text-gray-300 font-semibold mb-1">
                    Drop JSON file here or click to browse
                  </div>
                  <div className="text-gray-500 text-sm">
                    Optional: aggregate.json for throughput/goodput metrics
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Upload Button */}
          <div className="flex gap-3">
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={handleUpload}
              disabled={!jsonlFile || uploading}
              className="flex-1 px-8 py-4 bg-gradient-to-r from-nvidia-green to-green-500 text-black font-bold rounded-xl shadow-lg shadow-nvidia-green/50 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {uploading ? (
                <>
                  <div className="w-5 h-5 border-2 border-black/30 border-t-black rounded-full animate-spin" />
                  Uploading...
                </>
              ) : (
                <>
                  <Upload className="w-5 h-5" />
                  Upload Benchmark
                </>
              )}
            </motion.button>

            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => router.push('/')}
              className="px-6 py-4 bg-white/5 border border-white/10 text-white font-bold rounded-xl hover:border-white/20"
            >
              Cancel
            </motion.button>
          </div>
        </motion.div>

        {/* Upload Result */}
        {uploadResult && (
          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            className="bg-nvidia-green/10 border border-nvidia-green rounded-2xl p-6"
          >
            <div className="flex items-start gap-3 mb-4">
              <CheckCircle className="w-6 h-6 text-nvidia-green flex-shrink-0 mt-1" />
              <div>
                <h3 className="text-xl font-bold text-white mb-1">Upload Successful!</h3>
                <p className="text-gray-300">Benchmark ID: <span className="font-mono text-nvidia-green">{uploadResult.benchmark_id}</span></p>
              </div>
            </div>

            {uploadResult.summary && (
              <div className="bg-black/30 rounded-lg p-4">
                <div className="text-sm text-gray-400">
                  <div className="mb-2">
                    <span className="font-semibold text-white">Records Processed:</span>{' '}
                    {uploadResult.summary.records_processed}
                  </div>
                  <div>
                    <span className="font-semibold text-white">Statistics:</span>{' '}
                    {Object.keys(uploadResult.summary.statistics || {}).length} metrics computed
                  </div>
                </div>
              </div>
            )}

            <div className="mt-4 text-gray-300 text-sm">
              Redirecting to dashboard...
            </div>
          </motion.div>
        )}

        {/* Help Section */}
        <motion.div
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.2 }}
          className="bg-white/5 border border-white/10 rounded-xl p-6"
        >
          <h3 className="text-lg font-bold text-white mb-3">File Requirements</h3>
          <div className="space-y-2 text-gray-400 text-sm">
            <div className="flex items-start gap-2">
              <div className="w-1.5 h-1.5 bg-nvidia-green rounded-full mt-2"></div>
              <div>
                <span className="font-semibold text-white">records.jsonl:</span> One JSON object per line containing request-level metrics
              </div>
            </div>
            <div className="flex items-start gap-2">
              <div className="w-1.5 h-1.5 bg-nvidia-green rounded-full mt-2"></div>
              <div>
                <span className="font-semibold text-white">aggregate.json (optional):</span> System-level metrics like throughput and goodput
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  )
}
