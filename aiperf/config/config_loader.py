import os
import json
import yaml
import logging
from typing import Any, Dict, List, Optional, Union
from .config_models import AIperfConfig, EndpointConfig, DatasetConfig, TimingConfig, WorkerConfig, MetricsConfig, EndpointSelectionStrategy

logger = logging.getLogger(__name__)

class ConfigLoader:
    """Configuration loader for AIPerf."""
    
    @staticmethod
    def load_from_file(file_path: str) -> AIperfConfig:
        """Load configuration from a file.
        
        Args:
            file_path: Path to configuration file (json or yaml)
            
        Returns:
            AIperfConfig object
            
        Raises:
            FileNotFoundError: If file does not exist
            ValueError: If file format is not supported or is invalid
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
        
        _, ext = os.path.splitext(file_path)
        
        try:
            if ext.lower() == '.json':
                with open(file_path, 'r') as f:
                    config_dict = json.load(f)
            elif ext.lower() in ['.yaml', '.yml']:
                with open(file_path, 'r') as f:
                    config_dict = yaml.safe_load(f)
            else:
                raise ValueError(f"Unsupported configuration file format: {ext}")
                
            return ConfigLoader.load_from_dict(config_dict)
            
        except (json.JSONDecodeError, yaml.YAMLError) as e:
            raise ValueError(f"Invalid configuration file format: {e}")
    
    @staticmethod
    def load_from_dict(config_dict: Dict[str, Any]) -> AIperfConfig:
        """Load configuration from a dictionary.
        
        Args:
            config_dict: Configuration dictionary
            
        Returns:
            AIperfConfig object
            
        Raises:
            ValueError: If configuration is invalid
        """
        # Create endpoint configs
        endpoints = []
        for endpoint_dict in config_dict.get('endpoints', []):
            endpoints.append(EndpointConfig(
                name=endpoint_dict['name'],
                url=endpoint_dict['url'],
                api_type=endpoint_dict['api_type'],
                headers=endpoint_dict.get('headers', {}),
                auth=endpoint_dict.get('auth'),
                timeout=endpoint_dict.get('timeout', 30.0),
                weight=endpoint_dict.get('weight', 1.0),
                metadata=endpoint_dict.get('metadata', {})
            ))
        
        # Create dataset config
        dataset_dict = config_dict.get('dataset', {})
        dataset = DatasetConfig(
            source_type=dataset_dict.get('source_type', 'synthetic'),
            name=dataset_dict.get('name', 'default'),
            parameters=dataset_dict.get('parameters', {}),
            cache_dir=dataset_dict.get('cache_dir'),
            synthetic_params=dataset_dict.get('synthetic_params'),
            modality=dataset_dict.get('modality', 'text'),
            metadata=dataset_dict.get('metadata', {})
        )
        
        # Create timing config
        timing_dict = config_dict.get('timing', {})
        timing = TimingConfig(
            schedule_type=timing_dict.get('schedule_type', 'fixed'),
            parameters=timing_dict.get('parameters', {}),
            concurrency=timing_dict.get('concurrency'),
            request_rate=timing_dict.get('request_rate'),
            duration=timing_dict.get('duration'),
            start_delay=timing_dict.get('start_delay', 0.0),
            metadata=timing_dict.get('metadata', {})
        )
        
        # Create worker config
        worker_dict = config_dict.get('workers', {})
        workers = WorkerConfig(
            min_workers=worker_dict.get('min_workers', 1),
            max_workers=worker_dict.get('max_workers', 10),
            worker_startup_timeout=worker_dict.get('worker_startup_timeout', 30.0),
            worker_idle_timeout=worker_dict.get('worker_idle_timeout', 300.0),
            worker_keepalive_interval=worker_dict.get('worker_keepalive_interval', 10.0),
            metadata=worker_dict.get('metadata', {})
        )
        
        # Create metrics config
        metrics_dict = config_dict.get('metrics', {})
        metrics = MetricsConfig(
            enabled_metrics=metrics_dict.get('enabled_metrics', []),
            output_format=metrics_dict.get('output_format', 'json'),
            output_path=metrics_dict.get('output_path'),
            live_metrics=metrics_dict.get('live_metrics', True),
            server_metrics=metrics_dict.get('server_metrics', True),
            gpu_telemetry=metrics_dict.get('gpu_telemetry', True),
            metadata=metrics_dict.get('metadata', {})
        )
        
        # Parse endpoint selection strategy
        endpoint_selection_str = config_dict.get('endpoint_selection', 'ROUND_ROBIN')
        try:
            endpoint_selection = EndpointSelectionStrategy[endpoint_selection_str.upper()]
        except KeyError:
            logger.warning(f"Invalid endpoint selection strategy: {endpoint_selection_str}, using ROUND_ROBIN")
            endpoint_selection = EndpointSelectionStrategy.ROUND_ROBIN
        
        # Create main config
        config = AIperfConfig(
            profile_name=config_dict.get('profile_name', 'default'),
            endpoints=endpoints,
            dataset=dataset,
            timing=timing,
            workers=workers,
            metrics=metrics,
            endpoint_selection=endpoint_selection,
            log_level=config_dict.get('log_level', 'INFO'),
            debug_mode=config_dict.get('debug_mode', False),
            deterministic=config_dict.get('deterministic', True),
            seed=config_dict.get('seed'),
            metadata=config_dict.get('metadata', {})
        )
        
        # Validate the config
        errors = config.validate()
        if errors:
            raise ValueError(f"Invalid configuration: {', '.join(errors)}")
        
        return config 