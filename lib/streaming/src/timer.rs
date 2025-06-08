use pyo3::prelude::*;
use std::time::{SystemTime, UNIX_EPOCH, Instant};
use chrono::Utc;

/// High-precision timer for measuring timestamps with nanosecond accuracy
#[pyclass]
pub struct PrecisionTimer {
    start_time: Instant,
    system_start: SystemTime,
}

#[pymethods]
impl PrecisionTimer {
    #[new]
    pub fn new() -> Self {
        Self {
            start_time: Instant::now(),
            system_start: SystemTime::now(),
        }
    }

    /// Get the current timestamp in nanoseconds since UNIX epoch
    pub fn now_ns(&self) -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_nanos() as u64
    }

    /// Get a high-precision timestamp in nanoseconds since timer creation
    pub fn elapsed_ns(&self) -> u64 {
        self.start_time.elapsed().as_nanos() as u64
    }

    /// Get the current UTC timestamp as an ISO string
    pub fn now_iso(&self) -> String {
        Utc::now().to_rfc3339()
    }

    /// Reset the timer
    pub fn reset(&mut self) {
        self.start_time = Instant::now();
        self.system_start = SystemTime::now();
    }
}

impl Default for PrecisionTimer {
    fn default() -> Self {
        Self::new()
    }
}