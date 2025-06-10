#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
Debug utilities for ZMQ communication debugging.

This module provides utilities to help debug message flow issues in the
DEALER-ROUTER broker architecture, particularly useful for tracking
conversation_response messages that are not being received by listeners.
"""

import logging


def configure_zmq_debug_logging(
    level: str = "INFO",
    format_string: str | None = None,
    include_timestamp: bool = True,
    include_thread: bool = False,
    file_path: str | None = None,
) -> None:
    """
    Configure debug logging for ZMQ communication components.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        format_string: Custom format string (if None, uses default)
        include_timestamp: Whether to include timestamp in logs
        include_thread: Whether to include thread info in logs
        file_path: Optional file path to write logs to (in addition to console)
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Build format string
    if format_string is None:
        parts = []
        if include_timestamp:
            parts.append("%(asctime)s")
        parts.append("%(levelname)-8s")
        if include_thread:
            parts.append("[%(threadName)s]")
        parts.append("%(name)s")
        parts.append("%(message)s")
        format_string = " - ".join(parts)

    # Configure root logger
    logging.basicConfig(
        level=numeric_level,
        format=format_string,
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )

    # Specific loggers for ZMQ components
    zmq_loggers = [
        "ZMQDealerClient",
        "ZMQRouterClient",
        "ZMQDealerRouterBroker",
        "_BrokerFrontendRouterClient",
        "_BrokerBackendDealerClient",
        "BaseZMQClient",
    ]

    for logger_name in zmq_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(numeric_level)

        # Add file handler if specified
        if file_path:
            file_handler = logging.FileHandler(file_path)
            file_handler.setLevel(numeric_level)
            file_handler.setFormatter(
                logging.Formatter(format_string, datefmt="%Y-%m-%d %H:%M:%S")
            )
            logger.addHandler(file_handler)

    print(f"ZMQ Debug logging configured at {level} level")
    if file_path:
        print(f"Logs will also be written to: {file_path}")


def enable_full_debug_trace() -> None:
    """
    Enable full debug tracing for ZMQ communication.
    This will show all message flow details.
    """
    configure_zmq_debug_logging(
        level="DEBUG",
        include_timestamp=True,
        include_thread=True,
    )

    # Also enable ZMQ library debug logging
    logging.getLogger("zmq").setLevel(logging.DEBUG)

    print("Full ZMQ debug tracing enabled")


def enable_message_flow_tracking() -> None:
    """
    Enable INFO level logging optimized for tracking message flow.
    This shows key message events without overwhelming detail.
    """
    configure_zmq_debug_logging(
        level="INFO",
        include_timestamp=True,
        include_thread=False,
    )

    print("ZMQ message flow tracking enabled")


def create_debug_session_logger(session_name: str) -> logging.Logger:
    """
    Create a logger specifically for a debug session.

    Args:
        session_name: Name for this debug session

    Returns:
        Logger instance configured for the session
    """
    logger = logging.getLogger(f"DEBUG_SESSION_{session_name}")
    logger.setLevel(logging.DEBUG)

    # Create file handler for this session
    file_handler = logging.FileHandler(f"zmq_debug_{session_name}.log")
    file_handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)-8s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S.%f",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.info(f"Debug session '{session_name}' started")
    return logger


def log_message_trace(
    logger: logging.Logger,
    component: str,
    action: str,
    message_id: str,
    message_type: str,
    additional_info: dict | None = None,
) -> None:
    """
    Log a standardized message trace entry.

    Args:
        logger: Logger to use
        component: Component name (e.g., "DEALER[client_123]", "ROUTER[service_456]")
        action: Action being performed (e.g., "SENDING", "RECEIVED", "PROCESSING")
        message_id: Message request ID
        message_type: Type of message
        additional_info: Optional dictionary of additional info to log
    """
    base_msg = f"{component} {action} - ID: {message_id}, Type: {message_type}"

    if additional_info:
        info_parts = [f"{k}: {v}" for k, v in additional_info.items()]
        base_msg += f", {', '.join(info_parts)}"

    logger.info(base_msg)


# Example usage functions for common debugging scenarios


def debug_conversation_response_flow():
    """
    Configure logging specifically for debugging conversation_response message flow.
    """
    enable_message_flow_tracking()

    print("""
=== Conversation Response Debug Mode ===

This configuration will help track conversation_response messages through the system:

1. DEALER clients will log when they send requests and receive responses
2. ROUTER services will log when they receive requests and send responses
3. Broker will log message flow through the proxy

Look for these patterns in the logs:
- DEALER[id] REQUEST START - Look for your conversation request
- ROUTER[id] HANDLING REQUEST - Confirm the router receives it
- ROUTER[id] SENDING RESPONSE - Confirm the router sends a response
- DEALER[id] RESPONSE RECEIVED - Check if the original client gets it

If you have a capture_address configured on your broker, you'll also see:
- BROKER CAPTURED MESSAGE - All messages flowing through the proxy

Tip: Search logs for your specific request_id to follow a single message's journey.
    """)


def debug_broker_proxy_flow():
    """
    Configure logging specifically for debugging broker proxy message flow.
    """
    enable_full_debug_trace()

    print("""
=== Broker Proxy Debug Mode ===

This configuration will show detailed broker proxy operation:

1. Broker initialization and socket binding
2. All messages flowing through the proxy (if capture is enabled)
3. Detailed frame analysis for multipart messages
4. Socket identity and routing information

Make sure your broker is configured with a capture_address to see message flow:

    broker_config = BaseZMQDealerRouterBrokerConfig(
        frontend_address="tcp://*:5555",
        backend_address="tcp://*:5556",
        capture_address="tcp://*:5557"  # Add this for message monitoring
    )
    """)


if __name__ == "__main__":
    """
    Command line interface for quick debug setup.
    """
    import argparse

    parser = argparse.ArgumentParser(description="ZMQ Debug Logging Setup")
    parser.add_argument(
        "--mode",
        choices=["full", "flow", "conversation"],
        default="flow",
        help="Debug mode to enable",
    )
    parser.add_argument("--file", help="Optional log file path")

    args = parser.parse_args()

    if args.mode == "full":
        enable_full_debug_trace()
    elif args.mode == "conversation":
        debug_conversation_response_flow()
    else:
        enable_message_flow_tracking()

    if args.file:
        configure_zmq_debug_logging(file_path=args.file)
