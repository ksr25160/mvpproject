#!/bin/bash

# Azure Web App Startup Script
echo "=== Azure Web App Startup ==="
echo "Working directory: $(pwd)"
echo "Available files:"
ls -la

# Set environment variables
export PORT=${PORT:-8000}
export PYTHONPATH="/home/site/wwwroot:$PYTHONPATH"

echo "PORT: $PORT"
echo "PYTHONPATH: $PYTHONPATH"

# Change to the application directory
cd /home/site/wwwroot

# Install dependencies
echo "Installing dependencies..."
pip install --no-cache-dir -r requirements.txt

# Create logs directory
mkdir -p logs

# Start the application
echo "Starting Python application on port $PORT..."
python main.py
