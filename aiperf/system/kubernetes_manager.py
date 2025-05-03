import asyncio
import base64
import json
import logging
import os
import tempfile
import uuid
import yaml
from typing import Any, Dict, List, Optional, Set, Tuple

from ..config.config_models import AIperfConfig, KubernetesConfig

class KubernetesManager:
    """Manager for Kubernetes deployments of AIPerf.
    
    Responsible for creating, deploying, and managing AIPerf components in Kubernetes.
    """
    
    def __init__(self, config: AIperfConfig):
        """Initialize the Kubernetes manager.
        
        Args:
            config: AIPerf configuration
        """
        self.config = config
        self.kubernetes_config = config.kubernetes
        self.logger = logging.getLogger(f"kubernetes_manager_{uuid.uuid4().hex[:8]}")
        self._manifests: Dict[str, Dict[str, Any]] = {}
        
        # Ensure kubernetes package is installed
        try:
            from kubernetes import client, config as k8s_config
            # Ensure dynamic module and ApiException are available
            try:
                from kubernetes.client.rest import ApiException
            except ImportError:
                # Create a dummy ApiException if the import fails
                class ApiException(Exception):
                    pass
                # Add it to the client module
                client.rest = type('rest', (), {'ApiException': ApiException})
                
            self.k8s_client = client
            self.k8s_config = k8s_config
            self._init_kubernetes_client()
        except ImportError:
            self.logger.error("Kubernetes Python client not installed. Please install with: pip install kubernetes")
            raise
    
    def _init_kubernetes_client(self) -> None:
        """Initialize Kubernetes client."""
        try:
            # Try to load in-cluster config first
            self.k8s_config.load_incluster_config()
            self.logger.info("Using in-cluster Kubernetes configuration")
        except Exception:
            # Fall back to kubeconfig
            self.k8s_config.load_kube_config()
            self.logger.info("Using kubeconfig for Kubernetes configuration")
            
        # Create API clients
        self.core_api = self.k8s_client.CoreV1Api()
        self.apps_api = self.k8s_client.AppsV1Api()
        self.batch_api = self.k8s_client.BatchV1Api()
        
    async def apply_resources(self, dry_run: bool = False) -> bool:
        """Apply Kubernetes resources for AIPerf deployment.
        
        Args:
            dry_run: If True, only validate and print resources without applying
            
        Returns:
            True if resources were applied successfully, False otherwise
        """
        try:
            # Generate manifests
            await self._generate_manifests()
            
            if dry_run:
                self.logger.info("Dry run enabled, resources will not be applied")
                self._print_manifests()
                return True
                
            # Create namespace if it doesn't exist
            await self._ensure_namespace()
            
            # Apply ConfigMap if enabled
            if self.kubernetes_config.use_config_map:
                await self._apply_config_map()
                
            # Apply PVC if specified
            if self.kubernetes_config.persistent_volume_claim:
                await self._ensure_pvc()
                
            # Apply controller deployment
            await self._apply_controller_deployment()
            
            # Apply worker deployment
            await self._apply_worker_deployment()
            
            # Apply services
            await self._apply_services()
            
            self.logger.info(f"AIPerf resources applied to namespace {self.kubernetes_config.namespace}")
            return True
        except Exception as e:
            self.logger.error(f"Error applying Kubernetes resources: {e}")
            return False
            
    async def delete_resources(self) -> bool:
        """Delete AIPerf Kubernetes resources.
        
        Returns:
            True if resources were deleted successfully, False otherwise
        """
        try:
            namespace = self.kubernetes_config.namespace
            
            # Delete deployments
            try:
                self.apps_api.delete_namespaced_deployment("aiperf-controller", namespace)
                self.logger.info("Deleted controller deployment")
            except Exception as e:
                self.logger.warning(f"Error deleting controller deployment: {e}")
                
            try:
                self.apps_api.delete_namespaced_deployment("aiperf-workers", namespace)
                self.logger.info("Deleted workers deployment")
            except Exception as e:
                self.logger.warning(f"Error deleting workers deployment: {e}")
                
            # Delete services
            for service_name in ["aiperf-controller", "aiperf-workers"]:
                try:
                    self.core_api.delete_namespaced_service(service_name, namespace)
                    self.logger.info(f"Deleted service {service_name}")
                except Exception as e:
                    self.logger.warning(f"Error deleting service {service_name}: {e}")
                    
            # Delete ConfigMap
            if self.kubernetes_config.use_config_map:
                try:
                    self.core_api.delete_namespaced_config_map("aiperf-config", namespace)
                    self.logger.info("Deleted ConfigMap")
                except Exception as e:
                    self.logger.warning(f"Error deleting ConfigMap: {e}")
                    
            # Don't delete PVC by default to preserve data
            # User should delete manually if needed
            
            self.logger.info(f"AIPerf resources deleted from namespace {namespace}")
            return True
        except Exception as e:
            self.logger.error(f"Error deleting Kubernetes resources: {e}")
            return False
            
    async def get_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of AIPerf Kubernetes resources.
        
        Returns:
            Dictionary with status information for each component
        """
        try:
            namespace = self.kubernetes_config.namespace
            status = {}
            
            # Check deployments
            try:
                controller_deployment = self.apps_api.read_namespaced_deployment("aiperf-controller", namespace)
                status["controller"] = {
                    "ready": controller_deployment.status.ready_replicas or 0,
                    "total": controller_deployment.status.replicas or 0,
                    "available": controller_deployment.status.available_replicas or 0,
                    "conditions": [
                        {"type": c.type, "status": c.status, "reason": c.reason}
                        for c in controller_deployment.status.conditions or []
                    ]
                }
            except Exception as e:
                status["controller"] = {"error": str(e)}
                
            try:
                workers_deployment = self.apps_api.read_namespaced_deployment("aiperf-workers", namespace)
                status["workers"] = {
                    "ready": workers_deployment.status.ready_replicas or 0,
                    "total": workers_deployment.status.replicas or 0,
                    "available": workers_deployment.status.available_replicas or 0,
                    "conditions": [
                        {"type": c.type, "status": c.status, "reason": c.reason}
                        for c in workers_deployment.status.conditions or []
                    ]
                }
            except Exception as e:
                status["workers"] = {"error": str(e)}
                
            # Check pods
            try:
                pods = self.core_api.list_namespaced_pod(
                    namespace, label_selector="app.kubernetes.io/part-of=aiperf"
                )
                status["pods"] = []
                for pod in pods.items:
                    pod_status = {
                        "name": pod.metadata.name,
                        "phase": pod.status.phase,
                        "start_time": pod.status.start_time.isoformat() if pod.status.start_time else None,
                        "conditions": [
                            {"type": c.type, "status": c.status}
                            for c in pod.status.conditions or []
                        ],
                        "containers": [
                            {
                                "name": cs.name,
                                "ready": cs.ready,
                                "restart_count": cs.restart_count,
                                "state": 
                                    "running" if cs.state.running else
                                    "waiting" if cs.state.waiting else
                                    "terminated" if cs.state.terminated else
                                    "unknown"
                            }
                            for cs in pod.status.container_statuses or []
                        ]
                    }
                    status["pods"].append(pod_status)
            except Exception as e:
                status["pods"] = {"error": str(e)}
                
            # Check services
            try:
                services = self.core_api.list_namespaced_service(
                    namespace, label_selector="app.kubernetes.io/part-of=aiperf"
                )
                status["services"] = []
                for service in services.items:
                    service_status = {
                        "name": service.metadata.name,
                        "type": service.spec.type,
                        "cluster_ip": service.spec.cluster_ip,
                        "ports": [
                            {"name": p.name, "port": p.port, "target_port": p.target_port}
                            for p in service.spec.ports or []
                        ]
                    }
                    status["services"].append(service_status)
            except Exception as e:
                status["services"] = {"error": str(e)}
                
            return status
        except Exception as e:
            self.logger.error(f"Error getting Kubernetes status: {e}")
            return {"error": str(e)}
    
    async def scale_workers(self, replicas: int) -> bool:
        """Scale worker deployment.
        
        Args:
            replicas: Number of worker replicas
            
        Returns:
            True if scaling was successful, False otherwise
        """
        try:
            namespace = self.kubernetes_config.namespace
            
            # Update deployment
            self.apps_api.patch_namespaced_deployment(
                "aiperf-workers",
                namespace,
                {"spec": {"replicas": replicas}}
            )
            
            self.logger.info(f"Scaled workers to {replicas} replicas")
            return True
        except Exception as e:
            self.logger.error(f"Error scaling workers: {e}")
            return False
    
    async def _generate_manifests(self) -> None:
        """Generate Kubernetes manifests."""
        # Generate ConfigMap
        if self.kubernetes_config.use_config_map:
            self._manifests["configmap"] = self._generate_config_map()
            
        # Generate controller deployment
        self._manifests["controller_deployment"] = self._generate_controller_deployment()
        
        # Generate worker deployment
        self._manifests["worker_deployment"] = self._generate_worker_deployment()
        
        # Generate services
        self._manifests["controller_service"] = self._generate_controller_service()
        self._manifests["worker_service"] = self._generate_worker_service()
        
    def _print_manifests(self) -> None:
        """Print manifests for debugging."""
        for name, manifest in self._manifests.items():
            self.logger.info(f"=== {name} ===")
            self.logger.info(yaml.dump(manifest))
            self.logger.info("")
            
    async def _ensure_namespace(self) -> None:
        """Ensure namespace exists."""
        try:
            namespace = self.kubernetes_config.namespace
            self.core_api.read_namespace(namespace)
            self.logger.info(f"Namespace {namespace} already exists")
        except Exception:
            # Create namespace
            body = {
                "apiVersion": "v1",
                "kind": "Namespace",
                "metadata": {
                    "name": namespace,
                    "labels": {
                        "app.kubernetes.io/part-of": "aiperf"
                    }
                }
            }
            self.core_api.create_namespace(body)
            self.logger.info(f"Created namespace {namespace}")
            
    async def _apply_config_map(self) -> None:
        """Apply ConfigMap with configuration."""
        try:
            namespace = self.kubernetes_config.namespace
            config_map = self._generate_config_map()
            
            try:
                # Try to update existing ConfigMap
                self.core_api.replace_namespaced_config_map("aiperf-config", namespace, config_map)
                self.logger.info("Updated ConfigMap")
            except Exception:
                # Create new ConfigMap
                self.core_api.create_namespaced_config_map(namespace, config_map)
                self.logger.info("Created ConfigMap")
        except Exception as e:
            self.logger.error(f"Error applying ConfigMap: {e}")
            raise
            
    async def _ensure_pvc(self) -> None:
        """Ensure PVC exists."""
        if not self.kubernetes_config.persistent_volume_claim:
            return
            
        try:
            namespace = self.kubernetes_config.namespace
            pvc_name = self.kubernetes_config.persistent_volume_claim
            
            try:
                # Check if PVC exists
                self.core_api.read_namespaced_persistent_volume_claim(pvc_name, namespace)
                self.logger.info(f"PVC {pvc_name} already exists")
            except Exception:
                # PVC doesn't exist, create it
                self.logger.warning(f"PVC {pvc_name} specified but doesn't exist. Make sure it's created externally.")
        except Exception as e:
            self.logger.error(f"Error ensuring PVC: {e}")
            
    async def _apply_controller_deployment(self) -> None:
        """Apply controller deployment."""
        try:
            namespace = self.kubernetes_config.namespace
            deployment = self._generate_controller_deployment()
            
            try:
                # Try to update existing deployment
                self.apps_api.replace_namespaced_deployment("aiperf-controller", namespace, deployment)
                self.logger.info("Updated controller deployment")
            except Exception:
                # Create new deployment
                self.apps_api.create_namespaced_deployment(namespace, deployment)
                self.logger.info("Created controller deployment")
        except Exception as e:
            self.logger.error(f"Error applying controller deployment: {e}")
            raise
            
    async def _apply_worker_deployment(self) -> None:
        """Apply worker deployment."""
        try:
            namespace = self.kubernetes_config.namespace
            deployment = self._generate_worker_deployment()
            
            try:
                # Try to update existing deployment
                self.apps_api.replace_namespaced_deployment("aiperf-workers", namespace, deployment)
                self.logger.info("Updated workers deployment")
            except Exception:
                # Create new deployment
                self.apps_api.create_namespaced_deployment(namespace, deployment)
                self.logger.info("Created workers deployment")
        except Exception as e:
            self.logger.error(f"Error applying worker deployment: {e}")
            raise
            
    async def _apply_services(self) -> None:
        """Apply services."""
        try:
            namespace = self.kubernetes_config.namespace
            
            # Controller service
            controller_service = self._generate_controller_service()
            try:
                # Try to update existing service
                self.core_api.replace_namespaced_service("aiperf-controller", namespace, controller_service)
                self.logger.info("Updated controller service")
            except Exception:
                # Create new service
                self.core_api.create_namespaced_service(namespace, controller_service)
                self.logger.info("Created controller service")
                
            # Worker service
            worker_service = self._generate_worker_service()
            try:
                # Try to update existing service
                self.core_api.replace_namespaced_service("aiperf-workers", namespace, worker_service)
                self.logger.info("Updated workers service")
            except Exception:
                # Create new service
                self.core_api.create_namespaced_service(namespace, worker_service)
                self.logger.info("Created workers service")
        except Exception as e:
            self.logger.error(f"Error applying services: {e}")
            raise
    
    def _generate_config_map(self) -> Dict[str, Any]:
        """Generate ConfigMap manifest.
        
        Returns:
            ConfigMap manifest
        """
        # Convert config to dict excluding sensitive data
        config_dict = {
            "profile_name": self.config.profile_name,
            "endpoints": [
                {
                    "name": ep.name,
                    "url": ep.url,
                    "api_type": ep.api_type,
                    "timeout": ep.timeout,
                    "weight": ep.weight,
                    "metadata": ep.metadata
                }
                for ep in self.config.endpoints
            ],
            "dataset": self.config.dataset.__dict__,
            "timing": self.config.timing.__dict__,
            "workers": self.config.workers.__dict__,
            "metrics": self.config.metrics.__dict__,
            "communication": {
                "type": "zmq",
                "pub_address": "tcp://aiperf-controller:5557",
                "sub_address": "tcp://aiperf-controller:5558",
                "req_address": "tcp://aiperf-controller:5559",
                "rep_address": "tcp://aiperf-controller:5560",
                "parameters": self.config.communication.parameters,
                "metadata": self.config.communication.metadata
            },
            "endpoint_selection": self.config.endpoint_selection.name,
            "log_level": self.config.log_level,
            "debug_mode": self.config.debug_mode,
            "deterministic": self.config.deterministic,
            "seed": self.config.seed,
            "metadata": self.config.metadata
        }
        
        return {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": "aiperf-config",
                "namespace": self.kubernetes_config.namespace,
                "labels": {
                    "app.kubernetes.io/name": "aiperf-config",
                    "app.kubernetes.io/part-of": "aiperf",
                    "app.kubernetes.io/managed-by": "aiperf-kubernetes-manager"
                }
            },
            "data": {
                "config.json": json.dumps(config_dict, indent=2),
                "profile_name": self.config.profile_name
            }
        }
    
    def _generate_controller_deployment(self) -> Dict[str, Any]:
        """Generate controller deployment manifest.
        
        Returns:
            Controller deployment manifest
        """
        # Use controller image if specified, otherwise use default image
        image = self.kubernetes_config.controller_image or self.kubernetes_config.image
        
        # Base command
        command = [
            "python", "-m", "aiperf.cli.aiperf_cli", "run", 
            "/aiperf-config/config.json", "--log-level", self.config.log_level
        ]
        
        # Volume mounts
        volume_mounts = [
            {
                "name": "config-volume",
                "mountPath": "/aiperf-config"
            }
        ]
        
        # Add PVC if specified
        volumes = [
            {
                "name": "config-volume",
                "configMap": {
                    "name": "aiperf-config"
                }
            }
        ]
        
        if self.kubernetes_config.persistent_volume_claim:
            volume_mounts.append({
                "name": "data-volume",
                "mountPath": "/aiperf-data"
            })
            
            volumes.append({
                "name": "data-volume",
                "persistentVolumeClaim": {
                    "claimName": self.kubernetes_config.persistent_volume_claim
                }
            })
            
        # Labels
        labels = {
            "app.kubernetes.io/name": "aiperf-controller",
            "app.kubernetes.io/part-of": "aiperf",
            "app.kubernetes.io/managed-by": "aiperf-kubernetes-manager",
            "app.kubernetes.io/component": "controller"
        }
        
        # Add custom labels
        if self.kubernetes_config.labels:
            labels.update(self.kubernetes_config.labels)
            
        return {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": "aiperf-controller",
                "namespace": self.kubernetes_config.namespace,
                "labels": labels
            },
            "spec": {
                "replicas": 1,  # Controller should always be a singleton
                "selector": {
                    "matchLabels": {
                        "app.kubernetes.io/name": "aiperf-controller"
                    }
                },
                "template": {
                    "metadata": {
                        "labels": labels,
                        "annotations": self.kubernetes_config.annotations or {}
                    },
                    "spec": {
                        "serviceAccountName": self.kubernetes_config.service_account or "default",
                        "containers": [
                            {
                                "name": "controller",
                                "image": image,
                                "imagePullPolicy": self.kubernetes_config.pull_policy,
                                "command": command,
                                "ports": [
                                    {"containerPort": 5557, "name": "pub"},
                                    {"containerPort": 5558, "name": "sub"},
                                    {"containerPort": 5559, "name": "req"},
                                    {"containerPort": 5560, "name": "rep"}
                                ],
                                "resources": {
                                    "requests": self.kubernetes_config.resource_requests,
                                    "limits": self.kubernetes_config.resource_limits
                                },
                                "volumeMounts": volume_mounts,
                                "env": [
                                    {"name": "PYTHONUNBUFFERED", "value": "1"}
                                ]
                            }
                        ],
                        "volumes": volumes,
                        "nodeSelector": self.kubernetes_config.node_selector or {},
                        "tolerations": self.kubernetes_config.tolerations or []
                    }
                }
            }
        }
    
    def _generate_worker_deployment(self) -> Dict[str, Any]:
        """Generate worker deployment manifest.
        
        Returns:
            Worker deployment manifest
        """
        # Use worker image if specified, otherwise use default image
        image = self.kubernetes_config.worker_image or self.kubernetes_config.image
        
        # Base command for worker (needs to connect to controller)
        command = [
            "python", "-m", "aiperf.cli.worker_cli", "run",
            "--controller", "aiperf-controller",
            "--log-level", self.config.log_level
        ]
        
        # Volume mounts
        volume_mounts = []
        
        # Add PVC if specified
        volumes = []
        
        if self.kubernetes_config.persistent_volume_claim:
            volume_mounts.append({
                "name": "data-volume",
                "mountPath": "/aiperf-data"
            })
            
            volumes.append({
                "name": "data-volume",
                "persistentVolumeClaim": {
                    "claimName": self.kubernetes_config.persistent_volume_claim
                }
            })
            
        # Labels
        labels = {
            "app.kubernetes.io/name": "aiperf-workers",
            "app.kubernetes.io/part-of": "aiperf",
            "app.kubernetes.io/managed-by": "aiperf-kubernetes-manager",
            "app.kubernetes.io/component": "worker"
        }
        
        # Add custom labels
        if self.kubernetes_config.labels:
            labels.update(self.kubernetes_config.labels)
            
        # Determine number of replicas
        replicas = self.config.workers.min_workers
        
        return {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": "aiperf-workers",
                "namespace": self.kubernetes_config.namespace,
                "labels": labels
            },
            "spec": {
                "replicas": replicas,
                "selector": {
                    "matchLabels": {
                        "app.kubernetes.io/name": "aiperf-workers"
                    }
                },
                "template": {
                    "metadata": {
                        "labels": labels,
                        "annotations": self.kubernetes_config.annotations or {}
                    },
                    "spec": {
                        "serviceAccountName": self.kubernetes_config.service_account or "default",
                        "containers": [
                            {
                                "name": "worker",
                                "image": image,
                                "imagePullPolicy": self.kubernetes_config.pull_policy,
                                "command": command,
                                "resources": {
                                    "requests": self.kubernetes_config.resource_requests,
                                    "limits": self.kubernetes_config.resource_limits
                                },
                                "volumeMounts": volume_mounts,
                                "env": [
                                    {"name": "PYTHONUNBUFFERED", "value": "1"}
                                ]
                            }
                        ],
                        "volumes": volumes,
                        "nodeSelector": self.kubernetes_config.node_selector or {},
                        "tolerations": self.kubernetes_config.tolerations or []
                    }
                }
            }
        }
    
    def _generate_controller_service(self) -> Dict[str, Any]:
        """Generate controller service manifest.
        
        Returns:
            Controller service manifest
        """
        return {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": "aiperf-controller",
                "namespace": self.kubernetes_config.namespace,
                "labels": {
                    "app.kubernetes.io/name": "aiperf-controller",
                    "app.kubernetes.io/part-of": "aiperf",
                    "app.kubernetes.io/managed-by": "aiperf-kubernetes-manager"
                }
            },
            "spec": {
                "selector": {
                    "app.kubernetes.io/name": "aiperf-controller"
                },
                "ports": [
                    {"port": 5557, "targetPort": 5557, "name": "pub"},
                    {"port": 5558, "targetPort": 5558, "name": "sub"},
                    {"port": 5559, "targetPort": 5559, "name": "req"},
                    {"port": 5560, "targetPort": 5560, "name": "rep"}
                ]
            }
        }
    
    def _generate_worker_service(self) -> Dict[str, Any]:
        """Generate worker service manifest.
        
        Returns:
            Worker service manifest
        """
        return {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": "aiperf-workers",
                "namespace": self.kubernetes_config.namespace,
                "labels": {
                    "app.kubernetes.io/name": "aiperf-workers",
                    "app.kubernetes.io/part-of": "aiperf",
                    "app.kubernetes.io/managed-by": "aiperf-kubernetes-manager"
                }
            },
            "spec": {
                "selector": {
                    "app.kubernetes.io/name": "aiperf-workers"
                },
                "ports": [
                    {"port": 8080, "targetPort": 8080, "name": "http"}
                ]
            }
        } 