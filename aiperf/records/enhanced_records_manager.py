import uuid
import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple, Callable, Set, Union

from ..common.base_manager import BaseManager
from ..common.models import Conversation, ConversationTurn
from ..config.config_models import RecordsConfig
from ..common.communication import Communication


class EnhancedRecordsManager(BaseManager):
    """Enhanced records manager for AIPerf.

    This is a full implementation that properly handles component registration
    and communication with other AIPerf components.

    Responsible for managing records, including:
    - Storing records of benchmark runs
    - Calculating metrics from records
    - Providing query API for records
    - Supporting archiving and exporting
    """

    def __init__(
        self,
        config: RecordsConfig,
        communication: Optional[Communication] = None,
        component_id: Optional[str] = None,
    ):
        """Initialize the records manager.

        Args:
            config: Records configuration
            communication: Communication interface
            component_id: Optional component ID
        """
        super().__init__(
            component_id=component_id or f"records_manager_{uuid.uuid4().hex[:8]}",
            config=config.__dict__,
        )
        self.records_config = config
        self.communication = communication
        self._records: Dict[str, Dict[str, Any]] = {}
        self._records_lock = asyncio.Lock()
        self._listeners: Dict[str, List[Callable]] = {}
        self._is_initialized = False
        self._is_ready = False
        self._record_count = 0
        self._load_fixtures()

    def _load_fixtures(self):
        """Load pre-defined fixtures for testing records."""
        try:
            fixtures_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "fixtures",
                "sample_records.json",
            )
            if os.path.exists(fixtures_path):
                with open(fixtures_path, "r") as f:
                    data = json.load(f)
                    if "records" in data and isinstance(data["records"], list):
                        for record in data["records"]:
                            if "record_id" in record:
                                self._records[record["record_id"]] = record
                        self.logger.info(
                            f"Loaded {len(self._records)} records from fixtures"
                        )
                    else:
                        self.logger.warning(
                            f"Invalid fixtures format in {fixtures_path}"
                        )
            else:
                self.logger.warning(f"Fixtures file not found at {fixtures_path}")
        except Exception as e:
            self.logger.error(f"Error loading fixtures: {e}")

    async def initialize(self) -> bool:
        """Initialize the records manager.

        Returns:
            True if initialization was successful, False otherwise
        """
        self.logger.info(f"Initializing enhanced records manager: {self.component_id}")

        try:
            # Create directory for record storage if it doesn't exist
            if self.records_config.storage_path:
                os.makedirs(self.records_config.storage_path, exist_ok=True)
                self.logger.info(
                    f"Initialized storage path: {self.records_config.storage_path}"
                )

            # Set up communication if provided
            if self.communication:
                # Subscribe to relevant topics
                await self.communication.subscribe(
                    "records.request", self._handle_records_request
                )
                self.logger.info(f"Subscribed to records.request topic")

                # Subscribe to worker results
                await self.communication.subscribe(
                    "worker.results", self._handle_worker_results
                )
                self.logger.info(f"Subscribed to worker.results topic")

                # Announce our presence to the system
                await self.publish_identity()
                self.logger.info("Published records manager identity")

            # Load existing records if applicable
            loaded = await self._load_existing_records()
            if loaded:
                self.logger.info(f"Loaded {len(self._records)} existing records")

            self._is_initialized = True
            self._is_ready = True
            return True
        except Exception as e:
            self.logger.error(f"Error initializing records manager: {e}")
            return False

    async def _load_existing_records(self) -> bool:
        """Load existing records from storage.

        Returns:
            True if loading was successful, False otherwise
        """
        if not self.records_config.storage_path:
            return False

        try:
            records_file = os.path.join(
                self.records_config.storage_path, "records.json"
            )
            if os.path.exists(records_file):
                with open(records_file, "r") as f:
                    data = json.load(f)
                    if "records" in data and isinstance(data["records"], list):
                        async with self._records_lock:
                            for record in data["records"]:
                                if "record_id" in record:
                                    self._records[record["record_id"]] = record
                        self.logger.info(
                            f"Loaded {len(self._records)} records from storage"
                        )
                        return True
                    else:
                        self.logger.warning(f"Invalid records format in {records_file}")
            return True  # Successfully attempted to load, even if no records were found
        except Exception as e:
            self.logger.error(f"Error loading existing records: {e}")
            return False

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
                "record_count": len(self._records),
                "storage_path": self.records_config.storage_path,
                "has_persistence": bool(self.records_config.storage_path),
            }

            # Publish identity to system.identity topic
            success = await self.communication.publish("system.identity", identity)
            if success:
                self.logger.info(
                    f"Published records manager identity: {self.component_id}"
                )
            else:
                self.logger.warning("Failed to publish records manager identity")

            # Also create a specific topic for this component
            success = await self.communication.publish(
                f"records.identity.{self.component_id}", identity
            )

            return success
        except Exception as e:
            self.logger.error(f"Error publishing records manager identity: {e}")
            return False

    async def ready_check(self) -> bool:
        """Check if the records manager is ready.

        Returns:
            True if the records manager is ready, False otherwise
        """
        return self._is_initialized and self._is_ready

    async def shutdown(self) -> bool:
        """Gracefully shutdown the records manager.

        Returns:
            True if shutdown was successful, False otherwise
        """
        self.logger.info("Shutting down records manager")

        try:
            # Save records if storage is enabled
            if self.records_config.storage_path:
                await self._save_records()

            # Announce shutdown
            if self.communication:
                try:
                    await self.communication.publish(
                        "system.events",
                        {
                            "event_type": "component_shutdown",
                            "component_id": self.component_id,
                            "component_type": "records_manager",
                            "timestamp": time.time(),
                        },
                    )
                except Exception as e:
                    self.logger.error(f"Error publishing shutdown event: {e}")

            self._is_shutdown = True
            self._is_ready = False
            self._is_initialized = False
            return True
        except Exception as e:
            self.logger.error(f"Error shutting down records manager: {e}")
            self._is_shutdown = True  # Mark as shutdown even on error
            return False

    async def _save_records(self) -> bool:
        """Save records to storage.

        Returns:
            True if saving was successful, False otherwise
        """
        if not self.records_config.storage_path:
            return False

        try:
            records_file = os.path.join(
                self.records_config.storage_path, "records.json"
            )
            # Create a backup of the existing file if it exists
            if os.path.exists(records_file):
                backup_file = f"{records_file}.{int(time.time())}.bak"
                os.rename(records_file, backup_file)
                self.logger.info(f"Created backup of records file: {backup_file}")

            async with self._records_lock:
                records_data = {
                    "records": list(self._records.values()),
                    "metadata": {
                        "created_at": time.time(),
                        "format_version": "1.0",
                        "system": "aiperf",
                        "record_count": len(self._records),
                    },
                }
                with open(records_file, "w") as f:
                    json.dump(records_data, f, indent=2)
                self.logger.info(
                    f"Saved {len(self._records)} records to {records_file}"
                )
                return True
        except Exception as e:
            self.logger.error(f"Error saving records: {e}")
            return False

    async def _handle_records_request(self, message: Dict[str, Any]) -> None:
        """Handle records request message.

        Args:
            message: Message dictionary
        """
        if not self.communication:
            return

        try:
            # Extract data from message
            data = message.get("data", {})
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    data = {"error": "Invalid JSON in message data"}

            command = data.get("command")
            payload = data.get("payload", {})

            # For compatibility with both styles of messaging
            source = message.get("source") or message.get("client_id")
            request_id = data.get("request_id") or str(uuid.uuid4())

            if not source:
                self.logger.warning("Records request missing source/client_id")
                return

            self.logger.info(f"Received records request: {command} from {source}")

            # Process request
            response = await self.handle_command(command, payload)
            response["request_id"] = request_id

            # Send response
            success = False

            # Try both formats of response
            try:
                # First try direct response if request has client_id
                if "client_id" in message:
                    success = await self.communication.respond(
                        message["client_id"], response
                    )
                    if success:
                        self.logger.info(
                            f"Sent direct response to {message['client_id']}"
                        )

                # If that fails or wasn't available, try topic-based response
                if not success:
                    if "source" in message:
                        success = await self.communication.publish(
                            f"records.response.{source}", response
                        )
                        if success:
                            self.logger.info(
                                f"Published response to records.response.{source}"
                            )
                    else:
                        # Fallback to generic response topic
                        success = await self.communication.publish(
                            "records.response",
                            {
                                **response,
                                "target": source,
                            },
                        )
                        self.logger.info(
                            f"Published response to records.response with target={source}"
                        )
            except Exception as e:
                self.logger.error(f"Error sending response: {e}")
                # Try one last fallback
                try:
                    await self.communication.publish(
                        "system.events",
                        {
                            "event_type": "records_response_error",
                            "component_id": self.component_id,
                            "error": str(e),
                            "target": source,
                            "request_id": request_id,
                        },
                    )
                except:
                    pass
        except Exception as e:
            self.logger.error(f"Error handling records request: {e}")

    async def _handle_worker_results(self, message: Dict[str, Any]) -> None:
        """Handle worker results message.

        Args:
            message: Message dictionary with worker results
        """
        try:
            data = message.get("data", {})
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    self.logger.error("Invalid JSON in worker results data")
                    return

            worker_id = (
                data.get("worker_id")
                or message.get("source")
                or message.get("client_id")
            )
            if not worker_id:
                self.logger.warning("Worker results missing worker_id/source/client_id")
                return

            self.logger.info(f"Received worker results from {worker_id}")

            # Process results
            success = await self.store_record(data)
            if success:
                self.logger.info(f"Stored record for worker {worker_id}")

                # Notify listeners
                record_id = data.get("record_id")
                if record_id:
                    await self._notify_listeners(
                        "record_added", {"record_id": record_id}
                    )
            else:
                self.logger.error(f"Failed to store record for worker {worker_id}")
        except Exception as e:
            self.logger.error(f"Error handling worker results: {e}")

    async def store_record(self, record_data: Dict[str, Any]) -> bool:
        """Store a record.

        Args:
            record_data: Record data

        Returns:
            True if storage was successful, False otherwise
        """
        try:
            # Add default record ID if not provided
            if "record_id" not in record_data:
                record_data["record_id"] = f"record_{uuid.uuid4().hex}"

            # Add timestamp if not provided
            if "timestamp" not in record_data:
                record_data["timestamp"] = time.time()

            # Store the record
            async with self._records_lock:
                self._records[record_data["record_id"]] = record_data
                self._record_count += 1

            # Save to disk if auto-save is enabled
            if (
                self.records_config.auto_save
                and self._record_count % self.records_config.save_interval == 0
            ):
                await self._save_records()

            # Publish event if appropriate
            if self.communication and self.records_config.publish_events:
                await self.communication.publish(
                    "records.events",
                    {
                        "event_type": "record_stored",
                        "record_id": record_data["record_id"],
                        "timestamp": time.time(),
                        "component_id": self.component_id,
                    },
                )

            return True
        except Exception as e:
            self.logger.error(f"Error storing record: {e}")
            return False

    async def handle_command(
        self, command: str, payload: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Handle a command.

        Args:
            command: Command string
            payload: Optional command payload

        Returns:
            Response dictionary with results
        """
        response = {"status": "error", "message": f"Unknown command: {command}"}
        payload = payload or {}

        if command == "get_record":
            record_id = payload.get("record_id")
            if not record_id:
                response = {"status": "error", "message": "Missing record_id"}
            else:
                record = await self.get_record(record_id)
                if record:
                    response = {"status": "success", "record": record}
                else:
                    response = {"status": "error", "message": "Record not found"}

        elif command == "query_records":
            filters = payload.get("filters", {})
            limit = payload.get("limit", 100)
            offset = payload.get("offset", 0)
            records = await self.query_records(filters, limit, offset)
            response = {
                "status": "success",
                "records": records,
                "total": len(records),
                "limit": limit,
                "offset": offset,
            }

        elif command == "get_metrics":
            metric_name = payload.get("metric_name")
            filters = payload.get("filters", {})
            metrics = await self.get_metrics(metric_name, filters)
            response = {"status": "success", "metrics": metrics}

        elif command == "delete_record":
            record_id = payload.get("record_id")
            if not record_id:
                response = {"status": "error", "message": "Missing record_id"}
            else:
                success = await self.delete_record(record_id)
                if success:
                    response = {
                        "status": "success",
                        "message": f"Record {record_id} deleted",
                    }
                else:
                    response = {
                        "status": "error",
                        "message": f"Failed to delete record {record_id}",
                    }

        elif command == "add_listener":
            event_type = payload.get("event_type")
            callback_topic = payload.get("callback_topic")
            listener_id = payload.get("listener_id")

            if not event_type or not callback_topic:
                response = {
                    "status": "error",
                    "message": "Missing event_type or callback_topic",
                }
            else:
                success = await self.add_listener(
                    event_type, callback_topic, listener_id
                )
                if success:
                    response = {"status": "success", "message": "Listener added"}
                else:
                    response = {"status": "error", "message": "Failed to add listener"}

        elif command == "get_status":
            status = await self.get_status()
            response = {"status": "success", "data": status}

        elif command == "save_records":
            force = payload.get("force", False)
            if force or self.records_config.storage_path:
                success = await self._save_records()
                if success:
                    response = {
                        "status": "success",
                        "message": "Records saved successfully",
                    }
                else:
                    response = {"status": "error", "message": "Failed to save records"}
            else:
                response = {"status": "error", "message": "No storage path configured"}

        return response

    async def get_status(self) -> Dict[str, Any]:
        """Get status information about the records manager.

        Returns:
            Dictionary with status information
        """
        return {
            "component_id": self.component_id,
            "component_type": "records_manager",
            "is_ready": self._is_ready,
            "is_initialized": self._is_initialized,
            "record_count": len(self._records),
            "storage_path": self.records_config.storage_path,
            "auto_save": self.records_config.auto_save,
            "save_interval": self.records_config.save_interval,
            "uptime": time.time() - self.start_time
            if hasattr(self, "start_time")
            else 0,
        }

    async def add_listener(
        self, event_type: str, callback_topic: str, listener_id: Optional[str] = None
    ) -> bool:
        """Add a listener for events.

        Args:
            event_type: Type of event to listen for
            callback_topic: Topic to publish events to
            listener_id: Optional listener ID

        Returns:
            True if listener was added successfully, False otherwise
        """
        if not self.communication:
            return False

        try:
            listener_id = listener_id or str(uuid.uuid4())

            async def callback(event_data):
                await self.communication.publish(
                    callback_topic,
                    {
                        "event": event_data,
                        "listener_id": listener_id,
                        "timestamp": time.time(),
                        "source": self.component_id,
                    },
                )

            if event_type not in self._listeners:
                self._listeners[event_type] = []

            self._listeners[event_type].append(callback)
            self.logger.info(
                f"Added listener {listener_id} for event type {event_type}"
            )
            return True
        except Exception as e:
            self.logger.error(f"Error adding listener: {e}")
            return False

    async def _notify_listeners(
        self, event_type: str, event_data: Dict[str, Any]
    ) -> None:
        """Notify listeners of an event.

        Args:
            event_type: Type of event
            event_data: Event data
        """
        if event_type not in self._listeners:
            return

        for callback in self._listeners[event_type]:
            try:
                await callback(event_data)
            except Exception as e:
                self.logger.error(f"Error notifying listener for {event_type}: {e}")

    async def get_record(self, record_id: str) -> Optional[Dict[str, Any]]:
        """Get a record by ID.

        Args:
            record_id: Record ID

        Returns:
            Record dictionary or None if not found
        """
        async with self._records_lock:
            return self._records.get(record_id)

    async def query_records(
        self, filters: Dict[str, Any], limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Query records with filters.

        Args:
            filters: Filter dictionary
            limit: Maximum number of records to return
            offset: Offset into results

        Returns:
            List of matching records
        """
        results = []

        async with self._records_lock:
            # Apply filters
            filtered_records = self._records.values()

            if filters:
                filtered_records = self._apply_filters(filtered_records, filters)

            # Sort by timestamp if available
            sorted_records = sorted(
                filtered_records, key=lambda r: r.get("timestamp", 0), reverse=True
            )

            # Apply limit and offset
            results = sorted_records[offset : offset + limit]

        return results

    def _apply_filters(
        self, records: List[Dict[str, Any]], filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Apply filters to records.

        Args:
            records: List of records
            filters: Filter dictionary

        Returns:
            Filtered list of records
        """
        result = []

        for record in records:
            match = True

            for key, value in filters.items():
                # Handle nested keys with dot notation (e.g., "conversation.metadata.model")
                if "." in key:
                    parts = key.split(".")
                    current = record
                    for part in parts:
                        if isinstance(current, dict) and part in current:
                            current = current[part]
                        else:
                            current = None
                            break

                    if current != value:
                        match = False
                        break
                # Handle direct keys
                elif key not in record or record[key] != value:
                    match = False
                    break

            if match:
                result.append(record)

        return result

    async def get_metrics(
        self, metric_name: Optional[str] = None, filters: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Get metrics from records.

        Args:
            metric_name: Optional specific metric to retrieve
            filters: Optional filters to apply

        Returns:
            Dictionary with metrics data
        """
        filters = filters or {}
        metrics = {}

        # Get the records to analyze
        records = await self.query_records(filters, limit=1000)

        if not records:
            return metrics

        # Calculate metrics
        if not metric_name:
            # Calculate all metrics
            metrics["total_records"] = len(records)
            metrics["avg_latency"] = self._calc_avg_metric(
                records, "metrics", "request_latency", "value"
            )
            metrics["avg_time_to_first_token"] = self._calc_avg_metric(
                records, "metrics", "time_to_first_token", "value"
            )
            metrics["avg_output_token_throughput"] = self._calc_avg_metric(
                records, "metrics", "output_token_throughput", "value"
            )

            # Count by model
            metrics["models"] = self._count_by_field(records, "raw_data", "model")

            # Calculate errors
            metrics["errors"] = sum(
                1
                for r in records
                if any(
                    not turn.get("success", True)
                    for turn in r.get("conversation", {}).get("turns", [])
                )
            )
        else:
            # Calculate specific metric
            if metric_name == "latency":
                metrics["avg_latency"] = self._calc_avg_metric(
                    records, "metrics", "request_latency", "value"
                )
                metrics["min_latency"] = self._calc_min_metric(
                    records, "metrics", "request_latency", "value"
                )
                metrics["max_latency"] = self._calc_max_metric(
                    records, "metrics", "request_latency", "value"
                )
            elif metric_name == "time_to_first_token":
                metrics["avg_ttft"] = self._calc_avg_metric(
                    records, "metrics", "time_to_first_token", "value"
                )
                metrics["min_ttft"] = self._calc_min_metric(
                    records, "metrics", "time_to_first_token", "value"
                )
                metrics["max_ttft"] = self._calc_max_metric(
                    records, "metrics", "time_to_first_token", "value"
                )
            elif metric_name == "token_throughput":
                metrics["avg_throughput"] = self._calc_avg_metric(
                    records, "metrics", "output_token_throughput", "value"
                )
                metrics["min_throughput"] = self._calc_min_metric(
                    records, "metrics", "output_token_throughput", "value"
                )
                metrics["max_throughput"] = self._calc_max_metric(
                    records, "metrics", "output_token_throughput", "value"
                )
            elif metric_name == "model_distribution":
                metrics["models"] = self._count_by_field(records, "raw_data", "model")
            elif metric_name == "errors":
                metrics["error_count"] = sum(
                    1
                    for r in records
                    if any(
                        not turn.get("success", True)
                        for turn in r.get("conversation", {}).get("turns", [])
                    )
                )
                metrics["error_rate"] = (
                    metrics["error_count"] / len(records) if records else 0
                )

        return metrics

    def _calc_avg_metric(
        self, records: List[Dict[str, Any]], *path_parts: str
    ) -> float:
        """Calculate average of a metric field.

        Args:
            records: List of records
            *path_parts: Path to the metric field

        Returns:
            Average value or 0 if not found
        """
        values = []

        for record in records:
            current = record
            for part in path_parts:
                if isinstance(current, dict) and part in current:
                    if isinstance(current[part], list) and part == "metrics":
                        # Handle metrics list case - find the right metric
                        metric_name = path_parts[-2] if len(path_parts) >= 2 else None
                        value_field = path_parts[-1] if len(path_parts) >= 1 else None

                        for metric in current[part]:
                            if metric.get("name") == metric_name:
                                values.append(metric.get(value_field, 0))
                                break
                        break
                    current = current[part]
                else:
                    current = None
                    break

            if current is not None and path_parts[-1] == current:
                values.append(current)

        return sum(values) / len(values) if values else 0

    def _calc_min_metric(
        self, records: List[Dict[str, Any]], *path_parts: str
    ) -> float:
        """Calculate minimum of a metric field.

        Args:
            records: List of records
            *path_parts: Path to the metric field

        Returns:
            Minimum value or 0 if not found
        """
        values = []

        for record in records:
            current = record
            for part in path_parts:
                if isinstance(current, dict) and part in current:
                    if isinstance(current[part], list) and part == "metrics":
                        # Handle metrics list case - find the right metric
                        metric_name = path_parts[-2] if len(path_parts) >= 2 else None
                        value_field = path_parts[-1] if len(path_parts) >= 1 else None

                        for metric in current[part]:
                            if metric.get("name") == metric_name:
                                values.append(metric.get(value_field, 0))
                                break
                        break
                    current = current[part]
                else:
                    current = None
                    break

            if current is not None and path_parts[-1] == current:
                values.append(current)

        return min(values) if values else 0

    def _calc_max_metric(
        self, records: List[Dict[str, Any]], *path_parts: str
    ) -> float:
        """Calculate maximum of a metric field.

        Args:
            records: List of records
            *path_parts: Path to the metric field

        Returns:
            Maximum value or 0 if not found
        """
        values = []

        for record in records:
            current = record
            for part in path_parts:
                if isinstance(current, dict) and part in current:
                    if isinstance(current[part], list) and part == "metrics":
                        # Handle metrics list case - find the right metric
                        metric_name = path_parts[-2] if len(path_parts) >= 2 else None
                        value_field = path_parts[-1] if len(path_parts) >= 1 else None

                        for metric in current[part]:
                            if metric.get("name") == metric_name:
                                values.append(metric.get(value_field, 0))
                                break
                        break
                    current = current[part]
                else:
                    current = None
                    break

            if current is not None and path_parts[-1] == current:
                values.append(current)

        return max(values) if values else 0

    def _count_by_field(
        self, records: List[Dict[str, Any]], *path_parts: str
    ) -> Dict[str, int]:
        """Count occurrences of values in a field.

        Args:
            records: List of records
            *path_parts: Path to the field

        Returns:
            Dictionary with counts
        """
        counts = {}

        for record in records:
            current = record
            for part in path_parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    current = None
                    break

            if current is not None:
                if current in counts:
                    counts[current] += 1
                else:
                    counts[current] = 1

        return counts

    async def delete_record(self, record_id: str) -> bool:
        """Delete a record.

        Args:
            record_id: Record ID

        Returns:
            True if deletion was successful, False otherwise
        """
        async with self._records_lock:
            if record_id in self._records:
                del self._records[record_id]
                self.logger.info(f"Deleted record {record_id}")

                # Notify listeners
                await self._notify_listeners("record_deleted", {"record_id": record_id})

                return True
            else:
                self.logger.warning(f"Record {record_id} not found for deletion")
                return False
