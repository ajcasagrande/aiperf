<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
- AioHttp Client Session is created
    - no request is made to server yet
- `record.start_perf_ns = time.perf_counter_ns()`
    - store the time at which the request starts
- `session.post(...)`
    - will make new tcp connection, or re-use existing from pool.
- Read the response code of the POST
- If response code != 200 OK:
    - read error response and return
- `record.recv_start_perf_ns = time.perf_counter_ns()`
    - this is the time at which we start receiving actual content from the server (NOTE: This is NOT the same as TTFT. In the case of streaming, this is the time at which the server responds with a 200 OK initializing the stream)
- If response content_type is `text/event-stream`:
    - process the rest of the response using our custom Async SSE Stream Reader
    - `responses = AioHttpSSEStreamReader(response).read_complete_stream()`
- Otherwise (non-streaming):
    - read the rest of the response body as text
    - `record.end_perf_ns = time.perf_counter_ns()`

Custom Async SSE Stream Reader:
- While the stream is not at EOF
  - read a single byte of the stream
      - This will block until data is available from the server
      - `responses[i].perf_ns = time.perf_counter_ns()`
  - continue reading the stream until you see a blank line (`\n\n`) (this denotes the end of an SSE message delimiter)
  - decode the bytes, parse SSE fields (data/event, etc.)

TTFT: `responses[0].perf_ns - record.start_perf_ns`, where responses[0] is first non-empty SSE data payload
TTST: `responses[1].perf_ns - responses[0].perf_ns`, where both responses are non-empty SSE data payloads
Request Latency: `responses[-1].perf_ns - record.start_perf_ns`, time of last packet minus start time
ITL: `(request_latency - ttft) / (osl - 1)`, avg of inter-arrival times excluding first token