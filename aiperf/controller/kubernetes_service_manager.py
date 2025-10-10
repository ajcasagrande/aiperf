# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import uuid
from datetime import datetime
from pathlib import Path

from kubernetes import client, config
from kubernetes.client.rest import ApiException
from pydantic import BaseModel

from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.constants import (
    DEFAULT_SERVICE_REGISTRATION_TIMEOUT,
    DEFAULT_SERVICE_START_TIMEOUT,
)
from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import ServiceRegistrationStatus, ServiceRunType, ServiceType
from aiperf.common.exceptions import AIPerfError
from aiperf.common.factories import ServiceFactory, ServiceManagerFactory
from aiperf.common.hooks import on_init
from aiperf.common.protocols import ServiceManagerProtocol
from aiperf.common.types import ServiceTypeT
from aiperf.controller.base_service_manager import BaseServiceManager


class ServiceKubernetesRunInfo(BaseModel):
    """Information about a service running in a Kubernetes pod."""

    pod_name: str
    service_type: ServiceTypeT
    service_id: str
    namespace: str
    node_name: str | None = None


@implements_protocol(ServiceManagerProtocol)
@ServiceManagerFactory.register(ServiceRunType.KUBERNETES)
class KubernetesServiceManager(BaseServiceManager):
    """
    Service Manager for starting and stopping services in a Kubernetes cluster.

    This manager handles:
    - Creating namespace and RBAC resources
    - Deploying service pods via Kubernetes API
    - Creating Kubernetes Services for ZMQ communication
    - Managing pod lifecycle (start, stop, cleanup)
    - Tracking pod status and registration
    """

    def __init__(
        self,
        required_services: dict[ServiceTypeT, int],
        service_config: ServiceConfig,
        user_config: UserConfig,
        **kwargs,
    ):
        super().__init__(required_services, service_config, user_config, **kwargs)

        # Track Kubernetes-specific info
        self.kubernetes_info: list[ServiceKubernetesRunInfo] = []

        # Initialize Kubernetes client
        self._init_kubernetes_client()

        # Namespace management
        self.namespace = self._determine_namespace()

        # Check if we're running inside a pod (System Controller)
        # If so, DON'T auto-cleanup - let the CLI handle cleanup after retrieving results
        namespace_file = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace")
        running_in_cluster = namespace_file.exists()

        if running_in_cluster:
            # Pods should never self-cleanup - CLI handles it
            self.should_cleanup_namespace = False
            self.debug("Running in-cluster: disabling auto-cleanup (CLI will handle it)")
        else:
            # CLI uses the configured auto-cleanup setting
            self.should_cleanup_namespace = self.service_config.kubernetes.should_auto_cleanup
            self.debug(f"Running from CLI: auto_cleanup={self.should_cleanup_namespace}")

        self.debug(
            f"Kubernetes mode initialized: namespace={self.namespace}, "
            f"auto_cleanup={self.should_cleanup_namespace}"
        )

    @on_init
    async def _initialize_kubernetes_resources(self) -> None:
        """Set up Kubernetes resources during initialization phase."""
        await self._setup_kubernetes_resources()

    def _init_kubernetes_client(self) -> None:
        """Initialize Kubernetes client from kubeconfig."""
        kubeconfig_path = self.service_config.kubernetes.kubeconfig_path
        if kubeconfig_path and kubeconfig_path.exists():
            config.load_kube_config(config_file=str(kubeconfig_path))
            self.debug(f"Loaded kubeconfig from {kubeconfig_path}")
        else:
            # Try default kubeconfig location
            default_kubeconfig = Path.home() / ".kube" / "config"
            if default_kubeconfig.exists():
                config.load_kube_config(config_file=str(default_kubeconfig))
                self.debug(f"Loaded kubeconfig from {default_kubeconfig}")
            else:
                # Try in-cluster config (when running inside a pod)
                try:
                    config.load_incluster_config()
                    self.debug("Loaded in-cluster Kubernetes config")
                except config.ConfigException:
                    raise AIPerfError(
                        "Could not find Kubernetes configuration. Please ensure kubeconfig is available or "
                        "specify --kubeconfig path."
                    )

        # Initialize API clients
        self.core_v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
        self.rbac_v1 = client.RbacAuthorizationV1Api()

    def _determine_namespace(self) -> str:
        """Determine which namespace to use."""
        # If namespace is explicitly set in config, use it
        if self.service_config.kubernetes.kubernetes_namespace:
            return self.service_config.kubernetes.kubernetes_namespace

        # If we're running inside a pod (in-cluster), use the current namespace
        # This is set by Kubernetes via downward API
        namespace_file = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace")
        if namespace_file.exists():
            current_namespace = namespace_file.read_text().strip()
            self.debug(
                f"Detected running in-cluster, using namespace: {current_namespace}"
            )
            return current_namespace

        # Auto-generate unique namespace (for CLI orchestrator)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        return f"aiperf-{timestamp}-{unique_id}"

    async def _setup_kubernetes_resources(self) -> None:
        """Create namespace, RBAC resources, and Kubernetes Services."""
        self.debug("Setting up Kubernetes resources...")

        # Check if we're running in-cluster
        namespace_file = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace")
        running_in_cluster = namespace_file.exists()

        if not running_in_cluster:
            # Only create namespace and RBAC if we're NOT running in-cluster
            # When in-cluster, these already exist (created by the CLI orchestrator)
            self.debug("Running from CLI - creating namespace and RBAC resources")
            await self._create_namespace()
            await self._create_rbac_resources()
        else:
            self.debug(
                "Running in-cluster - skipping namespace/RBAC creation (already exist)"
            )

        # Create Kubernetes Services for pods that BIND sockets
        # These must be created before pods start so others can connect
        await self._create_system_controller_service()
        await self._create_timing_manager_service()
        await self._create_records_manager_service()

        self.info(f"Kubernetes resources created in namespace: {self.namespace}")

    async def _create_namespace(self) -> None:
        """Create Kubernetes namespace if it doesn't exist."""
        namespace_body = client.V1Namespace(
            metadata=client.V1ObjectMeta(
                name=self.namespace,
                labels={
                    "app": "aiperf",
                    "created-by": "aiperf-cli",
                },
            )
        )

        try:
            self.core_v1.create_namespace(body=namespace_body)
            self.debug(f"Created namespace: {self.namespace}")
        except ApiException as e:
            if e.status == 409:  # Already exists
                self.debug(f"Namespace {self.namespace} already exists")
            else:
                raise AIPerfError(f"Failed to create namespace: {e}")

    async def _create_rbac_resources(self) -> None:
        """Create ServiceAccount, Role, and RoleBinding for AIPerf pods."""
        service_account_name = self.service_config.kubernetes.kubernetes_service_account

        # ServiceAccount
        service_account = client.V1ServiceAccount(
            metadata=client.V1ObjectMeta(name=service_account_name)
        )

        try:
            self.core_v1.create_namespaced_service_account(
                namespace=self.namespace, body=service_account
            )
            self.debug(f"Created ServiceAccount: {service_account_name}")
        except ApiException as e:
            if e.status == 409:  # Already exists
                self.debug(f"ServiceAccount {service_account_name} already exists")
            else:
                raise AIPerfError(f"Failed to create ServiceAccount: {e}")

        # Role (namespace-scoped permissions)
        role = client.V1Role(
            metadata=client.V1ObjectMeta(name="aiperf-role"),
            rules=[
                client.V1PolicyRule(
                    api_groups=[""],
                    resources=["pods", "services", "configmaps"],
                    verbs=[
                        "create",
                        "get",
                        "list",
                        "watch",
                        "update",
                        "patch",
                        "delete",
                    ],
                ),
                client.V1PolicyRule(
                    api_groups=["apps"],
                    resources=["deployments", "replicasets"],
                    verbs=[
                        "create",
                        "get",
                        "list",
                        "watch",
                        "update",
                        "patch",
                        "delete",
                    ],
                ),
            ],
        )

        try:
            self.rbac_v1.create_namespaced_role(namespace=self.namespace, body=role)
            self.debug("Created Role: aiperf-role")
        except ApiException as e:
            if e.status == 409:  # Already exists
                self.debug("Role aiperf-role already exists")
            else:
                raise AIPerfError(f"Failed to create Role: {e}")

        # RoleBinding
        role_binding = client.V1RoleBinding(
            metadata=client.V1ObjectMeta(name="aiperf-role-binding"),
            subjects=[
                client.RbacV1Subject(
                    kind="ServiceAccount",
                    name=service_account_name,
                    namespace=self.namespace,
                )
            ],
            role_ref=client.V1RoleRef(
                kind="Role", name="aiperf-role", api_group="rbac.authorization.k8s.io"
            ),
        )

        try:
            self.rbac_v1.create_namespaced_role_binding(
                namespace=self.namespace, body=role_binding
            )
            self.debug("Created RoleBinding: aiperf-role-binding")
        except ApiException as e:
            if e.status == 409:  # Already exists
                self.debug("RoleBinding aiperf-role-binding already exists")
            else:
                raise AIPerfError(f"Failed to create RoleBinding: {e}")

    async def _create_system_controller_service(self) -> None:
        """Create Kubernetes Service to expose System Controller ZMQ ports.

        This service exposes all ZMQ proxy ports so other pods can connect.
        """
        # Get ZMQ port configuration
        zmq_config = self.service_config.comm_config

        # Define service ports for all ZMQ endpoints
        service_ports = [
            # Core ZMQ ports
            client.V1ServicePort(
                name="credit-drop",
                port=5562,
                target_port=5562,
                protocol="TCP",
            ),
            client.V1ServicePort(
                name="credit-return",
                port=5563,
                target_port=5563,
                protocol="TCP",
            ),
            client.V1ServicePort(
                name="records",
                port=5557,
                target_port=5557,
                protocol="TCP",
            ),
            # Dataset Manager Proxy
            client.V1ServicePort(
                name="dataset-proxy-frontend",
                port=5661,
                target_port=5661,
                protocol="TCP",
            ),
            client.V1ServicePort(
                name="dataset-proxy-backend",
                port=5662,
                target_port=5662,
                protocol="TCP",
            ),
            # Event Bus Proxy
            client.V1ServicePort(
                name="event-bus-frontend",
                port=5663,
                target_port=5663,
                protocol="TCP",
            ),
            client.V1ServicePort(
                name="event-bus-backend",
                port=5664,
                target_port=5664,
                protocol="TCP",
            ),
            # Raw Inference Proxy
            client.V1ServicePort(
                name="raw-inference-frontend",
                port=5665,
                target_port=5665,
                protocol="TCP",
            ),
            client.V1ServicePort(
                name="raw-inference-backend",
                port=5666,
                target_port=5666,
                protocol="TCP",
            ),
        ]

        # Service specification
        service_spec = client.V1ServiceSpec(
            selector={
                "app": "aiperf",
                "service-type": str(ServiceType.SYSTEM_CONTROLLER),
            },
            ports=service_ports,
            type="ClusterIP",  # Internal service
        )

        # Service metadata
        service_name = "aiperf-system-controller"
        service_metadata = client.V1ObjectMeta(
            name=service_name,
            namespace=self.namespace,
            labels={
                "app": "aiperf",
                "component": "system-controller",
            },
        )

        service = client.V1Service(
            metadata=service_metadata,
            spec=service_spec,
        )

        try:
            self.core_v1.create_namespaced_service(
                namespace=self.namespace, body=service
            )
            self.info(f"Created Kubernetes Service: {service_name}")

            # Update ZMQ host to use the Service DNS name
            full_dns = f"{service_name}.{self.namespace}.svc.cluster.local"
            if hasattr(self.service_config.comm_config, "host"):
                self.service_config.comm_config.host = full_dns
                self.debug(f"Updated ZMQ host to: {full_dns}")

        except ApiException as e:
            if e.status == 409:  # Already exists
                self.debug(f"Service {service_name} already exists")
            else:
                raise AIPerfError(f"Failed to create Service: {e}")

    async def _create_timing_manager_service(self) -> None:
        """Create Kubernetes Service to expose TimingManager ZMQ ports.

        TimingManager binds CREDIT_DROP (PUSH) and CREDIT_RETURN (PULL) sockets.
        """
        service_ports = [
            client.V1ServicePort(
                name="credit-drop",
                port=self.service_config.comm_config.credit_drop_port if hasattr(self.service_config.comm_config, 'credit_drop_port') else 5562,
                target_port=self.service_config.comm_config.credit_drop_port if hasattr(self.service_config.comm_config, 'credit_drop_port') else 5562,
                protocol="TCP",
            ),
            client.V1ServicePort(
                name="credit-return",
                port=self.service_config.comm_config.credit_return_port if hasattr(self.service_config.comm_config, 'credit_return_port') else 5563,
                target_port=self.service_config.comm_config.credit_return_port if hasattr(self.service_config.comm_config, 'credit_return_port') else 5563,
                protocol="TCP",
            ),
        ]

        service = client.V1Service(
            metadata=client.V1ObjectMeta(name="timing-manager"),
            spec=client.V1ServiceSpec(
                selector={
                    "app": "aiperf",
                    "service-type": str(ServiceType.TIMING_MANAGER),
                },
                ports=service_ports,
                type="ClusterIP",
            ),
        )

        try:
            self.core_v1.create_namespaced_service(
                namespace=self.namespace, body=service
            )
            self.debug("Created Kubernetes Service: timing-manager")
        except ApiException as e:
            if e.status == 409:
                self.debug("Service timing-manager already exists")
            else:
                raise AIPerfError(f"Failed to create timing-manager Service: {e}")

    async def _create_records_manager_service(self) -> None:
        """Create Kubernetes Service to expose RecordsManager ZMQ port.

        RecordsManager binds RECORDS (PULL) socket.
        """
        service_ports = [
            client.V1ServicePort(
                name="records",
                port=self.service_config.comm_config.records_push_pull_port if hasattr(self.service_config.comm_config, 'records_push_pull_port') else 5557,
                target_port=self.service_config.comm_config.records_push_pull_port if hasattr(self.service_config.comm_config, 'records_push_pull_port') else 5557,
                protocol="TCP",
            ),
        ]

        service = client.V1Service(
            metadata=client.V1ObjectMeta(name="records-manager"),
            spec=client.V1ServiceSpec(
                selector={
                    "app": "aiperf",
                    "service-type": str(ServiceType.RECORDS_MANAGER),
                },
                ports=service_ports,
                type="ClusterIP",
            ),
        )

        try:
            self.core_v1.create_namespaced_service(
                namespace=self.namespace, body=service
            )
            self.debug("Created Kubernetes Service: records-manager")
        except ApiException as e:
            if e.status == 409:
                self.debug("Service records-manager already exists")
            else:
                raise AIPerfError(f"Failed to create records-manager Service: {e}")

    def _create_pod_spec(
        self, service_type: ServiceTypeT, service_id: str
    ) -> client.V1Pod:
        """Create a Kubernetes Pod specification for a service.

        Args:
            service_type: Type of AIPerf service
            service_id: Unique ID for this service instance

        Returns:
            V1Pod specification ready to be created
        """
        # For Kubernetes, we need different ZMQ host configurations:
        # - System Controller: bind to 0.0.0.0 (all interfaces) - handled by pod entrypoint
        # - Service pods: bind to 0.0.0.0 for their own sockets (CREDIT_*, RECORDS),
        #   but connect to aiperf-system-controller for System Controller's proxy addresses

        # Create a copy of service_config to avoid modifying the shared instance
        import copy

        pod_service_config = copy.deepcopy(self.service_config)

        # Configure ZMQ hosts based on service type and socket patterns
        # Architecture:
        #   - TimingManager: BINDS credit_drop (PUSH) and credit_return (PULL) -> host=0.0.0.0
        #   - RecordsManager: BINDS records (PULL) -> host=0.0.0.0
        #   - Workers: CONNECT to timing-manager for credits, records-manager for records
        #   - All services: CONNECT to aiperf-system-controller for proxies
        if service_type != ServiceType.SYSTEM_CONTROLLER:
            if pod_service_config.zmq_tcp:
                # Services that BIND sockets need host=0.0.0.0
                if service_type in (ServiceType.TIMING_MANAGER, ServiceType.RECORDS_MANAGER):
                    pod_service_config.zmq_tcp.host = "0.0.0.0"
                    # But still connect to System Controller for proxies
                    sc_dns = "aiperf-system-controller"
                    pod_service_config.zmq_tcp.event_bus_proxy_config.host = sc_dns
                    pod_service_config.zmq_tcp.dataset_manager_proxy_config.host = sc_dns
                    pod_service_config.zmq_tcp.raw_inference_proxy_config.host = sc_dns
                    self.debug(
                        f"Configured BIND service {service_id}: host=0.0.0.0, proxy_hosts={sc_dns}"
                    )
                else:
                    # Services that CONNECT: use Service DNS names based on socket usage
                    # - Workers: connect to timing-manager (credits) and records-manager (records)
                    # - RecordProcessors: connect to records-manager (records only)
                    # - WorkerManager/DatasetManager: only use proxies, connect to system-controller
                    #
                    # Since ZMQTCPConfig has one 'host' field for all non-proxy addresses:
                    #   - Workers: use timing-manager (covers credit_drop & credit_return)
                    #   - RecordProcessors: use records-manager (covers records)
                    #   - Others: use aiperf-system-controller
                    sc_dns = "aiperf-system-controller"

                    if service_type == ServiceType.WORKER:
                        # Workers use credits from timing-manager
                        pod_service_config.zmq_tcp.host = "timing-manager"
                        self.debug(f"Configured Worker {service_id}: credit_host=timing-manager")
                    elif service_type == ServiceType.RECORD_PROCESSOR:
                        # RecordProcessors send records to records-manager
                        pod_service_config.zmq_tcp.host = "records-manager"
                        self.debug(f"Configured RecordProcessor {service_id}: records_host=records-manager")
                    else:
                        # WorkerManager, DatasetManager: only use proxies
                        pod_service_config.zmq_tcp.host = sc_dns
                        self.debug(f"Configured {service_type} {service_id}: host={sc_dns}")

                    # All services connect to System Controller for proxies
                    pod_service_config.zmq_tcp.event_bus_proxy_config.host = sc_dns
                    pod_service_config.zmq_tcp.dataset_manager_proxy_config.host = sc_dns
                    pod_service_config.zmq_tcp.raw_inference_proxy_config.host = sc_dns

                # Update internal cache
                pod_service_config._comm_config = pod_service_config.zmq_tcp

        # Serialize configs to JSON for environment variables
        # Use exclude_none=False to ensure proxy host overrides are included
        service_config_json = pod_service_config.model_dump_json(exclude_none=False)
        user_config_json = self.user_config.model_dump_json(exclude_unset=True)

        # Environment variables for the pod
        env_vars = [
            client.V1EnvVar(name="AIPERF_SERVICE_TYPE", value=str(service_type)),
            client.V1EnvVar(name="AIPERF_SERVICE_ID", value=service_id),
            client.V1EnvVar(name="AIPERF_SERVICE_CONFIG", value=service_config_json),
            client.V1EnvVar(name="AIPERF_USER_CONFIG", value=user_config_json),
        ]

        # Container specification
        container = client.V1Container(
            name="aiperf-service",
            image=self.service_config.kubernetes.kubernetes_image,
            image_pull_policy=self.service_config.kubernetes.kubernetes_image_pull_policy,
            env=env_vars,
            # Command to bootstrap the service
            command=["python", "-m", "aiperf.controller.kubernetes_pod_entrypoint"],
        )

        # Pod specification
        pod_spec = client.V1PodSpec(
            service_account_name=self.service_config.kubernetes.kubernetes_service_account,
            containers=[container],
            restart_policy="Never",  # Don't auto-restart failed pods
        )

        # Pod metadata - use service_id as pod name (already contains service type)
        # Ensure valid Kubernetes pod name: lowercase alphanumeric, hyphens only,
        # start and end with alphanumeric
        pod_name = service_id.lower()
        pod_metadata = client.V1ObjectMeta(
            name=pod_name,
            namespace=self.namespace,
            labels={
                "app": "aiperf",
                "service-type": str(service_type),
                "service-id": service_id,
            },
        )

        return client.V1Pod(metadata=pod_metadata, spec=pod_spec)

    async def run_service(
        self, service_type: ServiceTypeT, num_replicas: int = 1
    ) -> None:
        """Run a service by creating Kubernetes pods.

        Args:
            service_type: Type of service to run
            num_replicas: Number of pod replicas to create
        """
        self.debug(f"Creating {num_replicas} pod(s) for service {service_type}")

        service_class = ServiceFactory.get_class_from_type(service_type)

        for replica in range(num_replicas):
            # Generate service ID with hyphens instead of underscores for Kubernetes compatibility
            # Pod names must match [a-z0-9]([-a-z0-9]*[a-z0-9])?
            service_id_base = str(service_type).replace("_", "-")
            service_id = f"{service_id_base}-{uuid.uuid4().hex[:8]}"

            # Create pod specification
            pod_spec = self._create_pod_spec(service_type, service_id)

            # Create the pod via Kubernetes API
            try:
                created_pod = self.core_v1.create_namespaced_pod(
                    namespace=self.namespace, body=pod_spec
                )
                pod_name = created_pod.metadata.name

                self.debug(
                    f"Created pod {pod_name} for service {service_type} (replica {replica + 1}/{num_replicas})"
                )

                # Track the pod
                self.kubernetes_info.append(
                    ServiceKubernetesRunInfo(
                        pod_name=pod_name,
                        service_type=service_type,
                        service_id=service_id,
                        namespace=self.namespace,
                    )
                )

            except ApiException as e:
                raise AIPerfError(
                    f"Failed to create pod for {service_type}: {e.reason}"
                )

    async def stop_service(
        self, service_type: ServiceTypeT, service_id: str | None = None
    ) -> list[BaseException | None]:
        """Stop service pods gracefully.

        Args:
            service_type: Type of service to stop
            service_id: Optional specific service ID to stop

        Returns:
            List of exceptions (or None) for each pod stopped
        """
        self.debug(f"Stopping {service_type} pod(s) with id: {service_id}")

        results = []
        for info in list(self.kubernetes_info):
            if info.service_type == service_type and (
                service_id is None or info.service_id == service_id
            ):
                try:
                    # Delete the pod
                    self.core_v1.delete_namespaced_pod(
                        name=info.pod_name,
                        namespace=self.namespace,
                        grace_period_seconds=30,  # 30 second graceful shutdown
                    )
                    self.debug(f"Deleted pod {info.pod_name}")
                    self.kubernetes_info.remove(info)
                    results.append(None)
                except ApiException as e:
                    self.error(f"Failed to delete pod {info.pod_name}: {e.reason}")
                    results.append(e)

        return results

    async def shutdown_all_services(self) -> list[BaseException | None]:
        """Stop all service pods gracefully.

        In Kubernetes mode, when running in-cluster (inside a pod), we DON'T delete
        pods here. The CLI will handle cleanup after retrieving results.
        """
        # Check if we're running inside a pod
        namespace_file = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace")
        running_in_cluster = namespace_file.exists()

        if running_in_cluster:
            self.debug(
                "Running in-cluster: skipping pod deletion (CLI will handle cleanup after result retrieval)"
            )
            # Just mark services as stopped but don't delete pods
            return []

        # CLI-side shutdown: delete all pods
        self.debug("Stopping all service pods")

        results = []
        for info in list(self.kubernetes_info):
            try:
                self.core_v1.delete_namespaced_pod(
                    name=info.pod_name,
                    namespace=self.namespace,
                    grace_period_seconds=30,
                )
                self.debug(f"Deleted pod {info.pod_name}")
                results.append(None)
            except ApiException as e:
                self.error(f"Failed to delete pod {info.pod_name}: {e.reason}")
                results.append(e)

        self.kubernetes_info.clear()

        # Cleanup namespace if auto-generated
        if self.should_cleanup_namespace:
            await self._cleanup_namespace()

        return results

    async def kill_all_services(self) -> list[BaseException | None]:
        """Force kill all service pods immediately."""
        self.debug("Force killing all service pods")

        results = []
        for info in list(self.kubernetes_info):
            try:
                self.core_v1.delete_namespaced_pod(
                    name=info.pod_name,
                    namespace=self.namespace,
                    grace_period_seconds=0,  # Immediate kill
                )
                self.debug(f"Force killed pod {info.pod_name}")
                results.append(None)
            except ApiException as e:
                self.error(f"Failed to kill pod {info.pod_name}: {e.reason}")
                results.append(e)

        self.kubernetes_info.clear()

        # Cleanup namespace if auto-generated
        if self.should_cleanup_namespace:
            await self._cleanup_namespace()

        return results

    async def _cleanup_namespace(self) -> None:
        """Delete the namespace and all resources within it."""
        try:
            self.info(f"Cleaning up namespace: {self.namespace}")
            self.core_v1.delete_namespace(
                name=self.namespace,
                grace_period_seconds=30,
            )
            self.debug(f"Namespace {self.namespace} deleted")
        except ApiException as e:
            self.error(f"Failed to delete namespace {self.namespace}: {e.reason}")

    async def wait_for_all_services_registration(
        self,
        stop_event: asyncio.Event,
        timeout_seconds: float = DEFAULT_SERVICE_REGISTRATION_TIMEOUT,
    ) -> None:
        """Wait for all required services to be registered.

        For Kubernetes, this means waiting for:
        1. Pods to be in Running state
        2. Services to register with the System Controller via ZMQ

        Args:
            stop_event: Event to check if operation should be cancelled
            timeout_seconds: Maximum time to wait in seconds

        Raises:
            AIPerfError: If any service failed to register within timeout
        """
        self.debug("Waiting for all required services to register...")

        required_types = set(self.required_services.keys())

        async def _wait_for_registration():
            while not stop_event.is_set():
                # First, check that all pods are running
                all_pods_running = await self._check_all_pods_running()
                if not all_pods_running:
                    await asyncio.sleep(1)
                    continue

                # Then check service registration (same as multiprocess)
                registered_types = {
                    service_info.service_type
                    for service_info in self.service_id_map.values()
                    if service_info.registration_status
                    == ServiceRegistrationStatus.REGISTERED
                }

                if required_types.issubset(registered_types):
                    self.info("All services registered successfully")
                    return

                # Check for failed pods
                failed_pods = await self._get_failed_pods()
                if failed_pods:
                    raise AIPerfError(
                        f"The following pods failed before registering: {failed_pods}"
                    )

                await asyncio.sleep(0.5)

        try:
            await asyncio.wait_for(_wait_for_registration(), timeout=timeout_seconds)
        except asyncio.TimeoutError as e:
            # Log which services didn't register
            registered_types_set = set(
                service_info.service_type
                for service_info in self.service_id_map.values()
                if service_info.registration_status
                == ServiceRegistrationStatus.REGISTERED
            )

            for service_type in required_types:
                if service_type not in registered_types_set:
                    self.error(
                        f"Service {service_type} failed to register within timeout"
                    )

            raise AIPerfError("Some services failed to register within timeout") from e

    async def wait_for_all_services_start(
        self,
        stop_event: asyncio.Event,
        timeout_seconds: float = DEFAULT_SERVICE_START_TIMEOUT,
    ) -> None:
        """Wait for all required services to be started.

        For Kubernetes, this is similar to registration but checks that services
        have completed their start phase.

        Args:
            stop_event: Event to check if operation should be cancelled
            timeout_seconds: Maximum time to wait in seconds

        Raises:
            AIPerfError: If any service failed to start within timeout
        """
        self.debug("Waiting for all required services to start...")

        # For now, we use the same logic as multiprocess since services
        # report their lifecycle state via ZMQ
        # TODO: Could add additional Kubernetes-specific health checks here

        async def _wait_for_start():
            while not stop_event.is_set():
                # Check for failed pods
                failed_pods = await self._get_failed_pods()
                if failed_pods:
                    raise AIPerfError(f"The following pods failed: {failed_pods}")

                await asyncio.sleep(0.5)

        try:
            await asyncio.wait_for(_wait_for_start(), timeout=timeout_seconds)
        except asyncio.TimeoutError as e:
            raise AIPerfError("Some services failed to start within timeout") from e

    async def _check_all_pods_running(self) -> bool:
        """Check if all tracked pods are in Running state.

        Returns:
            True if all pods are running, False otherwise
        """
        for info in self.kubernetes_info:
            try:
                pod = self.core_v1.read_namespaced_pod_status(
                    name=info.pod_name, namespace=self.namespace
                )

                if pod.status.phase != "Running":
                    return False

            except ApiException as e:
                self.error(f"Failed to read pod status for {info.pod_name}: {e.reason}")
                return False

        return True

    async def _get_failed_pods(self) -> list[str]:
        """Get list of pod names that have failed.

        Returns:
            List of failed pod names
        """
        failed = []
        for info in self.kubernetes_info:
            try:
                pod = self.core_v1.read_namespaced_pod_status(
                    name=info.pod_name, namespace=self.namespace
                )

                if pod.status.phase == "Failed":
                    failed.append(info.pod_name)

            except ApiException as e:
                self.error(f"Failed to read pod status for {info.pod_name}: {e.reason}")

        return failed

    async def retrieve_artifacts_from_records_manager(
        self, local_artifact_dir: Path
    ) -> None:
        """Retrieve artifact files from the Records Manager pod.

        This downloads the benchmark results (JSON, CSV, logs) from the
        Records Manager pod to the local filesystem.

        Args:
            local_artifact_dir: Local directory to save artifacts
        """
        # Find the Records Manager pod
        records_manager_pod = None
        for info in self.kubernetes_info:
            if info.service_type == ServiceType.RECORDS_MANAGER:
                records_manager_pod = info
                break

        if not records_manager_pod:
            self.warning("No Records Manager pod found - skipping artifact retrieval")
            return

        self.info(f"Retrieving artifacts from pod: {records_manager_pod.pod_name}")

        # Get the artifact directory path from config
        remote_artifact_dir = self.user_config.output.artifact_directory

        # Create local directory if it doesn't exist
        local_artifact_dir.mkdir(parents=True, exist_ok=True)

        # List of files to retrieve
        artifact_files = [
            "profile_export_aiperf.json",
            "profile_export_aiperf.csv",
            "inputs_aiperf.json",
            "logs/aiperf.log",
        ]

        for artifact_file in artifact_files:
            remote_path = f"{remote_artifact_dir}/{artifact_file}"
            local_path = local_artifact_dir / artifact_file

            try:
                # Use kubectl cp via subprocess for file copying
                # Format: kubectl cp <namespace>/<pod>:<remote_path> <local_path>
                import subprocess

                cmd = [
                    "kubectl",
                    "cp",
                    f"{self.namespace}/{records_manager_pod.pod_name}:{remote_path}",
                    str(local_path),
                ]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

                if result.returncode == 0:
                    self.debug(f"Retrieved artifact: {artifact_file}")
                else:
                    self.warning(f"Failed to retrieve {artifact_file}: {result.stderr}")

            except subprocess.TimeoutExpired:
                self.error(f"Timeout retrieving {artifact_file}")
            except Exception as e:
                self.error(f"Error retrieving {artifact_file}: {e}")

        self.info(f"Artifacts saved to: {local_artifact_dir}")
