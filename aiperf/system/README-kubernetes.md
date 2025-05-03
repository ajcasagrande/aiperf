# AIPerf Kubernetes Support

AIPerf can be deployed and scaled in Kubernetes to handle large-scale inference benchmarking. This document explains how to set up, configure, and use AIPerf with Kubernetes.

## Prerequisites

- A functioning Kubernetes cluster
- `kubectl` configured to access your cluster
- Python 3.8+ with the `kubernetes` package installed (`pip install kubernetes`)

## Overview

When running in Kubernetes mode, AIPerf deploys:

1. A controller pod that manages the test
2. Worker pods that issue requests to the target inference endpoints
3. Services for communication between components
4. Optional ConfigMaps for configuration

The controller pod hosts the dataset manager, timing manager, records manager, and post-processors. The worker pods connect to the controller using ZeroMQ and receive their configuration and work assignments.

## Getting Started

### 1. Create a Configuration File

Create a YAML configuration file with Kubernetes settings. See `aiperf/config/examples/kubernetes_config.yaml` for an example.

Important configuration settings:

```yaml
communication:
  type: zmq  # Must be zmq for Kubernetes, not memory

kubernetes:
  enabled: true
  namespace: aiperf
  image: aiperf:latest
  persistent_volume_claim: aiperf-data  # Optional
```

### 2. Build the AIPerf Image

```bash
# From the repository root
docker build -t aiperf:latest .
```

If using a private registry, push the image:

```bash
docker tag aiperf:latest your-registry.com/aiperf:latest
docker push your-registry.com/aiperf:latest
```

Update your configuration to use the registry image:

```yaml
kubernetes:
  image: your-registry.com/aiperf:latest
```

### 3. Create the Namespace

```bash
kubectl create namespace aiperf
```

### 4. Create Persistent Volume Claim (Optional)

If you want to persist test results:

```bash
kubectl apply -f - <<EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: aiperf-data
  namespace: aiperf
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
EOF
```

### 5. Deploy to Kubernetes

Use the AIPerf CLI to deploy:

```bash
python -m aiperf.cli.aiperf_cli kubernetes apply your_config.yaml
```

Or to deploy and run:

```bash
python -m aiperf.cli.aiperf_cli run your_config.yaml --kubernetes
```

## CLI Options

AIPerf's CLI supports several Kubernetes-related commands and options:

### Kubernetes Subcommand

```bash
# Apply resources
python -m aiperf.cli.aiperf_cli kubernetes apply your_config.yaml [--dry-run]

# Delete resources
python -m aiperf.cli.aiperf_cli kubernetes delete your_config.yaml

# Check status
python -m aiperf.cli.aiperf_cli kubernetes status
```

### Run with Kubernetes

```bash
python -m aiperf.cli.aiperf_cli run your_config.yaml --kubernetes [options]
```

Options:
- `--k8s-namespace`: Override the namespace
- `--k8s-image`: Override the container image
- `--k8s-service-account`: Specify a service account
- `--k8s-no-config-map`: Disable ConfigMap usage
- `--k8s-persistent-volume-claim`: Specify a PVC for results

## Advanced Configuration

### Resource Requests and Limits

```yaml
kubernetes:
  resource_requests:
    cpu: 200m
    memory: 256Mi
  resource_limits:
    cpu: 1
    memory: 1Gi
```

### Node Selection

```yaml
kubernetes:
  node_selector:
    cloud.google.com/gke-nodepool: aiperf-pool
  tolerations:
    - key: dedicated
      operator: Equal
      value: aiperf
      effect: NoSchedule
```

### Using Different Images for Controller and Workers

```yaml
kubernetes:
  image: aiperf:latest
  controller_image: aiperf-controller:latest
  worker_image: aiperf-worker:latest
```

## Monitoring

To get the status of the deployment:

```bash
python -m aiperf.cli.aiperf_cli kubernetes status
```

You can also use standard Kubernetes tools:

```bash
kubectl -n aiperf get pods
kubectl -n aiperf logs -f deployment/aiperf-controller
```

## Troubleshooting

### Common Issues

1. **Communication Errors**
   
   Ensure you're using ZMQ communication type, not memory:
   ```yaml
   communication:
     type: zmq
   ```

2. **Image Pull Errors**
   
   If using a private registry, ensure your cluster has access:
   ```bash
   kubectl create secret docker-registry regcred \
     --docker-server=your-registry.com \
     --docker-username=user \
     --docker-password=pass \
     --docker-email=email \
     --namespace=aiperf
   ```
   
   Then add to your config:
   ```yaml
   kubernetes:
     image_pull_secrets:
       - name: regcred
   ```

3. **Permission Issues**
   
   Create a service account with appropriate permissions:
   ```bash
   kubectl apply -f service-account.yaml
   ```
   
   Then use it in your config:
   ```yaml
   kubernetes:
     service_account: aiperf-sa
   ```

4. **Pod Crashed or Not Starting**
   
   Check logs:
   ```bash
   kubectl -n aiperf logs -f pod/aiperf-controller-xyz
   kubectl -n aiperf describe pod/aiperf-controller-xyz
   ``` 