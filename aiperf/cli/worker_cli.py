import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import uuid
from typing import Any, Dict, Optional

# Add parent directory to path if running as script
if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from aiperf.workers.worker import Worker
from aiperf.common.zmq_communication import ZMQCommunication
from aiperf.util.logging_util import setup_logging

def parse_args() -> argparse.Namespace:
    """Parse command line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(description="AIPerf Worker CLI")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Run command
    run_parser = subparsers.add_parser("run", help="Run a worker")
    run_parser.add_argument("--controller", required=True, help="Controller hostname or IP")
    run_parser.add_argument("--pub-port", type=int, default=5557, help="Controller PUB port")
    run_parser.add_argument("--sub-port", type=int, default=5558, help="Controller SUB port")
    run_parser.add_argument("--req-port", type=int, default=5559, help="Controller REQ port")
    run_parser.add_argument("--rep-port", type=int, default=5560, help="Controller REP port")
    run_parser.add_argument("--worker-id", help="Worker ID (generated if not provided)")
    run_parser.add_argument("--log-level", default="INFO", help="Log level")
    run_parser.add_argument("--log-file", help="Path to log file")
    
    return parser.parse_args()

async def run_worker(args: argparse.Namespace) -> int:
    """Run a worker.
    
    Args:
        args: Command line arguments
        
    Returns:
        Exit code
    """
    worker_id = args.worker_id or f"worker_{uuid.uuid4().hex[:8]}"
    logging.info(f"Starting worker {worker_id}")
    
    try:
        # Set up ZMQ communication
        communication = ZMQCommunication(
            component_id=worker_id,
            pub_address=f"tcp://{args.controller}:{args.pub_port}",
            sub_address=f"tcp://{args.controller}:{args.sub_port}",
            req_address=f"tcp://{args.controller}:{args.req_port}",
            rep_address=f"tcp://{args.controller}:{args.rep_port}"
        )
        
        # Initialize communication
        await communication.initialize()
        
        # Connect to controller and get configuration
        logging.info(f"Connecting to controller at {args.controller}")
        
        # Request worker configuration from controller
        config_response = await communication.request(
            "system_controller", 
            {
                "command": "get_worker_config"
            },
            timeout=30.0
        )
        
        if not config_response or "status" not in config_response or config_response["status"] != "success":
            logging.error(f"Failed to get worker configuration: {config_response}")
            return 1
            
        # Extract endpoint config from response
        endpoint_config = config_response.get("endpoint_config")
        if not endpoint_config:
            logging.error("No endpoint configuration provided")
            return 1
            
        # Create worker
        worker = Worker(
            endpoint_config=endpoint_config,
            communication=communication,
            component_id=worker_id
        )
        
        # Initialize worker
        if not await worker.initialize():
            logging.error("Failed to initialize worker")
            return 1
            
        # Publish identity
        if not await worker.publish_identity():
            logging.warning("Failed to publish worker identity")
            
        # Register with controller
        registration_response = await communication.request(
            "system_controller", 
            {
                "command": "register_worker",
                "worker_id": worker_id
            }
        )
        
        if not registration_response or "status" not in registration_response or registration_response["status"] != "success":
            logging.error(f"Failed to register worker: {registration_response}")
            return 1
            
        logging.info(f"Worker {worker_id} registered successfully")
        
        # Set up signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()
        for signame in ('SIGINT', 'SIGTERM'):
            try:
                loop.add_signal_handler(
                    getattr(signal, signame),
                    lambda: asyncio.create_task(shutdown(worker))
                )
            except (NotImplementedError, AttributeError):
                # Windows doesn't support SIGINT/SIGTERM
                pass
                
        # Run until shutdown
        shutdown_event = asyncio.Event()
        
        # Subscribe to shutdown events
        await communication.subscribe("system.shutdown", lambda _: shutdown_event.set())
        
        logging.info(f"Worker {worker_id} running, waiting for tasks")
        await shutdown_event.wait()
        
        # Ensure we shutdown
        await worker.shutdown()
        await communication.shutdown()
        
        return 0
    except Exception as e:
        logging.error(f"Error in worker: {e}")
        return 1

async def shutdown(worker: Worker) -> None:
    """Shut down worker gracefully.
    
    Args:
        worker: Worker instance
    """
    logging.info("Shutting down worker")
    await worker.shutdown()
    
async def main_async() -> int:
    """Main entry point (async).
    
    Returns:
        Exit code
    """
    args = parse_args()
    
    # Set up logging
    if hasattr(args, "log_level") and hasattr(args, "log_file"):
        setup_logging(args.log_level, args.log_file)
    elif hasattr(args, "log_level"):
        setup_logging(args.log_level)
    
    # Execute command
    if args.command == "run":
        return await run_worker(args)
    else:
        logging.error(f"Unknown command: {args.command}")
        return 1

def main() -> int:
    """Main entry point.
    
    Returns:
        Exit code
    """
    return asyncio.run(main_async())

if __name__ == "__main__":
    sys.exit(main()) 