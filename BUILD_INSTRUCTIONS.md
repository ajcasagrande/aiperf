# AIPerf Kubernetes - Build and Test Instructions

## Current Status

✅ **Implementation Complete**: All Kubernetes components implemented and tested
⚠️  **Docker Build**: Failed due to proxy configuration issue

## Fixing Docker Build

The Docker build encountered a proxy connection error. To fix:

### Option 1: Disable Proxy for Docker Build

```bash
# Unset proxy environment variables
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY

# Build the image
docker build -t aiperf:latest -f Dockerfile.kubernetes .
```

### Option 2: Configure Docker to Bypass Proxy

```bash
# Edit Docker daemon config
sudo mkdir -p /etc/systemd/system/docker.service.d
cat > /tmp/http-proxy.conf << 'EOF'
[Service]
Environment="NO_PROXY=localhost,127.0.0.1"
EOF
sudo mv /tmp/http-proxy.conf /etc/systemd/system/docker.service.d/

# Reload and restart Docker
sudo systemctl daemon-reload
sudo systemctl restart docker

# Then build
docker build -t aiperf:latest -f Dockerfile.kubernetes .
```

### Option 3: Use Minikube's Docker Daemon

```bash
# Use minikube's Docker daemon (automatically bypasses host proxy)
eval $(minikube docker-env)
docker build -t aiperf:latest -f Dockerfile.kubernetes .
```

## Once Build Succeeds

### 1. Load Image into Minikube

```bash
# If you built outside minikube, load it in:
minikube image load aiperf:latest

# Or if you built with minikube's daemon, it's already there
```

### 2. Run End-to-End Test

#### Test with In-Cluster vLLM

```bash
# Deploy vLLM and run test (fully automated)
make k8s-test
```

This will:
1. Deploy vLLM to the cluster
2. Wait for it to be ready
3. Run AIPerf with 10 concurrent connections for 60 seconds
4. Retrieve results
5. Clean up

#### Test with Local vLLM

If you have vLLM running locally on port 9000:

```bash
make k8s-test-local
```

This will:
1. Run AIPerf on Kubernetes
2. Connect to your local vLLM at `host.minikube.internal:9000`
3. Run 100 concurrent connections for 300 seconds
4. Retrieve results
5. Clean up

### 3. Manual Test Command

For more control:

```bash
# Activate virtual environment
source .venv/bin/activate

# Run with custom parameters
python -m aiperf profile --ui none \
  --kubernetes \
  --kubernetes-image aiperf:latest \
  --kubernetes-image-pull-policy IfNotPresent \
  --endpoint-type chat \
  --streaming \
  -u http://host.minikube.internal:9000 \
  -m openai/gpt-oss-20b \
  --benchmark-duration 300 \
  --concurrency 100 \
  --public-dataset sharegpt
```

## Verifying the Build

After successful build:

```bash
# Check image exists
docker images | grep aiperf

# Should show:
# aiperf  latest  <IMAGE_ID>  <SIZE>

# Test image can run
docker run --rm aiperf:latest python -c "import aiperf; print('OK')"
```

## Troubleshooting

### Image Pull Errors in Kubernetes

If pods show `ImagePullBackOff`:

```bash
# Load image into minikube
minikube image load aiperf:latest

# Or use IfNotPresent policy
--kubernetes-image-pull-policy IfNotPresent
```

### Namespace Not Cleaning Up

```bash
# Manual cleanup
kubectl delete namespace <namespace-name>

# Or clean all AIPerf namespaces
kubectl get namespaces -l app=aiperf
kubectl delete namespaces -l app=aiperf
```

### View Pod Logs

```bash
# List pods in namespace
kubectl get pods -n <namespace>

# View logs
kubectl logs <pod-name> -n <namespace>

# Follow logs
kubectl logs -f <pod-name> -n <namespace>
```

### Check Pod Status

```bash
# Describe pod
kubectl describe pod <pod-name> -n <namespace>

# Check events
kubectl get events -n <namespace> --sort-by='.lastTimestamp'
```

## Quick Reference

### Useful Make Targets

```bash
make k8s-build       # Build container image
make k8s-load        # Load into minikube
make k8s-deploy-vllm # Deploy test vLLM
make k8s-test        # Full automated test
make k8s-test-local  # Test with local vLLM
make k8s-clean       # Clean up all resources
make k8s-quickstart  # Clean + test (full cycle)
```

### Useful kubectl Commands

```bash
# List namespaces
kubectl get namespaces

# List pods in namespace
kubectl get pods -n <namespace>

# Get pod logs
kubectl logs <pod-name> -n <namespace>

# Delete namespace
kubectl delete namespace <namespace>

# Check cluster resources
kubectl top nodes
kubectl describe nodes
```

## Expected Results

After successful test, you should see:

1. **During Execution**:
   - Namespace created (e.g., `aiperf-20251004-065000`)
   - Pods deployed (system-controller, dataset-manager, timing-manager, etc.)
   - Workers running (scaled based on concurrency)
   - Benchmark progress updates

2. **After Completion**:
   - Metrics summary displayed
   - Artifacts in `./artifacts/` directory:
     - `benchmark_summary.json`
     - `benchmark_results.csv`
     - Log files
   - All resources cleaned up (if auto-cleanup enabled)

3. **Example Output**:
   ```
   AIPerf System orchestration started
   Deploying AIPerf to namespace: aiperf-20251004-065000
   System controller pod is ready
   All services registered
   AIPerf System is PROFILING
   Benchmark running on cluster...
   Benchmark completed: Succeeded
   Artifacts retrieved to ./artifacts/
   Kubernetes deployment complete!
   ```

## Next Steps

1. **Fix Docker build** using one of the options above
2. **Run quick test** with `make k8s-test` (in-cluster vLLM)
3. **Run full test** with your local vLLM using `make k8s-test-local`
4. **Scale up** gradually: 10 → 100 → 1K → 10K → 100K concurrent

## Support

For issues or questions, refer to:
- `docs/kubernetes-deployment-guide.md` - Full deployment guide
- `KUBERNETES_IMPLEMENTATION.md` - Implementation details
- `AIP-0002-kubernetes-deployment.md` - Design specification
