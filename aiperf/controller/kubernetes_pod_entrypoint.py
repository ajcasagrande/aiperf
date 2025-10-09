# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Kubernetes Pod Entrypoint

This module serves as the entry point for AIPerf service pods running in Kubernetes.
It reads configuration from environment variables and bootstraps the appropriate service.
"""

import json
import os
import sys

from aiperf.common.bootstrap import bootstrap_and_run_service
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.factories import ServiceFactory


def main() -> None:
    """Main entrypoint for Kubernetes pods.

    This function:
    1. Reads configuration from environment variables
    2. Determines which service to run
    3. Bootstraps and runs the service
    """
    # Get service type from environment
    service_type_str = os.environ.get("AIPERF_SERVICE_TYPE")
    if not service_type_str:
        print(
            "ERROR: AIPERF_SERVICE_TYPE environment variable not set", file=sys.stderr
        )
        sys.exit(1)

    # Get service ID from environment
    service_id = os.environ.get("AIPERF_SERVICE_ID")
    if not service_id:
        print("ERROR: AIPERF_SERVICE_ID environment variable not set", file=sys.stderr)
        sys.exit(1)

    # Get service config from environment
    service_config_json = os.environ.get("AIPERF_SERVICE_CONFIG")
    if not service_config_json:
        print(
            "ERROR: AIPERF_SERVICE_CONFIG environment variable not set", file=sys.stderr
        )
        sys.exit(1)

    # Get user config from environment
    user_config_json = os.environ.get("AIPERF_USER_CONFIG")
    if not user_config_json:
        print("ERROR: AIPERF_USER_CONFIG environment variable not set", file=sys.stderr)
        sys.exit(1)

    try:
        # Parse configurations
        service_config_dict = json.loads(service_config_json)
        user_config_dict = json.loads(user_config_json)

        service_config = ServiceConfig(**service_config_dict)
        user_config = UserConfig(**user_config_dict)

        print(f"Starting service: {service_type_str} with ID: {service_id}")

        # Load all modules to ensure service classes are registered
        from aiperf.module_loader import ensure_modules_loaded

        ensure_modules_loaded()

        # Special handling for System Controller in Kubernetes
        # System Controller needs to BIND to 0.0.0.0 (all interfaces)
        # Other services CONNECT to "aiperf-system-controller" (the Service DNS name)
        from aiperf.common.enums import ServiceType

        if service_type_str == str(ServiceType.SYSTEM_CONTROLLER):
            print("System Controller detected - configuring ZMQ to bind to 0.0.0.0")
            if service_config.zmq_tcp:
                # Override ALL proxy hosts to 0.0.0.0 so System Controller binds to all interfaces
                # The Kubernetes Service will route traffic from "aiperf-system-controller" to this pod
                service_config.zmq_tcp.host = "0.0.0.0"

                # Also override proxy configs
                if service_config.zmq_tcp.event_bus_proxy_config:
                    service_config.zmq_tcp.event_bus_proxy_config.host = "0.0.0.0"
                if service_config.zmq_tcp.dataset_manager_proxy_config:
                    service_config.zmq_tcp.dataset_manager_proxy_config.host = "0.0.0.0"
                if service_config.zmq_tcp.raw_inference_proxy_config:
                    service_config.zmq_tcp.raw_inference_proxy_config.host = "0.0.0.0"

                # Update the internal comm_config cache
                service_config._comm_config = service_config.zmq_tcp

                print(f"ZMQ configured to bind to: {service_config.zmq_tcp.host}")

        # Get the service class
        service_class = ServiceFactory.get_class_from_type(service_type_str)

        # Bootstrap and run the service
        bootstrap_and_run_service(
            service_class=service_class,
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
        )

    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse configuration JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to start service: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
