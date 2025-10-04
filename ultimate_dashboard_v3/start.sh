#!/bin/bash
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

# NVIDIA AIPerf Dashboard v3 - Quick Start Script
# Starts both backend and frontend in parallel

set -e

echo "════════════════════════════════════════════════════════════════════════════════"
echo "                    🚀 NVIDIA AIPerf Dashboard v3.0"
echo "                       Starting Services..."
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down services..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit
}

trap cleanup EXIT INT TERM

# Start backend
echo "📡 Starting Backend Server (FastAPI)..."
cd backend

# Check if port 8000 is available
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️  Port 8000 is already in use. Killing existing process..."
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    sleep 2
fi

# Activate .venv
if [ -f "../../.venv/bin/activate" ]; then
    source ../../.venv/bin/activate
elif [ -f "../.venv/bin/activate" ]; then
    source ../.venv/bin/activate
else
    echo "⚠️  No .venv found, using system python"
fi

python main.py > ../backend.log 2>&1 &
BACKEND_PID=$!
cd ..

# Wait for backend to start
echo "Waiting for backend to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:8000 > /dev/null 2>&1; then
        echo "✅ Backend is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Backend failed to start. Check backend.log for details."
        exit 1
    fi
    sleep 1
done

# Start frontend
echo ""
echo "🎨 Starting Frontend Server (Next.js)..."
cd frontend
npm run dev > ../frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

# Wait for frontend to start
echo "Waiting for frontend to be ready..."
for i in {1..60}; do
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        echo "✅ Frontend is ready!"
        break
    fi
    if [ $i -eq 60 ]; then
        echo "❌ Frontend failed to start. Check frontend.log for details."
        exit 1
    fi
    sleep 1
done

echo ""
echo "════════════════════════════════════════════════════════════════════════════════"
echo "✨ Dashboard is running!"
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""
echo "${GREEN}🌐 Frontend:${NC}  http://localhost:3000"
echo "${GREEN}📊 Backend API:${NC} http://localhost:8000"
echo "${GREEN}📖 API Docs:${NC}   http://localhost:8000/docs"
echo ""
echo "Logs:"
echo "  Backend:  tail -f backend.log"
echo "  Frontend: tail -f frontend.log"
echo ""
echo "Press Ctrl+C to stop all services"
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""

# Try to open browser
if command -v xdg-open > /dev/null; then
    xdg-open http://localhost:3000 2>/dev/null
elif command -v open > /dev/null; then
    open http://localhost:3000 2>/dev/null
fi

# Keep script running
wait
