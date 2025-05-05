import logging
import sys
from argparse import ArgumentParser

from aiperf.common.config.service_config import ControllerConfig
from aiperf.common.service import bootstrap_and_run_service
from aiperf.services.system_controller.main import SystemController

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


def main() -> None:
    """Main entry point for the AIPerf system."""
    parser = ArgumentParser(description="AIPerf Benchmarking System")
    parser.add_argument("--config", type=str, help="Path to configuration file")
    parser.add_argument(
        "--log-level",
        type=str,
        default="DEBUG",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level",
    )
    parser.add_argument(
        "--workers", type=int, default=1, help="Number of worker processes"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port to run the service on"
    )
    parser.add_argument(
        "--process-backend",
        type=str,
        default="multiprocessing",
        choices=["multiprocessing", "kubernetes", "k8s"],
        help="Process manager backend to use",
    )
    parser.add_argument(
        "--namespace",
        type=str,
        default="default",
        help="Kubernetes namespace (only used with kubernetes backend)",
    )
    args = parser.parse_args()

    # Set log level from command line
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Load configuration
    config = ControllerConfig(
        workers=args.workers,
        port=args.port,
        process_backend=args.process_backend,
        namespace=args.namespace,
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
