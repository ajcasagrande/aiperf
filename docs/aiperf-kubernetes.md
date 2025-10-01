<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# AIPerf Kubernetes Deployment Enhancement

**Status**: Draft

**Authors**: @ajcasagrande

**Category**: Architecture

**Replaces**: None

**Replaced By**: None

**Sponsor**: @ganeshku1

**Required Reviewers**: @ajcasagrande @ganeshku1 @nicolasnoble

**Review Date**: [Date for review]

**Pull Request**: [Link to Pull Request of the Proposal itself]

**Implementation PR / Tracking Issue**: [Link to Pull Request or Tracking Issue for Implementation]

# Summary

This proposal outlines the enhancement of AIPerf to support distributed deployment on Kubernetes clusters. The enhancement enables AIPerf to generate significantly higher concurrent loads by distributing work across multiple pods in a Kubernetes cluster, overcoming single-node performance limitations. The solution adopts a true per-service pod architecture where each AIPerf service runs in its own dedicated pod, enabling independent scaling and resource allocation.

AIPerf currently supports only single-node multiprocess deployment. This enhancement proposes implementing the existing `KubernetesServiceManager` stub to enable distributed deployment while maintaining full compatibility with existing service management patterns, ZMQ communication protocols, and configuration systems.

# Motivation

The current AIPerf implementation is limited to single-node execution, which constrains the maximum concurrent load that can be generated for benchmarking AI inference services. A critical limitation of single-node deployments is the exhaustion of ephemeral ports, which limits concurrent connections to approximately 65,535 per node (with practical limits around 63,500 due to reserved ports). As AI inference workloads scale to serve production traffic, there is a critical need to validate performance under extremely high concurrency conditions. Single-node AIPerf deployments cannot achieve these concurrency levels due to operating system networking constraints, hardware limitations, and the inherent scalability limits of running all services on a single machine.

Dynamo inference services are deployed on Kubernetes clusters and need to be validated against realistic, high-concurrency load patterns that exceed single-node capabilities. The lack of distributed load generation capability prevents teams from conducting comprehensive performance validation before deploying to production, potentially leading to service degradation or failures under actual concurrent user load.

## Goals

* Enable distributed load generation across multiple Kubernetes pods to achieve high concurrency levels
* Overcome single-node ephemeral port limitations by distributing connections across multiple worker pods
* Maintain compatibility with existing AIPerf CLI interfaces and configuration options
* Provide seamless deployment experience through CLI parameters
* Preserve existing ZMQ-based communication patterns between AIPerf services while adapting for distributed deployment
* Enable scaling of worker and record processor pods based on concurrency requirements

### Non Goals

* Supporting non-Kubernetes container orchestration platforms in this implementation
* Providing a web-based UI for job management and visualization
* Implementing cross-cluster or multi-cloud distributed deployments
* Replacing the existing single-node deployment mode (both modes coexist)

## Requirements

### REQ 1 Distributed Architecture Support

AIPerf **MUST** support deployment of its services across multiple Kubernetes pods using a true per-service pod architecture while maintaining the existing service communication patterns. Each AIPerf service (system controller, dataset manager, timing manager, records manager, worker manager, worker, record processor) **MUST** run in its own dedicated pod. Worker and record processor services **MUST** be deployable as independently scalable pod replicas.

### REQ 2 Kubernetes API Integration and Compatibility

The implementation **MUST** use the Kubernetes API directly for pod orchestration rather than relying on external tools. The `KubernetesServiceManager` **MUST** implement the existing `ServiceManagerProtocol` interface to ensure compatibility with AIPerf's service management architecture. The implementation **MUST** follow the same patterns as `MultiProcessServiceManager` for service lifecycle management. The system **SHOULD** use the existing `bootstrap_and_run_service` function for service startup. The system **SHOULD** support programmatic deployment through CLI parameters.

### REQ 3 Concurrency Scaling

The distributed deployment **MUST** be capable of sustaining at least 1M concurrent connections when deployed with sufficient pod replicas. The system **MUST** support dynamic scaling of worker pods based on target concurrency requirements and overcome single-node ephemeral port limitations.

### REQ 4 Communication Protocol Compatibility

The distributed implementation **MUST** maintain compatibility with existing ZMQ-based communication patterns. All inter-service communication **MUST** function correctly across pod boundaries using the same message protocols.

### REQ 5 Deployment Lifecycle Management

The system **MUST** support complete lifecycle management including deployment, configuration, execution, and cleanup of Kubernetes resources. Failed deployments **SHOULD** be automatically cleaned up to prevent resource leaks.

### REQ 6 Developer Experience and Simplicity

The implementation **MUST** provide a simple, intuitive deployment experience that allows developers to achieve 1M+ concurrent connections with minimal configuration. The system **SHOULD** follow basic Kubernetes security practices while prioritizing ease of use and performance over enterprise complexity.


# Proposal

## Architecture Overview

The proposed Kubernetes deployment architecture adopts a true per-service pod approach where each AIPerf service runs in its own dedicated pod. This design provides maximum flexibility for independent scaling, resource allocation, and fault isolation. The architecture separates AIPerf services into two categories:

1. **Singleton Service Pods**: Core coordination services that run as single instances
2. **Scalable Service Pods**: Services that scale horizontally based on load requirements

### Service Pod Architecture

#### System Controller Pod
- **Single pod** running the system controller service
- Orchestrates the entire benchmark lifecycle and coordinates other services
- Manages the ProxyManager with embedded ZMQ proxies for message routing
- Singleton deployment - only one instance per benchmark

#### Dataset Manager Pod
- **Single pod** running the dataset manager service
- Manages dataset loading and distribution across the cluster
- Singleton deployment - only one instance per benchmark

#### Timing Manager Pod
- **Single pod** running the timing manager service
- Issues credits (request tokens) and controls benchmark timing
- Singleton deployment - only one instance per benchmark

#### Records Manager Pod
- **Single pod** running the records manager service
- Collects and aggregates metrics from distributed record processors
- Singleton deployment - only one instance per benchmark

#### Worker Manager Pod
- **Single pod** running the worker manager service
- Coordinates worker scaling and management operations
- Singleton deployment - only one instance per benchmark

#### Worker Pods (Scalable)
- **Multiple pods** each running a single worker service instance
- Execute inference requests against target endpoints
- Scale horizontally based on target concurrency requirements (1 to N replicas)
- Each pod can handle concurrent connections up to the configured `AIPERF_HTTP_CONNECTION_LIMIT`

#### Record Processor Pods (Scalable)
- **Multiple pods** each running a single record processor service instance
- Perform request and response tokenization and initial metrics processing
- Scale horizontally based on response processing throughput and concurrent request volume (1 to N replicas)
- Send processed metrics back to the records manager via ZMQ

## Communication Architecture

The existing ZMQ-based communication patterns are preserved with the following adaptations for distributed deployment:

### ZMQ Communication Flow
The existing ZMQ communication uses multiple proxy patterns managed by the ProxyManager:

1. **Credit Distribution**: Timing manager pushes credits through CREDIT_DROP address, workers pull via PUSH/PULL pattern
2. **Credit Return**: Workers return completed credits through CREDIT_RETURN address
3. **Raw Inference Results**: Workers send raw responses through RAW_INFERENCE_PROXY_FRONTEND to record processors via PUSH/PULL proxy
4. **Processed Records**: Record processors send processed metrics to records manager via RECORDS address using PUSH/PULL
5. **Event Bus**: System controller and services communicate via EVENT_BUS_PROXY using PUB/SUB pattern for coordination messages
6. **Dataset Requests**: Workers request conversation data from dataset manager via DATASET_MANAGER_PROXY using DEALER/ROUTER pattern

### Network Configuration
- System controller pod exposes ZMQ proxy ports via Kubernetes services
- All service pods connect to system controller services using Kubernetes DNS
- Each singleton service pod exposes its own service endpoint for direct communication
- All ZMQ communication uses TCP transport

## Deployment Modes

### CLI-Driven Deployment

**Basic Kubernetes Deployment**:
Users will deploy AIPerf to Kubernetes using the `--kubernetes` flag. The AIPerf CLI will bootstrap a System Controller pod into the cluster, which then orchestrates the deployment of all other service pods (workers, record processors, etc.) and manages the benchmark lifecycle.

## Resource Management

### Basic Resource Allocation
AIPerf will use sensible defaults for pod resource allocation:
- **Control Services** (system-controller, dataset-manager, etc.): Basic CPU and memory allocation
- **Worker Pods**: Resource allocation optimized for handling concurrent connections
- **Record Processors**: Resource allocation for metrics processing workload

### Scaling Strategy
- Singleton service pods remain single instances
- Worker pods scale based on target concurrency requirements
- Record processor pods scale based on worker count

# Implementation Details

## Decoupled Architecture Design

### Current Architecture Analysis
The existing architecture has a key architectural issue that becomes clear when considering Kubernetes deployment:

**Current Architecture Problem:**
- UI is instantiated and managed inside SystemController process
- This creates tight coupling between business logic and presentation layer
- In Kubernetes mode, UI should run locally while SystemController runs in pod

**UI is Already Decoupled via ZMQ (Good!):**
- UI receives all data via ZMQ message bus (`MessageBusClientMixin`)
- Progress updates via `@on_message(MessageType.WORKER_HEALTH)`
- Metrics via `@on_message(MessageType.REALTIME_METRICS)`
- Worker status via `@on_message(MessageType.WORKER_STATUS_SUMMARY)`
- Uses standard ZMQ addresses: `EVENT_BUS_PROXY_BACKEND` for subscriptions

**Proposed Fix: CLI-Managed UI Lifecycle**
Move UI lifecycle management from SystemController to CLI orchestrator for clean separation of concerns.

### Proposed Decoupled Architecture

**Clean Component Separation:**
1. **CLI Orchestrator**: Deployment mode detection, UI lifecycle, user interaction
2. **Deployment Managers**: Mode-specific deployment logic (Multiprocess vs Kubernetes)
3. **SystemController**: Pure service orchestration and business logic (enhanced ServiceManager)
4. **ServiceManager**: Individual service process/pod lifecycle management

## Bootstrap Flow and Service Management

### Multiprocessing Mode Flow (Improved)
1. **CLI Orchestrator**: Detects multiprocessing mode (default)
2. **MultiprocessDeploymentManager**: Deploys SystemController as local process (no UI)
3. **CLI Orchestrator**: Starts UI client locally, connects to SystemController via ZMQ IPC
4. **SystemController**: Service orchestration using MultiProcessServiceManager

### Kubernetes Mode Flow
1. **CLI Orchestrator**: Detects Kubernetes mode (`--kubernetes` flag present)
2. **KubernetesDeploymentManager**: Creates namespace, deploys SystemController pod (no UI)
3. **CLI Orchestrator**: Starts UI client locally, connects via port-forward to SystemController ZMQ
4. **SystemController**: Service orchestration using KubernetesServiceManager (same code as multiprocess)

### Key Architectural Improvement
**Before**: SystemController = monolithic (service management + UI + console output + process lifecycle)
**After**: Clean layered architecture with focused responsibilities per component

### Communication Architecture

**Both modes use the same communication pattern**: CLI ↔ UI ↔ SystemController via ZMQ

**Multiprocessing Mode:**
- UI connects to SystemController via ZMQ IPC sockets (local)
- Same machine, different processes

**Kubernetes Mode:**
- UI connects to SystemController via ZMQ TCP over port-forward (remote)
- Different machines, same ZMQ protocol

**Key Insight**: Minimal implementation changes needed since UI already uses ZMQ for all data

### Kubernetes Service Manager

The `KubernetesServiceManager` implements the same `ServiceManagerProtocol` interface as `MultiProcessServiceManager`, but deploys services as Kubernetes pods instead of processes:

**ServiceManagerProtocol Implementation:**
- `run_service(service_type, num_replicas)`: Deploy service pods using Kubernetes API (instead of spawning processes)
- `shutdown_all_services()`: Delete all pods (instead of terminating processes)
- `wait_for_all_services_registration()`: Monitor pod readiness and service registration (same pattern)

**Core Responsibilities:**
- **Pod Deployment**: Creates Kubernetes pod specifications for each service type
- **Service Discovery**: Manages Kubernetes services for ZMQ communication endpoints
- **Resource Lifecycle**: Handles pod deployment, scaling, and cleanup
- **Same Interface**: SystemController uses identical calls regardless of deployment mode

**Implementation Summary:**
The `KubernetesServiceManager` follows the same patterns as `MultiProcessServiceManager`:
- Uses Kubernetes Python client instead of `multiprocessing.Process`
- Maintains service tracking with pod information instead of process information
- Same interface allows SystemController to work with either implementation seamlessly

## ZMQ Network Configuration

### Service Exposure
The system controller pod exposes ZMQ proxy endpoints via Kubernetes services, while other services connect as clients:
```yaml
# System Controller Service (ZMQ Proxies)
apiVersion: v1
kind: Service
metadata:
  name: aiperf-system-controller
spec:
  selector:
    app: aiperf-system-controller
  ports:
    # Credit distribution (timing manager pushes, workers pull)
    - name: credit-drop
      port: 5562
      targetPort: 5562
    # Credit return (workers push back completed credits)
    - name: credit-return
      port: 5563
      targetPort: 5563
    # Raw inference proxy frontend (workers push responses)
    - name: raw-inference-proxy-frontend
      port: 5665
      targetPort: 5665
    # Records collection (record processors push processed data)
    - name: records
      port: 5557
      targetPort: 5557
    # Event bus proxy frontend (PUB/SUB for coordination)
    - name: event-bus-proxy-frontend
      port: 5663
      targetPort: 5663
    # Dataset manager proxy frontend (workers request data)
    - name: dataset-manager-proxy-frontend
      port: 5661
      targetPort: 5661
```

### Connection Configuration
Service pods use Kubernetes DNS for service discovery to connect to system controller proxies:
```python
# Service discovery configuration for accessing ZMQ proxies
SYSTEM_CONTROLLER_SERVICE = "aiperf-system-controller.aiperf-benchmarks.svc.cluster.local"

# ZMQ endpoint configuration using actual CommAddress mappings
CREDIT_DROP_ENDPOINT = f"tcp://{SYSTEM_CONTROLLER_SERVICE}:5562"
CREDIT_RETURN_ENDPOINT = f"tcp://{SYSTEM_CONTROLLER_SERVICE}:5563"
RAW_INFERENCE_PROXY_FRONTEND = f"tcp://{SYSTEM_CONTROLLER_SERVICE}:5665"
RECORDS_ENDPOINT = f"tcp://{SYSTEM_CONTROLLER_SERVICE}:5557"
EVENT_BUS_PROXY_FRONTEND = f"tcp://{SYSTEM_CONTROLLER_SERVICE}:5663"
DATASET_MANAGER_PROXY_FRONTEND = f"tcp://{SYSTEM_CONTROLLER_SERVICE}:5661"

# Services connect as clients to these proxy endpoints
# Workers: connect to CREDIT_DROP (pull), CREDIT_RETURN (push), RAW_INFERENCE_PROXY_FRONTEND (push)
# Record Processors: connect to RAW_INFERENCE_PROXY_BACKEND (pull), RECORDS (push)
# All Services: connect to EVENT_BUS_PROXY (pub/sub for coordination)
```

## CLI App Responsibilities

The AIPerf CLI app running on the user's local machine has specific responsibilities in the Kubernetes deployment flow:

### Bootstrap Responsibilities
1. **Initial Setup**: Create namespace, RBAC resources, and ConfigMaps with benchmark configuration
2. **System Controller Deployment**: Deploy the System Controller pod with complete benchmark parameters
3. **Monitoring**: Track benchmark progress via Kubernetes API (pod status, logs, annotations)
4. **Artifact Retrieval**: Copy results from Records Manager pod back to local filesystem after completion
5. **Cleanup Coordination**: Ensure all cluster resources are removed when benchmark ends

### Unified Communication Architecture

**SystemController Interface**: Both deployment modes expose the same interface
- **Control Plane**: Start/stop/configure benchmark operations
- **Data Plane**: Real-time metrics, progress updates, log streaming
- **Status Plane**: Health checks, service discovery, error reporting

**Connection Protocols**:
- **Multiprocessing**: Local ZMQ IPC sockets (current implementation)
- **Kubernetes**: ZMQ TCP over port-forward to EVENT_BUS_PROXY_BACKEND
- **Fallback**: Polling mode via Kubernetes API for basic monitoring

**Key Insight: Minimal Changes Required**
The UI is already decoupled via ZMQ message subscriptions. For Kubernetes mode:
1. SystemController pod exposes ZMQ EVENT_BUS_PROXY_BACKEND on a TCP port
2. CLI establishes port-forward to that ZMQ port
3. UI connects to localhost ZMQ port (same as current IPC, but TCP)
4. All existing `@on_message` handlers work unchanged


**Improved Architecture Components**:

```python
# CLI Orchestrator - manages both deployment and UI
class AIPerfCLI:
    def run_benchmark(self, config):
        # 1. Deploy SystemController (no UI)
        deployment_manager = self._get_deployment_manager()
        controller_endpoint = deployment_manager.deploy_system_controller(config)

        # 2. Start UI locally if requested
        if config.ui_type == UIType.DASHBOARD:
            ui_client = self._create_ui_client(controller_endpoint)
            ui_task = asyncio.create_task(ui_client.run_dashboard())

        # 3. Wait for completion
        try:
            return await deployment_manager.wait_for_completion()
        finally:
            if ui_task:
                ui_task.cancel()

# SystemController - pure business logic, no UI
class SystemController:
    def __init__(self, service_manager: ServiceManagerProtocol):
        self.service_manager = service_manager  # Multiprocess or Kubernetes
        # NO UI COMPONENTS - just ZMQ event bus for data publishing

    def start_benchmark(self, config):
        # Pure benchmark execution logic
        # Publishes progress via ZMQ EVENT_BUS
        pass

# UI Client - always runs locally, connects to remote SystemController
class UIClient:
    def __init__(self, zmq_endpoint: str):
        self.zmq_endpoint = zmq_endpoint  # IPC or TCP via port-forward

    async def run_dashboard(self):
        # Connect to SystemController's ZMQ EVENT_BUS
        # Run Textual dashboard locally
        # Handle user interactions (quit sends ZMQ command)
        pass
```

### Benefits of Decoupled Architecture

**1. Clean Separation of Concerns**
- **SystemController**: Pure benchmark execution, no UI coupling
- **CLI**: Manages deployment orchestration AND user interface
- **UI**: Always runs locally where user is, regardless of SystemController location

**2. Consistent User Experience**
- UI always runs on user's machine (responsive, local interactions)
- Same dashboard experience for both multiprocessing and Kubernetes
- No network latency for UI interactions (scrolling, panel switching)

**3. Simplified SystemController**
- No UI lifecycle management complexity
- Same code for both deployment modes
- Easier to containerize (no UI dependencies)
- Better resource usage (no UI overhead in pods)

**4. Flexible Architecture**
- UI can connect to local or remote SystemController transparently
- Multiple UI clients can connect simultaneously
- Easy to add new deployment modes without affecting UI
- SystemController can run headless for automation/CI

**5. Robust Connection Handling**
- UI can reconnect if connection drops
- SystemController continues running even if UI disconnects
- CLI manages both deployment lifecycle AND UI lifecycle

### Implementation Strategy

## SystemController Analysis: What Stays vs What Goes

### Current SystemController Responsibilities Analysis

**1. Service Orchestration & Lifecycle (STAYS - Core Business Logic)**
- ✅ **ProxyManager**: ZMQ proxy management for inter-service communication
- ✅ **ServiceManager**: Manages other service lifecycles (dataset, timing, workers, etc.)
- ✅ **Service Registration**: Handles `RegisterServiceCommand` from services
- ✅ **Service Coordination**: `ProfileConfigureCommand`, `ProfileStartCommand` orchestration
- ✅ **Worker Scaling**: `SpawnWorkersCommand`, `ShutdownWorkersCommand` handling
- ✅ **Message Processing**: Heartbeats, status updates, command responses
- ✅ **Signal Handling**: Graceful shutdown on SIGINT/SIGTERM

**2. Results Processing & Export (STAYS - Business Logic)**
- ✅ **Results Collection**: `ProcessRecordsResultMessage` handling
- ✅ **Data Export**: `ExporterManager` for CSV/JSON file generation
- ✅ **Metrics Processing**: Real-time metrics coordination

**3. UI Management (MOVES TO CLI - Presentation Layer)**
- ❌ **UI Instantiation**: `AIPerfUIFactory.create_instance()` → CLI responsibility
- ❌ **UI Lifecycle**: `self.attach_child_lifecycle(self.ui)` → CLI manages
- ❌ **Console Output**: `_print_post_benchmark_info_and_metrics()` → CLI shows results

**4. Process Management (CONTEXT-DEPENDENT)**
- ❌ **Process Exit**: `os._exit(0)` → CLI handles process lifecycle
- ❌ **Signal Setup**: `self.setup_signal_handlers()` → CLI handles in Kubernetes mode

### Proposed Refactored Architecture

**SystemController Becomes Pure Service Orchestrator:**
```python
class SystemController(BaseService):
    def __init__(self, service_manager: ServiceManagerProtocol, ...):
        # NO UI COMPONENTS
        self.service_manager = service_manager  # Injected by CLI
        self.proxy_manager = ProxyManager(...)
        # NO signal handlers (handled by deployment manager)

    # KEEPS: All service coordination logic
    # KEEPS: All business logic and message handling
    # KEEPS: Results processing and export
    # REMOVES: UI management, console output, process exit
```

**CLI Orchestrator Manages Everything Else:**
```python
class AIPerfCLI:
    def run_benchmark(self, config):
        # 1. Choose deployment strategy
        deployment_manager = self._get_deployment_manager(config)

        # 2. Deploy SystemController (pure business logic)
        controller_endpoint = deployment_manager.deploy_system_controller(config)

        # 3. Start UI locally if requested
        if config.ui_type == UIType.DASHBOARD:
            ui_task = self._start_ui_client(controller_endpoint)

        # 4. Wait for completion and handle results
        results = await deployment_manager.wait_for_completion()
        await self._display_final_results(results)  # Console output moves here

        # 5. Cleanup
        await deployment_manager.cleanup()
```

### Key Insight: SystemController ≈ Enhanced Service Manager

You're absolutely right! The SystemController is evolving to become more like the ServiceManager classes, but with additional responsibilities:

**ServiceManager (Base)**: Manages service processes/pods
**SystemController (Enhanced)**: ServiceManager + business logic coordination

**Comparison:**
```python
# MultiProcessServiceManager
- run_service() -> starts processes
- stop_service() -> stops processes
- wait_for_registration() -> waits for startup

# SystemController (New Role)
- run_service() -> delegates to ServiceManager
- coordinate_services() -> sends ProfileConfigure/Start commands
- handle_service_messages() -> processes heartbeats, status, results
- manage_proxies() -> handles ZMQ communication infrastructure
```

### Implementation Strategy

**Phase 1: Extract UI and Console Output**
- Move UI instantiation from SystemController to CLI orchestrator
- Move `_print_post_benchmark_info_and_metrics()` to CLI
- SystemController focuses purely on service coordination

**Phase 2: Extract Process Management**
- Remove `os._exit(0)` from SystemController
- CLI handles process lifecycle in multiprocessing mode
- Deployment managers handle container lifecycle in Kubernetes mode

**Phase 3: Inject Dependencies**
- SystemController receives ServiceManager via dependency injection
- Same SystemController code works with MultiProcessServiceManager or KubernetesServiceManager
- Clean separation of orchestration logic from deployment strategy

## Summary: SystemController Evolution

**Current State**: Monolithic orchestrator handling everything
- Service management + UI + console output + process lifecycle + business logic

**Future State**: Pure service orchestration layer
- **SystemController**: Service coordination + business logic (enhanced ServiceManager)
- **CLI**: Deployment orchestration + UI + user interaction
- **Deployment Managers**: Process/pod lifecycle management

**Key Benefits:**
1. **Same SystemController Code**: Works identically in multiprocess and Kubernetes modes
2. **Clean Layering**: Business logic separate from deployment and presentation concerns
3. **Easier Testing**: SystemController can be tested independently of deployment mode
4. **Better Containerization**: No UI dependencies in SystemController container
5. **Flexible UI**: UI always runs locally, can connect to SystemController anywhere

**Architecture Layers:**
```
┌─────────────────────────────────────────────────────┐
│ CLI Orchestrator                                    │
│ - Deployment mode detection                         │
│ - UI lifecycle management                           │
│ - Results display                                   │
│ - User interaction handling                         │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│ Deployment Manager (Multiprocess/Kubernetes)       │
│ - SystemController deployment                       │
│ - Process/pod lifecycle                            │
│ - Resource management                               │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│ SystemController (Pure Business Logic)             │
│ - Service coordination                              │
│ - ZMQ proxy management                              │
│ - Message processing                                │
│ - Results collection & export                       │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│ ServiceManager (Process/Pod Management)            │
│ - Individual service lifecycle                      │
│ - Service registration tracking                     │
│ - Resource allocation                               │
└─────────────────────────────────────────────────────┘
```

This evolution makes the SystemController much more focused and reusable across different deployment contexts.

**Phase 2: Add TCP Transport Support**
- Add TCP transport option for EVENT_BUS_PROXY_BACKEND (currently only IPC)
- CLI detects deployment mode and configures UI connection accordingly
- Zero changes to existing `@on_message` handlers or UI components

**Phase 3: Create Deployment Managers**
- Extract multiprocessing deployment logic to `MultiprocessDeploymentManager`
- Implement `KubernetesDeploymentManager` for pod orchestration
- CLI orchestrator manages both SystemController deployment AND UI lifecycle

### RBAC and Resource Management
The CLI app creates the initial Kubernetes resources programmatically through the Kubernetes API:

#### RBAC Resource Creation
```python
# ServiceAccount for AIPerf operations
service_account = {
    "apiVersion": "v1",
    "kind": "ServiceAccount",
    "metadata": {
        "name": "aiperf-service-account",
        "namespace": namespace
    }
}

# ClusterRole with required permissions (following least-privilege principle)
cluster_role = {
    "apiVersion": "rbac.authorization.k8s.io/v1",
    "kind": "ClusterRole",
    "metadata": {"name": "aiperf-cluster-role"},
    "rules": [
        {
            "apiGroups": [""],
            "resources": ["pods", "services", "configmaps"],
            "verbs": ["create", "get", "list", "watch", "update", "patch", "delete"]
        },
        {
            "apiGroups": ["apps"],
            "resources": ["deployments", "replicasets"],
            "verbs": ["create", "get", "list", "watch", "update", "patch", "delete"]
        },
    ]
}

# ClusterRoleBinding to associate ServiceAccount with ClusterRole
cluster_role_binding = {
    "apiVersion": "rbac.authorization.k8s.io/v1",
    "kind": "ClusterRoleBinding",
    "metadata": {"name": "aiperf-cluster-role-binding"},
    "subjects": [{"kind": "ServiceAccount", "name": "aiperf-service-account", "namespace": namespace}],
    "roleRef": {"kind": "ClusterRole", "name": "aiperf-cluster-role", "apiGroup": "rbac.authorization.k8s.io"}
}
```

#### Direct API vs YAML File Usage
The CLI app **MUST** use the Kubernetes Python client to create resources programmatically rather than generating YAML files:

**Direct API Approach:**
The CLI app will use the Kubernetes Python client to create resources programmatically. The client will automatically use the standard kubeconfig file (`~/.kube/config`) or in-cluster configuration if running inside a Kubernetes pod.


#### Resource Lifecycle Management
The CLI manages the initial bootstrap resources, while the System Controller pod manages all service-specific resources:

**CLI Responsibilities:**
- Create/delete namespace
- Setup/cleanup RBAC resources
- Deploy/remove System Controller pod
- Create initial ConfigMaps with benchmark configuration

**System Controller Pod Responsibilities:**
- Deploy all service pods (workers, record processors, etc.)
- Manage pod scaling and lifecycle
- Handle service-to-service communication setup
- Coordinate benchmark execution and results collection

## Configuration Management

### CLI Parameters

**Current Implementation**: The `service_run_type` parameter is currently disabled in CLI via `DisableCLI(reason="Only single support for now")` and defaults to `ServiceRunType.MULTIPROCESSING`.

**Simplified Deployment Mode Detection**: The system will automatically detect Kubernetes deployment mode when the `--kubernetes` flag is provided.

**Kubernetes Deployment Parameters**:
- `--kubernetes`: Enable Kubernetes deployment mode
- `--kubernetes-namespace`: Target Kubernetes namespace (optional, defaults to auto-generated namespace)
- `--kubeconfig`: Path to Kubernetes configuration file (optional, defaults to `~/.kube/config`)

**Namespace Behavior**:
- If `--kubernetes-namespace` is specified, AIPerf will use that namespace
- If not specified, AIPerf will auto-generate a unique namespace (e.g., `aiperf-<timestamp>` or `aiperf-<job-id>`)
- Auto-generated namespaces are automatically cleaned up after benchmark completion

**Existing Parameters (Work with Both Deployment Modes)**:
- `--record-processor-service-count`: Controls record processor scaling
- `--workers-max` / `--max-workers`: Controls worker scaling

### Environment Variable Injection
Configuration is passed to pods via environment variables and ConfigMaps:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: aiperf-config
data:
  target_url: "http://inference-service:8080"
  benchmark_duration: "300"
  # ... other AIPerf configuration
```

## Basic Security

AIPerf follows basic Kubernetes security practices without unnecessary complexity:

### Simple RBAC
```yaml
# Basic permissions for AIPerf operations
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: aiperf-operator
rules:
- apiGroups: [""]
  resources: ["pods", "services", "configmaps"]
  verbs: ["create", "get", "list", "watch", "delete"]
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["create", "get", "list", "watch", "delete"]
```

### Pod Security (Basic)
```yaml
# Simple non-root execution
apiVersion: v1
kind: Pod
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
  containers:
  - name: aiperf-worker
    securityContext:
      allowPrivilegeEscalation: false
```

**Security Philosophy**:
- Keep it simple and functional
- Basic non-root execution
- Standard Kubernetes RBAC
- No complex network policies by default
- Focus on performance over paranoid security


## Container Images

### Container Image
A single container image will support all AIPerf service modes. Service mode will be determined by environment variables passed to the pod, leveraging the existing `ServiceFactory` to instantiate the appropriate service class.

## UI Dashboard Architecture

### UI Architecture Solution

**Current Challenge**: UI is instantiated inside SystemController, creating tight coupling between business logic and presentation layer.

**Solution**: Move UI to CLI orchestrator, connect via existing ZMQ infrastructure.

**Implementation**:
- UI already receives all data via ZMQ (`@on_message` decorators on `MessageBusClientMixin`)
- Only change needed: UI connects to ZMQ TCP instead of IPC when in Kubernetes mode
- Same Textual dashboard, same user experience, same keyboard shortcuts

### Technical Implementation

**ZMQ Connection Pattern:**
- **Multiprocessing**: UI connects to `EVENT_BUS_PROXY_BACKEND` via IPC socket
- **Kubernetes**: UI connects to `EVENT_BUS_PROXY_BACKEND` via TCP socket over port-forward
- **Same Protocol**: All `@on_message` handlers work identically

**User Experience:**
- Same command: `aiperf profile --kubernetes --concurrency 1M`
- Same dashboard: Identical Textual UI with all features
- Same interactions: All keyboard shortcuts and navigation work normally

**Connection Details:**
- CLI automatically establishes port-forward to SystemController pod's ZMQ port
- UI connects to localhost ZMQ TCP port (transparent to user)
- Terminal size, mouse events, and keyboard input handled locally (no network latency)


### User Interaction Handling

**Local UI Interactions (No Changes):**
- All view controls, navigation, and screenshots work locally
- No network communication required for UI state changes
- Identical user experience to multiprocessing mode

**Process Control via ZMQ Commands:**
- Quit action (Ctrl+C) sends `ShutdownCommand` via ZMQ instead of SIGINT
- CLI monitors for shutdown commands and handles cleanup
- Graceful termination of SystemController pod


## Artifact and Export File Retrieval

AIPerf generates output files including metrics exports (JSON, CSV) and logs that users need to access after benchmark completion. In the Kubernetes deployment, these files are generated by the Records Manager pod and must be retrieved to the user's local filesystem.

### Basic Approach

The Records Manager pod acts as the central collection point for all benchmark artifacts. It receives processed metrics from distributed pods and generates the final export files in its local artifact directory using the existing AIPerf exporters.

After benchmark completion, AIPerf will automatically copy all artifact files from the Records Manager pod to the user's local filesystem using the Kubernetes API in Python. This preserves the standard AIPerf directory structure and provides users with the same export files they would receive from a single-node deployment.

Once files are successfully retrieved, all Kubernetes pods are automatically cleaned up to minimize cluster resource usage.

### **Deferred to Implementation**
- **Optimal ZMQ port allocation strategy**: Determine whether to use fixed ports or dynamic port allocation with service discovery
- **Pod anti-affinity rules**: Decide on pod placement strategies to optimize network performance and resource distribution
- **Persistent volume integration**: Define strategy for sharing dataset files and result artifacts across pods
- **Custom Resource Definition (CRD)**: Evaluate whether to implement a native Kubernetes CRD for BenchmarkJob resources
- **Graceful shutdown handling**: Implementation details for clean termination of distributed benchmark runs
- **Metric aggregation optimization**: Determine optimal batching and streaming strategies for high-volume metrics collection
- **ConfigMap vs Secret usage**: Define strategy for sensitive configuration data (API keys, certificates) vs regular config

# Implementation Phases

## Phase 0 Kubernetes Integration (MVP)

**Release Target**: Q1 2026

**Effort Estimate**: 6-8 weeks, 2 engineers

**Focus**: Get 1M+ concurrency working with simple, reliable deployment

**Core Features:**

* ✅ CLI deployment with automatic Kubernetes mode detection
* ✅ Worker pod scaling based on concurrency target
* ✅ ZMQ communication across pod boundaries
* ✅ **Same dashboard UI experience** (runs locally, connects via ZMQ)
* ✅ Automatic cleanup after test completion
* ✅ Basic RBAC security

# Related Proposals

N/A - This is the initial proposal for Kubernetes deployment support in AIPerf.

# Alternate Solutions

## Alt 1 Single Monolithic Pod Deployment

**Pros:**

* Simpler deployment model with fewer moving parts
* Easier debugging and troubleshooting with all services in one place
* Reduced network complexity as all communication remains local
* Lower resource overhead from avoiding inter-pod communication

**Cons:**

* Limited scalability as all services share the same resource constraints
* Difficult to scale individual services (workers, record processors) independently
* Higher memory usage per pod due to co-location of all services
* Reduced fault tolerance as single pod failure affects entire benchmark

**Reason Rejected:**

* Does not address the core requirement of generating high concurrency loads beyond single-node limits
* Cannot overcome connection limitations imposed by `AIPERF_HTTP_CONNECTION_LIMIT` configuration
* Prevents independent scaling of worker services which is essential for distributed load generation
* Conflicts with the architectural decision to adopt true per-service pod architecture for maximum flexibility

**Notes:**

This approach is similar to the current single-node deployment but containerized for Kubernetes. While simpler, it fails to leverage the primary benefits of distributed deployment.

## Alt 2 Hybrid Co-location Approach

**Pros:**

* Reduces pod count by co-locating coordination services
* Simpler service discovery with fewer network endpoints
* Potentially lower networking overhead between co-located services
* Easier resource management for singleton services

**Cons:**

* Mixed approach complicates deployment logic (some services co-located, others separate)
* Less flexibility for independent resource tuning of singleton services
* Reduced fault tolerance as controller pod failure affects multiple services
* Harder to debug individual service issues when co-located

**Reason Rejected:**

* Per-service pods provide maximum flexibility and isolation
* Resource requirements for singleton services are sufficiently small that co-location benefits are minimal
* Consistency of having all services in individual pods simplifies architecture

## Alt 3 Kubernetes Job-Based Deployment Only

**Pros:**

* Leverages native Kubernetes job scheduling and lifecycle management
* Integrates well with CI/CD pipelines and batch processing workflows
* Automatic cleanup and resource management through Kubernetes job controller
* Simple YAML-based configuration without custom CLI extensions

**Cons:**

* Limited real-time control and monitoring during benchmark execution
* Difficult to implement dynamic scaling based on runtime metrics
* Reduced flexibility for interactive benchmark sessions
* May not support complex coordination patterns required by AIPerf

**Reason Rejected:**

* Meeting discussion indicated desire for both interactive CLI-driven deployment and job-based execution
* Constraints of Kubernetes job model may limit AIPerf's coordination capabilities
* Decision made to support CLI-driven deployment as primary interface

**Notes:**

Job-based deployment provides excellent CI/CD integration but limits real-time interaction capabilities.

## Alt 4 External Orchestrator with Helm Charts

**Pros:**

* Leverages mature Helm ecosystem for templating and package management
* Easier deployment across different Kubernetes distributions
* Built-in versioning and rollback capabilities through Helm
* Community-standard approach for complex Kubernetes applications

**Cons:**

* Adds external dependency on Helm installation and management
* More complex CLI implementation to generate and apply Helm charts
* Additional learning curve for users unfamiliar with Helm
* May complicate custom resource management and cleanup logic

**Reason Rejected:**

* Meeting emphasized using Kubernetes API directly rather than external tools
* Adds complexity without addressing core scaling requirements
* Direct API approach provides more control over resource lifecycle management

**Notes:**

Helm charts could be provided as an optional deployment method in future releases.

# Background

AIPerf is NVIDIA's AI inference performance benchmarking tool designed to validate and stress-test AI inference services. The current implementation uses a multi-service architecture where services communicate via ZeroMQ (ZMQ) message passing. Services include the system controller (orchestration), dataset manager (data loading), timing manager (request rate control), workers (request execution), and record processors (response processing and metrics).

The single-node limitation has become a significant constraint as AI inference workloads scale to production-level concurrency volumes. A fundamental bottleneck is the exhaustion of ephemeral ports on a single system, which limits concurrent TCP connections to approximately 65,535 ports per node (practical limit ~63,500). Modern AI inference services require validation against concurrent loads exceeding 100,000 simultaneous connections, particularly for large language models and computer vision services deployed in production environments.

## References

* [Kubernetes API Documentation](https://kubernetes.io/docs/reference/kubernetes-api/)
* [ZeroMQ Distributed Messaging Guide](https://zguide.zeromq.org/docs/chapter4/)
* [Kubernetes Deployment and ReplicaSet Concepts](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)

## Terminology & Definitions

| Term | Definition |
| :---- | :---- |
| **Credit** | Token representing a single inference request to be executed by a worker |
| **Ephemeral Port** | Temporary port assigned by the OS for outbound connections, limited to ~65,535 per node |
| **Per-Service Pod** | Architecture where each AIPerf service runs in its own dedicated Kubernetes pod |
| **Record Processor** | AIPerf service responsible for response tokenization and initial metrics processing |
| **Service Pod** | Kubernetes pod containing a single AIPerf service instance |
| **ZMQ Proxy** | Service that routes messages between distributed ZeroMQ clients using various patterns |

## Acronyms & Abbreviations

**CRD:** Custom Resource Definition
**HPA:** Horizontal Pod Autoscaler
**mTLS:** Mutual Transport Layer Security
**NUMA:** Non-Uniform Memory Access
**RBAC:** Role-Based Access Control
**SR-IOV:** Single Root I/O Virtualization
**VPA:** Vertical Pod Autoscaler
**ZMQ:** ZeroMQ
