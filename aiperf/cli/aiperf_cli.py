import argparse
import asyncio
import json
import logging
import os
import sys
import yaml
from typing import Any, Dict, List, Optional, Tuple, Union

# Add parent directory to path if running as script
if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from aiperf.config.config_loader import ConfigLoader
from aiperf.system.system_controller import SystemController
from aiperf.util.logging_util import setup_logging

def parse_args() -> argparse.Namespace:
    """Parse command line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(description="AIPerf - AI Performance Benchmark Tool")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Run command
    run_parser = subparsers.add_parser("run", help="Run a profile")
    run_parser.add_argument("config", help="Path to configuration file (JSON or YAML)")
    run_parser.add_argument("--log-level", default="INFO", help="Log level")
    run_parser.add_argument("--log-file", help="Path to log file")
    run_parser.add_argument("--kubernetes", action="store_true", help="Enable Kubernetes deployment")
    run_parser.add_argument("--k8s-namespace", help="Kubernetes namespace to use")
    run_parser.add_argument("--k8s-image", help="Kubernetes image to use")
    run_parser.add_argument("--k8s-service-account", help="Kubernetes service account to use")
    run_parser.add_argument("--k8s-no-config-map", action="store_true", help="Disable ConfigMap usage")
    run_parser.add_argument("--k8s-persistent-volume-claim", help="Kubernetes PVC for results storage")
    
    # Replay command
    replay_parser = subparsers.add_parser("replay", help="Replay a profile from records")
    replay_parser.add_argument("records", help="Path to records file")
    replay_parser.add_argument("--log-level", default="INFO", help="Log level")
    replay_parser.add_argument("--log-file", help="Path to log file")
    replay_parser.add_argument("--output", help="Path to output report")
    
    # Generate command
    generate_parser = subparsers.add_parser("generate", help="Generate a synthetic dataset")
    generate_parser.add_argument("config", help="Path to configuration file (JSON or YAML)")
    generate_parser.add_argument("--output", required=True, help="Path to output dataset")
    generate_parser.add_argument("--log-level", default="INFO", help="Log level")
    generate_parser.add_argument("--log-file", help="Path to log file")
    
    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate a configuration file")
    validate_parser.add_argument("config", help="Path to configuration file (JSON or YAML)")
    
    # Kubernetes management commands
    k8s_parser = subparsers.add_parser("kubernetes", help="Kubernetes management commands")
    k8s_subparsers = k8s_parser.add_subparsers(dest="k8s_command", help="Kubernetes command to run")
    
    # Apply command
    apply_parser = k8s_subparsers.add_parser("apply", help="Apply Kubernetes resources")
    apply_parser.add_argument("config", help="Path to configuration file (JSON or YAML)")
    apply_parser.add_argument("--namespace", help="Kubernetes namespace to use")
    apply_parser.add_argument("--dry-run", action="store_true", help="Perform a dry run")
    apply_parser.add_argument("--log-level", default="INFO", help="Log level")
    
    # Delete command
    delete_parser = k8s_subparsers.add_parser("delete", help="Delete Kubernetes resources")
    delete_parser.add_argument("config", help="Path to configuration file (JSON or YAML)")
    delete_parser.add_argument("--namespace", help="Kubernetes namespace to use")
    delete_parser.add_argument("--log-level", default="INFO", help="Log level")
    
    # Status command
    status_parser = k8s_subparsers.add_parser("status", help="Show Kubernetes deployment status")
    status_parser.add_argument("--namespace", help="Kubernetes namespace to use")
    status_parser.add_argument("--log-level", default="INFO", help="Log level")
    
    return parser.parse_args()

async def run_profile(args: argparse.Namespace) -> int:
    """Run a profile.
    
    Args:
        args: Command line arguments
        
    Returns:
        Exit code
    """
    logging.info(f"Loading configuration from: {args.config}")
    
    try:
        config = ConfigLoader.load_from_file(args.config)
        
        # Apply Kubernetes settings from command line
        if args.kubernetes or config.kubernetes.enabled:
            config.kubernetes.enabled = True
            
            if args.k8s_namespace:
                config.kubernetes.namespace = args.k8s_namespace
                
            if args.k8s_image:
                config.kubernetes.image = args.k8s_image
                
            if args.k8s_service_account:
                config.kubernetes.service_account = args.k8s_service_account
                
            if args.k8s_no_config_map:
                config.kubernetes.use_config_map = False
                
            if args.k8s_persistent_volume_claim:
                config.kubernetes.persistent_volume_claim = args.k8s_persistent_volume_claim
                
            # When using Kubernetes, ensure ZMQ communication is enabled
            if config.communication.type == "memory":
                logging.warning("Switching communication type to 'zmq' for Kubernetes deployment")
                config.communication.type = "zmq"
                config.communication.pub_address = "tcp://*:5557"
                config.communication.sub_address = "tcp://*:5558"
                config.communication.req_address = "tcp://*:5559"
                config.communication.rep_address = "tcp://*:5560"
                
    except Exception as e:
        logging.error(f"Error loading configuration: {e}")
        return 1
    
    logging.info(f"Initializing system controller for profile: {config.profile_name}")
    controller = SystemController(config)
    
    # Initialize and start
    if not await controller.initialize():
        logging.error("Failed to initialize system controller")
        return 1
    
    # Wait for all components to be ready
    if not await controller.ready_check():
        logging.error("System is not ready")
        return 1
    
    # Start profile
    if not await controller.start_profile():
        logging.error("Failed to start profile")
        return 1
    
    try:
        # Wait for shutdown (e.g., CTRL+C)
        await controller.wait_for_shutdown()
    except KeyboardInterrupt:
        logging.info("Keyboard interrupt detected, shutting down...")
    finally:
        # Ensure we shutdown
        await controller.shutdown()
    
    return 0

async def replay_profile(args: argparse.Namespace) -> int:
    """Replay a profile from records.
    
    Args:
        args: Command line arguments
        
    Returns:
        Exit code
    """
    logging.info(f"Replaying profile from records: {args.records}")
    
    # This would be implemented with a dedicated replay processor
    logging.error("Replay functionality not yet implemented")
    return 1

async def generate_dataset(args: argparse.Namespace) -> int:
    """Generate a synthetic dataset.
    
    Args:
        args: Command line arguments
        
    Returns:
        Exit code
    """
    logging.info(f"Generating dataset with configuration: {args.config}")
    
    # This would be implemented with a dedicated dataset generator
    logging.error("Dataset generation functionality not yet implemented")
    return 1

async def validate_config(args: argparse.Namespace) -> int:
    """Validate a configuration file.
    
    Args:
        args: Command line arguments
        
    Returns:
        Exit code
    """
    logging.info(f"Validating configuration: {args.config}")
    
    try:
        config = ConfigLoader.load_from_file(args.config)
        errors = config.validate()
        
        if errors:
            logging.error("Configuration validation failed:")
            for error in errors:
                logging.error(f"  - {error}")
            return 1
        else:
            logging.info("Configuration validation successful")
            return 0
    except Exception as e:
        logging.error(f"Error validating configuration: {e}")
        return 1

async def k8s_apply(args: argparse.Namespace) -> int:
    """Apply Kubernetes resources.
    
    Args:
        args: Command line arguments
        
    Returns:
        Exit code
    """
    logging.info(f"Applying Kubernetes resources for configuration: {args.config}")
    
    try:
        # Load configuration
        config = ConfigLoader.load_from_file(args.config)
        
        # Override namespace if specified
        if args.namespace:
            config.kubernetes.namespace = args.namespace
            
        # Enable Kubernetes
        config.kubernetes.enabled = True
        
        # Import here to avoid dependency issues
        from aiperf.system.kubernetes_manager import KubernetesManager
        
        # Create manager and apply resources
        k8s_manager = KubernetesManager(config)
        success = await k8s_manager.apply_resources(dry_run=args.dry_run)
        
        if success:
            logging.info("Kubernetes resources applied successfully")
            return 0
        else:
            logging.error("Failed to apply Kubernetes resources")
            return 1
            
    except Exception as e:
        logging.error(f"Error applying Kubernetes resources: {e}")
        return 1

async def k8s_delete(args: argparse.Namespace) -> int:
    """Delete Kubernetes resources.
    
    Args:
        args: Command line arguments
        
    Returns:
        Exit code
    """
    logging.info(f"Deleting Kubernetes resources for configuration: {args.config}")
    
    try:
        # Load configuration
        config = ConfigLoader.load_from_file(args.config)
        
        # Override namespace if specified
        if args.namespace:
            config.kubernetes.namespace = args.namespace
            
        # Enable Kubernetes
        config.kubernetes.enabled = True
        
        # Import here to avoid dependency issues
        from aiperf.system.kubernetes_manager import KubernetesManager
        
        # Create manager and delete resources
        k8s_manager = KubernetesManager(config)
        success = await k8s_manager.delete_resources()
        
        if success:
            logging.info("Kubernetes resources deleted successfully")
            return 0
        else:
            logging.error("Failed to delete Kubernetes resources")
            return 1
            
    except Exception as e:
        logging.error(f"Error deleting Kubernetes resources: {e}")
        return 1

async def k8s_status(args: argparse.Namespace) -> int:
    """Show Kubernetes deployment status.
    
    Args:
        args: Command line arguments
        
    Returns:
        Exit code
    """
    logging.info("Showing Kubernetes deployment status")
    
    try:
        # Import here to avoid dependency issues
        from aiperf.system.kubernetes_manager import KubernetesManager
        
        # Create manager with minimal config and show status
        from aiperf.config.config_models import AIperfConfig, KubernetesConfig
        
        # Create a minimal config
        config = AIperfConfig(profile_name="status_check")
        config.kubernetes.enabled = True
        
        # Override namespace if specified
        if args.namespace:
            config.kubernetes.namespace = args.namespace
            
        # Create manager and get status
        k8s_manager = KubernetesManager(config)
        status = await k8s_manager.get_status()
        
        # Print status
        for component, component_status in status.items():
            logging.info(f"{component}: {component_status}")
            
        return 0
            
    except Exception as e:
        logging.error(f"Error getting Kubernetes status: {e}")
        return 1

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
        return await run_profile(args)
    elif args.command == "replay":
        return await replay_profile(args)
    elif args.command == "generate":
        return await generate_dataset(args)
    elif args.command == "validate":
        return await validate_config(args)
    elif args.command == "kubernetes":
        if args.k8s_command == "apply":
            return await k8s_apply(args)
        elif args.k8s_command == "delete":
            return await k8s_delete(args)
        elif args.k8s_command == "status":
            return await k8s_status(args)
        else:
            logging.error(f"Unknown Kubernetes command: {args.k8s_command}")
            return 1
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