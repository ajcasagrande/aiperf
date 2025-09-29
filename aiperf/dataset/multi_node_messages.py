# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from pydantic import Field

from aiperf.common.enums import MessageType
from aiperf.common.messages.base_messages import Message
from aiperf.common.messages.service_messages import BaseServiceMessage
from aiperf.common.types import MessageTypeT


class MultiNodeDatasetInfoMessage(BaseServiceMessage):
    """Enhanced dataset info message for multi-node deployments."""

    message_type: MessageTypeT = MessageType.DATASET_INFO

    # Deployment information
    deployment_mode: str = Field(
        description="Deployment mode (single_node, shared_storage, redis_distributed, hybrid)"
    )
    dataset_id: str = Field(description="Unique dataset identifier")
    node_id: str = Field(description="Node identifier where dataset was created")

    # Access methods
    data_location: str | None = Field(
        default=None,
        description="File path for memory-mapped data (shared storage mode)",
    )
    index_location: str | None = Field(
        default=None,
        description="File path for memory-mapped index (shared storage mode)",
    )

    # Redis configuration (if applicable)
    redis_host: str | None = Field(
        default=None, description="Redis host for distributed mode"
    )
    redis_port: int | None = Field(
        default=None, description="Redis port for distributed mode"
    )
    redis_db: int | None = Field(default=None, description="Redis database number")

    # Dataset metadata
    dataset_size: int = Field(
        default=0, description="Number of conversations in dataset"
    )
    compression_enabled: bool = Field(
        default=False, description="Whether compression is enabled"
    )

    # Performance hints
    preferred_access_method: str = Field(
        default="auto",
        description="Preferred access method for this node (local, redis, shared_storage)",
    )
    fallback_methods: list[str] = Field(
        default_factory=list, description="Available fallback access methods"
    )

    enabled: bool = Field(default=True, description="Whether dataset access is enabled")


class DatasetSyncRequestMessage(Message):
    """Request for dataset synchronization across nodes."""

    message_type: MessageTypeT = (
        MessageType.DATASET_TIMING_REQUEST
    )  # Reuse existing type

    dataset_id: str = Field(description="Dataset ID to synchronize")
    requesting_node: str = Field(description="Node requesting synchronization")
    sync_method: str = Field(
        default="incremental",
        description="Synchronization method (full, incremental, verify)",
    )


class DatasetSyncResponseMessage(Message):
    """Response for dataset synchronization."""

    message_type: MessageTypeT = (
        MessageType.DATASET_TIMING_RESPONSE
    )  # Reuse existing type

    dataset_id: str = Field(description="Dataset ID")
    sync_status: str = Field(
        description="Synchronization status (success, failed, partial)"
    )
    sync_details: dict[str, str] = Field(
        default_factory=dict, description="Additional synchronization details"
    )
    data_checksum: str | None = Field(
        default=None, description="Checksum for data integrity verification"
    )


class NodeDatasetStatusMessage(BaseServiceMessage):
    """Message reporting node-specific dataset status."""

    message_type: MessageTypeT = (
        MessageType.DATASET_CONFIGURED_NOTIFICATION
    )  # Reuse existing

    node_id: str = Field(description="Node identifier")
    dataset_id: str = Field(description="Dataset ID")
    status: str = Field(description="Status (ready, loading, error, unavailable)")

    # Access capabilities
    supports_local_access: bool = Field(
        default=False, description="Supports local mmap access"
    )
    supports_redis_access: bool = Field(
        default=False, description="Supports Redis access"
    )
    supports_shared_storage: bool = Field(
        default=False, description="Supports shared storage"
    )

    # Performance metrics
    avg_access_time_ms: float | None = Field(
        default=None, description="Average conversation access time in milliseconds"
    )
    cache_hit_ratio: float | None = Field(
        default=None, description="Cache hit ratio (0.0 to 1.0)"
    )

    error_message: str | None = Field(
        default=None, description="Error message if status is 'error'"
    )
