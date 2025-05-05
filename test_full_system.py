import asyncio
import logging
import sys
import time
from aiperf.config.config_loader import ConfigLoader
from aiperf.system.system_controller import SystemController
from aiperf.common.memory_communication import MemoryCommunication

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_full_system")


async def test_full_system():
    logger.info("Testing full AIPerf system...")

    # Load config
    config_path = "aiperf/config/examples/openai_example.yaml"
    logger.info(f"Loading configuration from: {config_path}")
    config = ConfigLoader.load_from_file(config_path)

    # Initialize system controller
    logger.info("Initializing system controller...")
    controller = SystemController(config)

    try:
        # Initialize the controller
        success = await controller.initialize()
        if not success:
            logger.error("Failed to initialize system controller")
            return 1

        logger.info("System controller initialized successfully")

        # Start profile
        logger.info("Starting profile...")
        success = await controller.start_profile()
        if not success:
            logger.error("Failed to start profile")
            return 1

        logger.info("Profile started successfully")

        # Run for a short period
        logger.info("Running profile for 10 seconds...")
        await asyncio.sleep(10)

        # Stop profile
        logger.info("Stopping profile...")
        success = await controller.stop_profile()
        if not success:
            logger.error("Failed to stop profile")
            return 1

        logger.info("Profile stopped successfully")

        # Graceful shutdown
        logger.info("Shutting down system...")
        success = await controller.shutdown()
        if not success:
            logger.error("Failed to shut down system")
            return 1

        logger.info("System shutdown successfully")

        return 0
    except Exception as e:
        logger.error(f"Error during test: {e}", exc_info=True)
        # Try to shut down anyway
        try:
            await controller.shutdown()
        except Exception:
            pass
        return 1


async def main():
    logger.info("Starting full system test...")

    try:
        result = await test_full_system()
        if result == 0:
            logger.info("Test completed successfully!")
        else:
            logger.error("Test failed with errors")
        return result
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
