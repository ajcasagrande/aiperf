use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::collections::HashMap;
use std::time::{Duration, Instant};
use futures_util::StreamExt;
use reqwest::Client;
use serde_json::Value;
use tokio::runtime::Runtime;

#[pyclass]
#[derive(Debug, Clone)]
pub struct StreamingOptions {
    #[pyo3(get, set)]
    pub timeout_ms: u64,
    #[pyo3(get, set)]
    pub connect_timeout_ms: u64,
    #[pyo3(get, set)]
    pub chunk_size: usize,
    #[pyo3(get, set)]
    pub enable_compression: bool,
    #[pyo3(get, set)]
    pub max_redirects: usize,
    #[pyo3(get, set)]
    pub user_agent: String,
}

#[pymethods]
impl StreamingOptions {
    #[new]
    #[pyo3(signature = (
        timeout_ms = 30000,
        connect_timeout_ms = 5000,
        chunk_size = 8192,
        enable_compression = true,
        max_redirects = 3,
        user_agent = "aiperf-streaming/1.0".to_string()
    ))]
    pub fn new(
        timeout_ms: u64,
        connect_timeout_ms: u64,
        chunk_size: usize,
        enable_compression: bool,
        max_redirects: usize,
        user_agent: String,
    ) -> Self {
        StreamingOptions {
            timeout_ms,
            connect_timeout_ms,
            chunk_size,
            enable_compression,
            max_redirects,
            user_agent,
        }
    }
}

#[pyclass]
pub struct StreamingResponse {
    #[pyo3(get)]
    pub chunks: Vec<StreamingChunk>,
    #[pyo3(get)]
    pub start_timestamp_ns: u128,
    #[pyo3(get)]
    pub first_chunk_timestamp_ns: Option<u128>,
    #[pyo3(get)]
    pub last_chunk_timestamp_ns: Option<u128>,
    #[pyo3(get)]
    pub total_duration_ns: Option<u128>,
    #[pyo3(get)]
    pub status_code: u16,
    #[pyo3(get)]
    pub headers: HashMap<String, String>,
    #[pyo3(get)]
    pub error: Option<String>,
}

#[pyclass]
#[derive(Debug, Clone)]
pub struct StreamingChunk {
    #[pyo3(get)]
    pub data: String,
    #[pyo3(get)]
    pub timestamp_ns: u128,
    #[pyo3(get)]
    pub chunk_index: usize,
    #[pyo3(get)]
    pub is_sse_data: bool,
}

#[pyclass]
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum RequestTimerKind {
    RequestStart = 0,
    RequestEnd = 1,
    SendStart = 2,
    SendEnd = 3,
    RecvStart = 4,
    RecvEnd = 5,
    RecvChunk = 6,
}

#[pymethods]
impl RequestTimerKind {
    #[classattr]
    const REQUEST_START: Self = RequestTimerKind::RequestStart;

    #[classattr]
    const REQUEST_END: Self = RequestTimerKind::RequestEnd;

    #[classattr]
    const SEND_START: Self = RequestTimerKind::SendStart;

    #[classattr]
    const SEND_END: Self = RequestTimerKind::SendEnd;

    #[classattr]
    const RECV_START: Self = RequestTimerKind::RecvStart;

    #[classattr]
    const RECV_END: Self = RequestTimerKind::RecvEnd;

    #[classattr]
    const RECV_CHUNK: Self = RequestTimerKind::RecvChunk;
}

#[pyclass]
pub struct RequestTimers {
    timestamps: HashMap<RequestTimerKind, u128>,
    start_instant: Instant,
}

#[pymethods]
impl RequestTimers {
    #[new]
    pub fn new() -> Self {
        let mut instance = RequestTimers {
            timestamps: HashMap::new(),
            start_instant: Instant::now(),
        };
        instance.reset();
        instance
    }

    pub fn reset(&mut self) {
        self.timestamps.clear();
        self.start_instant = Instant::now();
    }

    pub fn timestamp(&self, kind: RequestTimerKind) -> PyResult<u128> {
        match self.timestamps.get(&kind) {
            Some(&timestamp) => Ok(timestamp),
            None => Err(PyErr::new::<pyo3::exceptions::PyKeyError, _>(
                format!("Timestamp kind {:?} not found", kind)
            )),
        }
    }

    pub fn capture_timestamp(&mut self, kind: RequestTimerKind) -> u128 {
        let timestamp_ns = self.start_instant.elapsed().as_nanos();
        self.timestamps.insert(kind, timestamp_ns);
        timestamp_ns
    }

    pub fn duration(&self, start: RequestTimerKind, end: RequestTimerKind) -> u128 {
        let start_time = self.timestamps.get(&start).copied().unwrap_or(0);
        let end_time = self.timestamps.get(&end).copied().unwrap_or(0);

        // If the start or end timestamp is 0 then can't calculate the
        // duration, so return max to indicate error.
        if start_time == 0 || end_time == 0 {
            return u128::MAX;
        }

        if start_time > end_time {
            u128::MAX
        } else {
            end_time - start_time
        }
    }
}

#[pymethods]
impl StreamingChunk {
    #[new]
    pub fn new(data: String, timestamp_ns: u128, chunk_index: usize, is_sse_data: bool) -> Self {
        StreamingChunk {
            data,
            timestamp_ns,
            chunk_index,
            is_sse_data,
        }
    }
}

#[pyclass]
pub struct StreamingHttpClient {
    runtime: Runtime,
    timers: RequestTimers,
}

#[pymethods]
impl StreamingHttpClient {
    #[new]
    pub fn new() -> PyResult<Self> {
        let runtime = Runtime::new()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to create tokio runtime: {}", e)))?;

        let timers = RequestTimers::new();

        Ok(StreamingHttpClient { runtime, timers })
    }

    #[pyo3(signature = (url, headers = None, payload = None, options = None))]
    pub fn post_stream(
        &mut self,
        url: &str,
        headers: Option<&PyDict>,
        payload: Option<&PyDict>,
        options: Option<StreamingOptions>,
    ) -> PyResult<StreamingResponse> {
        let url = url.to_string();
        let headers_map = self.convert_headers(headers)?;
        let payload_value = self.convert_payload(payload)?;
        let options = options.unwrap_or_else(|| StreamingOptions::new(30000, 5000, 8192, true, 3, "aiperf-streaming/1.0".to_string()));

        let result = {
            let timers = &mut self.timers;
            self.runtime.block_on(async move {
                Self::execute_post_stream_static(timers, url, headers_map, payload_value, options).await
            })
        };
        result
    }
}

impl StreamingHttpClient {
    fn convert_headers(&self, headers: Option<&PyDict>) -> PyResult<HashMap<String, String>> {
        let mut headers_map = HashMap::new();

        if let Some(py_headers) = headers {
            for (key, value) in py_headers.iter() {
                let key_str = key.extract::<String>()?;
                let value_str = value.extract::<String>()?;
                headers_map.insert(key_str, value_str);
            }
        }

        Ok(headers_map)
    }

    fn convert_payload(&self, payload: Option<&PyDict>) -> PyResult<Option<Value>> {
        if let Some(py_payload) = payload {
            // Convert Python dict to JSON Value
            let json_str = match py_payload.get_item("__json__") {
                Ok(Some(item)) => match item.extract::<String>() {
                    Ok(s) => s,
                    Err(_) => {
                        // Fallback: convert dict to JSON manually
                        let mut json_map = serde_json::Map::new();
                        for (key, value) in py_payload.iter() {
                            if let (Ok(k), Ok(v)) = (key.extract::<String>(), value.extract::<String>()) {
                                json_map.insert(k, Value::String(v));
                            }
                        }
                        serde_json::to_string(&json_map).unwrap_or_default()
                    }
                },
                _ => {
                    // Fallback: convert dict to JSON manually
                    let mut json_map = serde_json::Map::new();
                    for (key, value) in py_payload.iter() {
                        if let (Ok(k), Ok(v)) = (key.extract::<String>(), value.extract::<String>()) {
                            json_map.insert(k, Value::String(v));
                        }
                    }
                    serde_json::to_string(&json_map).unwrap_or_default()
                }
            };

            serde_json::from_str(&json_str)
                .map(Some)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid JSON payload: {}", e)))
        } else {
            Ok(None)
        }
    }

    async fn execute_post_stream_static(
        timers: &mut RequestTimers,
        url: String,
        headers: HashMap<String, String>,
        payload: Option<Value>,
        options: StreamingOptions,
    ) -> PyResult<StreamingResponse> {
        // Reset and start timing
        timers.reset();
        let req_start_timestamp = timers.capture_timestamp(RequestTimerKind::RequestStart);

        // Build the client with options
        let mut client_builder = Client::builder()
            .timeout(Duration::from_millis(options.timeout_ms))
            .connect_timeout(Duration::from_millis(options.connect_timeout_ms))
            .redirect(reqwest::redirect::Policy::limited(options.max_redirects))
            .user_agent(&options.user_agent);

        if !options.enable_compression {
            client_builder = client_builder.no_gzip();
        }

        let client = client_builder
            .build()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to build client: {}", e)))?;

        // Build request
        let mut request_builder = client.post(&url);

        // Add headers
        for (key, value) in headers {
            request_builder = request_builder.header(&key, &value);
        }

        // Add payload if provided
        if let Some(json_payload) = payload {
            request_builder = request_builder.json(&json_payload);
        }

        // Execute request
        timers.capture_timestamp(RequestTimerKind::SendStart);

        let response = match request_builder.send().await {
            Ok(resp) => resp,
            Err(e) => {
                return Ok(StreamingResponse {
                    chunks: vec![],
                    start_timestamp_ns: req_start_timestamp,
                    first_chunk_timestamp_ns: None,
                    last_chunk_timestamp_ns: None,
                    total_duration_ns: None,
                    status_code: 0,
                    headers: HashMap::new(),
                    error: Some(format!("Request failed: {}", e)),
                });
            }
        };

        timers.capture_timestamp(RequestTimerKind::SendEnd);

        // Extract response metadata
        let status_code = response.status().as_u16();
        let headers_map: HashMap<String, String> = response
            .headers()
            .iter()
            .filter_map(|(k, v)| {
                v.to_str()
                    .ok()
                    .map(|v_str| (k.to_string(), v_str.to_string()))
            })
            .collect();

        // Check for error status
        if !response.status().is_success() {
            let error_text = response.text().await.unwrap_or_else(|_| "Unknown error".to_string());
            return Ok(StreamingResponse {
                chunks: vec![],
                start_timestamp_ns: req_start_timestamp,
                first_chunk_timestamp_ns: None,
                last_chunk_timestamp_ns: None,
                total_duration_ns: None,
                status_code,
                headers: headers_map,
                error: Some(format!("HTTP {}: {}", status_code, error_text)),
            });
        }

        // Start receiving response
        let recv_start_timestamp = timers.capture_timestamp(RequestTimerKind::RecvStart);

        let mut chunks = Vec::new();
        let mut chunk_index = 0;
        let mut first_chunk_timestamp = None;
        let mut last_chunk_timestamp = None;
        let mut buffer = String::new();

        // Stream the response
        let mut stream = response.bytes_stream();

        while let Some(chunk_result) = stream.next().await {
            let chunk_timestamp = timers.capture_timestamp(RequestTimerKind::RecvChunk);

            if first_chunk_timestamp.is_none() {
                first_chunk_timestamp = Some(chunk_timestamp);
            }
            last_chunk_timestamp = Some(chunk_timestamp);

            match chunk_result {
                Ok(bytes_chunk) => {
                    let chunk_str = String::from_utf8_lossy(&bytes_chunk).to_string();
                    buffer.push_str(&chunk_str);

                    // Process SSE data
                    Self::process_sse_buffer(&mut buffer, &mut chunks, chunk_timestamp, &mut chunk_index);
                }
                Err(e) => {
                    chunks.push(StreamingChunk::new(
                        format!("Error: {}", e),
                        chunk_timestamp,
                        chunk_index,
                        false,
                    ));
                    break;
                }
            }
        }

        // Process any remaining buffer content
        if !buffer.is_empty() {
            Self::process_remaining_buffer(&mut buffer, &mut chunks, last_chunk_timestamp.unwrap_or(recv_start_timestamp), &mut chunk_index);
        }

        timers.capture_timestamp(RequestTimerKind::RecvEnd);
        let end_timestamp = timers.capture_timestamp(RequestTimerKind::RequestEnd);

        let total_duration = if recv_start_timestamp > 0 && end_timestamp > recv_start_timestamp {
            Some(end_timestamp - recv_start_timestamp)
        } else {
            None
        };

        Ok(StreamingResponse {
            chunks,
            start_timestamp_ns: recv_start_timestamp,
            first_chunk_timestamp_ns: first_chunk_timestamp,
            last_chunk_timestamp_ns: last_chunk_timestamp,
            total_duration_ns: total_duration,
            status_code,
            headers: headers_map,
            error: None,
        })
    }

    fn process_sse_buffer(
        buffer: &mut String,
        chunks: &mut Vec<StreamingChunk>,
        timestamp: u128,
        chunk_index: &mut usize,
    ) {
        while let Some(line_end) = buffer.find('\n') {
            let line = buffer.drain(..=line_end).collect::<String>();
            let line = line.trim();

            if line.is_empty() {
                continue;
            }

            if line.starts_with("data: ") {
                let data_content = &line[6..]; // Remove "data: " prefix

                // Skip [DONE] marker
                if data_content == "[DONE]" {
                    break;
                }

                // Skip empty data at the start
                if data_content.trim().is_empty() && chunks.is_empty() {
                    continue;
                }

                chunks.push(StreamingChunk::new(
                    data_content.to_string(),
                    timestamp,
                    *chunk_index,
                    true,
                ));
                *chunk_index += 1;
            } else if line.starts_with("event: error") {
                chunks.push(StreamingChunk::new(
                    line.to_string(),
                    timestamp,
                    *chunk_index,
                    false,
                ));
                *chunk_index += 1;
                break;
            }
        }
    }

    fn process_remaining_buffer(
        buffer: &mut String,
        chunks: &mut Vec<StreamingChunk>,
        timestamp: u128,
        chunk_index: &mut usize,
    ) {
        if !buffer.trim().is_empty() {
            chunks.push(StreamingChunk::new(
                buffer.clone(),
                timestamp,
                *chunk_index,
                false,
            ));
        }
    }
}

#[pymodule]
fn aiperf_streaming(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<StreamingOptions>()?;
    m.add_class::<StreamingResponse>()?;
    m.add_class::<StreamingChunk>()?;
    m.add_class::<StreamingHttpClient>()?;
    m.add_class::<RequestTimerKind>()?;
    m.add_class::<RequestTimers>()?;
    Ok(())
}
