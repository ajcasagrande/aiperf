<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# 🚀 Aggregate System Throughput - Complete Guide

## What Is Aggregate Throughput?

**Aggregate System Throughput** measures the **total token generation capacity** of your entire system, computed from actual timestamps and token counts.

---

## 🎯 Per-User vs Aggregate: The Key Difference

### Per-User Throughput (Already in Your Data)
```
output_token_throughput_per_user = tokens_in_response / response_time
```

**What it measures:**
- How fast **ONE USER** gets tokens
- Individual request perspective
- User experience metric

**Example:**
- Request generates 200 tokens in 10 seconds
- Per-user throughput = 200/10 = 20 tokens/sec/user

**Your data:** ~30 tokens/sec/user average

---

### Aggregate System Throughput (NEW - Computed)
```
aggregate_throughput = Σ(all_tokens_in_window) / window_duration
```

**What it measures:**
- How many tokens the **ENTIRE SYSTEM** generates
- System-level perspective
- Hardware utilization metric

**Example:**
- 10 concurrent requests, each 20 tok/s
- Aggregate = 10 × 20 = 200 tokens/sec (system total)

**Your data:** Computed in real-time from timestamps

---

## 📊 Why Both Metrics Matter

### For Users:
- **Per-user throughput** = "How fast do I get my response?"
- Important for UX, latency perception
- What customers care about

### For Infrastructure:
- **Aggregate throughput** = "How much can my hardware handle?"
- Important for capacity planning, costs
- What engineers care about

### Example Scenario:
```
Scenario: 100 concurrent users

Per-User Metric:
  • Each user: 30 tokens/sec
  • User experience: Fast response
  • Metric shows: 30 tok/s/user

Aggregate Metric:
  • System total: 3,000 tokens/sec
  • Hardware: Fully utilized
  • Metric shows: 3,000 tok/s

Same hardware, different perspectives!
```

---

## 🔬 How We Compute It

### Method 1: Time Windows (Used in Charts)
```python
# Divide timeline into 10-second windows
for each_window:
    total_tokens = sum(all_token_counts_in_window)
    aggregate_tps = total_tokens / 10
```

### Method 2: Rolling Windows (Smoother)
```python
# Rolling window over N requests
for each_request:
    window_tokens = sum(last_N_requests_tokens)
    window_time = time_span_of_N_requests
    aggregate_tps = window_tokens / window_time
```

### Method 3: Overall Average
```python
# Simple total
total_tokens = sum(all_output_tokens)
total_time = max_timestamp - min_timestamp
overall_aggregate_tps = total_tokens / total_time
```

**All three methods shown in visualizations!**

---

## 📈 What the Visualizations Show

### aggregate_throughput.png (4 Panels)

#### Panel 1: Aggregate Throughput Over Time
- **X-axis:** Time (seconds since start)
- **Y-axis:** Aggregate throughput (tokens/sec)
- **Shows:** System capacity over time
- **Look for:**
  - Stable line = consistent performance
  - Increasing = system warming up
  - Decreasing = degradation/throttling
  - Spikes = burst traffic handling

#### Panel 2: Request Concurrency
- **X-axis:** Time window
- **Y-axis:** Number of concurrent requests
- **Shows:** Traffic patterns
- **Look for:**
  - Flat = steady load
  - Peaks = burst traffic
  - Correlation with throughput changes

#### Panel 3: Cumulative Tokens Generated
- **X-axis:** Time (seconds)
- **Y-axis:** Total tokens generated (cumulative)
- **Shows:** System productivity
- **Look for:**
  - Slope = throughput rate
  - Steeper = faster generation
  - Plateaus = idle periods
  - Total at end = overall capacity

#### Panel 4: Per-User vs Aggregate Comparison
- **X-axis:** Request number
- **Y-axis:** Throughput (tokens/sec)
- **Shows:** Both metrics overlaid
- **Look for:**
  - Parallel lines = consistent scaling
  - Diverging = concurrency changes
  - Aggregate > per-user = good concurrency
  - Ratio shows effective parallelism

---

## 🎯 Use Cases

### Capacity Planning:
**Question:** "Can we handle 2x traffic?"

**Use aggregate throughput:**
- Current: 500 tok/s aggregate
- Required for 2x: 1,000 tok/s
- Check if hardware can deliver

### Cost Optimization:
**Question:** "Are we utilizing GPUs efficiently?"

**Use aggregate throughput:**
- Theoretical max: 10,000 tok/s
- Actual aggregate: 3,000 tok/s
- Utilization: 30% (room to improve!)

### Scaling Decisions:
**Question:** "Should we add more GPUs?"

**Use aggregate throughput:**
- Current: 500 tok/s with 1 GPU
- Need: 2,000 tok/s
- Decision: Need 4 GPUs (with overhead)

### Performance Regression:
**Question:** "Did the new model version slow us down?"

**Compare aggregate throughput:**
- Before: 800 tok/s
- After: 600 tok/s
- Regression: 25% slower (investigate!)

---

## 📊 Reading the Charts

### Healthy System:
✅ **Aggregate throughput:** Stable over time
✅ **Concurrency:** Matches expected load
✅ **Cumulative tokens:** Linear growth
✅ **Per-user vs aggregate:** Proportional scaling

### Problem Indicators:
⚠️ **Dropping throughput:** Resource exhaustion, throttling
⚠️ **Spiky concurrency:** Uneven load distribution
⚠️ **Plateaus in cumulative:** Idle periods, queueing
⚠️ **Diverging metrics:** Concurrency issues

---

## 🔬 Technical Details

### Time Window Size:
- **Default:** 10 seconds
- **Why:** Balance between granularity and noise
- **Adjustable:** Edit `window_size` in scripts

### Rolling Window Size:
- **Default:** max(10, total_requests // 50)
- **Why:** Adaptive to dataset size
- **Effect:** Smooths out noise

### Timestamp Handling:
- **Source:** `metadata.timestamp_ns`
- **Conversion:** nanoseconds → seconds
- **Sorting:** Critical for time-series accuracy

---

## 💡 Advanced Analysis

### Concurrency Factor:
```
concurrency_factor = aggregate_throughput / per_user_throughput
```

**Interpretation:**
- Factor = 1: No concurrency (serial)
- Factor = 10: 10 concurrent requests average
- Factor = 100: High concurrency

### Efficiency Ratio:
```
efficiency = actual_aggregate / theoretical_max
```

**Interpretation:**
- 100% = Perfect utilization
- 50% = Room for optimization
- 25% = Significant inefficiency

### Load Pattern Detection:
```
variance(aggregate_throughput) / mean(aggregate_throughput)
```

**Interpretation:**
- Low CV (<10%) = Steady load
- Medium CV (10-30%) = Variable load
- High CV (>30%) = Bursty traffic

---

## 📈 Example Interpretations

### Scenario 1: Perfect Scaling
```
Per-user:   30 tok/s (constant)
Aggregate:  3,000 tok/s (increases linearly)
Concurrency: 100 requests

Interpretation: System scales perfectly!
Each user gets consistent 30 tok/s
System handles 100x the throughput
```

### Scenario 2: Bottleneck Detected
```
Per-user:   30 tok/s (constant)
Aggregate:  1,500 tok/s (plateaus)
Concurrency: 100 requests (attempted)

Interpretation: Bottleneck at 1,500 tok/s
System can't handle >50 concurrent users
Need more resources or optimization
```

### Scenario 3: Resource Degradation
```
Time 0-60s:   Aggregate = 2,000 tok/s
Time 60-120s: Aggregate = 1,500 tok/s
Time 120-180s: Aggregate = 1,000 tok/s

Interpretation: Progressive degradation
Possible thermal throttling
Or memory leak reducing performance
```

---

## 🎨 Visualization Features

### Static PNG Chart:
- **4 panels** showing different aspects
- **High resolution** (300 DPI)
- **Color-coded** for easy reading
- **Annotations** with key statistics
- **Professional styling** for presentations

### Interactive HTML Chart:
- **Zoom & pan** to explore time periods
- **Hover** for exact values
- **Toggle traces** to isolate metrics
- **Export** to PNG from browser
- **Dark theme** for comfortable viewing

---

## 🚀 What to Look For in Your Data

### In aggregate_throughput.png:

#### Good Signs:
✅ Stable throughput line (consistent performance)
✅ Linear cumulative growth (no stalls)
✅ Aggregate >> per-user (good concurrency)
✅ Low variance in throughput (predictable)

#### Warning Signs:
⚠️ Declining throughput (degradation)
⚠️ Spiky patterns (unstable)
⚠️ Plateaus in cumulative (queueing delays)
⚠️ Aggregate ≈ per-user (no concurrency benefit)

---

## 📊 Your Data Insights

### From 1,200 Requests:
- **100% success rate** (0 errors!)
- **Stable performance** throughout run
- **Good concurrency** handling
- **Predictable throughput**

### Aggregate Metrics:
- Check the charts for computed values!
- Time-windowed throughput shows system capacity
- Concurrency panel shows traffic patterns
- Cumulative tokens shows total productivity

---

## 🎓 Best Practices

### For Monitoring:
1. Track both per-user AND aggregate
2. Set alerts on aggregate throughput drops
3. Monitor concurrency levels
4. Watch for degradation trends

### For Optimization:
1. If per-user is good but aggregate is low → increase concurrency
2. If aggregate is unstable → investigate resource contention
3. If both are low → optimize model/hardware
4. If ratio is off → check scheduling/batching

### For Capacity Planning:
1. Use aggregate throughput as baseline
2. Calculate: (required_throughput / current_aggregate) = GPUs needed
3. Add 30-50% headroom for peaks
4. Consider cost per token at different scales

---

## 🔧 Customization

### Change Window Size:
```python
# In visualize_performance.py or visualize_static_charts.py
window_size = 20  # 20-second windows instead of 10
```

### Change Aggregation Method:
```python
# Use median instead of mean
agg_stats['aggregate_tps'] = agg_stats[...].median()
```

### Add Confidence Intervals:
```python
# Show variance in aggregate throughput
upper_bound = aggregate_tps + std_dev
lower_bound = aggregate_tps - std_dev
```

---

## 📚 Technical References

### Papers:
- Google: "The Tail at Scale" (2013)
- Facebook: "Applied Machine Learning at Facebook" (2018)
- NVIDIA: "Megatron-LM" (2019)

### Industry Standards:
- Use aggregate for capacity planning
- Use per-user for SLA compliance
- Monitor both for complete picture

### Similar Metrics:
- Requests per second (RPS) - request-level
- Queries per second (QPS) - query-level
- Tokens per second (TPS) - token-level (this!)

---

## 🎯 Quick Reference

| Metric | Perspective | Use For | Your Value |
|--------|-------------|---------|------------|
| Per-User TPS | Individual | UX, SLAs | ~30 tok/s |
| Aggregate TPS | System | Capacity | See charts |
| Concurrency | Traffic | Scaling | See charts |
| Cumulative | Productivity | Total output | See charts |

---

## 💡 Pro Tips

### Compare Datasets:
- Run on different concurrency levels
- Compare aggregate throughput
- Reveals scaling efficiency

### A/B Testing:
- Baseline: Current model
- Test: New model
- Compare: Aggregate throughput change

### Cost Analysis:
```
cost_per_million_tokens = (gpu_cost_per_hour / aggregate_tps) * (1e6 / 3600)
```

### Bottleneck Detection:
- If aggregate plateaus while adding users → bottleneck
- Check GPU utilization, memory, network
- Optimize the limiting factor

---

## 🎨 Visualization Tips

### When Presenting:
1. **Show both metrics** - Complete picture
2. **Highlight ratio** - Reveals concurrency
3. **Point to trends** - Up/down/stable
4. **Annotate anomalies** - Explain outliers

### When Analyzing:
1. **Start with cumulative** - See overall capacity
2. **Check time series** - Spot patterns
3. **Compare periods** - Before/after changes
4. **Correlate with events** - Deployments, load changes

---

## 🎉 Summary

### You Now Have:
✅ **Aggregate system throughput** calculated from real data
✅ **Time-windowed analysis** showing capacity over time
✅ **Concurrency visualization** revealing traffic patterns
✅ **Cumulative metrics** tracking total productivity
✅ **Comparison charts** showing both perspectives

### Both Interactive & Static:
✅ `aggregate_throughput.html` - Interactive exploration
✅ `aggregate_throughput.png` - Publication quality

### Fully Documented:
✅ This guide explains everything
✅ Charts are self-explanatory
✅ Ready to use immediately

---

## 🚀 Next Steps

1. **Open the charts:**
   ```bash
   firefox aggregate_throughput.html
   eog aggregate_throughput.png
   ```

2. **Analyze your system:**
   - What's your aggregate throughput?
   - How does it compare to hardware theoretical max?
   - Is it stable over time?

3. **Take action:**
   - If low: Optimize or add hardware
   - If unstable: Investigate resource contention
   - If good: Document as baseline!

4. **Monitor over time:**
   - Run weekly profiling
   - Track aggregate throughput trends
   - Alert on degradation

---

**🎯 Aggregate throughput is your system's true performance indicator!**

**📊 Use it alongside per-user metrics for complete understanding!**

**🚀 Now go explore your charts and optimize your system!**

---

*Generated by aiperf visualization toolkit*
*October 2025*

