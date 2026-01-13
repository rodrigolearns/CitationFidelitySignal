#!/bin/bash

echo "🚀 Starting React Frontend..."
echo "================================"

cd "$(dirname "$0")/frontend"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing npm dependencies..."
    npm install
fi

echo ""
echo "🎉 Starting Vite dev server on http://localhost:3000"
echo ""

npm run dev
