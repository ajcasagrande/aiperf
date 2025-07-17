<!--
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
-->
# Type Checking Setup for AIPerf

This guide explains the comprehensive type checking setup for the AIPerf project and how to use the various tools.

## 📁 Files Created/Modified

### New Files
- `aiperf/py.typed` - Marker file indicating type support (PEP 561)
- `tools/type_tools.py` - Comprehensive type checking and stub generation script
- `tools/type_demo.py` - Demonstration of common type issues and fixes
- `tools/TYPE_CHECKING_GUIDE.md` - This guide

### Modified Files
- `pyproject.toml` - Added mypy configuration and type checking dependencies
- `Makefile` - Added type checking targets

## 🎯 What is `py.typed`?

The `py.typed` file is a simple marker file that tells type checkers and IDEs that your package supports type hints according to [PEP 561](https://www.python.org/dev/peps/pep-0561/).

### Benefits:
- ✅ IDEs provide better autocompletion
- ✅ Type checkers can verify code using your package
- ✅ Indicates your package follows typing best practices
- ✅ Enables static analysis for downstream users

## 🛠️ Available Tools and Commands

### 1. Makefile Commands (Recommended)

```bash
# Run MyPy type checking
make type-check
# or
make mypy

# Generate .pyi stub files
make stubgen

# Run comprehensive type tools
make type-tools
```

### 2. Direct Tool Usage

```bash
# Activate virtual environment first
source .venv/bin/activate

# MyPy type checking
mypy aiperf/

# Generate stubs for your package (stubgen comes with mypy)
stubgen -p aiperf -o stubs/

# Generate stubs for dependencies
stubgen -p transformers -o stubs/

# Run comprehensive type analysis
python tools/type_tools.py
```

### 3. Type Demo

```bash
# See examples of type issues
python tools/type_demo.py

# Check the demo file for type errors
mypy tools/type_demo.py
```

## ⚙️ Configuration

### MyPy Configuration (in `pyproject.toml`)

```toml
[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
warn_unreachable = true
strict_equality = true
show_error_codes = true
files = ["aiperf/"]

[[tool.mypy.overrides]]
module = [
    "transformers.*",
    "dask.*",
    "bokeh.*",
    # ... other dependencies without types
]
ignore_missing_imports = true
```

## 📋 Type Checking Workflow

### 1. During Development

```bash
# Check types frequently
make type-check

# Fix any type errors reported
# Add type annotations where missing
# Use Union, Optional, Generic types as needed
```

### 2. Before Commits

```bash
# Run full type analysis
make type-tools

# This will:
# - Validate py.typed setup
# - Run mypy type checking
# - Run pyright (if available)
# - Generate stub files
# - Check dependencies
```

### 3. CI/CD Integration

Add to your CI pipeline:

```yaml
- name: Type checking
  run: |
    source .venv/bin/activate
    make type-check
```

## 🔧 Common Type Issues and Fixes

### Missing Return Type
```python
# ❌ Bad
def process_data(data):
    return data.upper()

# ✅ Good
def process_data(data: str) -> str:
    return data.upper()
```

### Optional Values
```python
# ❌ Bad
def get_user(user_id: int):
    return users.get(user_id)  # Could return None

# ✅ Good
def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    return users.get(user_id)
```

### Union Types
```python
# ❌ Bad
def parse_input(value):
    if isinstance(value, str):
        return int(value)
    return value

# ✅ Good
def parse_input(value: Union[str, int]) -> int:
    if isinstance(value, str):
        return int(value)
    return value
```

## 📊 Stub File Generation

### What are Stub Files?
- `.pyi` files containing only type information
- Used when source code can't have type annotations
- Provide types for external libraries
- Enable type checking without modifying source

### Generated Locations
- `stubs/aiperf/` - Your package stubs
- `stubs/transformers/` - Dependency stubs
- `stubs/other_deps/` - Other dependency stubs

### Using Generated Stubs
1. Add `stubs/` to your `PYTHONPATH` or mypy path
2. Type checkers will automatically find them
3. Consider contributing stubs to [typeshed](https://github.com/python/typeshed)

## 🚀 Advanced Usage

### Custom Type Checker Configuration

Create `.mypy.ini` for more complex setups:

```ini
[mypy]
python_version = 3.10
strict = True

[mypy-tests.*]
disallow_untyped_defs = False
```

### IDE Integration

Most IDEs automatically recognize `py.typed` and will:
- Provide better autocompletion
- Show type errors inline
- Enable better refactoring tools

### Type Checking in Pre-commit

Add to `.pre-commit-config.yaml`:

```yaml
- repo: local
  hooks:
    - id: mypy
      name: MyPy Type Checking
      entry: mypy
      language: system
      files: ^aiperf/
      pass_filenames: false
      args: [aiperf/]
```

## 🎯 Best Practices

1. **Start Gradually**: Use `# type: ignore` for complex legacy code
2. **Use Generics**: Prefer `List[str]` over `List[Any]`
3. **Document Complex Types**: Use type aliases for readability
4. **Test Your Types**: Type checkers catch many bugs early
5. **Keep Stubs Updated**: Regenerate stubs when APIs change

## 🆘 Troubleshooting

### Common Issues

**Import errors in mypy:**
- Add missing dependencies to `pyproject.toml`
- Use `ignore_missing_imports = true` for problematic modules

**Type errors in generated stubs:**
- Stubs may be imperfect; edit manually if needed
- Consider contributing fixes back to the community

**Performance issues:**
- Use `--cache-dir` to speed up repeated mypy runs
- Consider `--incremental` mode for large projects

## 📚 Additional Resources

- [MyPy Documentation](https://mypy.readthedocs.io/)
- [PEP 484 - Type Hints](https://www.python.org/dev/peps/pep-0484/)
- [PEP 561 - Distributing Type Information](https://www.python.org/dev/peps/pep-0561/)
- [Python Type Checking Guide](https://realpython.com/python-type-checking/)

---

Happy type checking! 🎉
