# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio

from pydantic import BaseModel, Field

from aiperf.common.enums.base_enums import CaseInsensitiveStrEnum
from aiperf.common.exceptions import AIPerfError


class SlurmJobState(CaseInsensitiveStrEnum):
    """SLURM job states as returned by squeue."""

    PENDING = "PD"
    RUNNING = "R"
    SUSPENDED = "S"
    COMPLETED = "CD"
    CANCELLED = "CA"
    FAILED = "F"
    TIMEOUT = "TO"
    NODE_FAIL = "NF"
    PREEMPTED = "PR"
    BOOT_FAIL = "BF"
    DEADLINE = "DL"
    OUT_OF_MEMORY = "OOM"


class SlurmJobInfo(BaseModel):
    """Information about a SLURM job."""

    job_id: str = Field(..., description="SLURM job ID")
    job_name: str = Field(..., description="Name of the job")
    user: str = Field(..., description="User who submitted the job")
    state: SlurmJobState = Field(..., description="Current job state")
    time: str = Field(..., description="Time the job has been running")
    time_left: str = Field(..., description="Time left for the job")
    nodes: str = Field(..., description="Nodes allocated to the job")
    nodelist: str = Field(..., description="List of nodes allocated")


class SlurmUtils:
    """Utilities for interacting with SLURM commands."""

    def __init__(
        self,
        partition: str | None = None,
        account: str | None = None,
        qos: str | None = None,
        reservation: str | None = None,
        job_name_prefix: str = "aiperf",
    ):
        """Initialize SLURM utilities.

        Args:
            partition: Default SLURM partition to use
            account: Default SLURM account to use
            qos: Default QoS to use
            reservation: Default reservation to use
            job_name_prefix: Prefix for job names
        """
        self.partition = partition
        self.account = account
        self.qos = qos
        self.reservation = reservation
        self.job_name_prefix = job_name_prefix

    async def submit_job(
        self,
        command: str,
        job_name: str,
        num_nodes: int = 1,
        num_tasks: int = 1,
        cpus_per_task: int = 1,
        memory_gb: int | None = None,
        time_limit: str = "01:00:00",
        output_file: str | None = None,
        error_file: str | None = None,
        working_directory: str | None = None,
        env_vars: dict[str, str] | None = None,
        additional_sbatch_args: list[str] | None = None,
    ) -> str:
        """Submit a job using sbatch.

        Args:
            command: Command to run in the job
            job_name: Name of the job
            num_nodes: Number of nodes to allocate
            num_tasks: Number of tasks
            cpus_per_task: Number of CPUs per task
            memory_gb: Memory in GB to allocate
            time_limit: Time limit for the job (HH:MM:SS format)
            output_file: Path for stdout output
            error_file: Path for stderr output
            working_directory: Working directory for the job
            env_vars: Environment variables to set
            additional_sbatch_args: Additional sbatch arguments

        Returns:
            Job ID as string

        Raises:
            AIPerfError: If job submission fails
        """
        sbatch_args = [
            "sbatch",
            "--job-name",
            f"{self.job_name_prefix}_{job_name}",
            "--nodes",
            str(num_nodes),
            "--ntasks",
            str(num_tasks),
            "--cpus-per-task",
            str(cpus_per_task),
            "--time",
            time_limit,
            "--parsable",  # Return job ID in parsable format
        ]

        # Add optional arguments
        if self.partition:
            sbatch_args.extend(["--partition", self.partition])
        if self.account:
            sbatch_args.extend(["--account", self.account])
        if self.qos:
            sbatch_args.extend(["--qos", self.qos])
        if self.reservation:
            sbatch_args.extend(["--reservation", self.reservation])
        if memory_gb:
            sbatch_args.extend(["--mem", f"{memory_gb}G"])
        if output_file:
            sbatch_args.extend(["--output", output_file])
        if error_file:
            sbatch_args.extend(["--error", error_file])
        if working_directory:
            sbatch_args.extend(["--chdir", working_directory])

        # Add environment variables
        if env_vars:
            for key, value in env_vars.items():
                sbatch_args.extend(["--export", f"{key}={value}"])

        # Add any additional sbatch arguments
        if additional_sbatch_args:
            sbatch_args.extend(additional_sbatch_args)

        # Add the command to run
        sbatch_args.extend(["--wrap", command])

        try:
            result = await self._run_command(sbatch_args)
            job_id = result.strip()
            return job_id
        except Exception as e:
            raise AIPerfError(f"Failed to submit SLURM job: {e}") from e

    async def get_job_info(self, job_id: str) -> SlurmJobInfo | None:
        """Get information about a specific job.

        Args:
            job_id: SLURM job ID

        Returns:
            Job information or None if job not found
        """
        try:
            cmd = [
                "squeue",
                "--job",
                job_id,
                "--format",
                "%.18i %.9P %.8j %.8u %.8T %.10M %.9l %.6D %R",
                "--noheader",
            ]
            result = await self._run_command(cmd)

            if not result.strip():
                return None

            # Parse the squeue output
            parts = result.strip().split()
            if len(parts) >= 9:
                return SlurmJobInfo(
                    job_id=parts[0],
                    job_name=parts[2],
                    user=parts[3],
                    state=SlurmJobState(parts[4]),
                    time=parts[5],
                    time_left=parts[6],
                    nodes=parts[7],
                    nodelist=" ".join(parts[8:]) if len(parts) > 8 else "",
                )
            return None
        except Exception:
            # Job might have completed and is no longer in squeue
            return None

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a SLURM job.

        Args:
            job_id: SLURM job ID to cancel

        Returns:
            True if cancellation was successful
        """
        try:
            await self._run_command(["scancel", job_id])
            return True
        except Exception:
            return False

    async def get_job_status(self, job_id: str) -> SlurmJobState | None:
        """Get the status of a job.

        Args:
            job_id: SLURM job ID

        Returns:
            Job state or None if not found
        """
        job_info = await self.get_job_info(job_id)
        return job_info.state if job_info else None

    async def wait_for_job_completion(
        self, job_id: str, check_interval: float = 5.0, timeout: float | None = None
    ) -> SlurmJobState:
        """Wait for a job to complete.

        Args:
            job_id: SLURM job ID
            check_interval: How often to check job status (seconds)
            timeout: Maximum time to wait (seconds), None for no timeout

        Returns:
            Final job state

        Raises:
            AIPerfError: If timeout is reached or job fails
        """
        start_time = asyncio.get_event_loop().time()

        while True:
            status = await self.get_job_status(job_id)

            if status is None:
                # Job might have completed and is no longer visible
                # Check using sacct for historical job info
                try:
                    cmd = [
                        "sacct",
                        "--job",
                        job_id,
                        "--format",
                        "State",
                        "--noheader",
                        "--parsable2",
                    ]
                    result = await self._run_command(cmd)
                    if result.strip():
                        # Return the last state from sacct
                        states = [
                            line.strip()
                            for line in result.strip().split("\n")
                            if line.strip()
                        ]
                        if states:
                            return SlurmJobState(states[-1])
                except Exception:
                    pass
                break

            if status in [
                SlurmJobState.COMPLETED,
                SlurmJobState.CANCELLED,
                SlurmJobState.FAILED,
                SlurmJobState.TIMEOUT,
                SlurmJobState.NODE_FAIL,
                SlurmJobState.BOOT_FAIL,
                SlurmJobState.DEADLINE,
                SlurmJobState.OUT_OF_MEMORY,
            ]:
                return status

            if timeout and (asyncio.get_event_loop().time() - start_time) > timeout:
                raise AIPerfError(f"Timeout waiting for job {job_id} to complete")

            await asyncio.sleep(check_interval)

        raise AIPerfError(f"Lost track of job {job_id}")

    async def is_slurm_available(self) -> bool:
        """Check if SLURM commands are available on the system.

        Returns:
            True if SLURM is available
        """
        try:
            await self._run_command(["which", "sbatch"])
            await self._run_command(["which", "squeue"])
            await self._run_command(["which", "scancel"])
            return True
        except Exception:
            return False

    async def _run_command(self, cmd: list[str]) -> str:
        """Run a shell command asynchronously.

        Args:
            cmd: Command and arguments as list

        Returns:
            stdout output as string

        Raises:
            AIPerfError: If command fails
        """
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                raise AIPerfError(
                    f"Command {' '.join(cmd)} failed with return code {process.returncode}: {stderr.decode()}"
                )

            return stdout.decode()
        except FileNotFoundError as e:
            raise AIPerfError(f"Command not found: {' '.join(cmd)}") from e
        except Exception as e:
            raise AIPerfError(f"Error running command {' '.join(cmd)}: {e}") from e
