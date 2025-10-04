<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Chapter 49: Deployment Guide

## Overview

This chapter covers deployment strategies for AIPerf in various environments, including Docker, Kubernetes, cloud platforms, and production best practices.

## Table of Contents

- [Deployment Patterns](#deployment-patterns)
- [Docker Deployment](#docker-deployment)
- [Kubernetes Deployment](#kubernetes-deployment)
- [Cloud Deployment](#cloud-deployment)
- [Monitoring and Operations](#monitoring-and-operations)
- [Security](#security)
- [Best Practices](#best-practices)

---

## Deployment Patterns

### Deployment Scenarios

```
┌────────────────────────────────────────────────────────────┐
│                  Deployment Scenarios                       │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Local Development                                       │
│     └─ Direct Python execution                              │
│                                                             │
│  2. Docker Container                                        │
│     └─ Isolated environment                                 │
│                                                             │
│  3. Kubernetes Cluster                                      │
│     └─ Scalable, distributed execution                      │
│                                                             │
│  4. Cloud Platform                                          │
│     └─ Managed infrastructure                               │
│                                                             │
│  5. CI/CD Pipeline                                          │
│     └─ Automated testing                                    │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

---

## Docker Deployment

### Official Dockerfile

**File**: `/home/anthony/nvidia/projects/aiperf/Dockerfile`

```dockerfile
FROM python:3.12-slim AS base

ENV USERNAME=appuser
ENV APP_NAME=aiperf

# Create app user
RUN groupadd -r $USERNAME \
    && useradd -r -g $USERNAME $USERNAME

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

FROM base AS final

# Create virtual environment
RUN mkdir /opt/$APP_NAME \
    && uv venv /opt/$APP_NAME/venv --python 3.12 \
    && chown -R $USERNAME:$USERNAME /opt/$APP_NAME

# Activate virtual environment
ENV VIRTUAL_ENV=/opt/$APP_NAME/venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

# Copy pyproject first for better layer caching
COPY pyproject.toml .

# Install dependencies
RUN uv sync --active --no-install-project

# Copy application
COPY . .

# Install the project
RUN uv sync --active --no-dev

# Command to run
ENTRYPOINT ["aiperf"]
```

### Build and Run

```bash
# Build image
docker build -t aiperf:latest .

# Run benchmark
docker run --rm \
  -v $(pwd)/results:/results \
  aiperf:latest profile \
    --model Qwen/Qwen3-0.6B \
    --url http://host.docker.internal:8000 \
    --endpoint-type chat \
    --request-count 100 \
    --output-file /results/benchmark.json
```

### Custom Dockerfile

```dockerfile
FROM aiperf:latest

# Install custom plugins
RUN pip install aiperf-my-plugin

# Copy custom datasets
COPY datasets/ /datasets/

# Set default configuration
ENV AIPERF_LOG_LEVEL=INFO
ENV AIPERF_OUTPUT_DIR=/results

# Custom entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  aiperf:
    image: aiperf:latest
    volumes:
      - ./results:/results
      - ./datasets:/datasets
    environment:
      - AIPERF_LOG_LEVEL=INFO
    command: >
      profile
        --model Qwen/Qwen3-0.6B
        --url http://inference-server:8000
        --endpoint-type chat
        --request-count 1000
        --concurrency 10
        --output-file /results/benchmark.json
    depends_on:
      - inference-server

  inference-server:
    image: vllm/vllm-openai:latest
    environment:
      - MODEL=Qwen/Qwen3-0.6B
    ports:
      - "8000:8000"
```

**Run:**
```bash
docker-compose up
```

---

## Kubernetes Deployment

### Basic Job

```yaml
# aiperf-job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: aiperf-benchmark
spec:
  template:
    spec:
      containers:
      - name: aiperf
        image: aiperf:latest
        command: ["aiperf", "profile"]
        args:
          - "--model"
          - "Qwen/Qwen3-0.6B"
          - "--url"
          - "http://inference-service:8000"
          - "--endpoint-type"
          - "chat"
          - "--request-count"
          - "1000"
          - "--concurrency"
          - "10"
          - "--output-file"
          - "/results/benchmark.json"
        volumeMounts:
        - name: results
          mountPath: /results
      volumes:
      - name: results
        persistentVolumeClaim:
          claimName: aiperf-results
      restartPolicy: Never
  backoffLimit: 3
```

**Deploy:**
```bash
kubectl apply -f aiperf-job.yaml

# Check status
kubectl get jobs

# View logs
kubectl logs job/aiperf-benchmark
```

### CronJob for Scheduled Benchmarks

```yaml
# aiperf-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: aiperf-hourly-benchmark
spec:
  schedule: "0 * * * *"  # Every hour
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: aiperf
            image: aiperf:latest
            command: ["aiperf", "profile"]
            args:
              - "--model"
              - "Qwen/Qwen3-0.6B"
              - "--url"
              - "http://inference-service:8000"
              - "--endpoint-type"
              - "chat"
              - "--request-count"
              - "500"
              - "--output-file"
              - "/results/benchmark-$(date +%Y%m%d-%H%M%S).json"
            volumeMounts:
            - name: results
              mountPath: /results
          volumes:
          - name: results
            persistentVolumeClaim:
              claimName: aiperf-results
          restartPolicy: OnFailure
```

### Helm Chart

```yaml
# values.yaml
image:
  repository: aiperf
  tag: latest
  pullPolicy: IfNotPresent

benchmark:
  model: "Qwen/Qwen3-0.6B"
  url: "http://inference-service:8000"
  endpointType: "chat"
  requestCount: 1000
  concurrency: 10

storage:
  size: 10Gi
  storageClass: standard

resources:
  limits:
    cpu: 2000m
    memory: 4Gi
  requests:
    cpu: 1000m
    memory: 2Gi
```

```yaml
# templates/job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: {{ include "aiperf.fullname" . }}
spec:
  template:
    spec:
      containers:
      - name: aiperf
        image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
        command: ["aiperf", "profile"]
        args:
          - "--model"
          - {{ .Values.benchmark.model | quote }}
          - "--url"
          - {{ .Values.benchmark.url | quote }}
          - "--endpoint-type"
          - {{ .Values.benchmark.endpointType | quote }}
          - "--request-count"
          - {{ .Values.benchmark.requestCount | quote }}
          - "--concurrency"
          - {{ .Values.benchmark.concurrency | quote }}
        resources:
          {{- toYaml .Values.resources | nindent 10 }}
      restartPolicy: Never
```

**Deploy:**
```bash
helm install aiperf-benchmark ./aiperf-chart
```

---

## Cloud Deployment

### AWS (ECS/Fargate)

**Task Definition:**
```json
{
  "family": "aiperf-benchmark",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "2048",
  "memory": "4096",
  "containerDefinitions": [
    {
      "name": "aiperf",
      "image": "aiperf:latest",
      "command": ["aiperf", "profile"],
      "environment": [
        {"name": "AIPERF_LOG_LEVEL", "value": "INFO"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/aiperf",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

**Run Task:**
```bash
aws ecs run-task \
  --cluster aiperf-cluster \
  --task-definition aiperf-benchmark \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx]}"
```

### GCP (Cloud Run Jobs)

```yaml
# job.yaml
apiVersion: run.googleapis.com/v1
kind: Job
metadata:
  name: aiperf-benchmark
spec:
  template:
    spec:
      template:
        spec:
          containers:
          - image: gcr.io/project-id/aiperf:latest
            args:
              - profile
              - --model
              - Qwen/Qwen3-0.6B
              - --url
              - http://inference-service:8000
              - --endpoint-type
              - chat
              - --request-count
              - "1000"
            resources:
              limits:
                cpu: 2
                memory: 4Gi
```

**Deploy:**
```bash
gcloud run jobs create aiperf-benchmark \
  --image=gcr.io/project-id/aiperf:latest \
  --region=us-central1
```

### Azure (Container Instances)

```bash
az container create \
  --resource-group aiperf-rg \
  --name aiperf-benchmark \
  --image aiperf:latest \
  --cpu 2 \
  --memory 4 \
  --restart-policy Never \
  --command-line "aiperf profile --model Qwen/Qwen3-0.6B --url http://inference-service:8000 --endpoint-type chat --request-count 1000"
```

---

## Monitoring and Operations

### Logging

**Centralized Logging:**
```yaml
# Fluentd daemonset
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: fluentd
spec:
  selector:
    matchLabels:
      name: fluentd
  template:
    metadata:
      labels:
        name: fluentd
    spec:
      containers:
      - name: fluentd
        image: fluent/fluentd-kubernetes-daemonset:v1-debian-elasticsearch
        env:
        - name: FLUENT_ELASTICSEARCH_HOST
          value: "elasticsearch.logging"
```

**Application Logging:**
```python
import logging
import sys

# Configure logging for container environments
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout  # Log to stdout for container log collection
)
```

### Metrics Collection

**Prometheus Integration:**
```python
from prometheus_client import Counter, Histogram, start_http_server

# Define metrics
requests_total = Counter('aiperf_requests_total', 'Total requests')
request_latency = Histogram('aiperf_request_latency_seconds', 'Request latency')

# Start metrics server
start_http_server(9090)

# Record metrics
@request_latency.time()
def process_request():
    requests_total.inc()
    # Process request
```

**ServiceMonitor:**
```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: aiperf-metrics
spec:
  selector:
    matchLabels:
      app: aiperf
  endpoints:
  - port: metrics
    interval: 30s
```

### Health Checks

```python
from aiohttp import web

async def health_check(request):
    """Health check endpoint"""
    return web.json_response({"status": "healthy"})

async def readiness_check(request):
    """Readiness check endpoint"""
    # Check if service is ready
    ready = await check_dependencies()
    status = 200 if ready else 503
    return web.json_response({"status": "ready" if ready else "not ready"}, status=status)

app = web.Application()
app.router.add_get("/health", health_check)
app.router.add_get("/ready", readiness_check)
```

**Kubernetes Probes:**
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
```

---

## Security

### Container Security

**Non-root User:**
```dockerfile
# Run as non-root
RUN useradd -m -u 1000 aiperf
USER aiperf
```

**Read-only Filesystem:**
```yaml
securityContext:
  readOnlyRootFilesystem: true
  runAsNonRoot: true
  runAsUser: 1000
```

**Resource Limits:**
```yaml
resources:
  limits:
    cpu: 2000m
    memory: 4Gi
    ephemeral-storage: 10Gi
  requests:
    cpu: 1000m
    memory: 2Gi
```

### Secrets Management

**Kubernetes Secrets:**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: aiperf-secrets
type: Opaque
data:
  api-key: <base64-encoded-key>
```

**Use in Pod:**
```yaml
env:
- name: API_KEY
  valueFrom:
    secretKeyRef:
      name: aiperf-secrets
      key: api-key
```

**External Secrets:**
```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: aiperf-secrets
spec:
  secretStoreRef:
    name: vault-backend
    kind: SecretStore
  target:
    name: aiperf-secrets
  data:
  - secretKey: api-key
    remoteRef:
      key: aiperf/api-key
```

---

## Best Practices

### 1. Configuration Management

Use ConfigMaps for non-sensitive configuration:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: aiperf-config
data:
  benchmark.yaml: |
    model: "Qwen/Qwen3-0.6B"
    endpoint_type: "chat"
    request_count: 1000
    concurrency: 10
```

### 2. Resource Management

Set appropriate resource limits:

```yaml
resources:
  requests:
    cpu: 1000m
    memory: 2Gi
  limits:
    cpu: 2000m
    memory: 4Gi
```

### 3. Persistent Storage

Use PVCs for results:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: aiperf-results
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 10Gi
```

### 4. Networking

Use Services for endpoint discovery:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: inference-service
spec:
  selector:
    app: inference-server
  ports:
    - port: 8000
      targetPort: 8000
```

### 5. Monitoring

Implement comprehensive monitoring:

- Collect metrics (Prometheus)
- Centralize logs (ELK, Loki)
- Set up alerts (Alertmanager)
- Create dashboards (Grafana)

---

## Key Takeaways

1. **Docker**: Containerize for consistency
2. **Kubernetes**: Orchestrate for scale
3. **Cloud**: Leverage managed services
4. **Monitoring**: Comprehensive observability
5. **Security**: Non-root, secrets, limits
6. **Automation**: CI/CD integration
7. **Best Practices**: Follow cloud-native patterns

---

## Navigation

- [Previous Chapter: Chapter 48 - Plugin Architecture](chapter-48-plugin-architecture.md)
- [Next Chapter: Chapter 50 - Troubleshooting Guide](chapter-50-troubleshooting-guide.md)
- [Return to Index](INDEX.md)

---

**Document Information**
- **File**: `/home/anthony/nvidia/projects/aiperf/guidebook/chapter-49-deployment-guide.md`
- **Purpose**: Deployment strategies for AIPerf
- **Target Audience**: DevOps engineers, system administrators
- **Related Files**:
  - `/home/anthony/nvidia/projects/aiperf/Dockerfile`
  - `/home/anthony/nvidia/projects/aiperf/Makefile`
