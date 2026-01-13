#!/bin/bash

echo "🚀 Starting FastAPI Backend..."
echo "================================"

cd "$(dirname "$0")/backend"

# Check if Neo4j is running
echo "📡 Checking Neo4j connection..."
if ! nc -z localhost 7687 2>/dev/null; then
    echo "❌ Error: Neo4j is not running on port 7687"
    echo "Please start Neo4j first: docker-compose up -d"
    exit 1
fi

echo "✅ Neo4j is running"
echo ""

# Install dependencies if needed
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

echo "📦 Installing dependencies..."
source venv/bin/activate
pip install -r requirements.txt

echo ""
echo "🎉 Starting FastAPI server on http://localhost:8000"
echo "📚 API docs available at http://localhost:8000/docs"
echo ""

python3 main.py
