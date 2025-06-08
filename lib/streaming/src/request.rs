use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;
use crate::timers::{RequestTimers, TimestampKind};

/// A single token from SSE streaming response data
#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StreamingToken {
    #[pyo3(get)]
    pub data: String,
    #[pyo3(get)]
    pub size_bytes: usize,
    #[pyo3(get)]
    pub token_index: usize,
}

#[pymethods]
impl StreamingToken {
    #[new]
    pub fn new(data: String, token_index: usize) -> Self {
        let size_bytes = data.len();
        Self {
            data,
            size_bytes,
            token_index,
        }
    }

    pub fn __repr__(&self) -> String {
        format!(
            "StreamingToken(token_index={}, size_bytes={}, data_preview=\"{}...\")",
            self.token_index,
            self.size_bytes,
            if self.data.len() > 50 { &self.data[..50] } else { &self.data }
        )
    }
}

/// A streaming HTTP request with timing and metadata
#[pyclass]
#[derive(Debug, Clone)]
pub struct StreamingRequest {
    #[pyo3(get)]
    pub request_id: String,
    #[pyo3(get)]
    pub url: String,
    #[pyo3(get)]
    pub method: String,
    pub headers: HashMap<String, String>,
    pub body: Option<String>,
    #[pyo3(get)]
    pub timers: RequestTimers,
    pub tokens: Vec<StreamingToken>,
    #[pyo3(get)]
    pub total_bytes: usize,
    #[pyo3(get)]
    pub token_count: usize,
    #[pyo3(get)]
    pub timeout_ms: Option<u64>,
    #[pyo3(get)]
    pub status_code: Option<u16>,
    pub response_headers: HashMap<String, String>,
    #[pyo3(get)]
    pub error_message: Option<String>,
}

#[pymethods]
impl StreamingRequest {
    #[new]
    pub fn new(
        url: String,
        method: Option<String>,
        headers: Option<HashMap<String, String>>,
        body: Option<String>,
        timeout_ms: Option<u64>,
    ) -> PyResult<Self> {
        let header_map = headers.unwrap_or_default();
        let request_id = Uuid::new_v4().to_string();
        let mut timers = RequestTimers::new();

        // Capture the request start immediately
        timers.capture(TimestampKind::RequestStart)?;

        Ok(Self {
            request_id,
            url,
            method: method.unwrap_or_else(|| "GET".to_string()),
            headers: header_map,
            body,
            timers,
            tokens: Vec::new(),
            total_bytes: 0,
            token_count: 0,
            timeout_ms,
            status_code: None,
            response_headers: HashMap::new(),
            error_message: None,
        })
    }

    /// Add a token to the request
    pub fn add_token(&mut self, token: StreamingToken) {
        self.total_bytes += token.size_bytes;
        self.token_count += 1;
        self.tokens.push(token);
    }

    /// Mark the request as completed
    pub fn complete(&mut self) -> PyResult<()> {
        self.timers.capture(TimestampKind::RequestEnd)
    }

    /// Set the HTTP status code
    pub fn set_status_code(&mut self, status_code: u16) {
        self.status_code = Some(status_code);
    }

    /// Set response headers
    pub fn set_response_headers(&mut self, headers: HashMap<String, String>) {
        self.response_headers = headers;
    }

    /// Set an error message
    pub fn set_error(&mut self, error: String) {
        self.error_message = Some(error);
    }

    /// Capture send start timing
    pub fn capture_send_start(&mut self) -> PyResult<()> {
        self.timers.capture(TimestampKind::SendStart)
    }

    /// Capture send end timing
    pub fn capture_send_end(&mut self) -> PyResult<()> {
        self.timers.capture(TimestampKind::SendEnd)
    }

    /// Capture receive start timing
    pub fn capture_recv_start(&mut self) -> PyResult<()> {
        self.timers.capture(TimestampKind::RecvStart)
    }

    /// Capture receive end timing
    pub fn capture_recv_end(&mut self) -> PyResult<()> {
        self.timers.capture(TimestampKind::RecvEnd)
    }

    /// Capture token start timing (for streaming tokens)
    pub fn capture_token_start(&mut self) -> PyResult<()> {
        self.timers.capture(TimestampKind::TokenStart)
    }

    /// Capture token end timing (for streaming tokens)
    pub fn capture_token_end(&mut self) -> PyResult<()> {
        self.timers.capture(TimestampKind::TokenEnd)
    }

    /// Check if the request was successful (2xx status code)
    pub fn is_success(&self) -> bool {
        match self.status_code {
            Some(status) => status >= 200 && status < 300,
            None => false, // No status code means request failed
        }
    }

    /// Get the total request duration in nanoseconds
    pub fn duration_ns(&self) -> PyResult<Option<u64>> {
        self.timers.duration_ns(TimestampKind::RequestStart, TimestampKind::RequestEnd)
    }

    /// Get all tokens as a Python list
    #[pyo3(signature = ())]
    pub fn get_tokens(&self, py: Python) -> PyResult<PyObject> {
        let py_list = PyList::empty(py);
        for token in &self.tokens {
            py_list.append(Py::new(py, token.clone())?)?;
        }
        Ok(py_list.into())
    }

    /// Get the full response body as a concatenated string
    pub fn get_response_text(&self) -> String {
        self.tokens.iter()
            .map(|token| token.data.as_str())
            .collect::<Vec<_>>()
            .join("")
    }

    /// Get response data as bytes (useful for binary content)
    pub fn get_response_bytes(&self) -> Vec<u8> {
        self.tokens.iter()
            .flat_map(|token| token.data.as_bytes())
            .cloned()
            .collect()
    }

    /// Get a specific token by index
    pub fn get_token(&self, index: usize) -> Option<StreamingToken> {
        self.tokens.get(index).cloned()
    }

    /// Get timing information for a specific token by index
    pub fn get_token_timing(&self, token_index: usize) -> PyResult<Option<u64>> {
        self.timers.token_duration_ns(token_index, token_index)
    }

    /// Get the first N characters of the response (useful for debugging)
    pub fn get_response_preview(&self, max_chars: Option<usize>) -> String {
        let full_text = self.get_response_text();
        match max_chars {
            Some(limit) if full_text.len() > limit => {
                format!("{}... ({} total chars)", &full_text[..limit], full_text.len())
            }
            _ => full_text
        }
    }

    /// Get headers as a Python dictionary
    pub fn get_headers(&self, py: Python) -> PyResult<PyObject> {
        let py_dict = PyDict::new(py);
        for (key, value) in &self.headers {
            py_dict.set_item(key, value)?;
        }
        Ok(py_dict.into())
    }

    /// Calculate bytes per second throughput
    pub fn throughput_bps(&self) -> PyResult<Option<f64>> {
        match self.duration_ns()? {
            Some(duration_ns) => {
                if duration_ns > 0 {
                    Ok(Some((self.total_bytes as f64) / (duration_ns as f64 / 1_000_000_000.0)))
                } else {
                    Ok(Some(0.0))
                }
            }
            None => Ok(None),
        }
    }

    /// Get token timing statistics from the request timers
    pub fn token_timings(&self) -> PyResult<Vec<u64>> {
        self.timers.get_token_durations_ns()
    }

    /// Get response headers as a Python dictionary
    pub fn get_response_headers(&self, py: Python) -> PyResult<PyObject> {
        let py_dict = PyDict::new(py);
        for (key, value) in &self.response_headers {
            py_dict.set_item(key, value)?;
        }
        Ok(py_dict.into())
    }

    pub fn __repr__(&self) -> String {
        format!(
            "StreamingRequest(id={}, url={}, method={}, tokens={}, total_bytes={})",
            self.request_id, self.url, self.method, self.token_count, self.total_bytes
        )
    }
}
