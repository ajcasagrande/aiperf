<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# AIPerf Snippets Quick Reference

## Quick Lookup Table

| Category | Prefix | Description |
|----------|--------|-------------|
| **Metrics** |
| Record | `metric-record` | Per-request metric |
| Aggregate | `metric-aggregate` | Accumulated metric |
| Derived | `metric-derived` | Computed from other metrics |
| Counter | `metric-counter` | Simple counting metric |
| **Datasets** |
| Loader | `dataset-loader` | Custom dataset loader |
| **Services** |
| Service | `service` | New AIPerf service |
| **Tests** |
| Unit | `test-unit` | Standard unit test |
| Metric | `test-metric` | Metric-specific test |
| Integration | `test-integration` | End-to-end test |
| **Config** |
| Config | `config` | Pydantic config class |
| **Mixins** |
| Mixin | `mixin` | Reusable behavior component |
| **Hooks** |
| Start | `hook-start` | on_start lifecycle hook |
| Stop | `hook-stop` | on_stop lifecycle hook |
| Message | `hook-message` | Message bus handler |
| Command | `hook-command` | Command handler |
| Background | `background-task` | Periodic background task |
| **Utils** |
| SPDX | `spdx` | License header |
| Logger | `logger` | Logger instance |
| Import Metric | `import-metric` | Metric imports |
| Import Config | `import-config` | Config imports |
| Import Factories | `import-factories` | Factory imports |
| Docstring | `docstring` | Comprehensive docstring |

## Metric Type Decision Tree

```
Need a metric?
│
├─ Per-request value?
│  └─ Use: metric-record
│     Example: input_token_count, latency
│
├─ Count/Sum/Accumulate across requests?
│  │
│  ├─ Simple counting?
│  │  └─ Use: metric-counter
│  │     Example: request_count, error_count
│  │
│  └─ Complex accumulation?
│     └─ Use: metric-aggregate
│        Example: max_latency, custom_sum
│
└─ Calculated from other metrics?
   └─ Use: metric-derived
      Example: throughput, average_tokens
```

## Common Patterns Cheat Sheet

### Create a Simple Counter Metric
```python
// Type: metric-counter
// Fill: MetricName, Description
// Result: Complete counter implementation
```

### Create a Ratio Metric
```python
// Type: metric-derived
// Set: unit = GenericMetricUnit.RATIO
// Implement: numerator / denominator
```

### Create a Throughput Metric
```python
// Type: metric-derived
// Set: unit = MetricOverTimeUnit.REQUESTS_PER_SECOND
// Implement: count / duration
```

### Add Test for Your Metric
```python
// Type: test-metric
// Fill: MetricName, test scenarios
// Run: pytest tests/metrics/test_your_metric.py
```

### Create Custom Dataset Loader
```python
// Type: dataset-loader
// Register: CustomDatasetType.YOUR_TYPE
// Implement: load_dataset() and convert_to_conversations()
```

## VS Code Snippet Syntax Quick Ref

| Syntax | Purpose | Example |
|--------|---------|---------|
| `$1`, `$2` | Tab stops | `def ${1:name}():` |
| `$0` | Final position | `return $0` |
| `${1:default}` | Placeholder | `${1:param_name}` |
| `${1\|a,b,c\|}` | Choices | `${1\|int,float,str\|}` |
| `$VAR` | Variable | `$CURRENT_YEAR` |
| `${VAR:default}` | Variable with default | `${USER:unknown}` |
| `${1/regex/repl/}` | Transform | `${1/(.*)/${1:/upcase}/}` |
| Same `$N` | Mirrored edits | `${1:x}...${1}` |

## Common Variables

| Variable | Value |
|----------|-------|
| `CURRENT_YEAR` | 2025 |
| `CURRENT_DATE` | 04 |
| `CURRENT_MONTH` | 10 |
| `TM_FILENAME` | my_file.py |
| `TM_FILENAME_BASE` | my_file |
| `TM_DIRECTORY` | /path/to/dir |
| `UUID` | UUID v4 |
| `CLIPBOARD` | Clipboard contents |

## Transform Examples

```python
# Snake case to Pascal case
${1:metric_name}  →  ${1/([A-Z])/_${1:/downcase}/g}  →  metric_name

# Pascal case to snake case
${1:MetricName}  →  ${1/([a-z])([A-Z])/$1_${2:/downcase}/g}  →  metric_name

# Filename to class name
TM_FILENAME_BASE  →  ${TM_FILENAME_BASE/(.*)/${1:/pascalcase}/}  →  MyFile

# Add spaces to Pascal case
${1:MetricName}  →  ${1/([a-z])([A-Z])/$1 $2/g}  →  Metric Name
```

## Workflow Examples

### 1. Create New Record Metric
```
1. Type: metric-record
2. Tab through:
   - MetricName
   - ValueType (int/float/str/bool)
   - Description
   - tag
   - Unit
   - Flags
   - _parse_record implementation
3. Save and run: test-metric
```

### 2. Create New Service
```
1. Type: service
2. Fill:
   - ServiceName
   - ServiceType enum
   - Hook type (on_start/on_message/etc)
3. Add lifecycle hooks:
   - hook-start
   - hook-stop
4. Register with factory (auto-done)
```

### 3. Add Dataset Support
```
1. Create loader: dataset-loader
2. Define CustomDatasetType in enums
3. Implement load_dataset()
4. Implement convert_to_conversations()
5. Test with integration-test
```

## Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Insert snippet | Type prefix + `Tab` |
| Next tabstop | `Tab` |
| Previous tabstop | `Shift+Tab` |
| Select choice | `↑`/`↓` + `Enter` |
| Exit snippet | `Esc` |
| Multi-cursor | `Alt+Click` |
| Select all occurrences | `Ctrl+Shift+L` |

## Debugging Snippets

### Problem: Snippet not appearing
```
✓ Check: In .py file?
✓ Check: Correct prefix?
✓ Reload: Ctrl+Shift+P → "Reload Window"
```

### Problem: Tabstops not working
```
✓ Check: Sequential numbering (1,2,3...)?
✓ Check: $0 exists?
✓ Check: Valid JSON?
```

### Problem: Transformation not working
```
✓ Test regex at: regex101.com
✓ Escape backslashes: \\\\ in JSON
✓ Check syntax: ${1/regex/repl/options}
```

## Pro Tips

### Tip 1: Multi-cursor Editing
After inserting snippet, use `Ctrl+D` to select next occurrence and edit multiple locations simultaneously.

### Tip 2: Choice Navigation
When at a choice list, type first letter to jump to that choice (e.g., type 'f' for 'float').

### Tip 3: Variable Preview
Use `Ctrl+Space` while typing `${}` to see available variables.

### Tip 4: Snippet Discovery
Type just `aiperf-` to see all available AIPerf snippets.

### Tip 5: Custom Shortcuts
Bind snippets to keyboard shortcuts in `keybindings.json`:
```json
{
  "key": "ctrl+shift+m",
  "command": "editor.action.insertSnippet",
  "args": { "name": "AIPerf Record Metric" }
}
```

## Testing Checklist

When creating/modifying snippets:

- [ ] All tabstops reachable via Tab
- [ ] Tab order is logical
- [ ] `$0` in correct final position
- [ ] Choices work (if used)
- [ ] Transformations correct (if used)
- [ ] Mirrored placeholders sync (if used)
- [ ] Generated code is valid Python
- [ ] Imports are correct
- [ ] Default values make sense
- [ ] Description is clear
- [ ] Prefix is intuitive

## Common Metric Patterns

### Pattern: Latency Metric (Time Difference)
```python
// Snippet: metric-record
// Type: float
// Unit: TimeMetricUnit.NANOSECONDS
// Implementation:
return record.response_end_ns - record.request_start_ns
```

### Pattern: Token Count (Direct Access)
```python
// Snippet: metric-record
// Type: int
// Unit: GenericMetricUnit.TOKENS
// Implementation:
return record.output_token_count
```

### Pattern: Rate (Count / Time)
```python
// Snippet: metric-derived
// Type: float
// Unit: MetricOverTimeUnit.TOKENS_PER_SECOND
// Dependencies: token_count, duration
// Implementation:
tokens = metric_results[TokenMetric.tag]
duration = metric_results.get_converted(DurationMetric, TimeUnit.SECONDS)
return tokens / duration
```

### Pattern: Percentage
```python
// Snippet: metric-derived
// Type: float
// Unit: GenericMetricUnit.PERCENTAGE
// Implementation:
return (good_count / total_count) * 100.0
```

## File Organization

```
.vscode/
├── aiperf.code-snippets          # Main snippet definitions
├── SNIPPETS.md                    # Complete guide (this file)
├── SNIPPETS_QUICK_REFERENCE.md   # Quick lookup
└── launch.json                    # Debug configurations
```

## Resources

- Full guide: `.vscode/SNIPPETS.md`
- Architecture: `.vscode/ARCHITECTURE.md`
- VS Code docs: https://code.visualstudio.com/docs/editor/userdefinedsnippets

---

**Last Updated**: 2025-10-04
**Version**: 1.0.0
