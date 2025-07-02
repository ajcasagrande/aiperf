<!--
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
-->
# AIPerf3 - Complete Python Codebase Tree Structure

```
aiperf3/
├── aiperf/
│   ├── __init__.py
│   ├── cli.py
│   │
│   ├── artifacts/
│   │   ├── profile_export_aiperf.json
│   │   └── logs/
│   │
│   ├── backend/
│   │   └── (empty directory)
│   │
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── http/
│   │   │   ├── __init__.py
│   │   │   ├── aiohttp_client.py
│   │   │   └── defaults.py
│   │   └── openai/
│   │       ├── __init__.py
│   │       ├── common.py
│   │       └── openai_aiohttp.py
│   │
│   ├── common/
│   │   ├── __init__.py
│   │   ├── bootstrap.py
│   │   ├── constants.py
│   │   ├── dataset_models.py
│   │   ├── enums.py
│   │   ├── exceptions.py
│   │   ├── factories.py
│   │   ├── hooks.py
│   │   ├── interfaces.py
│   │   ├── logging.py
│   │   ├── messages.py
│   │   ├── progress_models.py
│   │   ├── progress_tracker.py
│   │   ├── record_models.py
│   │   ├── service_models.py
│   │   ├── tokenizer.py
│   │   ├── types.py
│   │   ├── utils.py
│   │   │
│   │   ├── comms/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   └── zmq/
│   │   │       ├── __init__.py
│   │   │       ├── zmq_comms.py
│   │   │       └── clients/
│   │   │           ├── __init__.py
│   │   │           ├── base.py
│   │   │           ├── base_zmq_proxy.py
│   │   │           ├── dealer_req.py
│   │   │           ├── dealer_router_proxy.py
│   │   │           ├── pub.py
│   │   │           ├── pull.py
│   │   │           ├── push.py
│   │   │           ├── push_pull_proxy.py
│   │   │           ├── router_rep.py
│   │   │           ├── sub.py
│   │   │           └── xpub_xsub_proxy.py
│   │   │
│   │   ├── config/
│   │   │   ├── __init__.py
│   │   │   ├── base_config.py
│   │   │   ├── config_defaults.py
│   │   │   ├── config_validators.py
│   │   │   ├── loader.py
│   │   │   ├── service_config.py
│   │   │   ├── user_config.py
│   │   │   ├── zmq_config.py
│   │   │   │
│   │   │   ├── endpoint/
│   │   │   │   └── (directories exist)
│   │   │   ├── input/
│   │   │   │   └── (directories exist)
│   │   │   ├── output/
│   │   │   │   └── (directories exist)
│   │   │   └── tokenizer/
│   │   │       ├── __init__.py
│   │   │       └── tokenizer_config.py
│   │   │
│   │   └── service/
│   │       ├── __init__.py
│   │       ├── base2.py
│   │       ├── base_component_service.py
│   │       ├── base_controller_service.py
│   │       ├── base_service.py
│   │       └── base_service_interface.py
│   │
│   ├── converters/
│   │   ├── __init__.py
│   │   ├── base_converter.py
│   │   ├── base_sse.py
│   │   ├── openai_chat_completions.py
│   │   └── openai_completions.py
│   │
│   ├── data_exporter/
│   │   ├── __init__.py
│   │   ├── console_error_exporter.py
│   │   ├── console_exporter.py
│   │   ├── exporter_config.py
│   │   ├── exporter_manager.py
│   │   ├── json_exporter.py
│   │   └── record.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   │
│   │   ├── dataset/
│   │   │   └── (directories exist)
│   │   │
│   │   ├── inference_result_parser/
│   │   │   └── (directories exist)
│   │   │
│   │   ├── records_manager/
│   │   │   └── (directories exist)
│   │   │
│   │   ├── service_manager/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── kubernetes.py
│   │   │   └── multiprocess.py
│   │   │
│   │   ├── system_controller/
│   │   │   └── (directories exist)
│   │   │
│   │   ├── timing_manager/
│   │   │   └── (directories exist)
│   │   │
│   │   └── worker/
│   │       ├── __init__.py
│   │       ├── universal.py
│   │       ├── worker.py
│   │       ├── worker_manager.py
│   │       └── dask/
│   │           └── (directories exist)
│   │
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── .coverage
│   │   ├── base_test_component_service.py
│   │   ├── base_test_controller_service.py
│   │   ├── base_test_service.py
│   │   ├── conftest.py
│   │   ├── test_aiperf_task.py
│   │   ├── test_benchmark_duration_metric.py
│   │   ├── test_dataset_utils.py
│   │   ├── test_hooks.py
│   │   ├── test_max_response_metric.py
│   │   ├── test_messages.py
│   │   ├── test_metric_summary.py
│   │   ├── test_min_request_metric.py
│   │   ├── test_prompt_generator.py
│   │   ├── test_records.py
│   │   ├── test_request_latency_metric.py
│   │   ├── test_tokenizer.py
│   │   ├── test_ttft_metric.py
│   │   ├── test_ttst_metric.py
│   │   ├── test_ui.py
│   │   │
│   │   ├── clients/
│   │   │   └── (directories exist)
│   │   ├── comms/
│   │   │   └── (directories exist)
│   │   ├── composers/
│   │   │   └── (directories exist)
│   │   ├── config/
│   │   │   └── (directories exist)
│   │   ├── data_exporters/
│   │   │   └── (directories exist)
│   │   ├── generators/
│   │   │   └── (directories exist)
│   │   ├── services/
│   │   │   └── (directories exist)
│   │   └── utils/
│   │       └── (directories exist)
│   │
│   └── ui/
│       ├── __init__.py
│       ├── aiperf_ui.py
│       ├── logs_mixin.py
│       └── rich_dashboard.py
│
├── integration-tests/
│   ├── mock_server/
│   │   ├── __init__.py
│   │   ├── app.py
│   │   ├── config.py
│   │   ├── main.py
│   │   ├── models.py
│   │   └── tokenizer_service.py
│   │
│   └── tests/
│       ├── test_integration_simple.py
│       └── test_server.py
│
└── tools/
    ├── add_copyright.py
    └── generate_api_md.py

SUMMARY:
--------
📁 Total Directories: ~50+ (including cache/build dirs)
🐍 Total Python Files: ~100+ files
📊 Main Packages:
   • aiperf/ - Core application package
   • integration-tests/ - Integration testing
   • tools/ - Utility scripts

🔧 Key Components:
   • CLI Interface: cli.py
   • HTTP & OpenAI Clients: clients/
   • Service Architecture: services/ & common/service/
   • ZMQ Communication: common/comms/zmq/
   • Data Export: data_exporter/
   • UI Dashboard: ui/
   • Testing Suite: tests/ & integration-tests/
   • Protocol Converters: converters/
   • Configuration Management: common/config/
```

## Key Architecture Highlights:

### 🏗️ **Service-Oriented Architecture**
- **Base Services**: `common/service/` contains abstract base classes
- **Worker Services**: `services/worker/` handles distributed processing
- **Service Management**: `services/service_manager/` orchestrates services

### 🔌 **Communication Layer**
- **ZMQ Integration**: Full ZeroMQ implementation in `common/comms/zmq/`
- **HTTP Clients**: `clients/http/` and `clients/openai/` for API communication
- **Protocol Converters**: `converters/` for different API formats

### 📊 **Data & Monitoring**
- **Progress Tracking**: `common/progress_*` files
- **Record Management**: `common/record_models.py`
- **Rich UI Dashboard**: `ui/rich_dashboard.py`
- **Data Export**: Multiple export formats in `data_exporter/`

### 🧪 **Testing Infrastructure**
- **Unit Tests**: Comprehensive test suite in `tests/`
- **Integration Tests**: End-to-end testing in `integration-tests/`
- **Mock Server**: Complete mock server for testing

### ⚙️ **Configuration System**
- **Hierarchical Config**: `common/config/` with validators and defaults
- **Service-Specific**: Tokenizer, endpoint, input/output configs
