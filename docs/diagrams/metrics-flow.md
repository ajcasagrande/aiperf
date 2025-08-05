<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
```mermaid
flowchart TD
    %% Input Data
    A["ParsedResponseRecord<br/><em>Raw inference result</em>"]

    %% Stage 1: Distributed Record Processing
    A --> B1["MetricRecordProcessor (Worker 1)<br/><em>Distributed across multiple instances</em>"]
    A --> B2["MetricRecordProcessor (Worker 2)<br/><em>Distributed across multiple instances</em>"]
    A --> B3["MetricRecordProcessor (Worker N)<br/><em>Distributed across multiple instances</em>"]

    %% RECORD Metric Path
    B1 --> C1["RECORD: RequestLatencyMetric<br/>parse_record() → 125ms<br/><em>Individual value per request</em>"]
    B2 --> C2["RECORD: RequestLatencyMetric<br/>parse_record() → 87ms<br/><em>Individual value per request</em>"]
    B3 --> C3["RECORD: RequestLatencyMetric<br/>parse_record() → 203ms<br/><em>Individual value per request</em>"]

    %% AGGREGATE Metric Path
    B1 --> D1["AGGREGATE: TotalRequestsMetric<br/>parse_record() → +1<br/><em>Individual contribution</em>"]
    B2 --> D2["AGGREGATE: TotalRequestsMetric<br/>parse_record() → +1<br/><em>Individual contribution</em>"]
    B3 --> D3["AGGREGATE: TotalRequestsMetric<br/>parse_record() → +1<br/><em>Individual contribution</em>"]

    %% MetricRecordDict Collection
    C1 --> E1["MetricRecordDict<br/><em>Per-record results</em>"]
    D1 --> E1
    C2 --> E2["MetricRecordDict<br/><em>Per-record results</em>"]
    D2 --> E2
    C3 --> E3["MetricRecordDict<br/><em>Per-record results</em>"]
    D3 --> E3

    %% Transport to Central Manager
    E1 --> F["MetricRecordsMessage<br/><em>Async message transport</em>"]
    E2 --> F
    E3 --> F

    %% Stage 2: Centralized Results Processing
    F --> G["RecordsManager → MetricResultsProcessor<br/><em>Single centralized instance</em>"]

    %% RECORD Processing in Central
    G --> H1["RECORD Collection<br/>deque().append(125ms)<br/>deque().append(87ms)<br/>deque().append(203ms)<br/><em>Collect all individual values</em>"]

    %% AGGREGATE Processing in Central
    G --> H2["AGGREGATE Accumulation<br/>aggregate_value(+1) → total=1<br/>aggregate_value(+1) → total=2<br/>aggregate_value(+1) → total=3<br/><em>Accumulate across workers</em>"]

    %% DERIVED Processing (Only in Central)
    H1 --> I["DERIVED: ThroughputMetric<br/>derive_value(results)<br/>= total_requests / duration<br/>= 3 / 5.2s = 0.58 req/s<br/><em>Computed from other metrics</em>"]
    H2 --> I

    %% Stage 3: Statistical Summarization
    H1 --> J1["RECORD Statistics<br/>p50=125ms, p95=203ms<br/>mean=138ms, std=58ms<br/>min=87ms, max=203ms<br/><em>Full statistical analysis</em>"]

    H2 --> J2["AGGREGATE Result<br/>final_value=3<br/>count=1 (single value)<br/><em>Single accumulated total</em>"]

    I --> J3["DERIVED Result<br/>final_value=0.58<br/>count=1 (computed value)<br/><em>Single computed result</em>"]

    %% Final Output
    J1 --> K["MetricResult List<br/><em>Complete performance analysis</em>"]
    J2 --> K
    J3 --> K

    %% Styling
    classDef input fill:#e3f2fd,stroke:#1976d2,stroke-width:2px,color:#000000,font-weight:bold
    classDef distributed fill:#e8f5e8,stroke:#388e3c,stroke-width:2px,color:#000000,font-weight:bold
    classDef recordMetric fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#000000,font-weight:bold
    classDef aggregateMetric fill:#fce4ec,stroke:#c2185b,stroke-width:2px,color:#000000,font-weight:bold
    classDef derivedMetric fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,color:#000000,font-weight:bold
    classDef transport fill:#e0f2f1,stroke:#00695c,stroke-width:2px,color:#000000,font-weight:bold
    classDef central fill:#ffebee,stroke:#d32f2f,stroke-width:2px,color:#000000,font-weight:bold
    classDef collection fill:#fff8e1,stroke:#ffa000,stroke-width:2px,color:#000000,font-weight:bold
    classDef statistics fill:#e1f5fe,stroke:#0277bd,stroke-width:2px,color:#000000,font-weight:bold
    classDef output fill:#e8f5e8,stroke:#2e7d32,stroke-width:3px,color:#000000,font-weight:bold

    %% Apply styles
    class A input
    class B1,B2,B3 distributed
    class C1,C2,C3 recordMetric
    class D1,D2,D3 aggregateMetric
    class I derivedMetric
    class E1,E2,E3,F transport
    class G central
    class H1,H2 collection
    class J1,J2,J3 statistics
    class K output
```
