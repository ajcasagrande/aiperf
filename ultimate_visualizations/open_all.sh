#!/bin/bash
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
# Open all Ultimate AIPerf visualizations in browser

echo "🚀 Opening Ultimate AIPerf Visualization Suite..."
echo ""

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Function to open URL based on OS
open_browser() {
    local url="$1"
    if command -v xdg-open > /dev/null; then
        xdg-open "$url" &
    elif command -v open > /dev/null; then
        open "$url"
    elif command -v start > /dev/null; then
        start "$url"
    else
        echo "⚠️  Could not detect browser opener. Please open manually: $url"
    fi
}

# Open index first
echo "📊 Opening index page..."
open_browser "file://${SCRIPT_DIR}/index.html"
sleep 1

# Ask if user wants to open all visualizations
read -p "Open all 12 visualizations? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Opening all visualizations..."
    for i in {1..12}; do
        file=$(printf "%02d_*.html" $i)
        filepath=$(ls ${SCRIPT_DIR}/$file 2>/dev/null | head -1)
        if [ -f "$filepath" ]; then
            filename=$(basename "$filepath")
            echo "  ✓ Opening $filename"
            open_browser "file://${filepath}"
            sleep 0.5
        fi
    done
    echo ""
    echo "✨ All visualizations opened!"
else
    echo ""
    echo "ℹ️  You can view visualizations from the index page"
fi

echo ""
echo "Done! Navigate through the tabs to explore your performance data."

