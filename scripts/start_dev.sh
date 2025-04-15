#!/bin/bash

# TripleCaptain Development Server Start Script

echo "🏆 Starting TripleCaptain Development Environment"
echo "================================================"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Start database services
echo "🐳 Starting database services..."
docker-compose up -d

# Wait for services to be ready
echo "⏱️  Waiting for services to start..."
sleep 10

# Check if services are healthy
echo "🏥 Checking service health..."
if docker-compose ps | grep -q "unhealthy"; then
    echo "⚠️  Some services may not be healthy. Check docker-compose logs"
fi

# Create a new tmux session with multiple panes
if command -v tmux &> /dev/null; then
    echo "🖥️  Starting development servers in tmux..."
    
    # Create new tmux session
    tmux new-session -d -s triplecaptain
    
    # Split window horizontally
    tmux split-window -h
    
    # Send commands to each pane
    tmux send-keys -t triplecaptain:0.0 'cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000' C-m
    tmux send-keys -t triplecaptain:0.1 'cd frontend && npm start' C-m
    
    # Attach to the session
    echo "✅ Development servers started in tmux session 'triplecaptain'"
    echo "📝 Commands:"
    echo "   - Attach to session: tmux attach -t triplecaptain"
    echo "   - Detach from session: Ctrl+B, then D"
    echo "   - Kill session: tmux kill-session -t triplecaptain"
    echo ""
    echo "🌐 URLs:"
    echo "   - Frontend: http://localhost:3000"
    echo "   - Backend API: http://localhost:8000"
    echo "   - API Docs: http://localhost:8000/docs"
    echo ""
    echo "Press any key to attach to the tmux session (or Ctrl+C to exit)..."
    read -n 1
    tmux attach -t triplecaptain
else
    echo "📝 tmux not found. Starting servers manually:"
    echo "Terminal 1: cd backend && uvicorn app.main:app --reload"
    echo "Terminal 2: cd frontend && npm start"
    echo ""
    echo "🌐 URLs will be:"
    echo "   - Frontend: http://localhost:3000" 
    echo "   - Backend API: http://localhost:8000"
    echo "   - API Docs: http://localhost:8000/docs"
fi