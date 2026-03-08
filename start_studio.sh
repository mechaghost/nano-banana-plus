#!/bin/bash

# ==========================================
# AI Image Studio - Local Launch Script
# ==========================================
# This script boots both the FastAPI backend
# and the Vite/React frontend in the background.
# ==========================================

# Use absolute paths so this can be executed from anywhere
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🍌 Starting AI Image Studio (nano-banana-plus)..."

# 1. Kill any existing instances holding the ports
echo "🧹 Cleaning up old processes..."
lsof -ti:43211 | xargs kill -9 2>/dev/null
lsof -ti:43210 | xargs kill -9 2>/dev/null

# 2. Boot the Backend (FastAPI)
echo "🚀 Booting FastAPI Backend (Port 43211)..."
cd "$PROJECT_DIR/server" || exit
source venv/bin/activate
python3 main.py > .backend_log.txt 2>&1 &
BACKEND_PID=$!

# Wait a second to ensure backend grabs the port first
sleep 2

# 3. Boot the Frontend (Vite)
echo "🎨 Booting React Frontend (Port 43210)..."
cd "$PROJECT_DIR/web" || exit
npm run dev > .frontend_log.txt 2>&1 &
FRONTEND_PID=$!

echo ""
echo "✅ AI Image Studio is now running in the background!"
echo "--------------------------------------------------------"
echo "🖥️  Frontend UI:  http://127.0.0.1:43210"
echo "🔌 Backend API:  http://127.0.0.1:43211"
echo "--------------------------------------------------------"
echo "To stop the servers, run: lsof -ti:43211 | xargs kill -9; lsof -ti:43210 | xargs kill -9"

# Automatically open the browser to the UI
open "http://127.0.0.1:43210"

# Keep script alive to hold the background processes (optional, but helps if run in an active terminal)
wait
