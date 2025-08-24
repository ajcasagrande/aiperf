#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Example demonstrating how to use the SLURM Service Manager.

This example shows how to configure and use the SLURM service manager
for running AIPerf services on HPC clusters with SLURM.
"""

import asyncio

from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.enums import ServiceRunType, ServiceType
from aiperf.common.factories import ServiceManagerFactory


async def example_slurm_usage():
    """Example showing how to use SLURM service manager."""

    # Example SLURM configuration
    slurm_config = {
        "slurm_partition": "gpu",  # SLURM partition to use
        "slurm_account": "my_account",  # SLURM account
        "slurm_qos": "normal",  # Quality of Service
        "slurm_time_limit": "02:00:00",  # 2 hour time limit
        "slurm_memory_gb": 8,  # 8GB memory per job
        "slurm_cpus_per_task": 4,  # 4 CPUs per job
        "job_logs_directory": "/scratch/aiperf_logs",  # Where to store job logs
        "python_executable": "/opt/miniconda/envs/aiperf/bin/python",  # Python to use
        "working_directory": "/home/user/aiperf_workspace",  # Working directory
    }

    # Create service and user configs (you'd load these from your config files)
    service_config = ServiceConfig(
        service_run_type=ServiceRunType.SLURM,
        # ... other service config options
    )

    user_config = UserConfig(
        # ... your user config options
    )

    # Define which services to run
    required_services = {
        ServiceType.DATASET_MANAGER: 1,
        ServiceType.TIMING_MANAGER: 1,
        ServiceType.WORKER_MANAGER: 1,
        ServiceType.RECORDS_MANAGER: 1,
        ServiceType.RECORD_PROCESSOR: 2,  # Run 2 record processors
        ServiceType.WORKER: 4,  # Run 4 workers
    }

    # Create SLURM service manager
    service_manager = ServiceManagerFactory.create_instance(
        ServiceRunType.SLURM,
        required_services=required_services,
        service_config=service_config,
        user_config=user_config,
        **slurm_config,
    )

    try:
        # Initialize and start the service manager
        await service_manager.initialize()
        await service_manager.start()

        print("SLURM service manager started successfully!")
        print(f"Submitted {sum(required_services.values())} SLURM jobs")

        # Wait for services to register (in a real application, you'd handle this differently)
        stop_event = asyncio.Event()
        await service_manager.wait_for_all_services_registration(stop_event)
        print("All services registered!")

        # Wait for services to start
        await service_manager.wait_for_all_services_start(stop_event)
        print("All services started!")

        # In a real application, you would run your benchmark here
        # For this example, we'll just wait a bit
        await asyncio.sleep(10)

    except Exception as e:
        print(f"Error: {e}")

    finally:
        # Clean up - stop all services
        print("Stopping all SLURM jobs...")
        try:
            await service_manager.shutdown_all_services()
            print("All SLURM jobs stopped successfully")
        except Exception as e:
            print(f"Error stopping services: {e}")
            # Force kill if graceful shutdown fails
            await service_manager.kill_all_services()


def check_slurm_availability():
    """Check if SLURM is available on this system."""
    import subprocess

    try:
        subprocess.run(["which", "sbatch"], check=True, capture_output=True)
        subprocess.run(["which", "squeue"], check=True, capture_output=True)
        subprocess.run(["which", "scancel"], check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


if __name__ == "__main__":
    print("SLURM Service Manager Example")
    print("=" * 40)

    # Check if SLURM is available
    if not check_slurm_availability():
        print("ERROR: SLURM commands not found on this system")
        print("This example requires sbatch, squeue, and scancel to be available")
        print("Please ensure SLURM is installed and configured")
        exit(1)

    print("SLURM commands detected")
    print("Running example...")

    # Run the example
    asyncio.run(example_slurm_usage())
