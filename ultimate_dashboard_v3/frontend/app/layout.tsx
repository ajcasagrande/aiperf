import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { Providers } from './providers'
import { Toaster } from 'react-hot-toast'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'NVIDIA AIPerf Dashboard v3',
  description: 'Next-generation LLM performance benchmarking dashboard powered by NVIDIA',
  keywords: ['NVIDIA', 'AIPerf', 'LLM', 'benchmarking', 'performance', 'AI-Dynamo'],
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>
        <Providers>
          {children}
          <Toaster
            position="top-right"
            toastOptions={{
              style: {
                background: '#1A1A1A',
                color: '#fff',
                border: '1px solid #76B900',
              },
            }}
          />
        </Providers>
      </body>
    </html>
  )
}
