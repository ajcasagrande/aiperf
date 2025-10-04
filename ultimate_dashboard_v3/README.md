<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# 🚀 NVIDIA AIPerf Dashboard v3.0

> **The Ultimate LLM Performance Benchmarking Dashboard**
> Powered by NVIDIA | Built with AIPerf & AI-Dynamo

![Version](https://img.shields.io/badge/version-3.0.0-green)
![License](https://img.shields.io/badge/license-Apache%202.0-blue)
![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey)

---

## 🌟 What Makes v3 Revolutionary?

AIPerf Dashboard v3 is a **complete rewrite** using cutting-edge technologies to deliver the most advanced LLM benchmarking experience ever created:

### ⚡ **Next-Generation Features**

- 🤖 **AI-Powered Insights** - Intelligent performance analysis and recommendations
- 📊 **Real-Time Streaming** - Watch benchmarks run live via WebSocket
- 🔄 **Multi-Benchmark Comparison** - Compare multiple runs side-by-side
- 🎨 **3D Visualizations** - Explore performance in immersive 3D (coming soon)
- 📈 **Advanced Analytics** - Track 100+ metrics with percentile ladders
- 🎯 **Smart Alerts** - Get notified of performance anomalies
- 💰 **Cost Analysis** - Track token-based costs in real-time
- 🏆 **Leaderboards** - Compare against historical benchmarks
- 🌓 **Dark/Light Themes** - Beautiful UI with NVIDIA branding
- 📱 **Mobile Responsive** - Access from any device

### 🛠️ **Technology Stack**

#### Frontend
- **Next.js 14** - React framework with App Router
- **TypeScript** - Type-safe development
- **Tailwind CSS** - Utility-first styling
- **Recharts & D3.js** - Interactive visualizations
- **Three.js** - 3D graphics (React Three Fiber)
- **Framer Motion** - Smooth animations
- **TanStack Query** - Powerful data fetching
- **Zustand** - Lightweight state management

#### Backend
- **FastAPI** - High-performance async Python framework
- **Pandas & NumPy** - Data processing
- **WebSockets** - Real-time communication
- **Pydantic** - Data validation
- **Uvicorn** - ASGI server

---

## 🏗️ Architecture

```
ultimate_dashboard_v3/
├── backend/                  # FastAPI backend
│   ├── main.py              # API server & WebSocket
│   ├── data_processor.py    # Data analytics engine
│   ├── ai_insights.py       # AI-powered analysis
│   └── requirements.txt     # Python dependencies
│
├── frontend/                # Next.js 14 app
│   ├── app/                 # App Router pages
│   │   ├── page.tsx        # Homepage
│   │   ├── dashboard/      # Main dashboard
│   │   └── compare/        # Comparison view
│   ├── components/         # React components
│   ├── lib/               # Utilities & helpers
│   └── package.json       # Node dependencies
│
├── data/                   # Benchmark data storage
├── docker-compose.yml     # Docker orchestration
├── setup.sh              # Quick setup script
└── README.md            # This file
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **Node.js 18+**
- **npm 9+**
- Docker (optional, for containerized deployment)

### Option 1: Automated Setup (Recommended)

```bash
# Clone and setup everything in one command
cd ultimate_dashboard_v3
chmod +x setup.sh
./setup.sh
```

The script will:
1. ✅ Install backend dependencies
2. ✅ Install frontend dependencies
3. ✅ Create data directories
4. ✅ Start both servers
5. ✅ Open browser to dashboard

### Option 2: Manual Setup

#### Step 1: Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start backend server
python main.py
```

Backend will run at: **http://localhost:8000**
API docs at: **http://localhost:8000/docs**

#### Step 2: Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Frontend will run at: **http://localhost:3000**

### Option 3: Docker Deployment

```bash
# Build and start services
docker-compose up --build

# Stop services
docker-compose down
```

---

## 📊 Usage Guide

### 1. Upload Benchmark Data

Navigate to the dashboard and click **"Upload Benchmark"**:

- Upload your `profile_export.jsonl` file
- Optionally upload `profile_export_aiperf.json` for aggregate stats
- Dashboard will process and visualize automatically

### 2. View Performance Metrics

The dashboard displays:
- **KPI Cards** - Key metrics at a glance
- **Interactive Charts** - Latency, throughput, token metrics
- **AI Insights** - Intelligent performance recommendations
- **Detailed Tables** - Complete metric breakdown

### 3. Compare Benchmarks

Go to **Compare** page:
- Select multiple benchmarks
- View side-by-side comparison
- Analyze relative performance
- Identify optimization opportunities

### 4. Real-Time Monitoring

Connect via WebSocket to stream live metrics:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/realtime')
ws.send(JSON.stringify({ type: 'subscribe', benchmark_id: 'your-id' }))
```

---

## 🎯 API Documentation

### Endpoints

#### `GET /api/v3/benchmarks`
List all available benchmarks

#### `GET /api/v3/benchmarks/{id}`
Get detailed benchmark data

#### `POST /api/v3/benchmarks/upload`
Upload new benchmark data

#### `POST /api/v3/compare`
Compare multiple benchmarks

#### `POST /api/v3/insights`
Get AI-powered insights

#### `GET /api/v3/leaderboard`
View performance leaderboard

#### `GET /api/v3/trends/{metric}`
Get historical trends

#### `WS /ws/realtime`
WebSocket for real-time streaming

Full API documentation: **http://localhost:8000/docs**

---

## 🎨 Features Deep Dive

### AI-Powered Insights

The AI engine analyzes your benchmarks and provides:
- **Performance Scoring** - 0-100 composite score
- **Bottleneck Detection** - Identifies performance issues
- **Optimization Tips** - Actionable recommendations
- **Trend Prediction** - Forecasts future performance
- **Anomaly Detection** - Flags unusual patterns

### Multi-Benchmark Comparison

Compare across:
- **Throughput** - Request & token rates
- **Latency** - P50, P90, P99 distributions
- **Quality** - Goodput & SLA compliance
- **Efficiency** - Token economics
- **Cost** - Token-based pricing

### Real-Time Streaming

Monitor benchmarks as they run:
- Live metric updates
- Progress tracking
- Error notifications
- Performance alerts

---

## 📈 Metrics Tracked

### Core Metrics
- Request Throughput (req/s)
- Token Throughput (tok/s)
- Request Latency (P0-P100)
- Time to First Token (TTFT)
- Inter-Token Latency (ITL)
- Time to Second Token (TTST)

### Quality Metrics
- Goodput (quality-adjusted throughput)
- SLA Compliance Rate
- Error Rate
- Quality Score

### Token Metrics
- Input Sequence Length
- Output Sequence Length
- Reasoning Tokens
- Total Tokens
- Token Efficiency

### System Metrics
- Concurrency
- Worker Utilization
- Benchmark Duration
- Request Count

---

## 🔧 Configuration

### Backend Configuration

Edit `backend/config.py`:

```python
# API Settings
API_HOST = "0.0.0.0"
API_PORT = 8000

# Data Storage
DATA_DIR = "../data"

# AI Insights
ENABLE_AI_INSIGHTS = True
```

### Frontend Configuration

Edit `frontend/.env.local`:

```bash
# API Endpoint
NEXT_PUBLIC_API_URL=http://localhost:8000

# Features
NEXT_PUBLIC_ENABLE_3D=true
NEXT_PUBLIC_ENABLE_REALTIME=true
```

---

## 🐳 Docker Configuration

### `docker-compose.yml`

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    environment:
      - ENVIRONMENT=production

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://backend:8000
    depends_on:
      - backend
```

---

## 🎓 Examples

### Python API Client

```python
import requests

# Upload benchmark
with open('profile_export.jsonl', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/api/v3/benchmarks/upload',
        files={'jsonl_file': f}
    )
    benchmark_id = response.json()['benchmark_id']

# Get insights
response = requests.post(
    'http://localhost:8000/api/v3/insights',
    json={'benchmark_id': benchmark_id}
)
insights = response.json()
print(insights['summary'])
```

### JavaScript Client

```javascript
// Fetch benchmarks
const response = await fetch('http://localhost:8000/api/v3/benchmarks')
const { benchmarks } = await response.json()

// Compare benchmarks
const comparison = await fetch('http://localhost:8000/api/v3/compare', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    benchmark_ids: ['bench1', 'bench2'],
    metrics: ['request_latency', 'throughput']
  })
})
```

---

## 🔒 Security

- API rate limiting (coming soon)
- CORS configuration
- Input validation via Pydantic
- SQL injection protection
- XSS prevention in frontend

---

## 🚧 Roadmap

### v3.1 (Q1 2025)
- [ ] 3D performance landscapes
- [ ] PDF report generation
- [ ] Advanced filtering & search
- [ ] Custom metric definitions

### v3.2 (Q2 2025)
- [ ] Multi-user support
- [ ] Role-based access control
- [ ] Benchmark scheduling
- [ ] Email notifications

### v3.3 (Q3 2025)
- [ ] ML-powered predictions
- [ ] Integration with CI/CD
- [ ] Slack/Teams webhooks
- [ ] Mobile app

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

## 📝 License

Apache 2.0 License - see LICENSE file

---

## 🙏 Acknowledgments

**Built with:**
- NVIDIA AIPerf - Advanced benchmarking framework
- AI-Dynamo - Performance optimization toolkit
- Next.js - React framework
- FastAPI - Python web framework

**Powered by:**
- NVIDIA Corporation
- Open source community

---

## 📧 Support

- **Documentation**: See `/docs` folder
- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions
- **Email**: aiperf-support@nvidia.com

---

## 🌟 Show Your Support

If you find this dashboard useful, please:
- ⭐ Star the repository
- 🐛 Report bugs
- 💡 Suggest features
- 📢 Share with others

---

<div align="center">

**🚀 Built with ❤️ by NVIDIA**

*The Ultimate LLM Benchmarking Dashboard*

[![NVIDIA](https://img.shields.io/badge/NVIDIA-76B900?style=for-the-badge&logo=nvidia&logoColor=white)](https://nvidia.com)

</div>
