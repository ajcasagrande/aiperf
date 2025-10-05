# AIPerf VS Code Snippets Guide

## Overview

This guide provides comprehensive documentation for the AIPerf VS Code snippet system, including modern best practices for snippet creation, usage, and customization.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Snippet Categories](#snippet-categories)
3. [VS Code Snippet Syntax Reference](#vs-code-snippet-syntax-reference)
4. [Best Practices](#best-practices)
5. [Customization Guide](#customization-guide)
6. [Advanced Patterns](#advanced-patterns)

---

## Quick Start

### Installation

The snippets are automatically available in any Python file in this workspace. The snippet file is located at:
```
.vscode/aiperf.code-snippets
```

### Basic Usage

1. **Type a prefix**: Start typing one of the snippet prefixes (e.g., `metric-record`)
2. **Autocomplete appears**: VS Code shows matching snippets
3. **Select snippet**: Press `Tab` or `Enter` to insert
4. **Navigate placeholders**: Press `Tab` to move forward, `Shift+Tab` to move backward
5. **Choose from options**: For choice lists, use arrow keys and `Enter`
6. **Edit as needed**: Modify the inserted code to fit your needs

### Example: Creating a Record Metric

```python
# Type: metric-record
# Press: Tab
# Result: Complete metric template with placeholders
```

---

## Snippet Categories

### 1. Metrics (6 snippets)

#### Record Metrics
- **Prefix**: `aiperf-metric-record`, `metric-record`
- **Purpose**: Per-request metrics (computed independently for each request)
- **Use When**: You need to calculate a value for each individual request
- **Example**: Input token count, output token count, latency per request

```python
# Creates:
class MetricNameMetric(BaseRecordMetric[float]):
    tag = "metric_name"
    header = "Metric Name"
    # ... complete implementation
```

#### Aggregate Metrics
- **Prefix**: `aiperf-metric-aggregate`, `metric-aggregate`
- **Purpose**: Accumulated metrics across all requests
- **Use When**: You need to sum, count, or accumulate values across requests
- **Example**: Total request count, max latency across all requests

```python
# Creates:
class MetricNameMetric(BaseAggregateMetric[int]):
    def _parse_record(...) -> int:
        # Extract individual value

    def _aggregate_value(self, value: int) -> None:
        # Accumulate into self._value
```

#### Derived Metrics
- **Prefix**: `aiperf-metric-derived`, `metric-derived`
- **Purpose**: Computed from other metrics after all processing
- **Use When**: Your metric depends on other metrics' final values
- **Example**: Throughput (requests / duration), average tokens per request

```python
# Creates:
class MetricNameMetric(BaseDerivedMetric[float]):
    required_metrics = {DependencyMetric.tag, OtherMetric.tag}

    def _derive_value(self, metric_results: MetricResultsDict) -> float:
        # Compute from other metrics
```

#### Counter Metrics
- **Prefix**: `aiperf-metric-counter`, `metric-counter`
- **Purpose**: Simple counting (most common aggregate pattern)
- **Use When**: You just need to count occurrences
- **Example**: Error count, request count, token count

```python
# Creates:
class MetricNameMetric(BaseAggregateCounterMetric[int]):
    tag = "metric_name"
    # Automatically handles counting logic
```

### 2. Dataset Loaders (1 snippet)

#### Custom Dataset Loader
- **Prefix**: `aiperf-dataset-loader`, `dataset-loader`
- **Purpose**: Load custom dataset formats
- **Use When**: You have a proprietary or custom dataset format
- **Features**:
  - Factory registration
  - Media conversion support
  - Session management
  - Conversation building

```python
# Creates:
@CustomDatasetFactory.register(CustomDatasetType.CUSTOM_TYPE)
class DatasetNameDatasetLoader(MediaConversionMixin):
    def load_dataset(self) -> dict[str, list[SingleTurn]]:
        # Load from file

    def convert_to_conversations(self, data) -> list[Conversation]:
        # Convert to conversation format
```

### 3. Services (1 snippet)

#### AIPerf Service
- **Prefix**: `aiperf-service`, `service`
- **Purpose**: Create new system services
- **Use When**: Adding new functionality to AIPerf architecture
- **Features**:
  - Factory registration
  - Lifecycle hooks
  - Message handling
  - Configuration management

```python
# Creates:
@ServiceFactory.register(ServiceType.CUSTOM_SERVICE)
class ServiceNameService(BaseService):
    @on_message(MessageType.STATUS)
    async def _on_status(self, message: StatusMessage) -> None:
        # Handle message
```

### 4. Tests (3 snippets)

#### Unit Test
- **Prefix**: `aiperf-test-unit`, `test-unit`
- **Purpose**: Standard unit test class
- **Includes**:
  - Basic test method
  - Parametrized test
  - Error handling test
  - Arrange-Act-Assert pattern

#### Metric Test
- **Prefix**: `aiperf-test-metric`, `test-metric`
- **Purpose**: Specialized tests for metrics
- **Includes**:
  - No records test
  - Single record test
  - Multiple records parametrized test
  - Missing data test

#### Integration Test
- **Prefix**: `aiperf-test-integration`, `test-integration`
- **Purpose**: End-to-end integration tests
- **Includes**:
  - Configuration fixtures
  - System controller execution
  - Results validation

### 5. Configuration (1 snippet)

#### Config Class
- **Prefix**: `aiperf-config`, `config`
- **Purpose**: Pydantic configuration classes
- **Features**:
  - CLI parameter integration
  - Validation methods
  - Field annotations
  - Default values
  - Help text

```python
# Creates:
class ConfigNameConfig(BaseConfig):
    param_name: Annotated[
        str,
        Field(description="..."),
        CLIParameter(name=("--param-name",), group=Groups.GENERAL),
    ] = DefaultsClass.DEFAULT_VALUE
```

### 6. Mixins (1 snippet)

#### Mixin Class
- **Prefix**: `aiperf-mixin`, `mixin`
- **Purpose**: Reusable behavior components
- **Features**:
  - Hook providers
  - Message handlers
  - State management
  - Multiple inheritance support

### 7. Lifecycle Hooks (5 snippets)

#### on_start
- **Prefix**: `aiperf-hook-start`, `hook-start`
- **Use**: Initialize resources when service starts

#### on_stop
- **Prefix**: `aiperf-hook-stop`, `hook-stop`
- **Use**: Clean up resources when service stops

#### on_message
- **Prefix**: `aiperf-hook-message`, `hook-message`
- **Use**: Handle messages from message bus

#### on_command
- **Prefix**: `aiperf-hook-command`, `hook-command`
- **Use**: Handle command messages

#### background_task
- **Prefix**: `aiperf-hook-background`, `hook-background`, `background-task`
- **Use**: Periodic background tasks with interval control

### 8. Quick Snippets (6 snippets)

- **SPDX Header**: `spdx`, `aiperf-header`
- **Logger**: `aiperf-logger`, `logger`
- **Import Metric**: `import-metric`
- **Import Config**: `import-config`
- **Import Factories**: `import-factories`
- **Docstring**: `docstring`, `doc`

---

## VS Code Snippet Syntax Reference

### Tabstops

Tabstops control cursor position and navigation order:

```json
{
  "body": [
    "def ${1:function_name}(${2:param}):",
    "    ${3:# Implementation}",
    "    return $0"
  ]
}
```

- `$1`, `$2`, `$3`: Numbered tabstops (press Tab to navigate)
- `$0`: Final cursor position (always last)
- `${1:default}`: Tabstop with default value (selected for easy replacement)

### Multiple Occurrences

Use the same tabstop number to mirror edits across locations:

```json
{
  "body": [
    "class ${1:ClassName}:",
    "    def __init__(self):",
    "        self.name = '${1}'",
    "    ",
    "    def __repr__(self):",
    "        return f'${1}(...)'"
  ]
}
```

All `${1}` placeholders update simultaneously when you edit one.

### Choice Lists

Provide predefined options for a placeholder:

```json
{
  "body": [
    "log_level = ${1|DEBUG,INFO,WARNING,ERROR,CRITICAL|}"
  ]
}
```

- Press Tab to reach the choice
- Use arrow keys to select
- Press Enter to confirm

### Variables

Insert dynamic content:

```json
{
  "body": [
    "# Author: ${USER}",
    "# Date: ${CURRENT_YEAR}-${CURRENT_MONTH}-${CURRENT_DATE}",
    "# File: ${TM_FILENAME}",
    "",
    "class ${TM_FILENAME_BASE/(.*)/${1:/pascalcase}/}:",
    "    pass"
  ]
}
```

**Built-in Variables:**

#### Document Variables
- `TM_SELECTED_TEXT`: Currently selected text
- `TM_CURRENT_LINE`: Current line contents
- `TM_CURRENT_WORD`: Current word under cursor
- `TM_LINE_INDEX`: Zero-indexed line number
- `TM_LINE_NUMBER`: One-indexed line number
- `TM_FILENAME`: Current file name with extension
- `TM_FILENAME_BASE`: Current file name without extension
- `TM_DIRECTORY`: Directory of current file
- `TM_FILEPATH`: Full file path

#### Date/Time Variables
- `CURRENT_YEAR`: Current year (4 digits)
- `CURRENT_YEAR_SHORT`: Current year (2 digits)
- `CURRENT_MONTH`: Month as two digits (01-12)
- `CURRENT_MONTH_NAME`: Full month name (January, etc.)
- `CURRENT_MONTH_NAME_SHORT`: Short month name (Jan, etc.)
- `CURRENT_DATE`: Day of month (01-31)
- `CURRENT_DAY_NAME`: Day of week (Monday, etc.)
- `CURRENT_DAY_NAME_SHORT`: Short day name (Mon, etc.)
- `CURRENT_HOUR`: Hour in 24-hour format
- `CURRENT_MINUTE`: Current minute
- `CURRENT_SECOND`: Current second
- `CURRENT_SECONDS_UNIX`: Unix timestamp

#### Random/Unique Variables
- `RANDOM`: 6 random decimal digits
- `RANDOM_HEX`: 6 random hexadecimal digits
- `UUID`: UUID v4

#### Clipboard Variable
- `CLIPBOARD`: Contents of clipboard

#### Workspace Variables
- `WORKSPACE_NAME`: Name of opened workspace
- `WORKSPACE_FOLDER`: Path of opened workspace folder

#### Comment Variables
- `BLOCK_COMMENT_START`: Language-specific block comment start (e.g., `/*` in JS)
- `BLOCK_COMMENT_END`: Language-specific block comment end (e.g., `*/` in JS)
- `LINE_COMMENT`: Language-specific line comment (e.g., `//` in JS, `#` in Python)

### Transformations

Apply regex transformations to variables or placeholders:

**Syntax:**
```
${variable/regex/replacement/options}
${1/regex/replacement/options}
```

**Examples:**

```json
{
  "Convert snake_case to PascalCase": {
    "body": [
      "class ${1:ClassName/([A-Z])/_${1:/downcase}/g}:",
      "    pass"
    ]
  },
  "Convert PascalCase to snake_case": {
    "body": [
      "def ${1:FunctionName/([a-z])([A-Z])/$1_${2:/downcase}/g}():",
      "    pass"
    ]
  },
  "Extract filename as class name": {
    "body": [
      "class ${TM_FILENAME_BASE/(.*)/${1:/pascalcase}/}:",
      "    pass"
    ]
  }
}
```

**Transform Options:**
- `/upcase` or `/u`: Convert to uppercase
- `/downcase` or `/d`: Convert to lowercase
- `/capitalize` or `/c`: Capitalize first letter
- `/pascalcase` or `/p`: Convert to PascalCase
- `/camelcase` or `/ca`: Convert to camelCase

**Regex Options:**
- `g`: Global (replace all matches)
- `i`: Case insensitive
- `m`: Multiline mode

### Nested Placeholders

Placeholders can be nested for complex scenarios:

```json
{
  "body": [
    "def ${1:function_name}(${2:arg1: ${3:str}}, ${4:arg2: ${5:int}}):",
    "    ${6:# Implementation}",
    "    return $0"
  ]
}
```

### Conditional Insertions

Use special syntax for optional content:

```json
{
  "body": [
    "class ${1:ClassName}${2:(${3:BaseClass})}:",
    "    ${4:\"\"\"${5:Docstring}\"\"\"$}",
    "    pass"
  ]
}
```

Placeholders with `$` at the end create optional sections that collapse if left empty.

---

## Best Practices

### 1. Snippet Design Principles

#### Keep Snippets Focused
- One snippet = one clear purpose
- Don't try to handle too many variations in a single snippet
- Create multiple related snippets instead

#### Use Meaningful Prefixes
- Start with project namespace: `aiperf-`
- Include category: `metric-`, `test-`, `config-`
- Provide short alternatives: `metric-record` vs just `record`

#### Provide Good Defaults
- Use realistic default values
- Make defaults easy to replace
- Include examples in comments

#### Order Tabstops Logically
- Follow natural reading/writing order
- Group related placeholders
- Put most important values first
- Use `$0` for final cursor position

### 2. Placeholder Best Practices

#### Use Descriptive Placeholder Text
```json
// Bad
"${1:x}"

// Good
"${1:metric_name}"
```

#### Provide Type Hints
```json
"${1:param_name}: ${2:str} = ${3:\"default\"}"
```

#### Use Transformations for Consistency
```json
// Convert input automatically
"tag = \"${1:${2/([A-Z])/_${1:/downcase}/g}}\""
```

### 3. Choice Lists

#### When to Use Choices
- Limited set of valid options
- Enums or constants
- Common patterns
- Type selections

#### Choice List Tips
```json
// Keep choices sorted or in logical order
"${1|DEBUG,INFO,WARNING,ERROR,CRITICAL|}"

// Use meaningful first choice
"${1|True,False|}"  // Most common first
```

### 4. Documentation

#### Include Snippet Descriptions
```json
{
  "description": "Create a new Record Metric (computed per request)"
}
```

#### Add Inline Comments
```json
{
  "body": [
    "# Required: Unique identifier",
    "tag = \"${1:metric_name}\"",
    "",
    "# Optional: Short name for dashboards",
    "short_header = \"${2:Short Name}\""
  ]
}
```

#### Use Docstring Placeholders
```json
{
  "body": [
    "def ${1:function_name}(${2:param}):",
    "    \"\"\"",
    "    ${3:Brief description}.",
    "    ",
    "    Args:",
    "        ${4:param: Description}",
    "    \"\"\"",
    "    $0"
  ]
}
```

### 5. Testing Snippets

#### Test All Tabstops
- Navigate through all tabstops
- Verify tab order makes sense
- Check that `$0` is in the right place

#### Test Transformations
- Verify regex patterns work correctly
- Test edge cases (empty, special chars)
- Check case conversions

#### Test Multiple Occurrences
- Verify mirrored placeholders sync
- Check that independent placeholders don't interfere

### 6. Performance

#### Keep Snippets Lightweight
- Avoid extremely long snippets
- Break complex templates into multiple snippets
- Consider multi-step workflows

#### Limit Nesting
- Don't nest placeholders too deeply
- Keep transformations simple
- Avoid complex regex when possible

---

## Customization Guide

### Adding New Snippets

1. **Open the snippet file:**
   ```
   .vscode/aiperf.code-snippets
   ```

2. **Add your snippet:**
   ```json
   {
     "Your Snippet Name": {
       "prefix": ["your-prefix", "alias"],
       "description": "What it does",
       "scope": "python",
       "body": [
         "line 1",
         "line 2 with ${1:placeholder}",
         "$0"
       ]
     }
   }
   ```

3. **Test it:**
   - Create a new Python file
   - Type your prefix
   - Verify it works correctly

### Modifying Existing Snippets

1. **Find the snippet** in `aiperf.code-snippets`
2. **Edit the body** array
3. **Update placeholder numbers** if adding/removing tabstops
4. **Test thoroughly**

### Sharing Custom Snippets

To share your snippets with the team:

1. **Document your snippet:**
   - Add clear description
   - Explain use cases
   - Provide examples

2. **Follow conventions:**
   - Use `aiperf-` prefix
   - Include SPDX header
   - Match existing style

3. **Submit a PR:**
   - Update `aiperf.code-snippets`
   - Update this documentation
   - Include examples

---

## Advanced Patterns

### Pattern 1: Context-Aware Snippets

Use variables to adapt to context:

```json
{
  "Class from Filename": {
    "body": [
      "class ${TM_FILENAME_BASE/(.*)/${1:/pascalcase}/}:",
      "    \"\"\"${1:${TM_FILENAME_BASE/(.*)/${1:/capitalize}/}}.\"\"\"",
      "    pass"
    ]
  }
}
```

### Pattern 2: Smart Imports

Generate imports based on choices:

```json
{
  "Metric Type Import": {
    "body": [
      "from aiperf.metrics import ${1|BaseRecordMetric,BaseAggregateMetric,BaseDerivedMetric|}",
      "",
      "class ${2:MetricName}Metric($1[${3|int,float|}]):",
      "    pass"
    ]
  }
}
```

### Pattern 3: Nested Structures

Handle complex nested patterns:

```json
{
  "Config with Optional Validation": {
    "body": [
      "class ${1:ConfigName}Config(BaseConfig):",
      "    ${2:param}: Annotated[${3:str}, Field(description=\"${4:...}\")]${5: = ${6:\"default\"}}",
      "    ${7:",
      "    @model_validator(mode=\"after\")",
      "    def ${8:validate}(self) -> Self:",
      "        ${9:# Validation logic}",
      "        return self",
      "    }",
      "    $0"
    ]
  }
}
```

### Pattern 4: Multi-Step Workflows

Create snippets that guide multi-step processes:

```json
{
  "Complete Metric Implementation": {
    "body": [
      "# Step 1: Imports",
      "from aiperf.metrics import BaseRecordMetric",
      "from aiperf.common.enums import GenericMetricUnit, MetricFlags",
      "",
      "# Step 2: Define Metric",
      "class ${1:MetricName}Metric(BaseRecordMetric[${2|int,float|}]):",
      "    tag = \"${3:${1/([A-Z])/_${1:/downcase}/g}}\"",
      "    header = \"${4:${1/([a-z])([A-Z])/$1 $2/g}}\"",
      "    unit = GenericMetricUnit.${5:COUNT}",
      "    flags = MetricFlags.${6:LARGER_IS_BETTER}",
      "",
      "    def _parse_record(self, record, record_metrics) -> ${2}:",
      "        ${7:# Implementation}",
      "        return ${8:value}",
      "",
      "# Step 3: Add test (use 'test-metric' snippet next)",
      "$0"
    ]
  }
}
```

### Pattern 5: Template Variables

Use variables for boilerplate:

```json
{
  "Service with Auto-Generated Names": {
    "body": [
      "@ServiceFactory.register(ServiceType.${1:SERVICE_TYPE})",
      "class ${2:${1/(.*)_(.*)/${1:/pascalcase}${2:/pascalcase}/}}Service(BaseService):",
      "    \"\"\"${3:Service for handling ${1/(.*)_(.*)/${1:/downcase} ${2:/downcase}/}}.\"\"\"",
      "    ",
      "    def __init__(self, service_config, user_config):",
      "        super().__init__(service_config, user_config)",
      "        self.logger = AIPerfLogger(f\"{__name__}.{self.__class__.__name__}\")",
      "    $0"
    ]
  }
}
```

### Pattern 6: Conditional Sections

Create optional code sections:

```json
{
  "Function with Optional Decorator": {
    "body": [
      "${1:@${2|staticmethod,classmethod,property|}$}",
      "def ${3:function_name}(${4:self}${5:, ${6:param}: ${7:str}})${8: -> ${9:None}}:",
      "    \"\"\"${10:Brief description}.\"\"\"",
      "    ${11:pass}",
      "    $0"
    ]
  }
}
```

---

## Troubleshooting

### Snippet Not Appearing

1. **Check file scope**: Ensure you're in a `.py` file
2. **Verify prefix**: Type the full prefix exactly
3. **Reload VS Code**: Sometimes needed after edits
4. **Check syntax**: Ensure JSON is valid

### Tabstops Not Working

1. **Check numbering**: Must be sequential
2. **Verify `$0` exists**: Final cursor position required
3. **Escape special chars**: Use `\\$` for literal `$`

### Transformations Not Working

1. **Check regex syntax**: Must be valid regex
2. **Test patterns**: Use regex tester online
3. **Escape backslashes**: Use `\\` in JSON

### Choices Not Appearing

1. **Check syntax**: `${1|choice1,choice2|}`
2. **No spaces**: Around pipes or commas
3. **Valid options**: Check for typos

---

## Contributing

When contributing new snippets:

1. **Follow naming conventions**
   - Use `aiperf-` prefix
   - Include category
   - Provide aliases

2. **Test thoroughly**
   - All tabstops
   - All choices
   - All transformations

3. **Document well**
   - Clear description
   - Usage examples
   - Edge cases

4. **Update this guide**
   - Add to appropriate category
   - Include examples
   - Explain use cases

---

## Resources

### Official VS Code Docs
- [Snippets Documentation](https://code.visualstudio.com/docs/editor/userdefinedsnippets)
- [Variables Reference](https://code.visualstudio.com/docs/editor/userdefinedsnippets#_variables)

### AIPerf Architecture
- See `.vscode/ARCHITECTURE.md` for component overview
- See `docs/` for detailed documentation

### Tools
- [Snippet Generator](https://snippet-generator.app/) - Create snippets visually
- [Regex101](https://regex101.com/) - Test regex patterns
- [VS Code Variables Tester](https://github.com/zjffun/vscode-snippets-variable-viewer) - Preview variables

---

## Changelog

### 2025-10-04 - Initial Release
- 24 core snippets covering all major AIPerf patterns
- Comprehensive metric creation support
- Test templates (unit, integration, metric-specific)
- Service and configuration boilerplate
- Lifecycle hooks and mixin patterns
- Quick utility snippets

---

## License

SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: Apache-2.0
