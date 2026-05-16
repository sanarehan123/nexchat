#!/bin/bash
set -e

echo ""
echo "🚀 Setting up NexChat..."
echo "========================"

# Backend
echo ""
echo "📦 Installing Python backend dependencies..."
cd backend
pip install -r requirements.txt -q
cd ..

# Frontend
echo ""
echo "📦 Installing Next.js frontend dependencies..."
cd frontend
npm install --silent
cd ..

echo ""
echo "✅ Setup complete!"
echo ""
echo "To START the app, run:  ./start.sh"
echo ""
