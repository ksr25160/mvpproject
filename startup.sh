#!/bin/bash
# Azure App Service Startup Script for Streamlit Application

echo "Starting Meeting AI Application..."
echo "Current directory: $(pwd)"
echo "Directory contents: $(ls -la)"

# Install any additional dependencies if needed
pip install --no-cache-dir -r requirements.txt

# Create logs directory if it doesn't exist
mkdir -p logs

# Set environment variables for Streamlit
export STREAMLIT_SERVER_PORT=${PORT:-8000}
export STREAMLIT_SERVER_ADDRESS=0.0.0.0
export STREAMLIT_SERVER_HEADLESS=true
export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
export STREAMLIT_SERVER_ENABLE_CORS=false
export STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false

# Add Python path
export PYTHONPATH="${PYTHONPATH}:/home/site/wwwroot"

# Change to application directory
cd /home/site/wwwroot

# Check if app/app.py exists
if [ -f "app/app.py" ]; then
    echo "Found app/app.py, starting Streamlit on port $STREAMLIT_SERVER_PORT..."
    streamlit run app/app.py --server.port=$STREAMLIT_SERVER_PORT --server.address=$STREAMLIT_SERVER_ADDRESS --server.headless=true --browser.gatherUsageStats=false
elif [ -f "main.py" ]; then
    echo "Found main.py, starting with Python on port $STREAMLIT_SERVER_PORT..."
    python main.py
else
    echo "No main application file found. Available files:"
    ls -la
    exit 1
fi
