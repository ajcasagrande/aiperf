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
    
    def __init__(self, metrics_config: Optional[MetricsConfig] = None,
                 communication: Optional[Communication] = None,
                 component_id: Optional[str] = None, 
                 config: Optional[Dict[str, Any]] = None):
        """Initialize the records manager.
        
        Args:
            metrics_config: Optional metrics configuration
            communication: Communication interface
            component_id: Optional component ID
            config: Optional configuration dictionary
        """
        super().__init__(component_id=component_id or f"records_manager_{uuid.uuid4().hex[:8]}", 
                         config=config or {})
        self.metrics_config = metrics_config or MetricsConfig()
        self.communication = communication
        self._records: Dict[str, Record] = {}
        self._records_by_conversation: Dict[str, List[str]] = {}  # Conversation ID -> Record IDs
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
                await self.communication.subscribe("records.request", self._handle_records_request)
                
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
            self.logger.warning("No communication interface available, skipping identity publication")
            return False
            
        try:
            identity = {
                "component_id": self.component_id,
                "component_type": "records_manager",
                "records_count": len(self._records)
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
                
            self.logger.info(f"Flushing {len(self._records)} records to {self._output_path}")
            
            # Prepare records for serialization
            records_data = {}
            for record_id, record in self._records.items():
                records_data[record_id] = {
                    "record_id": record.record_id,
                    "conversation": record.conversation.__dict__ if record.conversation else None,
                    "metrics": [metric.__dict__ for metric in record.metrics],
                    "raw_data": record.raw_data
                }
                
            # Write to file
            with open(self._output_path, 'w') as f:
                json.dump(records_data, f, indent=2)
                
            return True
        except Exception as e:
            self.logger.error(f"Error flushing records to disk: {e}")
            return False
    
    async def handle_command(self, command: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
                    response = {"status": "success", "record": record.__dict__}
                else:
                    response = {"status": "error", "message": f"Record not found: {record_id}"}
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
                response = {"status": "error", "message": "Failed to flush records to disk"}
        
        return response
        
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
            
            # Process request based on action
            if action == "get_records":
                filters = data.get("filters", {})
                records = await self.get_records(filters)
                
                response = {
                    "status": "success",
                    "records": records
                }
                
                # Send response
                await self.communication.respond(client_id, request_id, response)
            else:
                # Handle other actions or use generic command processing
                payload = data
                command = action
                
                # Process request using the handle_command method
                response = await self.handle_command(command, payload)
                
                # Send response
                await self.communication.respond(client_id, request_id, response)
        except Exception as e:
            self.logger.error(f"Error handling records request: {e}")
    
    async def store_record(self, record_data: Union[Dict[str, Any], Record]) -> bool:
        """Store a record.
        
        Args:
            record_data: Record data to store (dictionary or Record object)
            
        Returns:
            True if the record was stored successfully, False otherwise
        """
        try:
            # Handle case where a Record object is passed directly
            if isinstance(record_data, Record):
                record = record_data
            else:
                # Convert record data to Record object
                record_id = record_data.get("record_id") or str(uuid.uuid4())
                
                # Process conversation data
                conversation_data = record_data.get("conversation", {})
                conversation = None
                if conversation_data:
                    if isinstance(conversation_data, Conversation):
                        conversation = conversation_data
                    else:
                        conversation = Conversation(
                            conversation_id=conversation_data.get("conversation_id", str(uuid.uuid4())),
                            turns=[],  # Would need to process turns here if needed
                            start_timestamp=conversation_data.get("start_timestamp", time.time()),
                            end_timestamp=conversation_data.get("end_timestamp"),
                            metadata=conversation_data.get("metadata", {})
                        )
                        
                # Process metrics data
                metrics: List[Metric] = []
                metrics_data = record_data.get("metrics", [])
                for metric_data in metrics_data:
                    metrics.append(Metric(
                        name=metric_data.get("name", "unknown"),
                        value=metric_data.get("value", 0),
                        timestamp=metric_data.get("timestamp", time.time()),
                        unit=metric_data.get("unit"),
                        labels=metric_data.get("labels", {})
                    ))
                    
                # Create record
                record = Record(
                    record_id=record_id,
                    conversation=conversation,
                    metrics=metrics,
                    raw_data=record_data.get("raw_data", {})
                )
            
            # Store record
            async with self._records_lock:
                self._records[record.record_id] = record
                
                # Index by conversation ID
                if record.conversation:
                    conversation_id = record.conversation.conversation_id
                    if conversation_id not in self._records_by_conversation:
                        self._records_by_conversation[conversation_id] = []
                    self._records_by_conversation[conversation_id].append(record.record_id)
                    
            # Notify listeners
            for listener in self._record_listeners:
                try:
                    listener(record)
                except Exception as e:
                    self.logger.error(f"Error notifying record listener: {e}")
                    
            # Publish record event
            if self.communication:
                await self.communication.publish("records.events", {
                    "event": "record_stored",
                    "record_id": record.record_id,
                    "timestamp": time.time(),
                    "manager_id": self.component_id
                })
                
            return True
        except Exception as e:
            self.logger.error(f"Error storing record: {e}")
            return False
    
    async def get_records(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Get records matching filters.
        
        Args:
            filters: Optional filters to apply
            
        Returns:
            List of matching records
        """
        try:
            result = []
            async with self._records_lock:
                # Apply filters if provided
                if filters:
                    conversation_id = filters.get("conversation_id")
                    if conversation_id:
                        # Filter by conversation ID
                        record_ids = self._records_by_conversation.get(conversation_id, [])
                        records = [self._records[rid] for rid in record_ids if rid in self._records]
                    else:
                        # Full scan with filter
                        records = []
                        for record in self._records.values():
                            if self._matches_filters(record, filters):
                                records.append(record)
                else:
                    # No filters, return all records
                    records = list(self._records.values())
                    
                # Convert to serializable format
                for record in records:
                    result.append({
                        "record_id": record.record_id,
                        "conversation_id": record.conversation.conversation_id if record.conversation else None,
                        "metrics_count": len(record.metrics),
                        "has_raw_data": bool(record.raw_data)
                    })
                    
            return result
        except Exception as e:
            self.logger.error(f"Error getting records: {e}")
            return []
    
    def _matches_filters(self, record: Record, filters: Dict[str, Any]) -> bool:
        """Check if a record matches filters.
        
        Args:
            record: Record to check
            filters: Filters to apply
            
        Returns:
            True if the record matches filters, False otherwise
        """
        # Check record ID
        if "record_id" in filters and record.record_id != filters["record_id"]:
            return False
            
        # Check conversation ID
        if "conversation_id" in filters and record.conversation:
            if record.conversation.conversation_id != filters["conversation_id"]:
                return False
                
        # Check metrics
        if "metric_name" in filters:
            metric_names = [m.name for m in record.metrics]
            if filters["metric_name"] not in metric_names:
                return False
                
        # Check raw data
        if "has_raw_data" in filters:
            if bool(record.raw_data) != filters["has_raw_data"]:
                return False
                
        # Add more filter logic as needed
        
        return True
    
    async def get_record(self, record_id: str) -> Optional[Record]:
        """Get a record by ID.
        
        Args:
            record_id: Record ID
            
        Returns:
            Record or None if not found
        """
        try:
            async with self._records_lock:
                return self._records.get(record_id)
        except Exception as e:
            self.logger.error(f"Error getting record: {e}")
            return None
    
    async def add_listener(self, listener: Callable[[Record], None]) -> bool:
        """Add a listener for new records.
        
        Args:
            listener: Function to call when a new record is stored
            
        Returns:
            True if the listener was added successfully, False otherwise
        """
        try:
            self._record_listeners.append(listener)
            self.logger.info("Added record listener")
            return True
        except Exception as e:
            self.logger.error(f"Error adding record listener: {e}")
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get record statistics.
        
        Returns:
            Dictionary with record statistics
        """
        try:
            async with self._records_lock:
                total_records = len(self._records)
                total_conversations = len(self._records_by_conversation)
                
                # Count metrics
                metrics_count = {}
                total_metrics = 0
                for record in self._records.values():
                    for metric in record.metrics:
                        metrics_count[metric.name] = metrics_count.get(metric.name, 0) + 1
                        total_metrics += 1
                
                return {
                    "total_records": total_records,
                    "records_count": total_records,  # Added for compatibility
                    "total_conversations": total_conversations,
                    "metrics_count": metrics_count,
                    "total_metrics": total_metrics,
                    "has_output_path": bool(self._output_path)
                }
        except Exception as e:
            self.logger.error(f"Error getting record stats: {e}")
            return {"error": str(e)}
