import pytest
import os
import json
import yaml
from unittest.mock import patch, mock_open

from aiperf.config.config_loader import ConfigLoader
from aiperf.config.config_models import EndpointSelectionStrategy, AIperfConfig


class TestConfigLoader:
    """Tests for the ConfigLoader class."""
    
    @pytest.fixture
    def sample_config_dict(self):
        """Create a sample configuration dictionary."""
        return {
            "profile_name": "test-profile",
            "endpoints": [
                {
                    "name": "test-endpoint",
                    "url": "https://api.example.com/v1/completions",
                    "api_type": "openai",
                    "headers": {"Content-Type": "application/json"},
                    "timeout": 10.0
                }
            ],
            "dataset": {
                "source_type": "synthetic",
                "name": "test-dataset",
                "parameters": {"max_length": 100},
                "synthetic_params": {"seed": 42}
            },
            "timing": {
                "schedule_type": "fixed",
                "parameters": {"request_rate": 10.0},
                "duration": 60.0
            },
            "workers": {
                "min_workers": 2,
                "max_workers": 10,
                "worker_startup_timeout": 10.0
            },
            "metrics": {
                "enabled_metrics": ["latency", "tps", "tokens_per_second"],
                "output_format": "json",
                "output_path": "/tmp/aiperf-results.json"
            },
            "endpoint_selection": "ROUND_ROBIN",
            "log_level": "DEBUG",
            "debug_mode": True,
            "deterministic": True,
            "seed": 42
        }
    
    @pytest.mark.parametrize("file_ext,file_content,expected_format", [
        (".json", '{"profile_name": "test-json"}', "json"),
        (".yaml", 'profile_name: test-yaml', "yaml"),
        (".yml", 'profile_name: test-yaml', "yaml"),  # Changed from test-yml to test-yaml
    ])
    def test_load_from_file_formats(self, file_ext, file_content, expected_format, sample_config_dict):
        """Test loading configuration from different file formats."""
        # Arrange
        file_path = f"config{file_ext}"
        
        # Create a modified dict based on the format
        expected_config = sample_config_dict.copy()
        if expected_format == "json":
            expected_config["profile_name"] = "test-json"
        else:
            expected_config["profile_name"] = f"test-{expected_format}"
        
        # Mock file operations and load_from_dict
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=file_content)), \
             patch.object(ConfigLoader, "load_from_dict", return_value=AIperfConfig(**expected_config)):
            
            # Act
            config = ConfigLoader.load_from_file(file_path)
            
            # Assert
            assert config.profile_name == expected_config["profile_name"]
            # Verify that load_from_dict was called with the proper dictionary
            if expected_format == "json":
                assert ConfigLoader.load_from_dict.call_args[0][0] == {"profile_name": "test-json"}
            else:
                assert ConfigLoader.load_from_dict.call_args[0][0] == {"profile_name": f"test-{expected_format}"}

    def test_load_from_file_not_found(self):
        """Test loading configuration from a non-existent file."""
        # Arrange
        file_path = "non_existent_file.json"
        
        # Mock file operations
        with patch("os.path.exists", return_value=False):
            # Act / Assert
            with pytest.raises(FileNotFoundError, match=f"Configuration file not found: {file_path}"):
                ConfigLoader.load_from_file(file_path)

    @pytest.mark.parametrize("file_ext,mock_error", [
        (".json", json.JSONDecodeError("Expecting value", "", 0)),
        (".yaml", yaml.YAMLError("Invalid YAML")),
    ])
    def test_load_from_file_invalid_format(self, file_ext, mock_error):
        """Test loading configuration from files with invalid format."""
        # Arrange
        file_path = f"invalid_config{file_ext}"
        
        # Mock file operations and parsing errors
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", mock_open()):
            
            if file_ext == ".json":
                with patch("json.load", side_effect=mock_error):
                    # Act / Assert
                    with pytest.raises(ValueError, match="Invalid configuration file format"):
                        ConfigLoader.load_from_file(file_path)
            else:
                with patch("yaml.safe_load", side_effect=mock_error):
                    # Act / Assert
                    with pytest.raises(ValueError, match="Invalid configuration file format"):
                        ConfigLoader.load_from_file(file_path)

    def test_load_from_file_unsupported_format(self):
        """Test loading configuration from a file with unsupported format."""
        # Arrange
        file_path = "config.unsupported"
        
        # Mock file operations
        with patch("os.path.exists", return_value=True):
            # Act / Assert
            with pytest.raises(ValueError, match="Unsupported configuration file format"):
                ConfigLoader.load_from_file(file_path)

    def test_load_from_dict(self, sample_config_dict):
        """Test loading configuration from a dictionary."""
        # Act
        config = ConfigLoader.load_from_dict(sample_config_dict)
        
        # Assert
        assert config.profile_name == sample_config_dict["profile_name"]
        assert len(config.endpoints) == len(sample_config_dict["endpoints"])
        assert config.endpoints[0].name == sample_config_dict["endpoints"][0]["name"]
        assert config.endpoints[0].url == sample_config_dict["endpoints"][0]["url"]
        assert config.dataset.source_type == sample_config_dict["dataset"]["source_type"]
        assert config.timing.schedule_type == sample_config_dict["timing"]["schedule_type"]
        assert config.workers.min_workers == sample_config_dict["workers"]["min_workers"]
        assert config.metrics.enabled_metrics == sample_config_dict["metrics"]["enabled_metrics"]
        assert config.endpoint_selection == EndpointSelectionStrategy.ROUND_ROBIN
        assert config.log_level == sample_config_dict["log_level"]
        assert config.debug_mode == sample_config_dict["debug_mode"]
        assert config.deterministic == sample_config_dict["deterministic"]
        assert config.seed == sample_config_dict["seed"]

    def test_load_from_dict_minimal(self):
        """Test loading configuration from a minimal dictionary."""
        # Arrange
        minimal_config = {
            "profile_name": "minimal-profile",
            "endpoints": [
                {
                    "name": "test-endpoint",
                    "url": "https://api.example.com/v1",
                    "api_type": "openai"
                }
            ]
        }
        
        # Act
        config = ConfigLoader.load_from_dict(minimal_config)
        
        # Assert
        assert config.profile_name == minimal_config["profile_name"]
        assert config.endpoints[0].name == minimal_config["endpoints"][0]["name"]
        # Check default values
        assert config.dataset.source_type == "synthetic"
        assert config.timing.schedule_type == "fixed"
        assert config.workers.min_workers == 1
        assert config.metrics.output_format == "json"
        assert config.endpoint_selection == EndpointSelectionStrategy.ROUND_ROBIN
        assert config.log_level == "INFO"
        assert config.debug_mode is False
        assert config.deterministic is True

    def test_load_from_dict_invalid_config(self):
        """Test loading configuration from an invalid dictionary."""
        # Arrange
        invalid_config = {
            "profile_name": "invalid-profile",
            # Missing required endpoints
        }
        
        # Act / Assert
        with pytest.raises(ValueError, match="Invalid configuration"):
            ConfigLoader.load_from_dict(invalid_config)

    @pytest.mark.parametrize("selection_str,expected_strategy", [
        ("ROUND_ROBIN", EndpointSelectionStrategy.ROUND_ROBIN),
        ("RANDOM", EndpointSelectionStrategy.RANDOM),
        ("WEIGHTED", EndpointSelectionStrategy.WEIGHTED),
        ("round_robin", EndpointSelectionStrategy.ROUND_ROBIN),  # Case insensitive
        ("invalid", EndpointSelectionStrategy.ROUND_ROBIN),  # Default to ROUND_ROBIN for invalid
    ])
    def test_endpoint_selection_strategy(self, selection_str, expected_strategy, sample_config_dict):
        """Test parsing of endpoint selection strategy."""
        # Arrange
        config_dict = sample_config_dict.copy()
        config_dict["endpoint_selection"] = selection_str
        
        # Act
        config = ConfigLoader.load_from_dict(config_dict)
        
        # Assert
        assert config.endpoint_selection == expected_strategy 