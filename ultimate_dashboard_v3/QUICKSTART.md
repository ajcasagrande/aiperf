<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# ⚡ Quick Start Guide - NVIDIA AIPerf Dashboard v3

Get up and running in **5 minutes**!

## 🎯 Step 1: Clone & Setup (2 minutes)

```bash
cd ultimate_dashboard_v3

# Run the automated setup script
chmod +x setup.sh
./setup.sh
```

The setup script will:
- ✅ Check prerequisites (Python 3.10+, Node.js 18+)
- ✅ Install backend dependencies
- ✅ Install frontend dependencies
- ✅ Create data directories

## 🚀 Step 2: Start the Dashboard (1 minute)

### Option A: Automated Start (Recommended)

```bash
chmod +x start.sh
./start.sh
```

This will:
- Start the backend API server
- Start the frontend web server
- Open your browser automatically

### Option B: Manual Start

**Terminal 1 - Backend:**
```bash
cd backend
source venv/bin/activate
python main.py
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

## 🌐 Step 3: Access the Dashboard (30 seconds)

Open your browser and navigate to:
- **Dashboard**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs

## 📊 Step 4: Upload Your First Benchmark (1 minute)

1. Click **"Upload Benchmark"** button
2. Select your `profile_export.jsonl` file
3. Optionally add `profile_export_aiperf.json`
4. Click Upload

That's it! Your dashboard is now showing your benchmark data.

---

## 🎓 Next Steps

### Explore Features
- View the main dashboard
- Check out AI-powered insights
- Compare multiple benchmarks
- Export reports

### Read Documentation
- [README.md](README.md) - Complete documentation
- [FEATURES.md](FEATURES.md) - Full feature list
- API Docs - http://localhost:8000/docs

### Customize
- Configure themes (dark/light)
- Set up alerts
- Create custom views
- Export data

---

## 🐳 Docker Quick Start

Prefer Docker? Even faster setup:

```bash
# Build and start everything
docker-compose up --build

# Access dashboard
open http://localhost:3000
```

---

## 🛠️ Troubleshooting

### Backend won't start
```bash
# Check if port 8000 is in use
lsof -i :8000

# View backend logs
tail -f backend.log
```

### Frontend won't start
```bash
# Check if port 3000 is in use
lsof -i :3000

# View frontend logs
tail -f frontend.log
```

### Dependencies fail to install
```bash
# Update package managers
pip install --upgrade pip
npm install -g npm@latest

# Try again
./setup.sh
```

---

## 📞 Need Help?

- **Documentation**: See README.md
- **Issues**: Create a GitHub issue
- **API Reference**: http://localhost:8000/docs

---

## ⭐ Quick Tips

1. **Use Chrome/Edge** for best performance
2. **Enable dark mode** for better visibility
3. **Upload aggregate JSON** for enhanced insights
4. **Compare benchmarks** to track improvements
5. **Export reports** to share with your team

---

**Total Time: ~5 minutes from zero to dashboard! 🚀**

*Powered by NVIDIA AIPerf*
