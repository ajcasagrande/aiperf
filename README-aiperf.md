# AIPerf - AI Model Performance Benchmarking System

AIPerf is a comprehensive benchmarking system designed to measure and compare the performance of AI models across different providers and configurations. It provides a scalable, modular architecture for consistent and reproducible performance testing.

## Features

- **Component-Based Architecture**: Clean separation of concerns with well-defined components
- **Flexible Configuration**: Adapt to different benchmarking scenarios through YAML configuration
- **Robust Communication**: Real-time component communication using a pub/sub messaging system
- **Synthetic Data Generation**: Create test data on-the-fly for benchmarking
- **Comprehensive Metrics**: Track and analyze key performance indicators
- **Mock Testing Support**: Test with a mock OpenAI API server to avoid using API credits
- **Enhanced Components**: Fully-featured component implementations for all system parts

## System Components

AIPerf consists of the following key components:

1. **System Controller**: Central orchestration component that manages the entire system
2. **Dataset Manager**: Handles data for benchmarking, including synthetic generation
3. **Records Manager**: Stores and analyzes benchmark results
4. **Timing Manager**: Controls timing and scheduling of benchmark workloads
5. **Worker Manager**: Manages workers that interact with AI service providers

## Requirements

- Python 3.8 or higher
- Dependencies listed in `requirements.txt`

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/aiperf.git
   cd aiperf
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

### Quick Start with Mock Server

The easiest way to get started is to use the included `start_aiperf.sh` script, which sets up a mock OpenAI server for testing:

```bash
./start_aiperf.sh
```

This will:
1. Start a mock OpenAI API server on port 8000
2. Modify the configuration to use the mock server
3. Run AIPerf with the modified configuration for 60 seconds

### Configuration Options

You can customize the test run with various options:

```bash
./start_aiperf.sh -c config_file.yaml -d 120 -p 8000 -v
```

Options:
- `-c CONFIG_FILE`: Path to AIPerf config file
- `-p MOCK_PORT`: Port for mock OpenAI server
- `-d DURATION`: Duration in seconds to run benchmark
- `-m DELAY_MIN`: Minimum delay for mock responses
- `-M DELAY_MAX`: Maximum delay for mock responses
- `-e ERROR_RATE`: Error rate for mock responses
- `-v`: Enable verbose logging
- `-h`: Show help message

### Running with Real API Services

To run with real API services, edit the configuration file to include your API keys:

```yaml
workers:
  clients:
    - client_type: openai
      api_key: your_api_key
      parameters:
        model: gpt-3.5-turbo
```

Then run AIPerf:

```bash
python -m aiperf.run --config your_config.yaml
```

## Creating Custom Configurations

AIPerf uses YAML for configuration. Example configurations are provided in the `aiperf/config/examples` directory.

```yaml
profile_name: openai_benchmark
communication_type: memory

dataset:
  name: synthetic_dataset
  source_type: synthetic
  modality: text
  cache_dir: /tmp/aiperf/dataset_cache
  synthetic_params:
    seed: 42
    pre_generate: 10

records:
  storage_path: /tmp/aiperf/records
  auto_save: true
  save_interval: 5
  publish_events: true

timing:
  distribution: uniform
  params:
    min_interval: 0.5
    max_interval: 2.0
  credit_ttl: 10.0

workers:
  worker_count: 2
  clients:
    - client_type: openai
      api_key: your_api_key_here
      parameters:
        model: gpt-3.5-turbo
        temperature: 0.7
        max_tokens: 100
```

## Development

### Project Structure

```
aiperf/
├── common/          # Common utilities and base classes
├── config/          # Configuration handling
├── dataset/         # Dataset management
├── fixtures/        # Test fixtures and sample data
├── records/         # Record storage and analysis
├── system/          # System controller
├── timing/          # Timing and scheduling
├── workers/         # Worker management
└── run.py           # Main entry point
```

### Adding New Components

1. Create a new class that inherits from `BaseManager`
2. Implement required methods
3. Update `component_init.py` to include initialization for your component
4. Add appropriate configuration options in `config_models.py`

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest test_full_components.py
```

## License

[MIT License](LICENSE)

## Acknowledgments

AIPerf was developed to provide a standardized way to benchmark AI model performance across different providers and configurations. 