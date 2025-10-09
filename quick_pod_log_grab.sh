#!/bin/bash
# Quickly grab logs from service pods while they're running

set -e

echo "Starting deployment and log capture..."
python debug_k8s_deploy.py > /tmp/debug-output.log 2>&1 &
DEBUG_PID=$!

# Wait for namespace to be created
sleep 5

# Find the namespace
NS=$(kubectl get namespaces | grep aiperf-debug | tail -1 | awk '{print $1}' || echo "")

if [ -z "$NS" ]; then
    echo "No namespace found yet, waiting..."
    sleep 10
    NS=$(kubectl get namespaces | grep aiperf-debug | tail -1 | awk '{print $1}' || echo "")
fi

echo "Namespace: $NS"

# Wait for pods to appear
sleep 15

echo "=== Pods at 15s ==="
kubectl get pods -n $NS

# Try to get logs from each service pod quickly
for service in dataset-manager timing-manager worker-manager records-manager telemetry-manager; do
    echo ""
    echo "=== Logs: $service ==="
    kubectl logs $service -n $NS --tail=200 2>&1 || echo "Not available yet"
done

# Wait for debug script to complete
wait $DEBUG_PID || true

echo ""
echo "Debug script completed"
echo "Namespace: $NS"
