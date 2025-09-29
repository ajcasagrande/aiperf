<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Multi-Node Dataset Deployment Guide

This guide explains how to deploy AIPerf datasets across multiple nodes for scalable performance testing.

## Overview

The multi-node dataset system provides several deployment strategies:

1. **Single Node**: Memory-mapped files (current solution) - optimal for single-node deployments
2. **Shared Storage**: NFS/CephFS-based distribution - simple multi-node solution
3. **Redis Distributed**: High-performance distributed caching - optimal for dynamic environments
4. **Hybrid**: Intelligent fallback with multiple strategies - automatic adaptation
5. **Auto**: Automatic detection and selection of optimal strategy

## Deployment Strategies

### 1. Single Node Deployment (Default)
Best for: Single-machine deployments, development, testing

```python
from aiperf.dataset.multi_node_dataset_manager import (
    MultiNodeDatasetManager,
    MultiNodeConfig,
    DeploymentMode
)

config = MultiNodeConfig(
    deployment_mode=DeploymentMode.SINGLE_NODE,
    enable_compression=True
)

async with MultiNodeDatasetManager(dataset, config) as manager:
    # Uses optimized memory-mapped files
    conversation = await manager.get_conversation("session_id")
```

**Pros:**
- Highest performance (direct memory access)
- No network overhead
- Simple setup

**Cons:**
- Limited to single node
- No cross-node scalability

### 2. Shared Storage Deployment
Best for: Traditional HPC environments, persistent shared filesystems

```python
config = MultiNodeConfig(
    deployment_mode=DeploymentMode.SHARED_STORAGE,
    shared_storage_path="/mnt/shared/aiperf",
    storage_type="nfs",  # or "ceph", "lustre"
    enable_compression=True
)

async with MultiNodeDatasetManager(dataset, config) as manager:
    # Files created on shared storage, accessible by all nodes
    paths = await manager.initialize()
```

**Setup Requirements:**
```bash
# NFS Setup Example
sudo apt-get install nfs-common
sudo mkdir -p /mnt/shared/aiperf
sudo mount -t nfs nfs-server:/path/to/shared /mnt/shared/aiperf

# CephFS Setup Example
sudo apt-get install ceph-fuse
sudo mkdir -p /mnt/shared/aiperf
sudo ceph-fuse /mnt/shared/aiperf
```

**Pros:**
- Simple multi-node setup
- Leverages existing infrastructure
- Good for stable cluster environments

**Cons:**
- Network I/O dependency
- Shared storage bottlenecks
- Requires persistent storage setup

### 3. Redis Distributed Deployment
Best for: Dynamic environments, Kubernetes, high-performance multi-node

```python
from aiperf.dataset.redis_dataset_cache import RedisDatasetConfig

redis_config = RedisDatasetConfig(
    host="redis-cluster.example.com",
    port=6379,
    password="your-password",
    db=0,
    ttl_seconds=3600,
    use_compression=True,
    max_connections=20
)

config = MultiNodeConfig(
    deployment_mode=DeploymentMode.REDIS_DISTRIBUTED,
    redis_config=redis_config,
    prefer_local_cache=True
)

async with MultiNodeDatasetManager(dataset, config) as manager:
    # Dataset stored in Redis, accessible cluster-wide
    conversation = await manager.get_conversation()
```

**Redis Setup:**
```bash
# Docker Redis Cluster
docker run -d --name redis-cluster \
  -p 6379:6379 \
  redis:7-alpine redis-server --appendonly yes

# Kubernetes Redis
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
EOF
```

**Pros:**
- High performance distributed access
- Automatic data distribution
- Great for dynamic scaling
- Built-in compression and TTL

**Cons:**
- Requires Redis infrastructure
- Memory usage on Redis server
- Network dependency

### 4. Hybrid Deployment (Recommended)
Best for: Production environments with varying conditions

```python
config = MultiNodeConfig(
    deployment_mode=DeploymentMode.HYBRID,
    # Configure multiple backends
    shared_storage_path="/mnt/shared/aiperf",
    redis_config=redis_config,
    prefer_local_cache=True,
    fallback_timeout=5.0,
    max_retry_attempts=3
)

async with MultiNodeDatasetManager(dataset, config) as manager:
    # Automatically tries Redis → Shared Storage → Local fallback
    conversation = await manager.get_conversation()
```

**Pros:**
- Intelligent fallback strategies
- Adapts to infrastructure changes
- Optimal performance when possible
- Robust failure handling

**Cons:**
- More complex setup
- Requires multiple backend configurations

### 5. Auto-Detection (Easiest)
Best for: Development, testing, adaptive deployments

```python
config = MultiNodeConfig(
    deployment_mode=DeploymentMode.AUTO,
    # Provide optional configurations
    shared_storage_path="/mnt/shared/aiperf",  # if available
    redis_config=redis_config,  # if available
    enable_compression=True
)

async with MultiNodeDatasetManager(dataset, config) as manager:
    # Automatically detects and uses best available option
    mode = manager.get_deployment_mode()
    print(f"Using deployment mode: {mode}")
```

## Kubernetes Integration

### Basic Deployment
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: aiperf-config
data:
  deployment_mode: "auto"
  enable_compression: "true"
  redis_host: "redis-service"
  redis_port: "6379"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: aiperf-workers
spec:
  replicas: 5
  template:
    spec:
      containers:
      - name: worker
        image: aiperf:latest
        env:
        - name: AIPERF_MULTI_NODE
          value: "true"
        - name: REDIS_HOST
          valueFrom:
            configMapKeyRef:
              name: aiperf-config
              key: redis_host
        volumeMounts:
        - name: shared-data
          mountPath: /mnt/shared
      volumes:
      - name: shared-data
        persistentVolumeClaim:
          claimName: shared-storage-pvc
```

### With Redis
```yaml
apiVersion: v1
kind: Service
metadata:
  name: redis-service
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: redis
spec:
  serviceName: redis-service
  replicas: 1
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
        volumeMounts:
        - name: redis-data
          mountPath: /data
  volumeClaimTemplates:
  - metadata:
      name: redis-data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 10Gi
```

## Performance Considerations

### Network Optimization
```python
config = MultiNodeConfig(
    enable_compression=True,  # Reduce network traffic
    prefer_local_cache=True,  # Cache frequently accessed data
    fallback_timeout=2.0,     # Quick fallback on failures
)
```

### Memory Management
```python
redis_config = RedisDatasetConfig(
    use_compression=True,      # Reduce Redis memory usage
    ttl_seconds=1800,         # Auto-expire old data
    max_connections=50,       # Connection pooling
)
```

### Storage Optimization
```python
config = MultiNodeConfig(
    storage_type="ceph",      # Use high-performance distributed storage
    enable_compression=True,   # Reduce storage footprint
)
```

## Monitoring and Observability

### Health Checks
```python
# Check deployment status
info = manager.get_dataset_info()
print(f"Mode: {info['deployment_mode']}")
print(f"Conversations: {info['conversations_count']}")
print(f"Compression: {info['compression_enabled']}")

# Performance monitoring
from aiperf.dataset.multi_node_messages import NodeDatasetStatusMessage

status = NodeDatasetStatusMessage(
    node_id=info['node_id'],
    dataset_id=info['dataset_id'],
    status="ready",
    supports_redis_access=True,
    avg_access_time_ms=1.2,
    cache_hit_ratio=0.95
)
```

### Logging Configuration
```python
import logging

# Enable detailed multi-node logging
logging.getLogger('aiperf.dataset.multi_node_dataset_manager').setLevel(logging.DEBUG)
logging.getLogger('aiperf.dataset.redis_dataset_cache').setLevel(logging.INFO)
logging.getLogger('aiperf.dataset.distributed_dataset_manager').setLevel(logging.INFO)
```

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**
   ```
   Error: Redis connection failed: Connection refused
   ```
   - Verify Redis server is running
   - Check network connectivity
   - Validate Redis configuration

2. **Shared Storage Not Accessible**
   ```
   Error: Shared storage path does not exist
   ```
   - Verify mount point exists
   - Check filesystem permissions
   - Confirm NFS/CephFS service status

3. **Fallback to Single Node**
   ```
   Warning: Multi-node environment detected but no distributed storage available
   ```
   - This is expected behavior when distributed backends are unavailable
   - Performance will be limited to single-node capabilities

### Performance Tuning

1. **Redis Performance**
   ```python
   redis_config = RedisDatasetConfig(
       max_connections=100,      # Increase for high concurrency
       use_compression=False,    # Disable if CPU is bottleneck
       ttl_seconds=7200,        # Longer TTL for stable datasets
   )
   ```

2. **Shared Storage Performance**
   ```python
   config = MultiNodeConfig(
       enable_compression=False,  # Let storage handle compression
       storage_type="lustre",     # Use high-performance filesystem
   )
   ```

3. **Hybrid Mode Tuning**
   ```python
   config = MultiNodeConfig(
       deployment_mode=DeploymentMode.HYBRID,
       fallback_timeout=1.0,     # Faster fallback
       prefer_local_cache=True,  # Aggressive local caching
   )
   ```

## Migration Guide

### From Single Node to Multi-Node
1. Install Redis or setup shared storage
2. Update configuration to use `DeploymentMode.AUTO`
3. Deploy across multiple nodes
4. Monitor performance and adjust settings

### From Shared Storage to Redis
1. Setup Redis cluster
2. Update configuration with Redis settings
3. Use `DeploymentMode.HYBRID` for gradual migration
4. Switch to `DeploymentMode.REDIS_DISTRIBUTED` when stable

This multi-node approach provides scalable, robust dataset distribution while maintaining the performance benefits of memory-mapped files where possible.
