#!/usr/bin/env python3
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
Test script to validate the ZMQ Dealer Router Broker configuration
"""

import asyncio
import logging

from aiperf.common.comms.zmq.clients.dealer_router import ZMQDealerRouterBroker
from aiperf.common.models import ZMQTCPDealerRouterBrokerConfig

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_broker_config():
    """Test that the broker configuration is set up correctly"""

    # Create broker config
    config = ZMQTCPDealerRouterBrokerConfig()

    # Display the configuration
    logger.info("=== Broker Configuration ===")
    logger.info(f"Frontend address (DEALER clients connect): {config.frontend_address}")
    logger.info(f"Backend address (ROUTER services connect): {config.backend_address}")
    logger.info(f"Host: {config.host}")
    logger.info(f"Frontend port: {config.frontend_port}")
    logger.info(f"Backend port: {config.backend_port}")

    # Create broker
    broker = ZMQDealerRouterBroker.from_config(config)

    if broker:
        logger.info("✅ Broker created successfully with new architecture")
        logger.info(f"Frontend socket binds to: {broker.frontend_address}")
        logger.info(f"Backend socket binds to: {broker.backend_address}")

        # Verify the socket naming
        logger.info(f"Frontend socket type: {type(broker.frontend_socket).__name__}")
        logger.info(f"Backend socket type: {type(broker.backend_socket).__name__}")

        logger.info("🔄 Message flow:")
        logger.info(
            "  DEALER Client → frontend_address → Frontend ROUTER → Proxy → Backend DEALER → backend_address → ROUTER Service"
        )
        logger.info(
            "  ROUTER Service → backend_address → Backend DEALER → Proxy → Frontend ROUTER → frontend_address → DEALER Client"
        )

    else:
        logger.error("❌ Failed to create broker")


if __name__ == "__main__":
    asyncio.run(test_broker_config())
