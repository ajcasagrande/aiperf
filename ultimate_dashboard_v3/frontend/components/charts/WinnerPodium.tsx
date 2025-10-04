'use client'

import { motion } from 'framer-motion'
import { Trophy, Medal, Award, Crown } from 'lucide-react'
import { ComparisonResult } from '@/lib/types'

interface WinnerPodiumProps {
  comparison: ComparisonResult
  rankedBenchmarks: Array<{ benchmarkId: string; score: number }>
}

export function WinnerPodium({ comparison, rankedBenchmarks }: WinnerPodiumProps) {
  if (rankedBenchmarks.length === 0) return null

  const top3 = rankedBenchmarks.slice(0, 3)
  const podiumOrder = top3.length >= 3 ? [top3[1], top3[0], top3[2]] : top3.length === 2 ? [top3[1], top3[0]] : [top3[0]]

  const getPodiumHeight = (rank: number) => {
    if (rank === 1) return 'h-64'
    if (rank === 2) return 'h-48'
    return 'h-40'
  }

  const getPodiumColor = (rank: number) => {
    if (rank === 1) return 'from-yellow-500 to-yellow-600'
    if (rank === 2) return 'from-gray-300 to-gray-400'
    return 'from-orange-500 to-orange-600'
  }

  const getIcon = (rank: number) => {
    if (rank === 1) return <Crown className="w-12 h-12" />
    if (rank === 2) return <Trophy className="w-10 h-10" />
    return <Medal className="w-8 h-8" />
  }

  return (
    <div className="relative py-12">
      {/* Spotlight effect */}
      <div className="absolute top-0 left-1/2 transform -translate-x-1/2 w-96 h-96 bg-gradient-radial from-yellow-400/20 via-yellow-400/5 to-transparent blur-3xl pointer-events-none" />

      <div className="relative z-10">
        {/* Title */}
        <motion.div
          initial={{ y: -50, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          className="text-center mb-12"
        >
          <div className="flex items-center justify-center gap-3 mb-4">
            <Trophy className="w-10 h-10 text-yellow-400" />
            <h2 className="text-4xl font-black bg-gradient-to-r from-yellow-400 via-yellow-500 to-yellow-600 bg-clip-text text-transparent">
              LEADERBOARD
            </h2>
            <Trophy className="w-10 h-10 text-yellow-400" />
          </div>
          <p className="text-gray-400 text-lg">Top Performance Rankings</p>
        </motion.div>

        {/* Podium */}
        <div className="flex items-end justify-center gap-4 max-w-5xl mx-auto">
          {podiumOrder.map((item, displayIndex) => {
            const actualRank = rankedBenchmarks.findIndex(b => b.benchmarkId === item.benchmarkId) + 1
            const isCenter = top3.length >= 3 ? displayIndex === 1 : displayIndex === 0

            return (
              <motion.div
                key={item.benchmarkId}
                initial={{ y: 100, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{
                  duration: 0.8,
                  delay: isCenter ? 0.2 : displayIndex * 0.2,
                  type: "spring",
                  bounce: 0.4
                }}
                className="flex-1 flex flex-col items-center"
              >
                {/* Winner Info Card */}
                <motion.div
                  animate={{
                    y: [0, -10, 0],
                  }}
                  transition={{
                    duration: 2,
                    repeat: Infinity,
                    ease: "easeInOut",
                    delay: displayIndex * 0.3
                  }}
                  className={`relative mb-6 ${isCenter ? 'scale-110' : 'scale-100'}`}
                >
                  {/* Glow effect for winner */}
                  {actualRank === 1 && (
                    <div className="absolute inset-0 bg-yellow-400/30 blur-xl rounded-full animate-pulse" />
                  )}

                  <div className={`relative bg-gradient-to-br ${getPodiumColor(actualRank)} rounded-2xl p-6 shadow-2xl min-w-[200px]`}>
                    {/* Crown/Trophy Icon */}
                    <div className="flex items-center justify-center mb-3 text-white">
                      {getIcon(actualRank)}
                    </div>

                    {/* Rank */}
                    <div className="text-center text-white font-black text-3xl mb-2">
                      #{actualRank}
                    </div>

                    {/* Benchmark Name */}
                    <div className="text-center text-white/90 font-bold text-sm mb-3 truncate px-2">
                      {item.benchmarkId.substring(0, 18)}
                    </div>

                    {/* Score */}
                    <div className="bg-black/20 rounded-lg p-3 text-center">
                      <div className="text-xs text-white/70 mb-1">Score</div>
                      <div className="text-2xl font-black text-white">
                        {item.score.toFixed(1)}%
                      </div>
                    </div>

                    {/* Confetti for winner */}
                    {actualRank === 1 && (
                      <>
                        <motion.div
                          animate={{
                            rotate: [0, 360],
                            scale: [1, 1.2, 1]
                          }}
                          transition={{
                            duration: 3,
                            repeat: Infinity,
                            ease: "linear"
                          }}
                          className="absolute -top-4 -right-4 w-8 h-8 bg-yellow-300 rounded-full opacity-50"
                        />
                        <motion.div
                          animate={{
                            rotate: [360, 0],
                            scale: [1, 1.2, 1]
                          }}
                          transition={{
                            duration: 3,
                            repeat: Infinity,
                            ease: "linear"
                          }}
                          className="absolute -top-4 -left-4 w-8 h-8 bg-yellow-300 rounded-full opacity-50"
                        />
                      </>
                    )}
                  </div>
                </motion.div>

                {/* Podium Stand */}
                <motion.div
                  initial={{ scaleY: 0 }}
                  animate={{ scaleY: 1 }}
                  transition={{
                    duration: 0.8,
                    delay: isCenter ? 0.5 : 0.3 + displayIndex * 0.2,
                    ease: "easeOut"
                  }}
                  className={`relative ${getPodiumHeight(actualRank)} w-full bg-gradient-to-b ${getPodiumColor(actualRank)} rounded-t-xl border-t-4 border-white/20 shadow-2xl overflow-hidden`}
                  style={{ transformOrigin: 'bottom' }}
                >
                  {/* Podium shine effect */}
                  <div className="absolute inset-0 bg-gradient-to-br from-white/20 via-transparent to-transparent" />

                  {/* Rank number on podium */}
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="text-white/30 font-black text-6xl">
                      {actualRank}
                    </div>
                  </div>

                  {/* Animated stripes for winner */}
                  {actualRank === 1 && (
                    <motion.div
                      animate={{
                        backgroundPosition: ['0% 0%', '100% 100%']
                      }}
                      transition={{
                        duration: 3,
                        repeat: Infinity,
                        ease: "linear"
                      }}
                      className="absolute inset-0 opacity-20"
                      style={{
                        backgroundImage: 'repeating-linear-gradient(45deg, transparent, transparent 10px, rgba(255,255,255,0.1) 10px, rgba(255,255,255,0.1) 20px)',
                        backgroundSize: '200% 200%'
                      }}
                    />
                  )}
                </motion.div>
              </motion.div>
            )
          })}
        </div>

        {/* Rest of rankings */}
        {rankedBenchmarks.length > 3 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1 }}
            className="mt-12 max-w-3xl mx-auto"
          >
            <h3 className="text-xl font-bold text-white mb-4 text-center">Other Competitors</h3>
            <div className="space-y-2">
              {rankedBenchmarks.slice(3).map((item, index) => (
                <motion.div
                  key={item.benchmarkId}
                  initial={{ x: -50, opacity: 0 }}
                  animate={{ x: 0, opacity: 1 }}
                  transition={{ delay: 1.2 + index * 0.1 }}
                  className="bg-white/5 border border-white/10 rounded-lg p-4 flex items-center justify-between hover:bg-white/10 transition-colors"
                >
                  <div className="flex items-center gap-4">
                    <div className="text-2xl font-bold text-gray-400">#{index + 4}</div>
                    <div>
                      <div className="text-white font-semibold">{item.benchmarkId.substring(0, 30)}</div>
                      <div className="text-sm text-gray-400">Score: {item.score.toFixed(1)}%</div>
                    </div>
                  </div>
                  <Award className="w-6 h-6 text-gray-600" />
                </motion.div>
              ))}
            </div>
          </motion.div>
        )}
      </div>
    </div>
  )
}
