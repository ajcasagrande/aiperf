#!/bin/bash
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
# Quick launcher for performance visualizations

echo "🎨 Opening Performance Visualizations..."
echo ""
echo "Choose an option:"
echo "1) Interactive Dashboard (recommended)"
echo "2) All Static PNGs"
echo "3) Individual Chart Browser"
echo "4) Start HTTP Server"
echo ""
read -p "Enter choice (1-4): " choice

case $choice in
    1)
        echo "Opening dashboard..."
        xdg-open performance_visualizations/dashboard.html 2>/dev/null || \
        firefox performance_visualizations/dashboard.html 2>/dev/null || \
        chromium performance_visualizations/dashboard.html 2>/dev/null || \
        echo "Please open: performance_visualizations/dashboard.html"
        ;;
    2)
        echo "Opening static charts..."
        eog performance_visualizations/*.png 2>/dev/null || \
        feh performance_visualizations/*.png 2>/dev/null || \
        echo "Please view: performance_visualizations/*.png"
        ;;
    3)
        echo "Choose a chart:"
        select file in performance_visualizations/*.html performance_visualizations/*.png; do
            xdg-open "$file" 2>/dev/null || firefox "$file" 2>/dev/null || echo "Open: $file"
            break
        done
        ;;
    4)
        echo "Starting HTTP server on port 8000..."
        echo "Open: http://localhost:8000/performance_visualizations/dashboard.html"
        cd performance_visualizations && python -m http.server 8000
        ;;
    *)
        echo "Invalid choice. Opening dashboard..."
        xdg-open performance_visualizations/dashboard.html 2>/dev/null
        ;;
esac
