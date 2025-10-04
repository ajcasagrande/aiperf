<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# 🚀 Aggregate Throughput - Simple Explanation

## What Did We Add?

**NEW:** Charts showing your **system's total token generation capacity** computed from raw timestamps and token counts.

---

## 🎯 The Key Difference (Simple Example)

### Imagine This Scenario:

You have **10 users** making requests **simultaneously** to your LLM system.

#### Per-User Throughput (Already in Your Data):
```
User 1: Gets 30 tokens/second
User 2: Gets 30 tokens/second
User 3: Gets 30 tokens/second
...
User 10: Gets 30 tokens/second

Metric shown: 30 tokens/sec/user
```

**This is INDIVIDUAL experience** - how fast each user gets their tokens.

---

#### Aggregate System Throughput (NEW - What We Computed):
```
User 1: 30 tokens/sec  ─┐
User 2: 30 tokens/sec   │
User 3: 30 tokens/sec   │
...                     ├─→ SYSTEM TOTAL
User 10: 30 tokens/sec ─┘

Aggregate: 10 × 30 = 300 tokens/sec

Metric shown: 300 tokens/sec (system)
```

**This is SYSTEM CAPACITY** - how many tokens your hardware generates total.

---

## 📊 What Each Chart Shows

### aggregate_throughput.png (4 Panels):

```
┌─────────────────────────┬─────────────────────────┐
│ Panel 1:                │ Panel 2:                │
│ Aggregate Throughput    │ Request Concurrency     │
│                         │                         │
│ Shows: System tok/s     │ Shows: # concurrent     │
│ over time               │ requests per window     │
│                         │                         │
│ 📈 Line chart with fill │ 📊 Bar chart            │
└─────────────────────────┴─────────────────────────┘
┌─────────────────────────┬─────────────────────────┐
│ Panel 3:                │ Panel 4:                │
│ Cumulative Tokens       │ Per-User vs Aggregate   │
│                         │                         │
│ Shows: Total tokens     │ Shows: Both metrics     │
│ generated over time     │ overlaid for comparison │
│                         │                         │
│ 📈 Filled area + stats  │ 📊 Overlay chart        │
└─────────────────────────┴─────────────────────────┘
```

---

## 🔬 How We Calculate It

### Step-by-Step:

```python
# 1. Get all timestamps and token counts
timestamps = [t1, t2, t3, ..., t1200]
tokens = [tok1, tok2, tok3, ..., tok1200]

# 2. Divide into 10-second windows
window_size = 10 seconds

# 3. For each window:
for window in time_windows:
    # Sum all tokens generated in this window
    total_tokens_in_window = sum(tokens in window)

    # Calculate throughput
    aggregate_tps = total_tokens_in_window / 10

# 4. Plot over time!
```

**Result:** You see how your **entire system** performs over time!

---

## 💡 Why This Matters

### For Capacity Planning:
```
Question: "Can we handle 2x more users?"

Check aggregate throughput:
  Current: 500 tok/s (system total)
  Need for 2x: 1,000 tok/s

Answer: Check if your hardware can deliver 1,000 tok/s
```

### For Cost Analysis:
```
Question: "What's our cost per million tokens?"

Use aggregate throughput:
  GPU cost: $5/hour
  Aggregate: 500 tok/s = 1.8M tokens/hour

Cost: $5 / 1.8M = $2.78 per million tokens
```

### For Optimization:
```
Question: "Where's our bottleneck?"

Check aggregate throughput chart:
  - If flat line → system at max capacity
  - If declining → performance degradation
  - If spiky → resource contention
```

---

## 📈 What Your Charts Will Show

### With 1,200 Requests Over 5 Minutes:

You'll see:
- ✅ **How throughput changes over time** (stable? increasing? decreasing?)
- ✅ **Traffic patterns** (steady load? bursts?)
- ✅ **Total productivity** (cumulative tokens)
- ✅ **Concurrency effectiveness** (per-user vs aggregate ratio)

---

## 🎯 Quick Reference

| Metric | Perspective | Formula | Use For |
|--------|-------------|---------|---------|
| **Per-User** | Individual | tokens/response_time | UX, SLAs |
| **Aggregate** | System | Σ(tokens)/time_window | Capacity, costs |

**Both are important! Both are now visualized!**

---

## 🚀 View Your New Charts

```bash
# Interactive (zoom, pan, explore)
firefox performance_visualizations/aggregate_throughput.html

# Static (print, present, share)
eog performance_visualizations/aggregate_throughput.png

# Complete dashboard (everything in one place)
firefox performance_visualizations/dashboard.html
```

---

## 🎉 Summary

### You Now Have:

✅ **System-level throughput metrics** - How much your hardware can do
✅ **Per-user metrics** - How fast each user gets tokens
✅ **Both visualized together** - Complete picture
✅ **Computed from raw data** - Not pre-calculated
✅ **1,200 requests analyzed** - Strong statistical power
✅ **100% success rate** - Clean, reliable data

### Using Latest Technology:

✅ **Plotly** - Interactive charts with zoom/pan
✅ **Matplotlib** - Publication-quality 300 DPI
✅ **Seaborn** - Beautiful statistical defaults
✅ **Best practices** - Research-based methodology

---

## 💪 What You Can Do With This

1. **Understand System Capacity** - Total tokens/sec your system can handle
2. **Plan Infrastructure** - How many GPUs needed for X users
3. **Optimize Costs** - Calculate $/token at current capacity
4. **Detect Bottlenecks** - Where throughput stops scaling
5. **Monitor Health** - Track aggregate throughput trends
6. **Benchmark Changes** - Compare before/after optimizations

---

**🎨 Your system's performance is now fully visualized!**

**📊 Both user-level AND system-level metrics available!**

**🚀 Open the charts and discover your system's true capacity!**

---

*Generated: October 4, 2025*
*Dataset: 1,200 requests (5 minutes)*
*New Feature: Aggregate System Throughput*
*Technology: Latest Python visualization libraries*

