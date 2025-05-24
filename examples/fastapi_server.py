#!/usr/bin/env python3
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
"""
Simple FastAPI webserver that logs requests and returns 'ok'.
Runs on port 9797.
"""

import logging
import time

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Configure logging
logging.basicConfig(
    level=logging.WARNING, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Example Request Logger",
    description="Simple FastAPI server that logs requests and returns 'ok'",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResponseModel(BaseModel):
    """Standard response model."""

    status: str = "ok"
    timestamp: float
    method: str
    path: str


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests."""
    start_time = time.time()

    # Log request details
    logger.info(
        f"REQUEST: {request.method} {request.url.path} "
        f"from {request.client.host if request.client else 'unknown'}"
    )

    # Log query parameters if any
    if request.query_params:
        logger.info(f"Query params: {dict(request.query_params)}")

    # Log headers (excluding authorization for security)
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in ["authorization", "cookie"]
    }
    logger.info(f"Headers: {headers}")

    # Process request
    response = await call_next(request)

    # Log response time
    process_time = time.time() - start_time
    logger.info(f"RESPONSE: {response.status_code} in {process_time:.4f}s")

    return response


@app.get("/", response_model=ResponseModel)
async def root(request: Request):
    """Root endpoint that returns ok."""
    return ResponseModel(
        timestamp=time.time(), method=request.method, path=request.url.path
    )


@app.get("/health", response_model=ResponseModel)
async def health(request: Request):
    """Health check endpoint."""
    return ResponseModel(
        timestamp=time.time(), method=request.method, path=request.url.path
    )


@app.post("/{path:path}")
@app.get("/{path:path}")
@app.put("/{path:path}")
@app.delete("/{path:path}")
@app.patch("/{path:path}")
@app.head("/{path:path}")
@app.options("/{path:path}")
async def catch_all(request: Request, path: str):
    """Catch-all endpoint for any path and method."""

    # Log request body for POST/PUT/PATCH
    if request.method in ["POST", "PUT", "PATCH"]:
        try:
            body = await request.body()
            if body:
                logger.info(
                    f"Request body: {body.decode('utf-8', errors='ignore')[:500]}..."
                )
        except Exception as e:
            logger.warning(f"Could not read request body: {e}")

    return ResponseModel(timestamp=time.time(), method=request.method, path=f"/{path}")


if __name__ == "__main__":
    logger.info("Starting FastAPI server on port 9797...")
    uvicorn.run(app, host="0.0.0.0", port=9797, log_level="info", access_log=True)
