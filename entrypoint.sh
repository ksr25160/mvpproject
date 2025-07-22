#!/bin/bash
# Backup entrypoint script
# Main startup is handled by Azure Portal "python main.py" command

echo "=== Backup Entrypoint Script ==="
echo "This is a backup script. Main startup uses: python main.py"
echo "Working directory: $(pwd)"
echo "PORT: ${PORT:-8000}"

# Only run if explicitly called with --backup flag
if [ "$1" = "--backup" ]; then
    echo "Running as backup entrypoint..."
    export PYTHONPATH="/home/site/wwwroot:$PYTHONPATH"
    mkdir -p logs
    exec python main.py
else
    echo "Use: $0 --backup to run as backup"
    echo "Normal startup should use Azure Portal startup command: python main.py"
fi
