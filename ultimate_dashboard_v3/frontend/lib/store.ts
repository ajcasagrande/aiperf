/**
 * Zustand store for global state management
 */

import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'
import { Benchmark, BenchmarkData, ComparisonResult, AIInsights } from './types'

interface DashboardStore {
  // Benchmarks
  benchmarks: Benchmark[]
  selectedBenchmark: BenchmarkData | null
  currentBenchmarkId: string | null

  // Comparison
  comparisonBenchmarks: string[]
  comparisonResult: ComparisonResult | null

  // Insights
  insights: AIInsights | null

  // UI State
  isLoading: boolean
  error: string | null

  // Actions
  setBenchmarks: (benchmarks: Benchmark[]) => void
  setSelectedBenchmark: (benchmark: BenchmarkData | null) => void
  setCurrentBenchmarkId: (id: string | null) => void
  addToComparison: (benchmarkId: string) => void
  removeFromComparison: (benchmarkId: string) => void
  clearComparison: () => void
  setComparisonResult: (result: ComparisonResult | null) => void
  setInsights: (insights: AIInsights | null) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  reset: () => void
}

const initialState = {
  benchmarks: [],
  selectedBenchmark: null,
  currentBenchmarkId: null,
  comparisonBenchmarks: [],
  comparisonResult: null,
  insights: null,
  isLoading: false,
  error: null,
}

export const useDashboardStore = create<DashboardStore>()(
  devtools(
    persist(
      (set) => ({
        ...initialState,

        setBenchmarks: (benchmarks) => set({ benchmarks }),

        setSelectedBenchmark: (benchmark) => set({ selectedBenchmark: benchmark }),

        setCurrentBenchmarkId: (id) => set({ currentBenchmarkId: id }),

        addToComparison: (benchmarkId) =>
          set((state) => {
            if (state.comparisonBenchmarks.includes(benchmarkId)) {
              return state
            }
            if (state.comparisonBenchmarks.length >= 10) {
              return { error: 'Maximum 10 benchmarks can be compared' }
            }
            return {
              comparisonBenchmarks: [...state.comparisonBenchmarks, benchmarkId],
              error: null,
            }
          }),

        removeFromComparison: (benchmarkId) =>
          set((state) => ({
            comparisonBenchmarks: state.comparisonBenchmarks.filter((id) => id !== benchmarkId),
          })),

        clearComparison: () =>
          set({
            comparisonBenchmarks: [],
            comparisonResult: null,
          }),

        setComparisonResult: (result) => set({ comparisonResult: result }),

        setInsights: (insights) => set({ insights }),

        setLoading: (loading) => set({ isLoading: loading }),

        setError: (error) => set({ error }),

        reset: () => set(initialState),
      }),
      {
        name: 'aiperf-dashboard-storage',
        partialize: (state) => ({
          comparisonBenchmarks: state.comparisonBenchmarks,
          currentBenchmarkId: state.currentBenchmarkId,
        }),
      }
    )
  )
)
