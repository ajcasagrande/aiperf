use pyo3::prelude::*;
use reqwest::{Client, ClientBuilder};
use std::collections::HashMap;
use std::sync::Arc;
use tokio_stream::StreamExt;

use crate::request::{StreamingRequest, StreamingToken};
use crate::errors::StreamingError;
use crate::timer::PrecisionTimer;
use crate::timers::{RequestTimers, TimestampKind};

/// High-performance streaming HTTP client with precise timing
#[pyclass]
pub struct StreamingHttpClient {
    client: Arc<Client>,
    default_timeout_ms: Option<u64>,
    default_headers: HashMap<String, String>,
    timer: PrecisionTimer,
    runtime: Arc<tokio::runtime::Runtime>,
}

#[pymethods]
impl StreamingHttpClient {
    #[new]
    pub fn new(
        timeout_ms: Option<u64>,
        default_headers: Option<HashMap<String, String>>,
        user_agent: Option<String>,
    ) -> PyResult<Self> {
        let headers: HashMap<String, String> = default_headers.unwrap_or_default();

        let mut client_builder: ClientBuilder = Client::builder()
            .use_rustls_tls()
            .tcp_keepalive(Some(std::time::Duration::from_secs(30)))
            .pool_idle_timeout(Some(std::time::Duration::from_secs(90)))
            .pool_max_idle_per_host(32);

        if let Some(timeout) = timeout_ms {
            client_builder = client_builder.timeout(std::time::Duration::from_millis(timeout));
        }

        if let Some(ua) = user_agent {
            client_builder = client_builder.user_agent(ua);
        }

        let client = client_builder.build()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                format!("Failed to create HTTP client: {}", e)
            ))?;

        let runtime = tokio::runtime::Runtime::new()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                format!("Failed to create async runtime: {}", e)
            ))?;

        Ok(Self {
            client: Arc::new(client),
            default_timeout_ms: timeout_ms,
            default_headers: headers,
            timer: PrecisionTimer::new(),
            runtime: Arc::new(runtime),
        })
    }

    /// Execute a streaming request and return the timing information
    pub fn stream_request(
        &self,
        mut request: StreamingRequest,
    ) -> PyResult<RequestTimers> {
        let client = Arc::clone(&self.client);
        let runtime = Arc::clone(&self.runtime);
        let default_headers = self.default_headers.clone();
        let default_timeout = self.default_timeout_ms;

        let result = runtime.block_on(async {
            Self::execute_streaming_request_async(
                client,
                &mut request,
                &default_headers,
                default_timeout
            ).await
        });

        match result {
            Ok(_) => Ok(request.timers),
            Err(e) => Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                format!("Streaming request failed: {}", e)
            )),
        }
    }

    /// Execute a streaming request and return both the request and timing information
    pub fn stream_request_with_details(
        &self,
        mut request: StreamingRequest,
    ) -> PyResult<(StreamingRequest, RequestTimers)> {
        let client = Arc::clone(&self.client);
        let runtime = Arc::clone(&self.runtime);
        let default_headers = self.default_headers.clone();
        let default_timeout = self.default_timeout_ms;

        let result = runtime.block_on(async {
            Self::execute_streaming_request_async(
                client,
                &mut request,
                &default_headers,
                default_timeout
            ).await
        });

        match result {
            Ok(_) => {
                let timers = request.timers.clone();
                Ok((request, timers))
            },
            Err(e) => Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                format!("Streaming request failed: {}", e)
            )),
        }
    }

    /// Execute multiple streaming requests concurrently and return timing information
    pub fn stream_requests_concurrent(
        &self,
        requests: Vec<StreamingRequest>,
        max_concurrent: Option<usize>,
    ) -> PyResult<Vec<RequestTimers>> {
        let client = Arc::clone(&self.client);
        let runtime = Arc::clone(&self.runtime);
        let concurrent_limit = max_concurrent.unwrap_or(10);
        let default_headers = self.default_headers.clone();
        let default_timeout = self.default_timeout_ms;

        let result = runtime.block_on(async move {
            let mut completed_requests = Vec::new();
            let semaphore = Arc::new(tokio::sync::Semaphore::new(concurrent_limit));
            let mut handles = Vec::new();

            for mut request in requests {
                let client_clone = Arc::clone(&client);
                let semaphore_clone = Arc::clone(&semaphore);
                let headers_clone = default_headers.clone();

                let handle = tokio::spawn(async move {
                    let _permit = semaphore_clone.acquire().await.unwrap();

                    // Execute request and capture any errors in the request object
                    match Self::execute_streaming_request_async(
                        client_clone,
                        &mut request,
                        &headers_clone,
                        default_timeout
                    ).await {
                        Ok(_) => {
                            // Request succeeded
                        }
                        Err(e) => {
                            // Request failed - error details should already be in the request object
                            if request.error_message.is_none() {
                                request.set_error(format!("Request execution failed: {}", e));
                            }
                        }
                    }

                    request
                });

                handles.push(handle);
            }

            for handle in handles {
                match handle.await {
                    Ok(request) => completed_requests.push(request.timers),
                    Err(e) => {
                        eprintln!("Task execution failed: {}", e);
                        // Could create a failed request object here if needed
                    }
                }
            }

            completed_requests
        });

        Ok(result)
    }

    /// Execute multiple streaming requests concurrently and return both requests and timing information
    pub fn stream_requests_concurrent_with_details(
        &self,
        requests: Vec<StreamingRequest>,
        max_concurrent: Option<usize>,
    ) -> PyResult<Vec<(StreamingRequest, RequestTimers)>> {
        let client = Arc::clone(&self.client);
        let runtime = Arc::clone(&self.runtime);
        let concurrent_limit = max_concurrent.unwrap_or(10);
        let default_headers = self.default_headers.clone();
        let default_timeout = self.default_timeout_ms;

        let result = runtime.block_on(async move {
            let mut completed_requests = Vec::new();
            let semaphore = Arc::new(tokio::sync::Semaphore::new(concurrent_limit));
            let mut handles = Vec::new();

            for mut request in requests {
                let client_clone = Arc::clone(&client);
                let semaphore_clone = Arc::clone(&semaphore);
                let headers_clone = default_headers.clone();

                let handle = tokio::spawn(async move {
                    let _permit = semaphore_clone.acquire().await.unwrap();

                    // Execute request and capture any errors in the request object
                    match Self::execute_streaming_request_async(
                        client_clone,
                        &mut request,
                        &headers_clone,
                        default_timeout
                    ).await {
                        Ok(_) => {
                            // Request succeeded
                        }
                        Err(e) => {
                            // Request failed - error details should already be in the request object
                            if request.error_message.is_none() {
                                request.set_error(format!("Request execution failed: {}", e));
                            }
                        }
                    }

                    request
                });

                handles.push(handle);
            }

            for handle in handles {
                match handle.await {
                    Ok(request) => {
                        let timers = request.timers.clone();
                        completed_requests.push((request, timers));
                    },
                    Err(e) => {
                        eprintln!("Task execution failed: {}", e);
                        // Could create a failed request object here if needed
                    }
                }
            }

            completed_requests
        });

        Ok(result)
    }

    /// Create a new RequestTimers instance for manual timing
    pub fn create_timer(&self) -> RequestTimers {
        RequestTimers::new()
    }

    /// Reset the internal timer
    pub fn reset_timer(&mut self) {
        self.timer.reset();
    }

    /// Get client statistics as a RequestTimers object
    pub fn get_stats(&self) -> PyResult<RequestTimers> {
        let timer = RequestTimers::new();
        // The timer already has a base time set, which represents when it was created
        Ok(timer)
    }
}

impl StreamingHttpClient {
    async fn execute_streaming_request_async(
        client: Arc<Client>,
        request: &mut StreamingRequest,
        default_headers: &HashMap<String, String>,
        default_timeout_ms: Option<u64>,
    ) -> Result<(), StreamingError> {
        let mut req_builder = match request.method.as_str() {
            "GET" => client.get(&request.url),
            "POST" => client.post(&request.url),
            "PUT" => client.put(&request.url),
            "DELETE" => client.delete(&request.url),
            "PATCH" => client.patch(&request.url),
            "HEAD" => client.head(&request.url),
            _ => return Err(StreamingError::InvalidRequest(
                format!("Unsupported HTTP method: {}", request.method)
            )),
        };

        // Add headers
        for (key, value) in default_headers {
            req_builder = req_builder.header(key, value);
        }
        for (key, value) in &request.headers {
            req_builder = req_builder.header(key, value);
        }

        // Add body if present
        if let Some(ref body) = request.body {
            req_builder = req_builder.body(body.clone());
        }

        // Set timeout
        if let Some(timeout) = request.timeout_ms.or(default_timeout_ms) {
            req_builder = req_builder.timeout(std::time::Duration::from_millis(timeout));
        }

        // Capture send start timing
        request.capture_send_start().map_err(|e| StreamingError::InvalidRequest(format!("Failed to capture send start: {}", e)))?;

        // Execute request
        let response = match req_builder.send().await {
            Ok(response) => {
                // Capture send end timing immediately after successful send
                request.capture_send_end().map_err(|e| StreamingError::InvalidRequest(format!("Failed to capture send end: {}", e)))?;
                response
            }
            Err(e) => {
                request.set_error(format!("Request failed: {}", e));
                return Err(StreamingError::from(e));
            }
        };

        // Capture status code
        let status_code = response.status().as_u16();
        request.set_status_code(status_code);

        // Capture response headers
        let mut response_headers = HashMap::new();
        for (name, value) in response.headers() {
            if let Ok(value_str) = value.to_str() {
                response_headers.insert(name.to_string(), value_str.to_string());
            }
        }
        request.set_response_headers(response_headers);

        // Check if response indicates success
        if !response.status().is_success() {
            let error_msg = format!("HTTP {} {}", status_code, response.status().canonical_reason().unwrap_or("Unknown"));
            request.set_error(error_msg.clone());

            // Still try to read the response body for error details
            Self::process_streaming_response_async(response, request).await?;

            return Err(StreamingError::HttpError(error_msg));
        }

        // Capture receive start timing before streaming
        request.capture_recv_start().map_err(|e| StreamingError::InvalidRequest(format!("Failed to capture recv start: {}", e)))?;

        // Stream the response
        Self::process_streaming_response_async(response, request).await?;

        // Capture receive end timing after streaming
        request.capture_recv_end().map_err(|e| StreamingError::InvalidRequest(format!("Failed to capture recv end: {}", e)))?;

        request.complete().map_err(|e| StreamingError::InvalidRequest(format!("Failed to complete request: {}", e)))?;
        Ok(())
    }

        async fn process_streaming_response_async(
        response: reqwest::Response,
        request: &mut StreamingRequest,
    ) -> Result<(), StreamingError> {
        let mut stream = response.bytes_stream();
        let mut token_index = 0;

        while let Some(token_result) = stream.next().await {
            let token_data = token_result?;

            // Capture token start timing for each SSE data payload
            request.capture_token_start().map_err(|e| StreamingError::InvalidRequest(format!("Failed to capture token start: {}", e)))?;

            // Create streaming token from SSE data payload
            let token = StreamingToken::new(
                String::from_utf8_lossy(&token_data).to_string(),
                token_index,
            );

            request.add_token(token);

            // Capture token end timing after processing the token
            request.capture_token_end().map_err(|e| StreamingError::InvalidRequest(format!("Failed to capture token end: {}", e)))?;

            token_index += 1;
        }

        Ok(())
    }
}



#[pyclass]
pub struct StreamingStats {
    #[pyo3(get)]
    pub total_requests: usize,
    #[pyo3(get)]
    pub total_bytes: usize,
    #[pyo3(get)]
    pub avg_chunk_size: f64,
    #[pyo3(get)]
    pub avg_throughput_bps: f64,
    #[pyo3(get)]
    pub timing_summary: RequestTimers,
    total_duration_ns: u64,
}

#[pymethods]
impl StreamingStats {
    #[new]
    pub fn new() -> Self {
        Self {
            total_requests: 0,
            total_bytes: 0,
            avg_chunk_size: 0.0,
            avg_throughput_bps: 0.0,
            timing_summary: RequestTimers::new(),
            total_duration_ns: 0,
        }
    }

    /// Add a request's timing information to the statistics
    pub fn add_timing(&mut self, timers: &RequestTimers) -> PyResult<()> {
        self.total_requests += 1;

        // Get the request duration and add to total
        if let Some(duration) = timers.duration_ns(TimestampKind::RequestStart, TimestampKind::RequestEnd)? {
            self.total_duration_ns += duration;
        }

        self.recalculate_averages();
        Ok(())
    }

    /// Add request data along with timing information
    pub fn add_request_with_timing(&mut self, request: &StreamingRequest, timers: &RequestTimers) -> PyResult<()> {
        self.total_requests += 1;
        self.total_bytes += request.total_bytes;

        if let Some(duration) = timers.duration_ns(TimestampKind::RequestStart, TimestampKind::RequestEnd)? {
            self.total_duration_ns += duration;
        }

        self.recalculate_averages();
        Ok(())
    }

    fn recalculate_averages(&mut self) {
        if self.total_requests > 0 {
            self.avg_chunk_size = self.total_bytes as f64 / self.total_requests as f64;

            if self.total_duration_ns > 0 {
                self.avg_throughput_bps = (self.total_bytes as f64) /
                    (self.total_duration_ns as f64 / 1_000_000_000.0);
            }
        }
    }

    pub fn __repr__(&self) -> String {
        format!(
            "StreamingStats(requests={}, bytes={}, avg_chunk_size={:.2}, avg_throughput_bps={:.2})",
            self.total_requests, self.total_bytes, self.avg_chunk_size, self.avg_throughput_bps
        )
    }
}
