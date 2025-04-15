#!/bin/bash

# TripleCaptain Development Server Stop Script

echo "🛑 Stopping TripleCaptain Development Environment"
echo "==============================================="

# Kill tmux session if it exists
if tmux has-session -t triplecaptain 2>/dev/null; then
    echo "🔪 Stopping tmux session..."
    tmux kill-session -t triplecaptain
    echo "✅ tmux session stopped"
fi

# Stop Docker services
echo "🐳 Stopping Docker services..."
docker-compose down

# Clean up any remaining processes
echo "🧹 Cleaning up processes..."
pkill -f "uvicorn app.main:app"
pkill -f "npm start"

echo "✅ All services stopped"
echo "💡 To start again, run: ./scripts/start_dev.sh"