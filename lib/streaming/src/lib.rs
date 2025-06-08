use pyo3::prelude::*;

mod client;
mod request;
mod timer;
mod timers;
mod errors;

use client::{StreamingHttpClient, StreamingStats};
use request::{StreamingRequest, StreamingTokenChunk};
use timer::PrecisionTimer;
use timers::{RequestTimers, TimestampKind};

/// A high-performance streaming HTTP client for AI performance analysis
#[pymodule]
fn aiperf_streaming(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<StreamingHttpClient>()?;
    m.add_class::<StreamingRequest>()?;
    m.add_class::<StreamingTokenChunk>()?;
    m.add_class::<StreamingStats>()?;
    m.add_class::<PrecisionTimer>()?;
    m.add_class::<RequestTimers>()?;
    m.add_class::<TimestampKind>()?;

    Ok(())
}
