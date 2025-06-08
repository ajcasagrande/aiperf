use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

/// A single chunk of streaming response data with precise timing
#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StreamingChunk {
    #[pyo3(get)]
    pub timestamp_ns: u64,
    #[pyo3(get)]
    pub data: String,
    #[pyo3(get)]
    pub size_bytes: usize,
    #[pyo3(get)]
    pub chunk_index: usize,
}

#[pymethods]
impl StreamingChunk {
    #[new]
    pub fn new(timestamp_ns: u64, data: String, chunk_index: usize) -> Self {
        let size_bytes = data.len();
        Self {
            timestamp_ns,
            data,
            size_bytes,
            chunk_index,
        }
    }

    pub fn __repr__(&self) -> String {
        format!(
            "StreamingChunk(timestamp_ns={}, size_bytes={}, chunk_index={})",
            self.timestamp_ns, self.size_bytes, self.chunk_index
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
    pub start_time_ns: u64,
    #[pyo3(get)]
    pub end_time_ns: Option<u64>,
    pub chunks: Vec<StreamingChunk>,
    #[pyo3(get)]
    pub total_bytes: usize,
    #[pyo3(get)]
    pub chunk_count: usize,
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
        let start_time_ns = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_nanos() as u64;

        Ok(Self {
            request_id,
            url,
            method: method.unwrap_or_else(|| "GET".to_string()),
            headers: header_map,
            body,
            start_time_ns,
            end_time_ns: None,
            chunks: Vec::new(),
            total_bytes: 0,
            chunk_count: 0,
            timeout_ms,
            status_code: None,
            response_headers: HashMap::new(),
            error_message: None,
        })
    }

    /// Add a chunk to the request
    pub fn add_chunk(&mut self, chunk: StreamingChunk) {
        self.total_bytes += chunk.size_bytes;
        self.chunk_count += 1;
        self.chunks.push(chunk);
    }

    /// Mark the request as completed
    pub fn complete(&mut self) {
        self.end_time_ns = Some(
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_nanos() as u64,
        );
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

    /// Check if the request was successful (2xx status code)
    pub fn is_success(&self) -> bool {
        match self.status_code {
            Some(status) => status >= 200 && status < 300,
            None => false, // No status code means request failed
        }
    }

    /// Get the total request duration in nanoseconds
    pub fn duration_ns(&self) -> Option<u64> {
        self.end_time_ns.map(|end| end - self.start_time_ns)
    }

    /// Get all chunks as a Python list
    pub fn get_chunks(&self, py: Python) -> PyResult<PyObject> {
        let py_list = PyList::empty(py);
        for chunk in &self.chunks {
            py_list.append(Py::new(py, chunk.clone())?)?;
        }
        Ok(py_list.into())
    }

    /// Get the full response body as a concatenated string
    pub fn get_response_text(&self) -> String {
        self.chunks.iter()
            .map(|chunk| chunk.data.as_str())
            .collect::<Vec<_>>()
            .join("")
    }

    /// Get response data as bytes (useful for binary content)
    pub fn get_response_bytes(&self) -> Vec<u8> {
        self.chunks.iter()
            .flat_map(|chunk| chunk.data.as_bytes())
            .cloned()
            .collect()
    }

    /// Get a specific chunk by index
    pub fn get_chunk(&self, index: usize) -> Option<StreamingChunk> {
        self.chunks.get(index).cloned()
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
    pub fn throughput_bps(&self) -> Option<f64> {
        self.duration_ns().map(|duration_ns| {
            if duration_ns > 0 {
                (self.total_bytes as f64) / (duration_ns as f64 / 1_000_000_000.0)
            } else {
                0.0
            }
        })
    }

    /// Get chunk timing statistics
    pub fn chunk_timings(&self) -> Vec<u64> {
        if self.chunks.is_empty() {
            return Vec::new();
        }

        let mut timings = Vec::new();
        let base_time = self.chunks[0].timestamp_ns;

        for chunk in &self.chunks {
            timings.push(chunk.timestamp_ns - base_time);
        }

        timings
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
            "StreamingRequest(id={}, url={}, method={}, chunks={}, total_bytes={})",
            self.request_id, self.url, self.method, self.chunk_count, self.total_bytes
        )
    }
}