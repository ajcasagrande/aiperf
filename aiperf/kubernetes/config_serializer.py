# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Configuration serialization for Kubernetes deployments."""

import json
from typing import Any

from aiperf.common.config import ServiceConfig, UserConfig


class ConfigSerializer:
    """Serializes AIPerf configuration for transfer to Kubernetes pods."""

    @staticmethod
    def serialize_to_configmap(
        user_config: UserConfig, service_config: ServiceConfig
    ) -> dict[str, str]:
        """Serialize configs to ConfigMap data format (str -> str mapping).

        Excludes zmq_tcp and zmq_ipc as these will be created fresh in each pod
        based on the service type and Kubernetes environment.
        """
        return {
            "user_config.json": json.dumps(
                user_config.model_dump(mode="json", exclude_defaults=True)
            ),
            "service_config.json": json.dumps(
                service_config.model_dump(
                    mode="json",
                    exclude_defaults=True,
                    exclude={"zmq_tcp", "zmq_ipc"},  # Create these fresh in each pod
                )
            ),
        }

    @staticmethod
    def deserialize_from_configmap(
        config_data: dict[str, str]
    ) -> tuple[UserConfig, ServiceConfig]:
        """Deserialize configs from ConfigMap data."""
        user_config_dict = json.loads(config_data["user_config.json"])
        service_config_dict = json.loads(config_data["service_config.json"])

        user_config = UserConfig(**user_config_dict)
        service_config = ServiceConfig(**service_config_dict)

        return user_config, service_config

    @staticmethod
    def serialize_to_env_vars(config: dict[str, Any]) -> list[dict[str, str]]:
        """Convert config dict to Kubernetes env var format."""
        env_vars = []
        for key, value in config.items():
            if isinstance(value, (str, int, float, bool)):
                env_vars.append({"name": f"AIPERF_{key.upper()}", "value": str(value)})
        return env_vars
