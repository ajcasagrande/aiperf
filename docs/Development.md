# Developers Guide
Execute the following commands to set up your development environment for `aiperf`.
Make sure you are in the root directory of the `aiperf` repository.

## Development Environment
- Install uv
https://docs.astral.sh/uv/getting-started/installation/
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

- Create virtual env
```bash
uv venv
```

- Activate venv
```bash
source .venv/bin/activate
```

- Install `aiperf` package in editable development mode
```bash
uv pip install -e .
```

- Run `aiperf`
```bash
aiperf
```
Press `Ctrl-C` to stop the process

- Run `aiperf` with `--help` to see available commands
```bash
aiperf --help
```





