use pyo3::prelude::*;
use pyo3::exceptions::PyException;

/// Custom error types for the streaming HTTP client
#[derive(Debug)]
pub enum StreamingError {
    HttpError(String),
    TimeoutError(String),
    ParseError(String),
    ConnectionError(String),
    InvalidRequest(String),
}

impl std::fmt::Display for StreamingError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            StreamingError::HttpError(msg) => write!(f, "HTTP Error: {}", msg),
            StreamingError::TimeoutError(msg) => write!(f, "Timeout Error: {}", msg),
            StreamingError::ParseError(msg) => write!(f, "Parse Error: {}", msg),
            StreamingError::ConnectionError(msg) => write!(f, "Connection Error: {}", msg),
            StreamingError::InvalidRequest(msg) => write!(f, "Invalid Request: {}", msg),
        }
    }
}

impl std::error::Error for StreamingError {}

impl From<StreamingError> for PyErr {
    fn from(err: StreamingError) -> PyErr {
        PyException::new_err(err.to_string())
    }
}

impl From<reqwest::Error> for StreamingError {
    fn from(err: reqwest::Error) -> Self {
        if err.is_timeout() {
            StreamingError::TimeoutError(err.to_string())
        } else if err.is_connect() {
            StreamingError::ConnectionError(err.to_string())
        } else {
            StreamingError::HttpError(err.to_string())
        }
    }
}

impl From<serde_json::Error> for StreamingError {
    fn from(err: serde_json::Error) -> Self {
        StreamingError::ParseError(err.to_string())
    }
}