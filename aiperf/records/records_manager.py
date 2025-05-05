import uuid
import asyncio
import logging
import time
import json
import os
from abc import abstractmethod
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable

from ..common.base_manager import BaseManager
from ..common.models import Record, Conversation, Metric
from ..common.communication import Communication
from ..config.config_models import MetricsConfig


class RecordsManager(BaseManager):
    """Records manager for AIPerf.

    Responsible for storing and managing records from worker requests,
    making them available for post-processors.
    """

    def __init__(
        self,
        metrics_config: Optional[MetricsConfig] = None,
        communication: Optional[Communication] = None,
        component_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the records manager.

        Args:
            metrics_config: Optional metrics configuration
            communication: Communication interface
            component_id: Optional component ID
            config: Optional configuration dictionary
        """
        super().__init__(
            component_id=component_id or f"records_manager_{uuid.uuid4().hex[:8]}",
            config=config or {},
        )
        self.metrics_config = metrics_config or MetricsConfig()
        self.communication = communication
        self._records: Dict[str, Record] = {}
        self._records_by_conversation: Dict[
            str, List[str]
        ] = {}  # Conversation ID -> Record IDs
        self._records_lock = asyncio.Lock()
        self._record_listeners: List[Callable[[Record], None]] = []
        self._is_initialized = False
        self._output_path = metrics_config.output_path if metrics_config else None

    async def initialize(self) -> bool:
        """Initialize the records manager.

        Returns:
            True if initialization was successful, False otherwise
        """
        self.logger.info("Initializing records manager")

        try:
            # Initialize storage
            await self._initialize_storage()

            # Set up communication if provided
            if self.communication:
                # Subscribe to relevant topics
                await self.communication.subscribe(
                    "records.request", self._handle_records_request
                )

            self._is_initialized = True
            self._is_ready = True
            return True
        except Exception as e:
            self.logger.error(f"Error initializing records manager: {e}")
            return False

    async def _initialize_storage(self) -> bool:
        """Initialize storage for records.

        Returns:
            True if initialization was successful, False otherwise
        """
        try:
            # Create output directory if configured
            if self._output_path:
                os.makedirs(os.path.dirname(self._output_path), exist_ok=True)

            # Initialize in-memory storage
            self._records = {}
            self._records_by_conversation = {}

            return True
        except Exception as e:
            self.logger.error(f"Error initializing storage: {e}")
            return False

    async def ready_check(self) -> bool:
        """Check if the records manager is ready.

        Returns:
            True if the records manager is ready, False otherwise
        """
        return self._is_initialized and self._is_ready

    async def publish_identity(self) -> bool:
        """Publish the records manager's identity.

        Returns:
            True if identity was published successfully, False otherwise
        """
        if not self.communication:
            self.logger.warning(
                "No communication interface available, skipping identity publication"
            )
            return False

        try:
            identity = {
                "component_id": self.component_id,
                "component_type": "records_manager",
                "records_count": len(self._records),
            }

            success = await self.communication.publish("system.identity", identity)
            if success:
                self.logger.info("Published records manager identity")
            else:
                self.logger.warning("Failed to publish records manager identity")

            return success
        except Exception as e:
            self.logger.error(f"Error publishing records manager identity: {e}")
            return False

    async def shutdown(self) -> bool:
        """Gracefully shutdown the records manager.

        Returns:
            True if shutdown was successful, False otherwise
        """
        self.logger.info("Shutting down records manager")

        try:
            # Flush records to disk if configured
            if self._output_path and self._records:
                await self._flush_records_to_disk()

            self._is_shutdown = True
            return True
        except Exception as e:
            self.logger.error(f"Error shutting down records manager: {e}")
            self._is_shutdown = True  # Mark as shutdown even on error
            return False

    async def _flush_records_to_disk(self) -> bool:
        """Flush records to disk.

        Returns:
            True if flush was successful, False otherwise
        """
        try:
            if not self._output_path:
                return False

            self.logger.info(
                f"Flushing {len(self._records)} records to {self._output_path}"
            )

            # Create directories if needed
            os.makedirs(
                os.path.dirname(self._output_path)
                if os.path.dirname(self._output_path)
                else ".",
                exist_ok=True,
            )

            # Prepare records for serialization
            records_data = {}
            for record_id, record in self._records.items():
                # Convert conversation turns to dictionaries
                conversation_dict = None
                if record.conversation:
                    turns_list = []
                    for turn in record.conversation.turns:
                        turn_dict = {
                            "request": turn.request,
                            "response": turn.response,
                            "success": turn.success,
                            "tokens": turn.tokens,
                            "latency": turn.latency,
                            "timestamp": turn.timestamp,
                            "metadata": turn.metadata,
                        }
                        turns_list.append(turn_dict)

                    conversation_dict = {
                        "conversation_id": record.conversation.conversation_id,
                        "turns": turns_list,
                        "created_at": record.conversation.created_at,
                        "updated_at": record.conversation.updated_at,
                        "metadata": record.conversation.metadata,
                    }

                # Convert metrics to dictionaries
                metrics_list = []
                for metric in record.metrics:
                    metric_dict = {
                        "name": metric.name,
                        "value": metric.value,
                        "timestamp": metric.timestamp,
                        "unit": metric.unit,
                        "labels": metric.labels,
                        "metadata": metric.metadata,
                    }
                    metrics_list.append(metric_dict)

                # Create serializable record
                records_data[record_id] = {
                    "record_id": record.record_id,
                    "conversation": conversation_dict,
                    "metrics": metrics_list,
                    "raw_data": record.raw_data,
                }

            # Write to file
            with open(self._output_path, "w") as f:
                json.dump(records_data, f, indent=2)

            return True
        except Exception as e:
            self.logger.error(f"Error flushing records to disk: {e}")
            return False

    async def _handle_records_request(self, message: Dict[str, Any]) -> None:
        """Handle records request message.

        Args:
            message: Message dictionary
        """
        if not self.communication:
            return

        try:
            client_id = message.get("client_id")
            data = message.get("data", {})

            if not client_id:
                self.logger.warning("Records request missing source")
                return

            # Extract request details
            request_id = data.get("request_id")
            action = data.get("action")

            # Process request
            response = await self.handle_command(action, data)

            # Send response
            await self.communication.respond(
                client_id, {"request_id": request_id, **response}
            )
        except Exception as e:
            self.logger.error(f"Error handling records request: {e}")

            # Try to send error response
            if client_id and request_id:
                try:
                    await self.communication.respond(
                        client_id,
                        {
                            "request_id": request_id,
                            "status": "error",
                            "message": f"Internal error: {str(e)}",
                        },
                    )
                except Exception:
                    pass

    async def handle_command(
        self, command: str, payload: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Handle a command from the system controller.

        Args:
            command: Command string
            payload: Optional command payload

        Returns:
            Response dictionary with results
        """
        response = {"status": "error", "message": f"Unknown command: {command}"}

        if command == "store_record":
            record = payload.get("record") if payload else None
            if record:
                success = await self.store_record(record)
                if success:
                    response = {"status": "success", "message": "Record stored"}
                else:
                    response = {"status": "error", "message": "Failed to store record"}
            else:
                response = {"status": "error", "message": "No record provided"}

        elif command == "get_records":
            filters = payload.get("filters", {}) if payload else {}
            records = await self.get_records(filters)
            response = {"status": "success", "records": records}

        elif command == "get_record":
            record_id = payload.get("record_id") if payload else None
            if record_id:
                record = await self.get_record(record_id)
                if record:
                    # Convert record to dictionary
                    record_dict = {
                        "record_id": record.record_id,
                        "conversation": record.conversation.__dict__
                        if record.conversation
                        else None,
                        "metrics": [metric.__dict__ for metric in record.metrics],
                        "raw_data": record.raw_data,
                    }
                    response = {"status": "success", "record": record_dict}
                else:
                    response = {
                        "status": "error",
                        "message": f"Record not found: {record_id}",
                    }
            else:
                response = {"status": "error", "message": "No record_id provided"}

        elif command == "get_stats":
            stats = await self.get_stats()
            response = {"status": "success", "stats": stats}

        elif command == "flush":
            success = await self._flush_records_to_disk()
            if success:
                response = {"status": "success", "message": "Records flushed to disk"}
            else:
                response = {
                    "status": "error",
                    "message": "Failed to flush records to disk",
                }

        return response

    async def store_record(self, record_data: Union[Dict[str, Any], Record]) -> bool:
        """Store a record.

        Args:
            record_data: Record data or Record object

        Returns:
            True if the record was stored successfully, False otherwise
        """
        try:
            # Convert record data to Record object if needed
            record = None
            if isinstance(record_data, Record):
                record = record_data
            elif isinstance(record_data, dict):
                # Get or generate record ID
                record_id = record_data.get("record_id") or str(uuid.uuid4())

                # Extract conversation data
                conversation = None
                conversation_data = record_data.get("conversation")
                if conversation_data:
                    if isinstance(conversation_data, Conversation):
                        conversation = conversation_data
                    elif isinstance(conversation_data, dict):
                        # Create conversation
                        conversation_id = conversation_data.get(
                            "conversation_id"
                        ) or str(uuid.uuid4())
                        conversation = Conversation(
                            conversation_id=conversation_id,
                            metadata=conversation_data.get("metadata", {}),
                        )

                        # Add turns if available
                        turns = conversation_data.get("turns", [])
                        for turn in turns:
                            if isinstance(turn, dict):
                                conversation.turns.append(turn)

                # Extract metrics data
                metrics = []
                metrics_data = record_data.get("metrics", [])
                for metric_data in metrics_data:
                    if isinstance(metric_data, Metric):
                        metrics.append(metric_data)
                    elif isinstance(metric_data, dict):
                        # Create metric
                        metric = Metric(
                            name=metric_data.get("name", "unknown"),
                            value=metric_data.get("value", 0),
                            timestamp=metric_data.get("timestamp", time.time()),
                            unit=metric_data.get("unit"),
                            labels=metric_data.get("labels", {}),
                            metadata=metric_data.get("metadata", {}),
                        )
                        metrics.append(metric)

                # Create record
                record = Record(
                    record_id=record_id,
                    conversation=conversation,
                    metrics=metrics,
                    raw_data=record_data.get("raw_data", {}),
                )
            else:
                self.logger.error(f"Invalid record data type: {type(record_data)}")
                return False

            # Store record
            async with self._records_lock:
                self._records[record.record_id] = record

                # Add to conversation index
                if record.conversation:
                    conversation_id = record.conversation.conversation_id
                    if conversation_id not in self._records_by_conversation:
                        self._records_by_conversation[conversation_id] = []
                    self._records_by_conversation[conversation_id].append(
                        record.record_id
                    )

            # Notify listeners
            for listener in self._record_listeners:
                try:
                    result = listener(record)
                    if asyncio.iscoroutine(result):
                        asyncio.create_task(result)
                except Exception as e:
                    self.logger.error(f"Error notifying record listener: {e}")

            # Publish record event if communication is available
            if self.communication:
                try:
                    # Create a simplified version of the record for the event
                    record_summary = {
                        "record_id": record.record_id,
                        "timestamp": time.time(),
                        "metrics_count": len(record.metrics),
                        "conversation_id": record.conversation.conversation_id
                        if record.conversation
                        else None,
                    }

                    await self.communication.publish(
                        "records.events",
                        {"event": "record_created", "record": record_summary},
                    )
                except Exception as e:
                    self.logger.error(f"Error publishing record event: {e}")

            return True
        except Exception as e:
            self.logger.error(f"Error storing record: {e}")
            return False

    async def get_records(
        self, filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Get records matching filters.

        Args:
            filters: Optional filters to apply

        Returns:
            List of records as dictionaries
        """
        try:
            result = []
            async with self._records_lock:
                for record in self._records.values():
                    if not filters or self._matches_filters(record, filters):
                        # Convert record to dictionary
                        record_dict = {
                            "record_id": record.record_id,
                            "timestamp": time.time(),
                            "metrics_count": len(record.metrics),
                            "conversation_id": record.conversation.conversation_id
                            if record.conversation
                            else None,
                            "metrics_summary": {
                                metric.name: metric.value for metric in record.metrics
                            },
                        }
                        result.append(record_dict)

            return result
        except Exception as e:
            self.logger.error(f"Error getting records: {e}")
            return []

    def _matches_filters(self, record: Record, filters: Dict[str, Any]) -> bool:
        """Check if a record matches the specified filters.

        Args:
            record: Record to check
            filters: Filters to apply

        Returns:
            True if the record matches the filters, False otherwise
        """
        # Check record ID
        if "record_id" in filters and record.record_id != filters["record_id"]:
            return False

        # Check conversation ID
        if "conversation_id" in filters and (
            not record.conversation
            or record.conversation.conversation_id != filters["conversation_id"]
        ):
            return False

        # Check metric filters
        if "metrics" in filters:
            metric_filters = filters["metrics"]
            for metric_name, metric_value in metric_filters.items():
                # Find metric with matching name
                metric_found = False
                for metric in record.metrics:
                    if metric.name == metric_name:
                        metric_found = True
                        # Check if value matches
                        if isinstance(metric_value, dict):
                            # Advanced filtering with operators
                            operator = metric_value.get("operator", "eq")
                            value = metric_value.get("value")

                            if operator == "eq" and metric.value != value:
                                return False
                            elif operator == "gt" and not (metric.value > value):
                                return False
                            elif operator == "lt" and not (metric.value < value):
                                return False
                            elif operator == "gte" and not (metric.value >= value):
                                return False
                            elif operator == "lte" and not (metric.value <= value):
                                return False
                        elif metric.value != metric_value:
                            return False

                # If we're looking for a specific metric and it wasn't found, filter out
                if not metric_found:
                    return False

        # Check timestamp range
        if "timestamp" in filters:
            timestamp_filter = filters["timestamp"]
            if isinstance(timestamp_filter, dict):
                # Check min timestamp
                if "min" in timestamp_filter:
                    min_timestamp = timestamp_filter["min"]
                    # Find most recent metric
                    if (
                        not record.metrics
                        or min(metric.timestamp for metric in record.metrics)
                        < min_timestamp
                    ):
                        return False

                # Check max timestamp
                if "max" in timestamp_filter:
                    max_timestamp = timestamp_filter["max"]
                    # Find oldest metric
                    if (
                        not record.metrics
                        or max(metric.timestamp for metric in record.metrics)
                        > max_timestamp
                    ):
                        return False

        # All filters passed
        return True

    async def get_record(self, record_id: str) -> Optional[Record]:
        """Get a specific record by ID.

        Args:
            record_id: Record ID

        Returns:
            Record object or None if not found
        """
        async with self._records_lock:
            return self._records.get(record_id)

    async def add_listener(self, listener: Callable[[Record], None]) -> bool:
        """Add a listener for new records.

        Args:
            listener: Function to call when a new record is added

        Returns:
            True if the listener was added successfully, False otherwise
        """
        try:
            self._record_listeners.append(listener)
            return True
        except Exception as e:
            self.logger.error(f"Error adding record listener: {e}")
            return False

    async def get_stats(self) -> Dict[str, Any]:
        """Get records manager statistics.

        Returns:
            Dictionary with statistics
        """
        try:
            stats = {
                "records_count": len(self._records),
                "conversations_count": len(self._records_by_conversation),
                "metrics_count": sum(
                    len(record.metrics) for record in self._records.values()
                ),
                "output_path": self._output_path,
                "has_listeners": len(self._record_listeners) > 0,
                "is_initialized": self._is_initialized,
                "is_ready": self._is_ready,
            }

            # Get metrics by type
            metrics_by_type = {}
            for record in self._records.values():
                for metric in record.metrics:
                    if metric.name not in metrics_by_type:
                        metrics_by_type[metric.name] = 0
                    metrics_by_type[metric.name] += 1

            stats["metrics_by_type"] = metrics_by_type

            return stats
        except Exception as e:
            self.logger.error(f"Error getting records manager stats: {e}")
            return {"error": str(e)}
