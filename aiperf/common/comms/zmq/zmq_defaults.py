# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

# ZMQ Constants
from dataclasses import dataclass

TOPIC_END = "$"
"""This is used to add to the end of each topic to prevent the topic from being a prefix of another topic.
This is required for the PUB/SUB pattern to work correctly, otherwise topics like "command_response" will be
received by the "command" subscriber as well.

For example:
- "command$"
- "command_response$"
"""

TOPIC_END_ENCODED = TOPIC_END.encode()
"""The encoded version of TOPIC_END."""

TOPIC_DELIMITER = "."
"""The delimiter between topic parts.
This is used to create an inverted hierarchy of topics for filtering by service type or service id.

For example:
- "command"
- "system_controller.command"
- "timing_manager_eff34565.command"
"""


@dataclass(frozen=True)
class ZMQSocketDefaults:
    """Default socket options for ZMQ sockets optimized for high concurrency."""

    # Increased timeouts to prevent any socket-level timeouts
    RCVTIMEO = 30000  # 30 seconds instead of 10
    SNDTIMEO = 30000  # 30 seconds instead of 10

    # High Water Mark - Increased for extreme concurrency
    SNDHWM = 0
    RCVHWM = 0

    # Connection settings - optimized for reliability
    IMMEDIATE = 1
    LINGER = 0
    TCP_KEEPALIVE = 1
    TCP_KEEPALIVE_IDLE = 300  # Increased from 60
    TCP_KEEPALIVE_INTVL = 30  # Increased from 10
    TCP_KEEPALIVE_CNT = 9  # Increased from 3


class ZMQExtremePerformanceDefaults:
    """Optimized ZMQ settings for 100K+ concurrent requests."""

    # Ultra-high performance timeouts
    RCVTIMEO = 1000  # 1 second - much faster for high throughput
    SNDTIMEO = 1000  # 1 second - much faster for high throughput

    # Extreme concurrency HWM settings
    SNDHWM = 0
    RCVHWM = 0

    # TCP optimizations for high throughput
    TCP_KEEPALIVE = 1
    TCP_KEEPALIVE_IDLE = 30  # Faster keepalive
    TCP_KEEPALIVE_INTVL = 5  # Faster keepalive interval
    TCP_KEEPALIVE_CNT = 2  # Fewer retries

    # Performance optimizations
    IMMEDIATE = 1  # No queuing delay
    LINGER = 0  # Fast shutdown
    BACKLOG = 1000  # Higher connection backlog
    MAXMSGSIZE = -1  # No message size limit

    # Router-specific optimizations
    ROUTER_MANDATORY = 0  # Don't fail on unroutable messages
    ROUTER_HANDOVER = 1  # Allow identity handover

    # Dealer-specific optimizations
    PROBE_ROUTER = 1  # Send empty message on connect
    REQ_CORRELATE = 1  # Correlate request/reply
    REQ_RELAXED = 1  # Relaxed request/reply state machine
