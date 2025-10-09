#!/bin/bash
# Monitor configuration phase in real-time

set -e

echo "Starting deployment..."
python debug_k8s_deploy.py > /tmp/monitor-deploy.log 2>&1 &
DEPLOY_PID=$!

sleep 10

NS=$(kubectl get namespaces | grep aiperf-debug | tail -1 | awk '{print $1}')
echo "Namespace: $NS"

# Monitor for 3 minutes
for i in {1..36}; do
    sleep 5
    echo ""
    echo "===== Check $i (${i}x5=${$((i*5))}s) ====="

    kubectl logs system-controller -n $NS --tail=20 2>&1 | grep -E "(Registered|CONFIGURING|CONFIGURED|PROFILING|ERROR)" | tail -10

    # Check if all pods still running
    kubectl get pods -n $NS 2>&1 | grep -v "NAME"

    # Check if system controller completed
    STATUS=$(kubectl get pod system-controller -n $NS -o jsonpath='{.status.phase}' 2>/dev/null || echo "Unknown")
    if [ "$STATUS" = "Succeeded" ] || [ "$STATUS" = "Completed" ]; then
        echo "System controller completed!"
        kubectl logs system-controller -n $NS --tail=100
        break
    fi
done

wait $DEPLOY_PID || true
echo "Deployment script completed"
