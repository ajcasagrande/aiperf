#!/bin/bash
# Check service pod logs in the latest AIPerf namespace

NAMESPACE=$(kubectl get namespaces | grep aiperf-debug | tail -1 | awk '{print $1}')

if [ -z "$NAMESPACE" ]; then
    echo "No AIPerf debug namespace found"
    exit 1
fi

echo "Checking namespace: $NAMESPACE"
echo ""

echo "=== Pods ==="
kubectl get pods -n $NAMESPACE
echo ""

echo "=== Events (recent) ==="
kubectl get events -n $NAMESPACE --sort-by='.lastTimestamp' | tail -20
echo ""

# Try to get logs from each service if it exists
for service in dataset-manager timing-manager worker-manager records-manager telemetry-manager; do
    echo "=== Logs: $service ==="
    kubectl logs $service -n $NAMESPACE --tail=30 2>&1 | head -20
    echo ""
done
