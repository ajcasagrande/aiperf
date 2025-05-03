import os
import pytest
import asyncio
import json
import yaml
from unittest.mock import MagicMock, patch
from typing import Dict, Any, List, Optional

from aiperf.config.config_models import (
    AIperfConfig, 
    KubernetesConfig, 
    CommunicationConfig,
    EndpointConfig,
    DatasetConfig,
    TimingConfig,
    WorkerConfig,
    MetricsConfig,
    EndpointSelectionStrategy
)
from aiperf.common.models import TimingCredit, Conversation, ConversationTurn
from aiperf.common.communication import Communication

# -------------------- Config Fixtures --------------------

@pytest.fixture
def sample_endpoint_config() -> EndpointConfig:
    """Sample endpoint configuration for testing."""
    return EndpointConfig(
        name="test-endpoint",
        url="https://api.example.com/v1/completions",
        api_type="openai",
        headers={"Content-Type": "application/json"},
        timeout=10.0,
        weight=1.0
    )

@pytest.fixture
def sample_dataset_config() -> DatasetConfig:
    """Sample dataset configuration for testing."""
    return DatasetConfig(
        source_type="synthetic",
        name="test-dataset",
        parameters={"max_length": 100},
        synthetic_params={"seed": 42}
    )

@pytest.fixture
def sample_timing_config() -> TimingConfig:
    """Sample timing configuration for testing."""
    return TimingConfig(
        schedule_type="fixed",
        parameters={"request_rate": 10.0},
        duration=60.0,
        request_rate=10.0
    )

@pytest.fixture
def sample_worker_config() -> WorkerConfig:
    """Sample worker configuration for testing."""
    return WorkerConfig(
        min_workers=2,
        max_workers=10,
        worker_startup_timeout=10.0,
        worker_idle_timeout=30.0
    )

@pytest.fixture
def sample_metrics_config() -> MetricsConfig:
    """Sample metrics configuration for testing."""
    return MetricsConfig(
        enabled_metrics=["latency", "tps", "tokens_per_second"],
        output_format="json",
        output_path="/tmp/aiperf-results.json"
    )

@pytest.fixture
def sample_communication_config() -> CommunicationConfig:
    """Sample communication configuration for testing."""
    return CommunicationConfig(
        type="zmq",
        pub_address="tcp://*:5557",
        sub_address="tcp://*:5558",
        req_address="tcp://*:5559",
        rep_address="tcp://*:5560"
    )

@pytest.fixture
def sample_kubernetes_config() -> KubernetesConfig:
    """Sample Kubernetes configuration for testing."""
    return KubernetesConfig(
        enabled=True,
        namespace="aiperf-test",
        image="aiperf:test",
        resource_requests={"cpu": "100m", "memory": "128Mi"},
        resource_limits={"cpu": "500m", "memory": "512Mi"},
        persistent_volume_claim="test-pvc"
    )

@pytest.fixture
def sample_aiperf_config(
    sample_endpoint_config, 
    sample_dataset_config,
    sample_timing_config,
    sample_worker_config,
    sample_metrics_config,
    sample_communication_config,
    sample_kubernetes_config
) -> AIperfConfig:
    """Sample AIPerf configuration for testing."""
    return AIperfConfig(
        profile_name="test-profile",
        endpoints=[sample_endpoint_config],
        dataset=sample_dataset_config,
        timing=sample_timing_config,
        workers=sample_worker_config,
        metrics=sample_metrics_config,
        communication=sample_communication_config,
        kubernetes=sample_kubernetes_config,
        endpoint_selection=EndpointSelectionStrategy.ROUND_ROBIN,
        log_level="DEBUG",
        debug_mode=True,
        deterministic=True,
        seed=42
    )

@pytest.fixture
def sample_aiperf_config_no_k8s(
    sample_endpoint_config, 
    sample_dataset_config,
    sample_timing_config,
    sample_worker_config,
    sample_metrics_config,
    sample_communication_config
) -> AIperfConfig:
    """Sample AIPerf configuration without Kubernetes for testing."""
    k8s_config = KubernetesConfig(enabled=False)
    return AIperfConfig(
        profile_name="test-profile-no-k8s",
        endpoints=[sample_endpoint_config],
        dataset=sample_dataset_config,
        timing=sample_timing_config,
        workers=sample_worker_config,
        metrics=sample_metrics_config,
        communication=sample_communication_config,
        kubernetes=k8s_config,
        endpoint_selection=EndpointSelectionStrategy.ROUND_ROBIN,
        log_level="DEBUG",
        debug_mode=True,
        deterministic=True,
        seed=42
    )

@pytest.fixture
def sample_kubernetes_yaml() -> str:
    """Sample Kubernetes YAML configuration for testing."""
    return """
profile_name: k8s-test
endpoints:
  - name: test-endpoint
    url: https://api.example.com/v1/completions
    api_type: openai
    headers:
      Content-Type: application/json
    timeout: 10.0

dataset:
  source_type: synthetic
  name: test-dataset
  synthetic_params:
    seed: 42

timing:
  schedule_type: fixed
  parameters:
    request_rate: 10.0
  duration: 60.0

workers:
  min_workers: 5
  max_workers: 20
  worker_startup_timeout: 10.0

metrics:
  enabled_metrics:
    - latency
    - tps
  output_format: json
  output_path: /aiperf-data/results.json

communication:
  type: zmq
  pub_address: tcp://*:5557
  sub_address: tcp://*:5558
  req_address: tcp://*:5559
  rep_address: tcp://*:5560

kubernetes:
  enabled: true
  namespace: aiperf-test
  image: aiperf:test
  resource_requests:
    cpu: 200m
    memory: 256Mi
  resource_limits:
    cpu: 1
    memory: 1Gi
  persistent_volume_claim: test-pvc

endpoint_selection: ROUND_ROBIN
log_level: INFO
deterministic: true
seed: 42
"""

@pytest.fixture
def sample_config_file(sample_kubernetes_yaml, tmp_path):
    """Create a sample configuration file for testing."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(sample_kubernetes_yaml)
    return str(config_file)

# -------------------- Mock Fixtures --------------------

@pytest.fixture
def mock_kubernetes_client():
    """Mock Kubernetes client for testing."""
    mock_client = MagicMock()
    
    # Set up core API mocks
    core_api = MagicMock()
    mock_client.CoreV1Api.return_value = core_api
    
    # Set up apps API mocks
    apps_api = MagicMock()
    mock_client.AppsV1Api.return_value = apps_api
    
    # Set up batch API mocks
    batch_api = MagicMock()
    mock_client.BatchV1Api.return_value = batch_api
    
    # Mock successful namespace read
    core_api.read_namespace.return_value = MagicMock()
    
    # Mock successful deployment creation
    apps_api.create_namespaced_deployment.return_value = MagicMock()
    
    # Mock successful service creation
    core_api.create_namespaced_service.return_value = MagicMock()
    
    # Mock successful config map creation
    core_api.create_namespaced_config_map.return_value = MagicMock()
    
    # Create a mock for rest module with ApiException
    mock_rest = MagicMock()
    mock_api_exception = type('ApiException', (Exception,), {})
    mock_rest.ApiException = mock_api_exception
    mock_client.rest = mock_rest
    
    # Patch kubernetes.client and kubernetes.client.rest
    with patch.dict('sys.modules', {
        'kubernetes.client': mock_client,
        'kubernetes.client.rest': mock_rest,
    }):
        yield mock_client

@pytest.fixture
def mock_kubernetes_config():
    """Mock Kubernetes config for testing."""
    mock_config = MagicMock()
    
    # Set up config mocks
    mock_config.load_kube_config = MagicMock()
    mock_config.load_incluster_config = MagicMock(
        side_effect=Exception("Not in cluster")
    )
    
    # Create a mock for dynamic module
    mock_dynamic = MagicMock()
    mock_client_mod = MagicMock()
    mock_dynamic.client = mock_client_mod
    
    # Patch kubernetes.config and kubernetes.dynamic
    with patch.dict('sys.modules', {
        'kubernetes.config': mock_config,
        'kubernetes.dynamic': mock_dynamic,
        'kubernetes.dynamic.client': mock_client_mod,
    }):
        yield mock_config

@pytest.fixture
def mock_communication():
    """Mock Communication object for testing."""
    comm = MagicMock(spec=Communication)
    comm.initialize.return_value = asyncio.Future()
    comm.initialize.return_value.set_result(True)
    comm.publish.return_value = asyncio.Future()
    comm.publish.return_value.set_result(True)
    comm.request.return_value = asyncio.Future()
    comm.request.return_value.set_result({"status": "success"})
    comm.subscribe.return_value = asyncio.Future()
    comm.subscribe.return_value.set_result(True)
    return comm

@pytest.fixture
def mock_zmq_communication(mock_communication):
    """Mock ZMQ Communication object for testing."""
    with patch("aiperf.common.communication.ZMQCommunication", return_value=mock_communication):
        yield mock_communication

# -------------------- Models Fixtures --------------------

@pytest.fixture
def sample_conversation_turn() -> ConversationTurn:
    """Sample conversation turn for testing."""
    return ConversationTurn(
        turn_id="turn_123",
        request_data={"prompt": "Hello, how are you?"},
        response_data={"text": "I'm doing well, thank you!"},
        request_timestamp=1630000000.0,
        response_timestamp=1630000001.0,
        metadata={"tokens": 15}
    )

@pytest.fixture
def sample_conversation(sample_conversation_turn) -> Conversation:
    """Sample conversation for testing."""
    conversation = Conversation(
        conversation_id="conv_456",
        metadata={"user_id": "test_user"}
    )
    conversation.add_turn(sample_conversation_turn)
    return conversation

@pytest.fixture
def sample_timing_credit() -> TimingCredit:
    """Sample timing credit for testing."""
    return TimingCredit(
        credit_id="credit_789",
        target_timestamp=1630000010.0,
        credit_type="request",
        parameters={"priority": "high"},
        issued_timestamp=1630000000.0
    )

# -------------------- Event Loop Fixture --------------------

@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for each test session.
    
    Note: This is kept for backward compatibility. 
    Future tests should use the pytest-asyncio marker with loop_scope instead.
    """
    import warnings
    warnings.warn(
        "The custom event_loop fixture is deprecated. "
        "Use @pytest.mark.asyncio(loop_scope='session') instead.",
        DeprecationWarning,
        stacklevel=2
    )
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close() 