import asyncio
import sys
import logging
from aiperf.config.config_loader import ConfigLoader
from aiperf.system.system_controller import SystemController


async def test_clean_shutdown():
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logging.info("Starting clean shutdown test")

    # Load config
    config_path = "aiperf/config/examples/openai_example.yaml"
    logging.info(f"Loading configuration from: {config_path}")
    config = ConfigLoader.load_from_file(config_path)

    # Initialize system controller
    logging.info("Initializing system controller...")
    controller = SystemController(config)

    # Initialize the controller
    success = await controller.initialize()
    if not success:
        logging.error("Failed to initialize system controller")
        return 1

    # Start profile
    logging.info("Starting profile...")
    success = await controller.start_profile()
    if not success:
        logging.error("Failed to start profile")
        return 1

    # Run for 3 seconds
    logging.info("Running for 3 seconds...")
    await asyncio.sleep(3)

    # Stop profile
    logging.info("Stopping profile...")
    success = await controller.stop_profile()
    if not success:
        logging.error("Failed to stop profile")

    # Shutdown cleanly
    logging.info("Shutting down...")
    success = await controller.shutdown()
    logging.info(f"Shutdown {'successful' if success else 'failed'}")

    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(test_clean_shutdown())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logging.info("Interrupted by user")
        sys.exit(130)
