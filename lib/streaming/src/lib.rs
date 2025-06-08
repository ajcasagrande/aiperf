use pyo3::prelude::*;

mod client;
mod request;
mod timer;
mod errors;

use client::{StreamingHttpClient, StreamingStats};
use request::{StreamingRequest, StreamingChunk};
use timer::PrecisionTimer;

/// A high-performance streaming HTTP client for AI performance analysis
#[pymodule]
fn aiperf_streaming(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<StreamingHttpClient>()?;
    m.add_class::<StreamingRequest>()?;
    m.add_class::<StreamingChunk>()?;
    m.add_class::<StreamingStats>()?;
    m.add_class::<PrecisionTimer>()?;

    Ok(())
}