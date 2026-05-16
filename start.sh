#!/bin/bash

echo ""
echo "⬡ Starting NexChat..."
echo "====================="
echo ""
echo "Backend  → http://localhost:8000"
echo "Frontend → http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both servers."
echo ""

# Start backend
cd backend
python main.py &
BACKEND_PID=$!
cd ..

# Wait a moment for backend to boot
sleep 2

# Start frontend
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

# Handle Ctrl+C
trap "echo ''; echo 'Stopping...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT

wait
