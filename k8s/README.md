<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# AIPerf Kubernetes Integration

This directory contains all the necessary resources to deploy and run AIPerf on Kubernetes.

## Structure

```
k8s/
├── README.md                           # This file
├── crds/                              # Custom Resource Definitions
│   ├── benchmarkrun-crd.yaml         # BenchmarkRun resource definition
│   └── benchmarktemplate-crd.yaml    # BenchmarkTemplate resource definition
├── helm/                              # Helm charts
│   └── aiperf/                        # Main AIPerf Helm chart
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
│           ├── configmap.yaml
│           ├── hpa.yaml
│           ├── rbac.yaml
│           ├── system-controller-deployment.yaml
│           ├── workers-deployment.yaml
│           └── _helpers.tpl
└── examples/                          # Example configurations
    ├── simple-benchmark.yaml         # Basic benchmark examples
    └── benchmark-template.yaml       # Template examples
```

## Quick Start

### Prerequisites

1. **Kubernetes Cluster**: v1.24+ with proper RBAC enabled
2. **Helm**: v3.8+ installed locally
3. **Storage Class**: Default storage class configured for persistent volumes
4. **Metrics Server**: For HPA functionality (optional but recommended)
5. **Prometheus Operator**: For monitoring (optional)

### Installation

1. **Install Custom Resource Definitions**:
   ```bash
   kubectl apply -f crds/
   ```

2. **Create Namespace**:
   ```bash
   kubectl create namespace aiperf-system
   ```

3. **Install AIPerf using Helm**:
   ```bash
   # Add dependencies (optional, for monitoring)
   helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
   helm repo add grafana https://grafana.github.io/helm-charts
   helm repo update

   # Install AIPerf
   helm install aiperf ./helm/aiperf \
     --namespace aiperf-system \
     --set monitoring.prometheus.enabled=true \
     --set workers.autoscaling.enabled=true
   ```

4. **Verify Installation**:
   ```bash
   kubectl get pods -n aiperf-system
   kubectl get svc -n aiperf-system
   ```

## Configuration

### Basic Configuration

The Helm chart provides extensive configuration options. Key settings include:

```yaml
# values.yaml
aiperf:
  benchmark:
    model: "your-model-name"
    endpoint_type: "chat"
    concurrency: 10
    request_count: 1000

workers:
  replicaCount: 10
  autoscaling:
    enabled: true
    minReplicas: 5
    maxReplicas: 100
    targetCPUUtilization: 70

monitoring:
  prometheus:
    enabled: true
  grafana:
    enabled: true
```

### Advanced Configuration

For production deployments, consider:

1. **Resource Management**:
   ```yaml
   workers:
     resources:
       requests:
         memory: "2Gi"
         cpu: "1"
       limits:
         memory: "4Gi"
         cpu: "2"
   ```

2. **Security**:
   ```yaml
   security:
     rbac:
       create: true
     podSecurityContext:
       runAsNonRoot: true
       runAsUser: 1000
   ```

3. **Networking**:
   ```yaml
   networking:
     networkPolicies:
       enabled: true
     serviceMesh:
       enabled: true
       type: "istio"
   ```

## Usage

### Running a Simple Benchmark

1. **Create a BenchmarkRun resource**:
   ```bash
   kubectl apply -f examples/simple-benchmark.yaml
   ```

2. **Monitor the benchmark**:
   ```bash
   kubectl get benchmarkrun -n aiperf-benchmarks
   kubectl describe benchmarkrun llama-2-simple-test -n aiperf-benchmarks
   ```

3. **View logs**:
   ```bash
   kubectl logs -n aiperf-system deployment/aiperf-system-controller
   kubectl logs -n aiperf-system deployment/aiperf-workers
   ```

### Using Templates

1. **Create a template**:
   ```bash
   kubectl apply -f examples/benchmark-template.yaml
   ```

2. **Use the template in a benchmark run**:
   ```yaml
   apiVersion: aiperf.nvidia.com/v1
   kind: BenchmarkRun
   metadata:
     name: my-benchmark
   spec:
     templateRef:
       name: llama-2-standard
       variant: heavy
     model: "llama-2-13b"
   ```

### Scaling

AIPerf automatically scales workers based on:

- CPU/Memory utilization
- Custom metrics (ZMQ queue depth)
- Manual scaling via HPA

To manually scale:
```bash
kubectl scale deployment aiperf-workers --replicas=20 -n aiperf-system
```

## Monitoring

### Prometheus Metrics

AIPerf exposes metrics for:

- Request throughput and latency
- Worker utilization
- Error rates
- Custom AI model metrics

### Grafana Dashboards

Pre-configured dashboards are available for:

- System overview
- Worker performance
- Request/response metrics
- Resource utilization

Access via:
```bash
kubectl port-forward svc/grafana 3000:3000 -n aiperf-system
```

### Alerts

Common alerts include:

- High worker CPU usage
- System controller down
- High error rates
- Queue depth issues

## Security

### RBAC Configuration

AIPerf uses minimal required permissions:

- **System Controller**: Full access to AIPerf resources, limited cluster access
- **Workers**: Read-only access to configs and secrets

### Network Security

- Network policies isolate components
- Service mesh provides mTLS (when enabled)
- Pod security contexts enforce non-root execution

### Secrets Management

Model credentials and API keys are stored as Kubernetes secrets:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: model-credentials
  namespace: aiperf-system
type: Opaque
data:
  api-key: <base64-encoded-key>
  endpoint-url: <base64-encoded-url>
```

## Troubleshooting

### Common Issues

1. **Pods stuck in Pending**:
   - Check resource requests vs. node capacity
   - Verify storage class availability
   - Check node selectors and tolerations

2. **Workers not scaling**:
   - Ensure metrics server is running
   - Verify HPA configuration
   - Check custom metrics availability

3. **ZMQ connection issues**:
   - Verify service DNS resolution
   - Check network policies
   - Examine ZMQ proxy logs

### Debugging Commands

```bash
# Check overall system status
kubectl get all -n aiperf-system

# Examine custom resources
kubectl get benchmarkruns -A
kubectl describe benchmarkrun <name> -n <namespace>

# Check logs
kubectl logs -f deployment/aiperf-system-controller -n aiperf-system
kubectl logs -f deployment/aiperf-workers -n aiperf-system

# Debug networking
kubectl exec -it deployment/aiperf-workers -n aiperf-system -- nslookup aiperf-zmq-proxy

# Check metrics
kubectl top pods -n aiperf-system
kubectl get hpa -n aiperf-system
```

### Performance Tuning

1. **Worker Resources**:
   - Adjust CPU/memory based on workload
   - Use resource limits to prevent noisy neighbors

2. **ZMQ Configuration**:
   - Tune queue depths and timeouts
   - Consider multiple ZMQ proxy instances for HA

3. **Storage**:
   - Use fast storage classes for datasets
   - Consider distributed storage for large scale

## Production Deployment

### High Availability

1. **Multiple Replicas**:
   ```yaml
   systemController:
     replicaCount: 2  # Not recommended, use leader election

   zmqProxy:
     replicaCount: 3  # Recommended for HA
   ```

2. **Pod Disruption Budgets**:
   ```yaml
   workers:
     podDisruptionBudget:
       enabled: true
       minAvailable: 50%
   ```

3. **Anti-affinity Rules**:
   ```yaml
   workers:
     affinity:
       podAntiAffinity:
         preferredDuringSchedulingIgnoredDuringExecution:
         - weight: 100
           podAffinityTerm:
             labelSelector:
               matchExpressions:
               - key: app
                 operator: In
                 values: [aiperf-worker]
             topologyKey: kubernetes.io/hostname
   ```

### Multi-cluster Deployment

For large-scale, distributed benchmarks across multiple clusters:

1. Use cluster federation or external controllers
2. Implement cross-cluster service discovery
3. Configure distributed storage and metrics collection

### Backup and Recovery

1. **Configuration Backup**:
   ```bash
   kubectl get benchmarkruns -o yaml > benchmarks-backup.yaml
   kubectl get benchmarktemplates -o yaml > templates-backup.yaml
   ```

2. **Data Backup**:
   - Configure persistent volume backups
   - Export results to external storage
   - Implement automated backup schedules

## Migration from Multiprocess

To migrate from multiprocess deployment:

1. **Export existing configurations**
2. **Create equivalent Kubernetes resources**
3. **Test with small workloads**
4. **Gradually migrate traffic**
5. **Decommission old deployment**

## Contributing

When contributing to the Kubernetes integration:

1. Follow Kubernetes best practices
2. Update CRD schemas for new features
3. Add appropriate RBAC permissions
4. Include monitoring and alerting
5. Update documentation and examples

## Support

For issues specific to Kubernetes integration:

1. Check the troubleshooting section
2. Review logs and metrics
3. File issues with:
   - Kubernetes version
   - AIPerf version
   - Cluster configuration
   - Complete error logs
