#!/bin/bash
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

# NVIDIA AIPerf Dashboard v3 - Quick Setup Script
# This script automates the entire setup process

set -e

echo "════════════════════════════════════════════════════════════════════════════════"
echo "                    🚀 NVIDIA AIPerf Dashboard v3.0"
echo "                       Quick Setup Script"
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check prerequisites
echo "📋 Checking prerequisites..."

command -v python3 >/dev/null 2>&1 || { echo "❌ Python 3 is required but not installed. Aborting." >&2; exit 1; }
echo "✅ Python 3 found: $(python3 --version)"

command -v node >/dev/null 2>&1 || { echo "❌ Node.js is required but not installed. Aborting." >&2; exit 1; }
echo "✅ Node.js found: $(node --version)"

command -v npm >/dev/null 2>&1 || { echo "❌ npm is required but not installed. Aborting." >&2; exit 1; }
echo "✅ npm found: $(npm --version)"

echo ""
echo "════════════════════════════════════════════════════════════════════════════════"
echo "📦 Setting up Backend (FastAPI)"
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""

cd backend

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo "✅ Backend setup complete!"
echo ""

cd ..

echo "════════════════════════════════════════════════════════════════════════════════"
echo "🎨 Setting up Frontend (Next.js)"
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""

cd frontend

# Install dependencies
echo "Installing Node.js dependencies (this may take a few minutes)..."
npm install --silent

echo "✅ Frontend setup complete!"
echo ""

cd ..

# Create data directory
echo "Creating data directory..."
mkdir -p data
echo "✅ Data directory created"

echo ""
echo "════════════════════════════════════════════════════════════════════════════════"
echo "✨ Setup Complete!"
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""
echo "To start the dashboard:"
echo ""
echo "1️⃣  Start Backend (Terminal 1):"
echo "   ${BLUE}cd backend && source venv/bin/activate && python main.py${NC}"
echo ""
echo "2️⃣  Start Frontend (Terminal 2):"
echo "   ${BLUE}cd frontend && npm run dev${NC}"
echo ""
echo "3️⃣  Open your browser:"
echo "   ${GREEN}🌐 Frontend: http://localhost:3000${NC}"
echo "   ${GREEN}📊 Backend API: http://localhost:8000${NC}"
echo "   ${GREEN}📖 API Docs: http://localhost:8000/docs${NC}"
echo ""
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""
echo "Or use the quick start command:"
echo "${YELLOW}./start.sh${NC}"
echo ""
echo "Happy benchmarking! 🚀"
echo ""
