# main.py

import sys
import logging
from managers.system_controller import SystemController

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(name)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def main():
    # Initialize the System Controller
    controller = SystemController()

    # Bring up the system components
    if not controller.bring_up():
        logger.error("Failed to bring up the system components.")
        sys.exit(1)

    # Start the benchmarking process
    logger.info("Starting benchmarking process")
    controller.start_benchmarking()

    # Gracefully shut down the system
    logger.info("Shutting down system controller")
    controller.shutdown()

if __name__ == "__main__":
    main()