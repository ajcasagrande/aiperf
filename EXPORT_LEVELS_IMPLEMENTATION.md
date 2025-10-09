<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Export Levels Implementation Summary

## ✅ Implementation Complete

I've successfully refactored the export system into three levels with proper unit conversion and filtering.

---

## 🎯 What Was Implemented

### 1. New Export Level Enum

**File:** `aiperf/common/enums/data_exporter_enums.py`

```python
class ExportLevel(CaseInsensitiveStrEnum):
    SUMMARY = "summary"  # Default - aggregated metrics only
    RECORDS = "records"  # Per-record metrics with conversion & filtering
    RAW = "raw"          # Full parsed records with all content
```

### 2. Configuration Changes

**File:** `aiperf/common/config/output_config.py`

- **Old:** `--export-raw-records` (boolean)
- **New:** `--export-level {summary|records|raw}` (enum)

### 3. Record Export Results Processor (NEW)

**File:** `aiperf/post_processors/record_export_results_processor.py`

- Runs in RecordsManager (centralized, single file)
- Exports per-record metrics to `record_metrics/record_metrics.jsonl`
- Converts to display units (ns → ms, etc.)
- Filters based on dev config (excludes experimental/internal by default)
- Pattern matches `ConsoleMetricsExporter` for consistency

### 4. Raw Record Writer (Updated)

**File:** `aiperf/records/raw_record_writer.py`

- Runs in RecordProcessor (distributed, multiple files)
- Exports full parsed records to `raw_records/raw_records_{processor_id}.jsonl`
- Uses Pydantic's `model_dump()` for complete serialization
- No filtering, no conversion (raw data)

---

## 📊 Export Level Comparison

| Aspect | Summary | Records | Raw |
|--------|---------|---------|-----|
| **Location** | ExporterManager | RecordsManager | RecordProcessor |
| **Timing** | After aggregation | During aggregation | During processing |
| **Files** | 2 files (JSON, CSV) | 1 file (JSONL) | N files (one per processor) |
| **Size** | ~10-50 KB | ~1-10 MB | ~100 MB - GB |
| **Unit Conversion** | ✅ Yes | ✅ Yes | ❌ No (raw) |
| **Filtering** | ✅ Yes | ✅ Yes | ❌ No (all data) |
| **Data** | Aggregated stats | Per-record metrics | Full request/response |

---

## 🔄 Data Flow

### Summary (Default)
```
RecordProcessor → RecordsManager → MetricResultsProcessor → ExporterManager
                                    (aggregates)           (exports summary)
```

### Records
```
RecordProcessor → RecordsManager → RecordExportResultsProcessor
                  (receives metrics) (writes per-record JSONL)
```

### Raw
```
RecordProcessor → (writes raw JSONL immediately)
(has full data)
```

---

## 📁 File Outputs

### Summary Level
```
artifacts/my-benchmark/
├── profile_export_aiperf.json  # Aggregated metrics
└── profile_export_aiperf.csv   # Same in CSV
```

### Records Level
```
artifacts/my-benchmark/
├── profile_export_aiperf.json  # Summary (always included)
├── profile_export_aiperf.csv   # Summary CSV
└── record_metrics/
    └── record_metrics.jsonl    # Per-record metrics ← NEW
```

### Raw Level
```
artifacts/my-benchmark/
├── profile_export_aiperf.json  # Summary (always included)
├── profile_export_aiperf.csv   # Summary CSV
└── raw_records/
    ├── raw_records_record-processor-1.jsonl  # ← NEW
    ├── raw_records_record-processor-2.jsonl
    └── raw_records_record-processor-3.jsonl
```

---

## 🎨 Design Decisions

### Why RecordsManager for "records" level?

**Centralized export:**
- ✅ Single file (easy to analyze)
- ✅ Already receives all metric data
- ✅ No duplicate data (each record processed once)
- ✅ Consistent ordering

**vs Distributed (RecordProcessor):**
- ❌ Multiple files to merge
- ❌ More complex to analyze

### Why RecordProcessor for "raw" level?

**Data availability:**
- ✅ Has complete ParsedResponseRecord
- ✅ Has full request/response content
- ✅ No extra ZMQ transfer needed

**Distributed writes:**
- ✅ Parallel I/O (better performance)
- ✅ Writes immediately (no memory buffering)

### Unit Conversion Pattern

Matches existing exporters:
```python
# Get display unit
display_unit = metric_class.display_unit or metric_class.unit

# Convert using unit's convert_to method
if display_unit != metric_class.unit and isinstance(value, int | float):
    value = metric_class.unit.convert_to(display_unit, value)
```

### Filtering Pattern

Matches `ConsoleMetricsExporter._should_show()`:
```python
# Always filter ERROR_ONLY and HIDDEN
if not metric_class.missing_flags(MetricFlags.ERROR_ONLY | MetricFlags.HIDDEN):
    return False

# Filter EXPERIMENTAL/INTERNAL unless dev mode
return show_internal or metric_class.missing_flags(
    MetricFlags.EXPERIMENTAL | MetricFlags.INTERNAL
)
```

---

## ✅ Implementation Checklist

- [x] ExportLevel enum created
- [x] Configuration updated to use enum
- [x] RecordExportResultsProcessor implemented
- [x] Unit conversion implemented (matches console exporter pattern)
- [x] Filtering implemented (matches console exporter pattern)
- [x] Developer mode support (show_internal_metrics)
- [x] RawRecordWriter updated to use export level
- [x] RecordProcessor integration updated
- [x] No linter errors
- [x] Documentation created (export-levels.md)
- [x] Migration notes added
- [x] Usage examples provided

---

## 🧪 Testing Recommendations

### Test Summary Level
```bash
aiperf profile --model test --url localhost:8000 --endpoint-type chat --request-count 10
# Should create: profile_export_aiperf.json, profile_export_aiperf.csv
# Should NOT create: record_metrics/, raw_records/
```

### Test Records Level
```bash
aiperf profile --model test --url localhost:8000 --endpoint-type chat --request-count 10 --export-level records
# Should create: profile_export_aiperf.json, profile_export_aiperf.csv, record_metrics/record_metrics.jsonl
# Should NOT create: raw_records/
```

### Test Raw Level
```bash
aiperf profile --model test --url localhost:8000 --endpoint-type chat --request-count 10 --export-level raw
# Should create: profile_export_aiperf.json, profile_export_aiperf.csv, raw_records/raw_records_*.jsonl
# Should NOT create: record_metrics/
```

### Test Filtering (Developer Mode)
```bash
export AIPERF_DEV_MODE=1
aiperf profile --model test --url localhost:8000 --endpoint-type chat --request-count 10 --export-level records --show-internal-metrics
# record_metrics.jsonl should include experimental/internal metrics
```

---

## 📝 Files Modified

1. `aiperf/common/enums/data_exporter_enums.py` - Added ExportLevel enum
2. `aiperf/common/enums/post_processor_enums.py` - Added RECORD_EXPORT type
3. `aiperf/common/enums/__init__.py` - Exported ExportLevel
4. `aiperf/common/config/output_config.py` - Changed to export_level enum
5. `aiperf/common/config/config_defaults.py` - Updated defaults
6. `aiperf/post_processors/record_export_results_processor.py` - **NEW** - Records level implementation
7. `aiperf/records/raw_record_writer.py` - Updated to use ExportLevel.RAW
8. `aiperf/records/record_processor_service.py` - Updated to use ExportLevel.RAW
9. `docs/export-levels.md` - **NEW** - Complete documentation
10. `docs/raw-records-export.md` - Updated for new flag

---

## 🚀 Ready to Use

Users can now:

```bash
# Default behavior (no change)
aiperf profile --model MODEL --url URL --endpoint-type chat

# Get per-record metrics
aiperf profile --model MODEL --url URL --endpoint-type chat --export-level records

# Get full raw data
aiperf profile --model MODEL --url URL --endpoint-type chat --export-level raw
```

**All levels:**
- ✅ Proper unit conversion
- ✅ Appropriate filtering
- ✅ Developer mode support
- ✅ Efficient implementation
- ✅ Clean, maintainable code

