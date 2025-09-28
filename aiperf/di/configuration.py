# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Configuration system for dependency injection."""

import os
import yaml
import json
from pathlib import Path
from typing import Any, Dict, Optional, Type, Union
from dataclasses import dataclass, field

from pydantic import BaseModel, ValidationError
from dependency_injector import providers

from aiperf.common.aiperf_logger import AIPerfLogger

logger = AIPerfLogger(__name__)


@dataclass
class DIConfiguration:
    """Configuration for the dependency injection system."""

    # Plugin discovery settings
    auto_discovery: bool = True
    plugin_paths: list[str] = field(default_factory=list)
    strict_validation: bool = False

    # Container settings
    lazy_loading: bool = True
    cache_providers: bool = True
    enable_wiring: bool = True

    # Service-specific configurations
    services: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    clients: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    exporters: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    processors: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    ui: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Global settings
    log_level: str = "INFO"
    debug_mode: bool = False


class ConfigurationLoader:
    """Loads configuration from various sources."""

    def __init__(self):
        self.logger = AIPerfLogger(self.__class__.__name__)

    def load_from_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Load configuration from file (YAML or JSON)."""
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")

        try:
            with open(file_path, 'r') as f:
                if file_path.suffix.lower() in ['.yaml', '.yml']:
                    config = yaml.safe_load(f)
                elif file_path.suffix.lower() == '.json':
                    config = json.load(f)
                else:
                    raise ValueError(f"Unsupported configuration file format: {file_path.suffix}")

            self.logger.info(f"Loaded configuration from {file_path}")
            return config or {}

        except Exception as e:
            self.logger.error(f"Failed to load configuration from {file_path}: {e}")
            raise

    def load_from_env(self, prefix: str = "AIPERF_DI") -> Dict[str, Any]:
        """Load configuration from environment variables."""
        config = {}

        for key, value in os.environ.items():
            if key.startswith(prefix + "_"):
                # Convert AIPERF_DI_SERVICES_WORKER_COUNT to nested dict
                config_key = key[len(prefix) + 1:].lower()
                keys = config_key.split('_')

                # Convert string values to appropriate types
                parsed_value = self._parse_env_value(value)

                # Create nested dictionary structure
                current = config
                for k in keys[:-1]:
                    if k not in current:
                        current[k] = {}
                    current = current[k]
                current[keys[-1]] = parsed_value

        if config:
            self.logger.info(f"Loaded configuration from environment variables with prefix '{prefix}'")

        return config

    def _parse_env_value(self, value: str) -> Any:
        """Parse environment variable value to appropriate type."""
        # Try boolean
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'

        # Try integer
        try:
            return int(value)
        except ValueError:
            pass

        # Try float
        try:
            return float(value)
        except ValueError:
            pass

        # Try JSON
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            pass

        # Return as string
        return value

    def merge_configs(self, *configs: Dict[str, Any]) -> Dict[str, Any]:
        """Merge multiple configuration dictionaries."""
        merged = {}

        for config in configs:
            self._deep_merge(merged, config)

        return merged

    def _deep_merge(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """Deep merge source into target dictionary."""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value


class DIConfigurationModel(BaseModel):
    """Pydantic model for DI configuration validation."""

    auto_discovery: bool = True
    plugin_paths: list[str] = []
    strict_validation: bool = False
    lazy_loading: bool = True
    cache_providers: bool = True
    enable_wiring: bool = True
    log_level: str = "INFO"
    debug_mode: bool = False

    # Service configurations
    services: Dict[str, Dict[str, Any]] = {}
    clients: Dict[str, Dict[str, Any]] = {}
    exporters: Dict[str, Dict[str, Any]] = {}
    processors: Dict[str, Dict[str, Any]] = {}
    ui: Dict[str, Dict[str, Any]] = {}

    class Config:
        extra = "allow"  # Allow additional fields for extensibility


class ConfigurationManager:
    """Manages DI configuration from multiple sources."""

    def __init__(self):
        self.loader = ConfigurationLoader()
        self.logger = AIPerfLogger(self.__class__.__name__)
        self._config: Optional[DIConfigurationModel] = None

    def load_configuration(
        self,
        config_file: Optional[Union[str, Path]] = None,
        env_prefix: str = "AIPERF_DI",
        additional_config: Optional[Dict[str, Any]] = None
    ) -> DIConfigurationModel:
        """Load and merge configuration from all sources."""
        configs = []

        # Load from file if provided
        if config_file:
            try:
                file_config = self.loader.load_from_file(config_file)
                configs.append(file_config)
            except Exception as e:
                self.logger.warning(f"Could not load config file {config_file}: {e}")

        # Load from environment
        env_config = self.loader.load_from_env(env_prefix)
        if env_config:
            configs.append(env_config)

        # Add additional config
        if additional_config:
            configs.append(additional_config)

        # Merge all configurations
        if configs:
            merged_config = self.loader.merge_configs(*configs)
        else:
            merged_config = {}

        # Validate and create configuration model
        try:
            self._config = DIConfigurationModel(**merged_config)
            self.logger.info("Configuration loaded and validated successfully")
            return self._config
        except ValidationError as e:
            self.logger.error(f"Configuration validation failed: {e}")
            raise

    def get_config(self) -> DIConfigurationModel:
        """Get current configuration."""
        if self._config is None:
            # Load default configuration
            self._config = self.load_configuration()
        return self._config

    def get_service_config(self, service_name: str) -> Dict[str, Any]:
        """Get configuration for a specific service."""
        config = self.get_config()
        return config.services.get(service_name, {})

    def get_client_config(self, client_name: str) -> Dict[str, Any]:
        """Get configuration for a specific client."""
        config = self.get_config()
        return config.clients.get(client_name, {})

    def get_exporter_config(self, exporter_name: str) -> Dict[str, Any]:
        """Get configuration for a specific exporter."""
        config = self.get_config()
        return config.exporters.get(exporter_name, {})

    def update_config(self, updates: Dict[str, Any]) -> None:
        """Update configuration at runtime."""
        if self._config is None:
            self._config = self.load_configuration()

        # Create updated config
        current_dict = self._config.model_dump()
        self.loader._deep_merge(current_dict, updates)

        try:
            self._config = DIConfigurationModel(**current_dict)
            self.logger.info("Configuration updated successfully")
        except ValidationError as e:
            self.logger.error(f"Configuration update validation failed: {e}")
            raise


# Global configuration manager
config_manager = ConfigurationManager()


def get_di_config() -> DIConfigurationModel:
    """Get global DI configuration."""
    return config_manager.get_config()


def load_di_config(
    config_file: Optional[Union[str, Path]] = None,
    env_prefix: str = "AIPERF_DI",
    **additional_config: Any
) -> DIConfigurationModel:
    """Load DI configuration from sources."""
    return config_manager.load_configuration(
        config_file=config_file,
        env_prefix=env_prefix,
        additional_config=additional_config
    )


def create_configuration_provider(config_key: str) -> providers.Configuration:
    """Create a configuration provider for a specific key."""
    config = get_di_config()
    provider = providers.Configuration()

    # Get configuration section
    config_section = getattr(config, config_key, {})
    if isinstance(config_section, dict):
        provider.from_dict(config_section)
    else:
        provider.from_value(config_section)

    return provider


# Default configuration file locations to check
DEFAULT_CONFIG_PATHS = [
    "aiperf.yaml",
    "aiperf.yml",
    "config/aiperf.yaml",
    "config/aiperf.yml",
    os.path.expanduser("~/.aiperf/config.yaml"),
    "/etc/aiperf/config.yaml",
]


def auto_load_config() -> DIConfigurationModel:
    """Automatically load configuration from standard locations."""
    for config_path in DEFAULT_CONFIG_PATHS:
        if os.path.exists(config_path):
            logger.info(f"Auto-loading configuration from {config_path}")
            return load_di_config(config_file=config_path)

    # No config file found, load from environment only
    logger.info("No configuration file found, loading from environment variables")
    return load_di_config()
