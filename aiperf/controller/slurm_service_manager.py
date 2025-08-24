# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import os
import uuid
from pathlib import Path

from pydantic import BaseModel, Field

from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.constants import (
    DEFAULT_SERVICE_REGISTRATION_TIMEOUT,
    DEFAULT_SERVICE_START_TIMEOUT,
    TASK_CANCEL_TIMEOUT_SHORT,
)
from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import ServiceRegistrationStatus, ServiceRunType
from aiperf.common.exceptions import AIPerfError
from aiperf.common.factories import ServiceFactory, ServiceManagerFactory
from aiperf.common.protocols import ServiceManagerProtocol
from aiperf.common.types import ServiceTypeT
from aiperf.controller.base_service_manager import BaseServiceManager
from aiperf.controller.slurm_utils import SlurmJobState, SlurmUtils


class ServiceSlurmRunInfo(BaseModel):
    """Information about a service running as a SLURM job."""

    job_id: str = Field(..., description="SLURM job ID")
    service_type: ServiceTypeT = Field(
        ...,
        description="Type of service running in the job",
    )
    service_id: str = Field(
        ...,
        description="ID of the service running in the job",
    )
    job_name: str = Field(..., description="SLURM job name")
    output_file: str | None = Field(default=None, description="Path to job output file")
    error_file: str | None = Field(default=None, description="Path to job error file")


@implements_protocol(ServiceManagerProtocol)
@ServiceManagerFactory.register(ServiceRunType.SLURM)
class SlurmServiceManager(BaseServiceManager):
    """
    Service Manager for starting and stopping services as SLURM jobs.
    """

    def __init__(
        self,
        required_services: dict[ServiceTypeT, int],
        service_config: ServiceConfig,
        user_config: UserConfig,
        slurm_partition: str | None = None,
        slurm_account: str | None = None,
        slurm_qos: str | None = None,
        slurm_reservation: str | None = None,
        slurm_time_limit: str = "01:00:00",
        slurm_memory_gb: int | None = None,
        slurm_cpus_per_task: int = 1,
        job_logs_directory: str | None = None,
        python_executable: str = "python",
        working_directory: str | None = None,
        **kwargs,
    ):
        """Initialize SLURM Service Manager.

        Args:
            required_services: Services to run and their replica counts
            service_config: Service configuration
            user_config: User configuration
            slurm_partition: SLURM partition to use
            slurm_account: SLURM account to charge
            slurm_qos: Quality of Service to use
            slurm_reservation: Reservation to use
            slurm_time_limit: Time limit for jobs (HH:MM:SS)
            slurm_memory_gb: Memory in GB to allocate per job
            slurm_cpus_per_task: CPUs per task
            job_logs_directory: Directory to store job logs
            python_executable: Python executable to use
            working_directory: Working directory for jobs
            **kwargs: Additional arguments
        """
        super().__init__(required_services, service_config, user_config, **kwargs)

        # SLURM configuration
        self.slurm_utils = SlurmUtils(
            partition=slurm_partition,
            account=slurm_account,
            qos=slurm_qos,
            reservation=slurm_reservation,
            job_name_prefix="aiperf",
        )
        self.slurm_time_limit = slurm_time_limit
        self.slurm_memory_gb = slurm_memory_gb
        self.slurm_cpus_per_task = slurm_cpus_per_task

        # Job management
        self.slurm_jobs: list[ServiceSlurmRunInfo] = []
        self.job_logs_directory = (
            Path(job_logs_directory)
            if job_logs_directory
            else Path.cwd() / "slurm_logs"
        )
        self.job_logs_directory.mkdir(parents=True, exist_ok=True)

        # Python and working directory
        self.python_executable = python_executable
        self.working_directory = working_directory or os.getcwd()

    async def _start_service_manager(self) -> None:
        """Override to check SLURM availability before starting."""
        # Check if SLURM is available
        if not await self.slurm_utils.is_slurm_available():
            raise AIPerfError(
                "SLURM commands (sbatch, squeue, scancel) not available on this system"
            )

        self.info("SLURM commands are available")
        await super()._start_service_manager()

    async def run_service(
        self, service_type: ServiceTypeT, num_replicas: int = 1
    ) -> None:
        """Run a service with the given number of replicas as SLURM jobs.

        Args:
            service_type: Type of service to run
            num_replicas: Number of replicas to start
        """
        self.debug(f"Starting {num_replicas} replicas of {service_type} as SLURM jobs")

        service_class = ServiceFactory.get_class_from_type(service_type)

        for replica_num in range(num_replicas):
            service_id = f"{service_type}_{uuid.uuid4().hex[:8]}"
            job_name = f"{service_type}_{replica_num}"

            # Create log files
            output_file = self.job_logs_directory / f"{job_name}_{service_id}.out"
            error_file = self.job_logs_directory / f"{job_name}_{service_id}.err"

            # Create the command to run the service
            # This assumes there's a way to bootstrap and run a service from the command line
            command = self._create_service_command(
                service_class=service_class.__name__,
                service_id=service_id,
                service_type=service_type,
            )

            # Prepare environment variables
            env_vars = {
                "AIPERF_SERVICE_ID": service_id,
                "AIPERF_SERVICE_TYPE": service_type,
            }

            try:
                job_id = await self.slurm_utils.submit_job(
                    command=command,
                    job_name=job_name,
                    num_nodes=1,
                    num_tasks=1,
                    cpus_per_task=self.slurm_cpus_per_task,
                    memory_gb=self.slurm_memory_gb,
                    time_limit=self.slurm_time_limit,
                    output_file=str(output_file),
                    error_file=str(error_file),
                    working_directory=self.working_directory,
                    env_vars=env_vars,
                )

                self.debug(
                    f"Submitted SLURM job {job_id} for {service_type} (service_id: {service_id})"
                )

                # Store job information
                job_info = ServiceSlurmRunInfo(
                    job_id=job_id,
                    service_type=service_type,
                    service_id=service_id,
                    job_name=job_name,
                    output_file=str(output_file),
                    error_file=str(error_file),
                )

                self.slurm_jobs.append(job_info)

                self.info(f"Started {service_type} as SLURM job {job_id}")

            except Exception as e:
                self.error(f"Failed to start {service_type} as SLURM job: {e}")
                raise

    def _create_service_command(
        self,
        service_class: str,
        service_id: str,
        service_type: ServiceTypeT,
    ) -> str:
        """Create the command to run a service.

        This method creates a command that runs the service using its main() function.
        Each service module has a main() function that calls bootstrap_and_run_service.

        Args:
            service_class: Name of the service class (not used directly)
            service_id: Unique service ID
            service_type: Type of service

        Returns:
            Command string to execute
        """
        # Map service types to their corresponding module paths
        service_module_map = {
            "system_controller": "aiperf.controller.system_controller",
            "dataset_manager": "aiperf.dataset.dataset_manager",
            "timing_manager": "aiperf.timing.timing_manager",
            "record_processor": "aiperf.records.record_processor_service",
            "records_manager": "aiperf.records.records_manager",
            "worker_manager": "aiperf.workers.worker_manager",
            "worker": "aiperf.workers.worker",
        }

        module_path = service_module_map.get(service_type)
        if not module_path:
            raise AIPerfError(f"Unknown service type: {service_type}")

        # Each service module has a main() function that bootstraps and runs the service
        # We can run it directly as a Python module
        return f"{self.python_executable} -m {module_path}"

    async def stop_service(
        self, service_type: ServiceTypeT, service_id: str | None = None
    ) -> list[BaseException | None]:
        """Stop SLURM jobs for the specified service type and optionally service ID.

        Args:
            service_type: Type of service to stop
            service_id: Specific service ID to stop (if None, stops all of this type)

        Returns:
            List of exceptions (if any) from stop operations
        """
        self.debug(f"Stopping {service_type} SLURM job(s) with id: {service_id}")

        jobs_to_stop = [
            job
            for job in self.slurm_jobs
            if job.service_type == service_type
            and (service_id is None or job.service_id == service_id)
        ]

        results = []
        for job in jobs_to_stop:
            try:
                success = await self.slurm_utils.cancel_job(job.job_id)
                if success:
                    self.debug(f"Cancelled SLURM job {job.job_id} for {service_type}")
                    # Wait for job to actually be cancelled
                    try:
                        final_state = await self.slurm_utils.wait_for_job_completion(
                            job.job_id, timeout=TASK_CANCEL_TIMEOUT_SHORT
                        )
                        if final_state == SlurmJobState.CANCELLED:
                            self.debug(f"Job {job.job_id} successfully cancelled")
                        else:
                            self.warning(
                                f"Job {job.job_id} ended with state {final_state}"
                            )
                    except Exception as e:
                        self.warning(
                            f"Error waiting for job {job.job_id} cancellation: {e}"
                        )

                    # Remove from our tracking list
                    self.slurm_jobs.remove(job)
                    results.append(None)
                else:
                    error = AIPerfError(f"Failed to cancel SLURM job {job.job_id}")
                    self.error(str(error))
                    results.append(error)
            except Exception as e:
                self.error(f"Error stopping SLURM job {job.job_id}: {e}")
                results.append(e)

        return results

    async def shutdown_all_services(self) -> list[BaseException | None]:
        """Stop all SLURM jobs."""
        self.debug("Stopping all SLURM jobs")

        results = []
        jobs_to_cancel = self.slurm_jobs.copy()

        # Cancel all jobs in parallel
        cancel_tasks = []
        for job in jobs_to_cancel:
            task = asyncio.create_task(self._cancel_job_with_wait(job))
            cancel_tasks.append(task)

        if cancel_tasks:
            results = await asyncio.gather(*cancel_tasks, return_exceptions=True)

        # Clear our job list
        self.slurm_jobs.clear()
        return results

    async def kill_all_services(self) -> list[BaseException | None]:
        """Force kill all SLURM jobs (same as shutdown for SLURM)."""
        self.debug("Force killing all SLURM jobs")
        # For SLURM, scancel is already a force operation
        return await self.shutdown_all_services()

    async def _cancel_job_with_wait(self, job: ServiceSlurmRunInfo) -> Exception | None:
        """Cancel a job and wait for it to finish.

        Args:
            job: Job information

        Returns:
            Exception if cancellation failed, None otherwise
        """
        try:
            success = await self.slurm_utils.cancel_job(job.job_id)
            if success:
                self.debug(f"Cancelled SLURM job {job.job_id}")
                # Wait for job to be cancelled (with timeout)
                try:
                    await self.slurm_utils.wait_for_job_completion(
                        job.job_id, timeout=TASK_CANCEL_TIMEOUT_SHORT
                    )
                except Exception as e:
                    self.warning(
                        f"Timeout waiting for job {job.job_id} cancellation: {e}"
                    )
                return None
            else:
                error = AIPerfError(f"Failed to cancel SLURM job {job.job_id}")
                self.error(str(error))
                return error
        except Exception as e:
            self.error(f"Error cancelling SLURM job {job.job_id}: {e}")
            return e

    async def wait_for_all_services_registration(
        self,
        stop_event: asyncio.Event,
        timeout_seconds: float = DEFAULT_SERVICE_REGISTRATION_TIMEOUT,
    ) -> None:
        """Wait for all required services to be registered.

        Args:
            stop_event: Event to check if operation should be cancelled
            timeout_seconds: Maximum time to wait in seconds

        Raises:
            Exception if any service failed to register, None otherwise
        """
        self.debug("Waiting for all required SLURM jobs to register their services...")

        # Get the set of required service types for checking completion
        required_types = set(self.required_services.keys())

        async def _wait_for_registration():
            while not stop_event.is_set():
                # Get all registered service types from the id map
                registered_types = {
                    service_info.service_type
                    for service_info in self.service_id_map.values()
                    if service_info.registration_status
                    == ServiceRegistrationStatus.REGISTERED
                }

                # Check if all required types are registered
                if required_types.issubset(registered_types):
                    return

                # Check if any of our jobs have failed
                for job in self.slurm_jobs:
                    job_status = await self.slurm_utils.get_job_status(job.job_id)
                    if job_status in [
                        SlurmJobState.FAILED,
                        SlurmJobState.CANCELLED,
                        SlurmJobState.TIMEOUT,
                        SlurmJobState.NODE_FAIL,
                        SlurmJobState.OUT_OF_MEMORY,
                    ]:
                        raise AIPerfError(
                            f"SLURM job {job.job_id} for {job.service_type} failed with state {job_status}"
                        )

                # Wait a bit before checking again
                await asyncio.sleep(0.5)

        try:
            await asyncio.wait_for(_wait_for_registration(), timeout=timeout_seconds)
        except asyncio.TimeoutError as e:
            # Log which services didn't register in time
            registered_types_set = set(
                service_info.service_type
                for service_info in self.service_id_map.values()
                if service_info.registration_status
                == ServiceRegistrationStatus.REGISTERED
            )

            for service_type in required_types:
                if service_type not in registered_types_set:
                    self.error(
                        f"Service {service_type} failed to register within timeout"
                    )
                    # Check corresponding SLURM job status
                    job = next(
                        (j for j in self.slurm_jobs if j.service_type == service_type),
                        None,
                    )
                    if job:
                        job_status = await self.slurm_utils.get_job_status(job.job_id)
                        self.error(f"SLURM job {job.job_id} status: {job_status}")

                        # Log job output if available
                        if job.error_file and Path(job.error_file).exists():
                            try:
                                with open(job.error_file) as f:
                                    error_content = f.read()
                                if error_content.strip():
                                    self.error(
                                        f"Job {job.job_id} stderr: {error_content}"
                                    )
                            except Exception:
                                pass

            raise AIPerfError(
                "Some SLURM services failed to register within timeout"
            ) from e

    async def wait_for_all_services_start(
        self,
        stop_event: asyncio.Event,
        timeout_seconds: float = DEFAULT_SERVICE_START_TIMEOUT,
    ) -> None:
        """Wait for all required services to be started.

        Args:
            stop_event: Event to check if operation should be cancelled
            timeout_seconds: Maximum time to wait in seconds
        """
        self.debug("Waiting for all required SLURM jobs to start...")

        async def _wait_for_jobs_to_start():
            while not stop_event.is_set():
                all_running = True

                for job in self.slurm_jobs:
                    job_status = await self.slurm_utils.get_job_status(job.job_id)

                    if job_status is None:
                        # Job might have completed already or failed
                        self.warning(f"Job {job.job_id} no longer visible in queue")
                        continue

                    if job_status == SlurmJobState.PENDING:
                        all_running = False
                        continue
                    elif job_status == SlurmJobState.RUNNING:
                        continue
                    elif job_status in [
                        SlurmJobState.FAILED,
                        SlurmJobState.CANCELLED,
                        SlurmJobState.TIMEOUT,
                        SlurmJobState.NODE_FAIL,
                        SlurmJobState.OUT_OF_MEMORY,
                    ]:
                        raise AIPerfError(
                            f"SLURM job {job.job_id} for {job.service_type} failed with state {job_status}"
                        )

                if all_running:
                    return

                await asyncio.sleep(1.0)

        try:
            await asyncio.wait_for(_wait_for_jobs_to_start(), timeout=timeout_seconds)
            self.info("All SLURM jobs are running")
        except asyncio.TimeoutError as e:
            # Log status of jobs that didn't start
            for job in self.slurm_jobs:
                job_status = await self.slurm_utils.get_job_status(job.job_id)
                self.error(
                    f"Job {job.job_id} ({job.service_type}) status: {job_status}"
                )

            raise AIPerfError("Some SLURM jobs failed to start within timeout") from e
