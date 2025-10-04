<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# 🏗️ Architecture Overview - NVIDIA AIPerf Dashboard v3

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User's Browser                           │
│                     (Chrome, Firefox, Edge)                      │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 │ HTTP/HTTPS & WebSocket
                 │
┌────────────────▼────────────────────────────────────────────────┐
│                    Frontend (Next.js 14)                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  React Components                                         │  │
│  │  • Dashboard • Comparison • Upload • Export              │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  State Management (Zustand)                              │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Data Fetching (TanStack Query)                          │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Visualizations (Recharts, D3.js, Three.js)             │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 │ REST API & WebSocket
                 │
┌────────────────▼────────────────────────────────────────────────┐
│                     Backend (FastAPI)                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  API Endpoints                                            │  │
│  │  /api/v3/benchmarks, /api/v3/compare, etc.              │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  WebSocket Handler                                        │  │
│  │  Real-time metric streaming                              │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Data Processor                                           │  │
│  │  • Pandas/NumPy • Statistics • Aggregations             │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  AI Insights Engine                                       │  │
│  │  • Analysis • Recommendations • Scoring                  │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 │ File I/O
                 │
┌────────────────▼────────────────────────────────────────────────┐
│                      Data Storage                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Benchmark Data (JSONL, JSON)                            │  │
│  │  data/benchmark_123/records.jsonl                        │  │
│  │  data/benchmark_123/aggregate.json                       │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Index File (JSON)                                       │  │
│  │  data/index.json                                         │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Technology Stack

### Frontend Layer

**Framework: Next.js 14**
- App Router for file-based routing
- React Server Components
- Server-Side Rendering (SSR)
- Static Site Generation (SSG)
- Edge runtime support

**UI Library: React 18**
- Functional components with hooks
- Context API for global state
- Suspense for lazy loading
- Concurrent rendering

**State Management: Zustand**
- Lightweight (1KB)
- No boilerplate
- TypeScript support
- Devtools integration

**Data Fetching: TanStack Query**
- Automatic caching
- Background refetching
- Optimistic updates
- Infinite queries

**Styling: Tailwind CSS**
- Utility-first CSS
- Dark mode support
- Responsive design
- Custom NVIDIA theme

**Charts: Recharts & D3.js**
- Responsive charts
- Interactive tooltips
- Real-time updates
- Custom animations

**3D: Three.js + React Three Fiber**
- Performance landscapes
- Interactive 3D views
- WebGL acceleration
- Camera controls

**Animations: Framer Motion**
- Spring physics
- Gesture support
- Layout animations
- Page transitions

### Backend Layer

**Framework: FastAPI**
- Async/await support
- Automatic API documentation
- Type validation (Pydantic)
- High performance

**Data Processing: Pandas**
- Vectorized operations
- DataFrame manipulation
- Efficient aggregations
- Memory optimization

**Numerical Computing: NumPy**
- Statistical functions
- Percentile calculations
- Array operations
- Fast computations

**WebSockets: websockets**
- Real-time communication
- Connection management
- Message broadcasting
- Auto-reconnect

**Server: Uvicorn**
- ASGI server
- Production-ready
- Hot reload (dev)
- Multiple workers

### Data Layer

**Storage: File-based**
- JSONL for records
- JSON for metadata
- Indexed access
- Fast queries

**Future: Database**
- SQLite for local
- PostgreSQL for production
- DuckDB for analytics
- Redis for caching

## Component Architecture

### Frontend Components

```
app/
├── layout.tsx              # Root layout
├── page.tsx               # Homepage
├── providers.tsx          # Global providers
├── globals.css           # Global styles
├── dashboard/
│   └── page.tsx          # Main dashboard
└── compare/
    └── page.tsx          # Comparison view

components/
├── ui/                   # Reusable UI components
│   ├── Button.tsx
│   ├── Card.tsx
│   ├── Chart.tsx
│   └── Table.tsx
├── charts/              # Chart components
│   ├── LatencyChart.tsx
│   ├── ThroughputChart.tsx
│   └── ComparisonChart.tsx
└── features/           # Feature-specific
    ├── BenchmarkUpload.tsx
    ├── MetricsTable.tsx
    └── InsightsPanel.tsx

lib/
├── api.ts             # API client
├── utils.ts           # Utilities
├── types.ts           # TypeScript types
└── constants.ts       # Constants
```

### Backend Modules

```
backend/
├── main.py                 # FastAPI app & routes
├── data_processor.py       # Data processing
├── ai_insights.py          # AI analysis
├── models.py              # Pydantic models
├── config.py              # Configuration
└── utils.py               # Utilities
```

## Data Flow

### Upload Flow

```
1. User uploads JSONL + JSON
   ↓
2. Frontend sends to /api/v3/benchmarks/upload
   ↓
3. Backend saves files to data/benchmark_id/
   ↓
4. DataProcessor parses and validates
   ↓
5. Statistics computed (mean, percentiles, etc.)
   ↓
6. Index updated with benchmark metadata
   ↓
7. Response sent with benchmark_id
   ↓
8. Frontend redirects to dashboard
```

### Query Flow

```
1. Frontend requests benchmark data
   ↓
2. API checks cache
   ↓
3. If miss: Load from disk
   ↓
4. Parse JSONL & JSON
   ↓
5. Compute statistics
   ↓
6. Cache result
   ↓
7. Return JSON response
   ↓
8. Frontend renders charts
```

### WebSocket Flow

```
1. Frontend opens WebSocket connection
   ↓
2. Send subscribe message with benchmark_id
   ↓
3. Backend adds to active connections
   ↓
4. As metrics arrive, broadcast to clients
   ↓
5. Frontend updates charts in real-time
   ↓
6. On disconnect, remove from connections
```

## Performance Optimizations

### Frontend

- **Code Splitting** - Dynamic imports for large components
- **Image Optimization** - Next.js Image component
- **Lazy Loading** - Suspense boundaries
- **Memoization** - React.memo, useMemo, useCallback
- **Virtual Scrolling** - For large tables
- **Debouncing** - Search and filter inputs
- **Service Worker** - Offline support (PWA)

### Backend

- **Async I/O** - Non-blocking file operations
- **Caching** - In-memory cache for hot data
- **Connection Pooling** - Reuse connections
- **Response Compression** - Gzip/Brotli
- **Pagination** - Limit result sets
- **Indexing** - Fast benchmark lookup
- **Parallel Processing** - Concurrent requests

### Data Processing

- **Vectorization** - NumPy/Pandas operations
- **Lazy Evaluation** - Compute on demand
- **Streaming** - Process large files in chunks
- **Aggregation** - Pre-compute statistics
- **Sampling** - Reduce data for visualization

## Security Architecture

### Frontend Security

- **XSS Prevention** - React escapes by default
- **CSRF Protection** - SameSite cookies
- **Content Security Policy** - Restrict scripts
- **HTTPS Only** - Force secure connections
- **Input Validation** - Client-side checks

### Backend Security

- **Input Validation** - Pydantic models
- **SQL Injection** - Parameterized queries (future)
- **Rate Limiting** - Prevent abuse
- **CORS** - Configured origins
- **Authentication** - API keys (future)
- **Authorization** - Role-based access (future)

## Scalability Considerations

### Current (Single Instance)

- Handles: ~100 concurrent users
- Storage: File-based (GB scale)
- Processing: In-memory (MB scale)

### Future (Distributed)

- Load Balancer → Multiple frontends
- API Gateway → Multiple backends
- Database → PostgreSQL cluster
- Cache → Redis cluster
- Queue → RabbitMQ/Redis
- Storage → S3/Cloud Storage

## Monitoring & Observability

### Logging

- FastAPI access logs
- Application logs (Python logging)
- Error tracking
- Performance metrics

### Metrics

- Request latency
- Response times
- Error rates
- Cache hit rates
- WebSocket connections

### Health Checks

- Backend: `/api/v3/health`
- Frontend: `/_next/health`
- Database: Connection test
- File system: Write test

## Deployment Architecture

### Development

```
localhost:3000 → Next.js dev server
localhost:8000 → FastAPI with uvicorn --reload
```

### Production (Docker)

```
nginx → frontend:3000 (Next.js production build)
nginx → backend:8000 (Uvicorn with workers)
```

### Production (Cloud)

```
Vercel → Frontend (Edge network)
Cloud Run → Backend (Auto-scaling)
Cloud Storage → Data persistence
```

## Future Enhancements

- **Microservices** - Split backend into services
- **Event Streaming** - Kafka/Pulsar
- **Time-Series DB** - InfluxDB/TimescaleDB
- **Graph Database** - Neo4j for relationships
- **ML Pipeline** - Model training & inference
- **CDN** - Global content delivery
- **Multi-Region** - Geographic distribution

---

**🏗️ Built for scale, optimized for performance**

*NVIDIA AIPerf Dashboard v3 - Enterprise-grade architecture*
