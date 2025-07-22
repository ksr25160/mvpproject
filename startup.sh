#!/bin/bash
# Azure App Service Startup Script for Streamlit Application

echo "Starting Meeting AI Application..."

# Install any additional dependencies if needed
pip install --no-cache-dir -r requirements.txt

# Create logs directory if it doesn't exist
mkdir -p logs

# Set environment variables for Streamlit
export STREAMLIT_SERVER_PORT=8501
export STREAMLIT_SERVER_ADDRESS=0.0.0.0
export STREAMLIT_SERVER_HEADLESS=true
export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
export STREAMLIT_SERVER_ENABLE_CORS=false
export STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false

# Add Python path
export PYTHONPATH="${PYTHONPATH}:/home/site/wwwroot"

# Change to application directory
cd /home/site/wwwroot

# Start the Streamlit application
echo "Starting Streamlit on port $STREAMLIT_SERVER_PORT..."
streamlit run app/app.py --server.port=$STREAMLIT_SERVER_PORT --server.address=$STREAMLIT_SERVER_ADDRESS --server.headless=true --browser.gatherUsageStats=false
