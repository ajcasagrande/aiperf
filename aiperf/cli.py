import logging
import sys
from argparse import ArgumentParser

from aiperf.common.bootstrap import bootstrap_and_run_service
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.service.base import get_logger
from aiperf.services.system_controller.system_controller import SystemController

# TODO: Each service may have to initialize logging from a common
#  configuration due to running on separate processes

logger = get_logger(__name__)


def main() -> None:
    """Main entry point for the AIPerf system."""
    parser = ArgumentParser(description="AIPerf Benchmarking System")
    parser.add_argument("--config", type=str, help="Path to configuration file")
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level",
    )
    parser.add_argument(
        "--run-type",
        type=str,
        default="process",
        choices=["process", "k8s"],
        help="Process manager backend to use (multiprocessing: 'process', or kubernetes: 'k8s')",
    )
    args = parser.parse_args()

    # Set logging level for the root logger (affects all loggers)
    logging.root.setLevel(getattr(logging, args.log_level))

    # Load configuration
    config = ServiceConfig(
        service_run_type=args.run_type,
    )

    if args.config:
        # In a real implementation, this would load from the specified file
        logger.info(f"Loading configuration from {args.config}")
        # config.load_from_file(args.config)

    # Create and start the system controller
    logger.info("Creating System Controller")

    logger.info("Starting AIPerf System")
    bootstrap_and_run_service(SystemController, config=config)


if __name__ == "__main__":
    sys.exit(main())
