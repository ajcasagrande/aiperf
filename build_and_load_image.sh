#!/bin/bash
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

# Build AIPerf image and load into minikube

set -e

echo "Building AIPerf image for Kubernetes..."

# Build locally first
docker build -t aiperf:k8s-new -f Dockerfile.kubernetes . 2>&1 | tail -20

echo ""
echo "Saving image to tar..."
docker save aiperf:k8s-new -o /tmp/aiperf-k8s.tar

echo "Loading image into minikube..."
minikube image load /tmp/aiperf-k8s.tar

echo "Cleaning up tar file..."
rm /tmp/aiperf-k8s.tar

echo ""
echo "✓ Image loaded into minikube"
echo ""

# Verify
echo "Images in minikube:"
minikube ssh -- docker images | grep aiperf | head -5

echo ""
echo "Done! Use image: aiperf:k8s-new"
