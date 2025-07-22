#!/bin/bash
# Azure App Service Startup Script (Backup/Debug only)
# Main startup is handled by Azure Portal "python main.py" command

echo "Startup script - This is a backup/debug script"
echo "Main startup should be handled by Azure Portal startup command: python main.py"
echo "Current directory: $(pwd)"
echo "Directory contents: $(ls -la)"

# Set basic environment variables
export PYTHONPATH="/home/site/wwwroot:$PYTHONPATH"
export PORT=${PORT:-8000}

# If called directly, run main.py
if [ "$1" = "--run" ]; then
    echo "Running main.py as backup..."
    python main.py
else
    echo "Use: $0 --run to execute as backup"
    echo "Normal startup should use Azure Portal startup command"
fi
