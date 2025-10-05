# AIPerf Plugin Wizard - AIP-001 Compliant

## Overview

The AIPerf Plugin Wizard creates complete plugin packages following the official **AIP-001 Plugin Architecture** specification. It generates production-ready plugin packages with entry points, dependency injection support, tests, and documentation.

## Features

### Follows AIP-001 Specification

- **Entry Point Based Discovery** - Uses `importlib.metadata.entry_points()`
- **Lazy Loading** - Plugins loaded only when needed
- **Type-Safe Contracts** - Full type hints and protocols
- **Dependency Injection** - Compatible with dependency-injector
- **Zero Boilerplate** - Automatic registration via entry points

### Supported Plugin Types

According to AIP-001, these entry point groups are supported:

| Entry Point Group | Purpose | Example |
|-------------------|---------|---------|
| `aiperf.endpoint` | API format handlers | NVIDIA NIM, OpenAI, Custom APIs |
| `aiperf.transport` | Communication protocols | HTTP, gRPC, WebSocket |
| `aiperf.data_exporter` | Export formats | CSV, JSON, Parquet, Prometheus |
| `aiperf.processor` | Data processors | Custom post-processing |
| `aiperf.metric` | Performance metrics | Custom latency, throughput |
| `aiperf.collector` | Data collection | Prometheus, OpenTelemetry |

## Usage

### Interactive CLI Wizard

```bash
cd /home/anthony/nvidia/projects/aiperf
python tools/plugin_wizard.py
```

Follow the prompts to create your plugin.

### What Gets Generated

Complete plugin package structure:

```
my-aiperf-plugin/
├── pyproject.toml              # With entry points configuration
├── src/
│   └── my_plugin/
│       ├── __init__.py
│       └── my_plugin.py        # Main plugin implementation
├── tests/
│   ├── __init__.py
│   └── test_my_plugin.py       # Test suite
├── .github/
│   └── workflows/
│       └── test.yml            # CI/CD automation
├── .pre-commit-config.yaml     # Code quality hooks
├── README.md                   # Complete documentation
└── LICENSE                     # Apache 2.0
```

## Plugin Discovery (AIP-001)

### How AIPerf Discovers Plugins

1. **Entry Points in pyproject.toml**:
```toml
[project.entry-points."aiperf.metric"]
my_metric = "my_plugin.my_metric:MyMetric"
```

2. **AIPerf Discovery Code**:
```python
from importlib.metadata import entry_points

# Discover all metric plugins
discovered_eps = entry_points(group='aiperf.metric')
for ep in discovered_eps:
    plugin_class = ep.load()  # Lazy load
    # Use plugin...
```

3. **Automatic Registration**:
- No manual registration code needed
- Plugins discovered automatically on AIPerf startup
- Works for both installed packages and editable installs

## Development Workflow

### Step 1: Create Plugin

```bash
python tools/plugin_wizard.py
```

Answer the prompts:
- Select plugin type (Metric, Endpoint, etc.)
- Provide plugin name and description
- Configure plugin-specific settings
- Generate complete package

### Step 2: Implement Plugin

Edit the generated `src/your_plugin/your_plugin.py`:

```python
def _parse_record(self, record, record_metrics):
    # Your implementation here
    return computed_value
```

### Step 3: Test Plugin

```bash
cd your-plugin-package
pip install -e ".[dev]"
pytest
```

### Step 4: Use with AIPerf

```bash
# Plugin is automatically discovered
aiperf profile --model gpt2 --url localhost:8000

# Your metric will appear in results automatically
```

### Step 5: Publish (Optional)

```bash
# Build distribution
python -m build

# Upload to PyPI
python -m twine upload dist/*
```

## Example: Creating a Metric Plugin

```bash
$ python tools/plugin_wizard.py

[Step 1] Plugin Type Selection
> 1. Metric - Performance metrics

[Step 2] Basic Information
> Plugin display name: Response Size Metric
> Plugin identifier: response_size
> Brief description: Measures response payload size in bytes

[Step 3] Package Information
> Package name: aiperf-response-size
> Author: Your Name
> Email: your.email@example.com

[Step 4] Metric-Specific Configuration
> Metric calculation type: record
> Return value type: int
> Display order: 500

✓ Created aiperf-response-size/pyproject.toml
✓ Created aiperf-response-size/src/aiperf_response_size/__init__.py
✓ Created aiperf-response-size/src/aiperf_response_size/response_size.py
✓ Created aiperf-response-size/tests/test_response_size.py
✓ Created aiperf-response-size/README.md
✓ Created aiperf-response-size/LICENSE
✓ Created aiperf-response-size/.github/workflows/test.yml

Next Steps:
  1. Implement TODOs in the generated files
  2. Run tests: pytest
  3. Install: pip install -e '.[dev]'
  4. Use with AIPerf - automatic discovery!
```

## Plugin Template Structure

### Generated pyproject.toml

```toml
[project.entry-points."aiperf.metric"]
response_size = "aiperf_response_size.response_size:ResponseSizeMetric"
```

This single entry point configuration makes your plugin discoverable by AIPerf.

### Generated Plugin Class

```python
class ResponseSizeMetric(BaseRecordMetric[int]):
    tag = "response_size"
    header = "Response Size"
    unit = GenericMetricUnit.BYTES

    def _parse_record(self, record, record_metrics):
        # Your implementation
        pass

def plugin_metadata():
    return {
        "name": "response_size",
        "aip_version": "001",
    }
```

## Advanced Features

### Dependency Injection (AIP-001)

If your plugin needs AIPerf services:

```python
class MyPlugin:
    def __init__(self, tokenizer=None, config=None):
        # Dependencies injected automatically
        self.tokenizer = tokenizer
        self.config = config
```

### Plugin Metadata

All plugins include `plugin_metadata()` function:

```python
def plugin_metadata():
    return {
        "name": "plugin_name",
        "display_name": "Human Readable Name",
        "version": "0.1.0",
        "plugin_type": "metric",
        "aip_version": "001",  # AIP-001 compliance
    }
```

### Testing Your Plugin

Generated test files include:

- Metadata validation
- Instantiation tests
- Functionality tests (TODO templates)
- pytest fixtures
- Coverage configuration

## Integration with AIPerf

### How Plugins Extend AIPerf

1. **Metrics**: Automatically included in metric computation pipeline
2. **Endpoints**: Available for `--endpoint-type` CLI flag
3. **Exporters**: Automatically run during result export
4. **Processors**: Integrated into data processing pipeline

### No Core Modifications Needed

- Plugins work with unmodified AIPerf
- Install plugin package → AIPerf discovers it
- Independent versioning and releases
- Third-party distribution via PyPI

## Troubleshooting

### Plugin Not Discovered

```bash
# Check entry points
python -c "from importlib.metadata import entry_points; print(list(entry_points(group='aiperf.metric')))"

# Reinstall in editable mode
pip install -e .
```

### Import Errors

- Ensure AIPerf is installed: `pip install aiperf`
- Check Python version: `>=3.10` required
- Verify package structure matches entry point

### Testing Issues

- Use `pytest --no-cov` for debugging with breakpoints
- Check test file imports
- Ensure test discovery finds your tests

## See Also

- **AIP-001 Specification**: https://github.com/ai-dynamo/enhancements/pull/43
- **Plugin Development Guide**: /guidebook/chapter-47-extending-aiperf.md
- **Metrics Guide**: /guidebook/chapter-44-custom-metrics-development.md
- **Contributing**: /CONTRIBUTING.md

## Support

For questions or issues:
- Open an issue on GitHub
- Check the guidebook chapters
- Ask in Discord community

---

**Version**: 1.0.0
**AIP Compliance**: AIP-001
**Status**: Production-ready
