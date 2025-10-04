<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# 🔧 Troubleshooting Guide - NVIDIA AIPerf Dashboard v3

## 🐛 Common Issues & Solutions

### **Issue: "Extra data: line 1 column XXXX" Error**

**Problem:** This happens when trying to parse a JSONL file as a single JSON object.

**✅ FIXED!** We've added robust error handling:
- Line-by-line JSONL parsing
- Skip malformed lines with warnings
- Better error messages
- Validation checks

**Solution:**
1. Restart the backend server:
   ```bash
   cd backend
   source venv/bin/activate
   python main.py
   ```

2. Try uploading again - the improved parser will:
   - Parse each line separately
   - Skip any malformed lines
   - Show warnings in console
   - Process valid records

---

### **Issue: "Cannot read properties of undefined (reading 'slice')" Error**

**Problem:** This happens when the AI insights API returns data without `key_findings` or `recommendations` arrays.

**✅ FIXED!** We've added null safety checks:
- Optional chaining for array access
- Fallback empty arrays
- Safe score handling with nullish coalescing
- Graceful degradation

**Solution:**
The fix has been applied to the dashboard code. The dashboard will now:
- Safely handle missing insight arrays
- Display empty insights sections gracefully
- Default score to 0 if undefined
- Continue rendering without errors

---

### **Issue: "Cannot read properties of undefined (reading 'map')" Error in Charts**

**Problem:** This happens when chart components receive undefined or incomplete data.

**✅ FIXED!** We've added defensive guards to all chart components:
- ComparisonChart checks for valid comparison data
- LatencyChart checks for non-empty records
- ThroughputChart checks for non-empty records
- DistributionChart checks for valid stats
- All charts display friendly "No data available" messages

**Solution:**
Charts now gracefully handle edge cases and display helpful messages when data is missing.

---

### **Issue: "No comparison data available" in Comparison Page**

**Problem:** The comparison page shows "No comparison data available" even when data exists, and the table shows N/A for all values.

**✅ FIXED!** The API client was returning the full response wrapper instead of the actual data:
- Fixed `compareBenchmarks()` to return `response.data.comparison` instead of `response.data`
- Fixed `getInsights()` to return `response.data.insights`
- Fixed `listBenchmarks()` to return `response.data.benchmarks`
- Updated all frontend code to match the new API structure

**Solution:**
The comparison page now displays real data with accurate metric values, charts, and winner identification.

---

### **Issue: Metrics Showing Empty/Zero After API Changes**

**Problem:** Token throughput, request throughput, and goodput showing as empty or 0 even though backend has correct data.

**✅ FIXED!** React Query was caching old data from before the API client changes:
- Added `refetchOnMount: true` to all queries
- Added `staleTime: 0` to force fresh data fetch
- Added debug logging to track data flow

**Solution:**
1. Hard refresh your browser (Ctrl+Shift+R or Cmd+Shift+R)
2. Check browser console for debug logs showing metric values
3. The dashboard will now always fetch fresh data on load

---

### **Issue: Upload Fails**

**Possible Causes:**

#### **1. Backend not running**
```bash
# Check if backend is running
curl http://localhost:8000

# Should return:
# {"service":"NVIDIA AIPerf Dashboard v3","status":"operational",...}
```

**Solution:** Start backend
```bash
cd backend
source venv/bin/activate
python main.py
```

#### **2. Wrong file type**
**Error:** "JSONL file must have .jsonl extension"

**Solution:**
- Make sure your file ends with `.jsonl`
- Not `.json` or `.txt`

#### **3. Empty file**
**Error:** "JSONL file is empty"

**Solution:**
- Check file has content
- File should have one JSON object per line

#### **4. Malformed JSONL**
**Error:** "No valid records found in JSONL file"

**Solution:**
- Each line must be valid JSON
- Check for syntax errors
- Use a JSONL validator

---

### **Issue: No Data Showing in Dashboard**

**Possible Causes:**

#### **1. No benchmarks uploaded**
**Solution:** Upload a benchmark first!

#### **2. Backend not connected**
**Check:** Open browser console (F12) and look for network errors

**Solution:**
```bash
# Verify backend is running
curl http://localhost:8000/api/v3/benchmarks

# Should return list of benchmarks
```

#### **3. CORS issues**
**Error in console:** "CORS policy blocked"

**Solution:** Backend already has CORS enabled, but check:
```python
# In backend/main.py - should be there:
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    ...
)
```

---

### **Issue: Comparison Not Working**

**Possible Causes:**

#### **1. Less than 2 benchmarks selected**
**Solution:** Select at least 2 benchmarks to compare

#### **2. No metrics selected**
**Solution:** Toggle at least one metric button (green = selected)

#### **3. Backend comparison error**
**Check console:** Look for error messages

**Solution:**
```bash
# Restart backend
cd backend
python main.py
```

---

### **Issue: Charts Not Rendering**

**Possible Causes:**

#### **1. No data in records**
**Solution:** Upload a JSONL file with actual records

#### **2. Missing metrics in data**
**Solution:** Make sure your JSONL has the required metrics:
- `request_latency`
- `ttft`
- `output_sequence_length`
- etc.

#### **3. Browser compatibility**
**Solution:** Use Chrome, Edge, or Firefox (latest versions)

---

### **Issue: Slow Performance**

**Possible Causes:**

#### **1. Large JSONL file**
**Note:** Dashboard limits charts to first 100-200 records for performance

**Solution:**
- This is intentional for smooth UX
- Full data is still processed for statistics
- Consider sampling large files

#### **2. Many benchmarks**
**Solution:**
- Clear comparison selection
- Use "Clear All" button
- Refresh page

---

## 🧪 Testing Your Upload

### **Test with Sample Data**

Create a test JSONL file:

```bash
cat > test_benchmark.jsonl << 'EOF'
{"metadata":{"x_request_id":"req1","timestamp_ns":1000000000,"worker_id":"w1","record_processor_id":"rp1","credit_phase":"prefill"},"metrics":{"request_latency":{"value":1000,"unit":"ms"},"ttft":{"value":200,"unit":"ms"},"output_sequence_length":{"value":100,"unit":"tokens"}}}
{"metadata":{"x_request_id":"req2","timestamp_ns":2000000000,"worker_id":"w1","record_processor_id":"rp1","credit_phase":"prefill"},"metrics":{"request_latency":{"value":1200,"unit":"ms"},"ttft":{"value":180,"unit":"ms"},"output_sequence_length":{"value":120,"unit":"tokens"}}}
{"metadata":{"x_request_id":"req3","timestamp_ns":3000000000,"worker_id":"w1","record_processor_id":"rp1","credit_phase":"prefill"},"metrics":{"request_latency":{"value":900,"unit":"ms"},"ttft":{"value":210,"unit":"ms"},"output_sequence_length":{"value":90,"unit":"tokens"}}}
EOF
```

Then upload `test_benchmark.jsonl` via the dashboard!

---

## 🔍 Debugging Tips

### **Backend Logs**

Check backend terminal for:
```
Warning: Skipping malformed JSON at line X
```

This means the parser found and skipped a bad line.

### **Frontend Logs**

Open browser console (F12) and check:
- Network tab for API calls
- Console tab for errors
- React Query Dev Tools (if enabled)

### **Check Data Directory**

```bash
ls -la ultimate_dashboard_v3/data/

# Should see:
# index.json
# benchmark_XXXXXXXX_XXXXXX/
```

### **Validate JSONL File**

```python
import json

# Check if JSONL is valid
with open('your_file.jsonl') as f:
    for i, line in enumerate(f, 1):
        try:
            json.loads(line)
            print(f"Line {i}: OK")
        except json.JSONDecodeError as e:
            print(f"Line {i}: ERROR - {e}")
```

---

## 📞 Still Having Issues?

### **1. Check Prerequisites**

```bash
# Python version
python --version  # Should be 3.10+

# Node version
node --version   # Should be 18+

# Dependencies installed?
cd backend && pip list | grep fastapi
cd frontend && npm list | grep next
```

### **2. Clean Install**

```bash
# Backend
cd backend
rm -rf venv
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend
rm -rf node_modules .next
npm install
```

### **3. Reset Data**

```bash
# WARNING: This deletes all uploaded benchmarks
rm -rf ultimate_dashboard_v3/data/*
```

### **4. Check Ports**

```bash
# Make sure ports are free
lsof -i :3000  # Frontend
lsof -i :8000  # Backend

# Kill if needed
kill -9 <PID>
```

---

## ✅ Verification Checklist

- [ ] Backend running on port 8000
- [ ] Frontend running on port 3000
- [ ] Can access http://localhost:3000
- [ ] Can see homepage
- [ ] Upload button appears
- [ ] File upload modal opens
- [ ] Can select/drag files
- [ ] Upload succeeds
- [ ] Dashboard shows data
- [ ] Charts render
- [ ] Can switch benchmarks
- [ ] Comparison page works
- [ ] Can select benchmarks
- [ ] Comparison charts appear

---

## 🎯 Quick Fixes Summary

| Problem | Quick Fix |
|---------|-----------|
| JSON parse error | ✅ **FIXED** - restart backend |
| "Cannot read properties of undefined" | ✅ **FIXED** - null safety added |
| Chart "Cannot read...map" error | ✅ **FIXED** - defensive guards added |
| "No comparison data available" | ✅ **FIXED** - API client data extraction |
| Metrics showing 0.00 | ✅ **FIXED** - aggregate data integration |
| Upload fails | Check file extension (.jsonl) |
| No data showing | Upload benchmark first |
| Backend error | Restart: `python main.py` |
| Frontend error | Restart: `npm run dev` |
| CORS error | Already fixed in code |
| Slow charts | Intentional - limits to 100-200 points |
| Comparison empty | Select 2+ benchmarks |

---

## 🚀 After Fixes

The dashboard now has:
- ✅ **Robust JSONL parsing** - handles malformed lines
- ✅ **Better error messages** - tells you exactly what went wrong
- ✅ **Validation checks** - file types, empty files, etc.
- ✅ **Error recovery** - skips bad lines, continues processing
- ✅ **Detailed logging** - see what's happening in terminal
- ✅ **Null safety** - handles undefined data gracefully
- ✅ **Graceful degradation** - displays empty sections when data is missing

**Just restart both frontend and backend and try again!** 🔥

---

<div align="center">

**🛠️ Most issues are fixed by restarting the backend!**

```bash
cd backend
python main.py
```

</div>
