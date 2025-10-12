'use client'

import { motion } from 'framer-motion'
import Link from 'next/link'
import {
  Zap,
  BarChart3,
  TrendingUp,
  Brain,
  Gauge,
  Sparkles,
  ArrowRight,
  Activity,
  Database,
  GitCompare,
  Play,
  GitBranch,
  Upload
} from 'lucide-react'

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-black via-nvidia-darkGray to-black">
      {/* Hero Section */}
      <div className="container mx-auto px-4 py-16">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="text-center mb-16"
        >
          <div className="flex items-center justify-center gap-3 mb-6">
            <Sparkles className="w-12 h-12 text-nvidia-green" />
            <h1 className="text-7xl font-bold">
              <span className="text-white">NVIDIA</span>
              <span className="gradient-text"> AIPerf</span>
            </h1>
          </div>

          <h2 className="text-3xl text-gray-300 mb-6">
            Ultimate Dashboard <span className="text-nvidia-green">v3.0</span>
          </h2>

          <p className="text-xl text-gray-400 max-w-3xl mx-auto mb-8">
            Next-generation LLM performance benchmarking with AI-powered insights,
            real-time analytics, and interactive 3D visualizations
          </p>

          <div className="flex flex-wrap gap-4 justify-center">
            <Link href="/dashboard">
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className="px-8 py-4 bg-nvidia-green text-black font-bold rounded-lg flex items-center gap-2 hover:bg-nvidia-green/90 transition-colors"
              >
                Launch Dashboard
                <ArrowRight className="w-5 h-5" />
              </motion.button>
            </Link>

            <Link href="/run">
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className="px-8 py-4 bg-gradient-to-r from-purple-600 to-blue-600 text-white font-bold rounded-lg flex items-center gap-2 hover:opacity-90 transition-opacity"
              >
                <Play className="w-5 h-5" />
                Run Benchmark
              </motion.button>
            </Link>

            <Link href="/compare">
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className="px-8 py-4 bg-white/10 text-white font-bold rounded-lg border border-white/20 hover:bg-white/20 transition-colors"
              >
                Compare Benchmarks
              </motion.button>
            </Link>

            <Link href="/traces">
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className="px-8 py-4 bg-gradient-to-r from-cyan-600 to-blue-600 text-white font-bold rounded-lg flex items-center gap-2 hover:opacity-90 transition-opacity"
              >
                <GitBranch className="w-5 h-5" />
                Request Traces
              </motion.button>
            </Link>

            <Link href="/upload">
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className="px-8 py-4 bg-white/10 text-white font-bold rounded-lg border border-white/20 hover:bg-white/20 transition-colors flex items-center gap-2"
              >
                <Upload className="w-5 h-5" />
                Upload Data
              </motion.button>
            </Link>
          </div>
        </motion.div>

        {/* Features Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-7xl mx-auto">
          <FeatureCard
            icon={<Brain className="w-8 h-8" />}
            title="AI-Powered Insights"
            description="Get intelligent recommendations and automated performance analysis"
            delay={0.1}
          />

          <FeatureCard
            icon={<Activity className="w-8 h-8" />}
            title="Real-Time Streaming"
            description="Watch your benchmarks run live with WebSocket support"
            delay={0.2}
          />

          <FeatureCard
            icon={<GitCompare className="w-8 h-8" />}
            title="Multi-Benchmark Comparison"
            description="Compare multiple runs side-by-side with interactive charts"
            delay={0.3}
          />

          <FeatureCard
            icon={<BarChart3 className="w-8 h-8" />}
            title="3D Visualizations"
            description="Explore performance landscapes in immersive 3D"
            delay={0.4}
          />

          <FeatureCard
            icon={<Gauge className="w-8 h-8" />}
            title="Advanced Metrics"
            description="Track throughput, latency, goodput, TTFT, and more"
            delay={0.5}
          />

          <FeatureCard
            icon={<TrendingUp className="w-8 h-8" />}
            title="Trend Analysis"
            description="Historical trends and predictive analytics"
            delay={0.6}
          />

          <FeatureCard
            icon={<Zap className="w-8 h-8" />}
            title="Lightning Fast"
            description="Built with Next.js 14 and FastAPI for maximum performance"
            delay={0.7}
          />

          <FeatureCard
            icon={<GitBranch className="w-8 h-8" />}
            title="Request Tracing"
            description="Deep dive into individual requests with timeline, waterfall, and error tracing"
            delay={0.8}
          />

          <FeatureCard
            icon={<Upload className="w-8 h-8" />}
            title="Easy Data Import"
            description="Upload JSONL benchmark data with drag-and-drop support"
            delay={0.9}
          />

          <FeatureCard
            icon={<Database className="w-8 h-8" />}
            title="Smart Data Processing"
            description="Efficient data handling with pandas and DuckDB"
            delay={1.0}
          />

          <FeatureCard
            icon={<Sparkles className="w-8 h-8" />}
            title="Modern UI/UX"
            description="Beautiful, responsive design with dark mode support"
            delay={0.9}
          />
        </div>

        {/* Stats Section */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1, duration: 0.5 }}
          className="mt-20 grid grid-cols-1 md:grid-cols-4 gap-8 max-w-6xl mx-auto"
        >
          <StatCard value="100+" label="Metrics Tracked" />
          <StatCard value="∞" label="Benchmarks Supported" />
          <StatCard value="< 1ms" label="Query Latency" />
          <StatCard value="100%" label="NVIDIA Powered" />
        </motion.div>

        {/* Footer */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.2, duration: 0.5 }}
          className="mt-20 text-center text-gray-500"
        >
          <p className="mb-2">
            Powered by <span className="text-nvidia-green font-bold">NVIDIA</span> •
            Built with <span className="text-nvidia-green">AIPerf</span> &
            <span className="text-nvidia-green"> AI-Dynamo</span>
          </p>
          <p className="text-sm">
            © 2025 NVIDIA Corporation. All rights reserved.
          </p>
        </motion.div>
      </div>
    </div>
  )
}

function FeatureCard({
  icon,
  title,
  description,
  delay
}: {
  icon: React.ReactNode
  title: string
  description: string
  delay: number
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.5 }}
      whileHover={{ scale: 1.05, y: -5 }}
      className="p-6 bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl hover:border-nvidia-green/50 transition-all cursor-pointer group"
    >
      <div className="text-nvidia-green mb-4 group-hover:scale-110 transition-transform">
        {icon}
      </div>
      <h3 className="text-xl font-bold text-white mb-2">{title}</h3>
      <p className="text-gray-400">{description}</p>
    </motion.div>
  )
}

function StatCard({ value, label }: { value: string; label: string }) {
  return (
    <div className="text-center">
      <div className="text-5xl font-bold gradient-text mb-2">{value}</div>
      <div className="text-gray-400 text-sm uppercase tracking-wider">{label}</div>
    </div>
  )
}
