use pyo3::prelude::*;
use std::collections::HashMap;
use std::time::Instant;

/// Timestamp kinds for request timing
#[pyclass]
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum TimestampKind {
    /// The start of request handling
    RequestStart,
    /// The end of request handling
    RequestEnd,
    /// The start of sending request bytes to the server (first byte)
    SendStart,
    /// The end of sending request bytes to the server (last byte)
    SendEnd,
    /// The start of receiving response bytes from the server (first byte)
    RecvStart,
    /// The end of receiving response bytes from the server (last byte)
    RecvEnd,
    /// The start of a token
    TokenStart,
    /// The end of a token
    TokenEnd,
}

#[pymethods]
impl TimestampKind {
    fn __str__(&self) -> &'static str {
        match self {
            TimestampKind::RequestStart => "REQUEST_START",
            TimestampKind::RequestEnd => "REQUEST_END",
            TimestampKind::SendStart => "SEND_START",
            TimestampKind::SendEnd => "SEND_END",
            TimestampKind::RecvStart => "RECV_START",
            TimestampKind::RecvEnd => "RECV_END",
            TimestampKind::TokenStart => "TOKEN_START",
            TimestampKind::TokenEnd => "TOKEN_END",
        }
    }

    fn __repr__(&self) -> String {
        format!("TimestampKind.{}", self.__str__())
    }
}

/// Request timers for precise timing measurements
#[pyclass]
#[derive(Debug, Clone)]
pub struct RequestTimers {
    /// HashMap storing all non-token timestamps
    timestamps: HashMap<TimestampKind, u128>,
    /// Vector storing all token start timestamps
    token_starts: Vec<u128>,
    /// Vector storing all token end timestamps
    token_ends: Vec<u128>,
    /// Base time for converting to nanoseconds
    base_time: Instant,
}

#[pymethods]
impl RequestTimers {
    #[new]
    pub fn new() -> Self {
        let base_time = Instant::now();
        Self {
            timestamps: HashMap::new(),
            token_starts: Vec::new(),
            token_ends: Vec::new(),
            base_time,
        }
    }

        /// Capture a timestamp for the specified kind
    pub fn capture(&mut self, kind: TimestampKind) -> PyResult<()> {
        let now = Instant::now();

        match kind {
            TimestampKind::TokenStart => self.token_starts.push(now.duration_since(self.base_time).as_nanos()),
            TimestampKind::TokenEnd => self.token_ends.push(now.duration_since(self.base_time).as_nanos()),
            TimestampKind::RequestStart => {
                self.base_time = now;
                self.timestamps.insert(kind, 0);
            }
            _ => {
                self.timestamps.insert(kind, now.duration_since(self.base_time).as_nanos());
            }
        }

        Ok(())
    }

    /// Get duration in nanoseconds between two timestamp kinds
    pub fn duration_ns(&self, from_kind: TimestampKind, to_kind: TimestampKind) -> PyResult<Option<u128>> {
        let from_time = self.get_timestamp(from_kind, None);
        let to_time = self.get_timestamp(to_kind, None);

        match (from_time, to_time) {
            (Some(from), Some(to)) => {
                if to >= from {
                    Ok(Some(to - from))
                } else {
                    Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                        "End time is before start time"
                    ))
                }
            }
            _ => Ok(None),
        }
    }

    /// Get duration in nanoseconds between specific token indices
    pub fn token_duration_ns(&self, from_token_idx: usize, to_token_idx: usize) -> PyResult<Option<u128>> {
        let from_time = self.token_starts.get(from_token_idx);
        let to_time = self.token_ends.get(to_token_idx);

        match (from_time, to_time) {
            (Some(from), Some(to)) => {
                if to >= from {
                    Ok(Some(*to - *from))
                } else {
                    Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                        "Token end time is before start time"
                    ))
                }
            }
            _ => Ok(None),
        }
    }

    /// Get timestamp in nanoseconds since base time for a specific kind
    pub fn timestamp_ns(&self, kind: TimestampKind, index: Option<usize>) -> Option<u128> {
        self.get_timestamp(kind, index)
    }

    /// Get the number of token start timestamps
    pub fn token_starts_count(&self) -> usize {
        self.token_starts.len()
    }

    /// Get the number of token end timestamps
    pub fn token_ends_count(&self) -> usize {
        self.token_ends.len()
    }

    /// Get all token start timestamps as nanoseconds since base time
    pub fn get_token_start_timestamps_ns(&self) -> Vec<u128> {
        self.token_starts
            .iter()
            .map(|instant| *instant)
            .collect()
    }

    /// Get all token end timestamps as nanoseconds since base time
    pub fn get_token_end_timestamps_ns(&self) -> Vec<u128> {
        self.token_ends
            .iter()
            .map(|instant| *instant)
            .collect()
    }

    /// Get all individual token durations in nanoseconds
    pub fn get_token_durations_ns(&self) -> PyResult<Vec<u128>> {
        let mut durations = Vec::new();
        let min_len = std::cmp::min(self.token_starts.len(), self.token_ends.len());

        for i in 0..min_len {
            let start = self.token_starts[i];
            let end = self.token_ends[i];

            if end >= start {
                durations.push(end - start);
            } else {
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    format!("Token {} end time is before start time", i)
                ));
            }
        }

        Ok(durations)
    }

    /// Clear all timestamps
    pub fn clear(&mut self) {
        self.timestamps.clear();
        self.token_starts.clear();
        self.token_ends.clear();
        self.base_time = Instant::now();
    }

    /// Check if a timestamp kind has been captured
    pub fn has_timestamp(&self, kind: TimestampKind) -> bool {
        match kind {
            TimestampKind::TokenStart => !self.token_starts.is_empty(),
            TimestampKind::TokenEnd => !self.token_ends.is_empty(),
            _ => self.timestamps.contains_key(&kind),
        }
    }

    fn __repr__(&self) -> String {
        format!(
            "RequestTimers(tokens_start={}, tokens_end={}, timestamps_count={})",
            self.token_starts.len(),
            self.token_ends.len(),
            self.timestamps.len(),
        )
    }
}

impl RequestTimers {
    /// Helper method to get timestamp for a specific kind and optional index
    fn get_timestamp(&self, kind: TimestampKind, index: Option<usize>) -> Option<u128> {
        match kind {
            TimestampKind::TokenStart => {
                let idx = index.unwrap_or(0);
                self.token_starts.get(idx).cloned()
            }
            TimestampKind::TokenEnd => {
                let idx = index.unwrap_or(0);
                self.token_ends.get(idx).cloned()
            }
            _ => self.timestamps.get(&kind).cloned(),
        }
    }
}
