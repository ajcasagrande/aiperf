#!/bin/bash
# Script to run the mock OpenAI API server and set up AIPerf to use it

set -e

# Set default port
PORT=8000

# Parse command line arguments
while getopts "p:" opt; do
  case $opt in
    p) PORT=$OPTARG ;;
    *) echo "Usage: $0 [-p PORT]" >&2; exit 1 ;;
  esac
done

# Check if Python and required packages are installed
echo "Checking dependencies..."
if ! command -v python3 &> /dev/null; then
    echo "Python3 is required but not installed. Please install Python3."
    exit 1
fi

# Install required packages if not already installed
echo "Installing required packages..."
python3 -m pip install -r requirements-mock.txt

# Make sure we have the example OpenAI config
CONFIG_FILE="aiperf/config/examples/openai_example.yaml"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Example config file not found: $CONFIG_FILE"
    exit 1
fi

# Create a modified config file that points to the mock server
echo "Creating modified config file..."
python3 modify_config.py "$CONFIG_FILE" --port "$PORT"

# Start the mock server
echo "Starting mock OpenAI API server on port $PORT..."
echo "Press Ctrl+C to stop the server"
python3 mock_openai_server.py

# Note: The script will stay running until the user presses Ctrl+C 