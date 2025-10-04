'use client'

import { useEffect, useRef } from 'react'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'

interface TerminalViewerProps {
  interactive?: boolean
  className?: string
  onResize?: (rows: number, cols: number) => void
  onData?: (data: string) => void
}

export default function TerminalViewer({ interactive = false, className = '', onResize, onData }: TerminalViewerProps) {
  const terminalRef = useRef<HTMLDivElement>(null)
  const terminalInstanceRef = useRef<Terminal | null>(null)
  const isInitialized = useRef(false)

  useEffect(() => {
    if (!terminalRef.current || isInitialized.current) return

    isInitialized.current = true
    console.log('Creating terminal instance')

    // Create terminal
    const terminal = new Terminal({
      fontSize: 14,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      theme: {
        background: '#000000',
        foreground: '#ffffff',
      },
      cursorBlink: false,
      disableStdin: !interactive,
      convertEol: true,
      scrollback: 10000,
    })

    const fitAddon = new FitAddon()
    terminal.loadAddon(fitAddon)
    terminal.open(terminalRef.current)

    terminalInstanceRef.current = terminal

    // Fit and initialize
    setTimeout(() => {
      fitAddon.fit()
      console.log('Terminal fitted:', terminal.rows, 'x', terminal.cols)

      // Expose globally
      ;(window as any).xterm = terminal

      // Call onResize
      if (onResize) {
        onResize(terminal.rows, terminal.cols)
      }

      // Welcome message
      console.log('Writing welcome message')
      terminal.write('\x1b[1;32m🚀 NVIDIA AIPerf Dashboard\x1b[0m\r\n')
      terminal.write('\x1b[90m' + '─'.repeat(80) + '\x1b[0m\r\n')
      terminal.write('\x1b[36mReady to run benchmarks\x1b[0m\r\n\r\n')

      // Debug: check buffer
      console.log('Terminal buffer lines:', terminal.buffer.active.length)
      console.log('Terminal viewport:', terminal.buffer.active.viewportY)

      // Process queued data
      const queue = (window as any).xtermQueue
      if (queue?.length > 0) {
        console.log('Processing', queue.length, 'queued items')
        queue.forEach((data: string) => terminal.write(data))
        ;(window as any).xtermQueue = []
      }
    }, 100)

    // Handle window resize
    const handleResize = () => fitAddon.fit()
    window.addEventListener('resize', handleResize)

    return () => {
      // Don't dispose - let it persist
      window.removeEventListener('resize', handleResize)
    }
  }, [])

  // Update interactive mode dynamically
  useEffect(() => {
    if (!terminalInstanceRef.current) return
    terminalInstanceRef.current.options.disableStdin = !interactive
  }, [interactive])

  // Update onData handler dynamically
  useEffect(() => {
    if (!terminalInstanceRef.current || !interactive || !onData) return
    const handler = terminalInstanceRef.current.onData(onData)
    return () => handler.dispose()
  }, [interactive, onData])

  // Notify onResize once after creation
  useEffect(() => {
    if (!terminalInstanceRef.current || !onResize) return
    const timer = setTimeout(() => {
      if (terminalInstanceRef.current) {
        onResize(terminalInstanceRef.current.rows, terminalInstanceRef.current.cols)
      }
    }, 200)
    return () => clearTimeout(timer)
  }, [onResize])

  return (
    <div
      ref={terminalRef}
      className={className}
      style={{
        width: '100%',
        height: '100%',
        minHeight: '400px',
        backgroundColor: '#000000',
        position: 'relative',
      }}
    />
  )
}
