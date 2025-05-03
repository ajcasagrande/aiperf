import uuid
import asyncio
import logging
import time
import json
import os
import statistics
import numpy as np
from abc import abstractmethod
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable

from ..common.base_manager import BaseManager
from ..common.models import Record, Metric
from ..config.config_models import MetricsConfig
from ..common.communication import Communication

class PostProcessor(BaseManager):
    """Base class for post-processors in AIPerf.
    
    Responsible for processing records to generate metrics and reports.
    """
    
    def __init__(self, config: MetricsConfig, 
                 communication: Optional[Communication] = None,
                 component_id: Optional[str] = None):
        """Initialize the post processor.
        
        Args:
            config: Metrics configuration
            communication: Communication interface
            component_id: Optional component ID
        """
        super().__init__(component_id=component_id or f"post_processor_{uuid.uuid4().hex[:8]}", 
                         config=config.__dict__)
        self.metrics_config = config
        self.communication = communication
        self._is_initialized = False
        self._metrics: Dict[str, List[Metric]] = {}
        self._metrics_lock = asyncio.Lock()
    
    async def initialize(self) -> bool:
        """Initialize the post processor.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        self.logger.info("Initializing post processor")
        
        try:
            # Initialize metrics
            await self._initialize_metrics()
            
            # Set up communication if provided
            if self.communication:
                # Subscribe to relevant topics
                await self.communication.subscribe("processors.request", self._handle_processor_request)
                
                # Subscribe to record events if live metrics are enabled
                if self.metrics_config.live_metrics:
                    await self.communication.subscribe("records.events", self._handle_record_event)
                
            self._is_initialized = True
            self._is_ready = True
            return True
        except Exception as e:
            self.logger.error(f"Error initializing post processor: {e}")
            return False
    
    async def _initialize_metrics(self) -> bool:
        """Initialize metrics.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        try:
            # Initialize metrics storage
            self._metrics = {}
            
            # Register default metrics
            for metric_name in self.metrics_config.enabled_metrics:
                self._metrics[metric_name] = []
                
            # Create output directory if configured
            if self.metrics_config.output_path:
                os.makedirs(os.path.dirname(self.metrics_config.output_path), exist_ok=True)
                
            return True
        except Exception as e:
            self.logger.error(f"Error initializing metrics: {e}")
            return False
    
    async def ready_check(self) -> bool:
        """Check if the post processor is ready.
        
        Returns:
            True if the post processor is ready, False otherwise
        """
        return self._is_initialized and self._is_ready
    
    async def publish_identity(self) -> bool:
        """Publish the post processor's identity.
        
        Returns:
            True if identity was published successfully, False otherwise
        """
        if not self.communication:
            self.logger.warning("No communication interface available, skipping identity publication")
            return False
            
        try:
            identity = {
                "component_id": self.component_id,
                "component_type": "post_processor",
                "enabled_metrics": list(self._metrics.keys())
            }
            
            success = await self.communication.publish("system.identity", identity)
            if success:
                self.logger.info("Published post processor identity")
            else:
                self.logger.warning("Failed to publish post processor identity")
                
            return success
        except Exception as e:
            self.logger.error(f"Error publishing post processor identity: {e}")
            return False
    
    async def shutdown(self) -> bool:
        """Gracefully shutdown the post processor.
        
        Returns:
            True if shutdown was successful, False otherwise
        """
        self.logger.info("Shutting down post processor")
        
        try:
            # Generate final report if configured
            if self.metrics_config.output_path:
                await self.generate_report(self.metrics_config.output_format, self.metrics_config.output_path)
                
            self._is_shutdown = True
            return True
        except Exception as e:
            self.logger.error(f"Error shutting down post processor: {e}")
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
        
        if command == "process_record":
            record = payload.get("record") if payload else None
            if record:
                metrics = await self.process_record(record)
                response = {"status": "success", "metrics": [m.__dict__ for m in metrics]}
            else:
                response = {"status": "error", "message": "No record provided"}
                
        elif command == "get_metrics":
            metric_names = payload.get("metric_names") if payload else None
            metrics = await self.get_metrics(metric_names)
            
            # Convert to serializable format
            serializable_metrics = {}
            for name, metric_list in metrics.items():
                serializable_metrics[name] = [m.__dict__ for m in metric_list]
                
            response = {"status": "success", "metrics": serializable_metrics}
            
        elif command == "generate_report":
            report_format = payload.get("format", "json") if payload else "json"
            output_path = payload.get("output_path") if payload else None
            report = await self.generate_report(report_format, output_path)
            response = {"status": "success", "report": report}
            
        elif command == "calculate_percentile":
            metric_name = payload.get("metric_name") if payload else None
            percentile = payload.get("percentile") if payload else 50
            
            if not metric_name:
                response = {"status": "error", "message": "Missing metric_name"}
            else:
                value = await self.calculate_percentile(metric_name, percentile)
                if value is not None:
                    response = {"status": "success", "value": value}
                else:
                    response = {"status": "error", "message": f"No data for metric: {metric_name}"}
        
        return response
        
    async def _handle_processor_request(self, message: Dict[str, Any]) -> None:
        """Handle processor request message.
        
        Args:
            message: Message dictionary
        """
        if not self.communication:
            return
            
        try:
            command = message.get("command")
            payload = message.get("payload", {})
            source = message.get("source")
            
            if not source:
                self.logger.warning("Processor request missing source")
                return
                
            # Process request
            response = await self.handle_command(command, payload)
            
            # Send response
            await self.communication.publish(f"processors.response.{source}", response)
        except Exception as e:
            self.logger.error(f"Error handling processor request: {e}")
            
    async def _handle_record_event(self, message: Dict[str, Any]) -> None:
        """Handle record event message.
        
        Args:
            message: Message dictionary
        """
        try:
            event = message.get("event")
            
            if event == "record_stored":
                record_id = message.get("record_id")
                
                if record_id and self.communication:
                    # Fetch record from records manager
                    response = await self.communication.request("records_manager", {
                        "command": "get_record",
                        "record_id": record_id
                    })
                    
                    record_data = response.get("record")
                    if record_data:
                        # Process record
                        await self.process_record(record_data)
        except Exception as e:
            self.logger.error(f"Error handling record event: {e}")
    
    async def process_record(self, record_data: Dict[str, Any]) -> List[Metric]:
        """Process a record and generate metrics.
        
        Args:
            record_data: Record data to process
            
        Returns:
            List of metrics generated from the record
        """
        try:
            result_metrics = []
            
            # Extract data from record
            record_id = record_data.get("record_id", "")
            conversation = record_data.get("conversation", {})
            metrics_data = record_data.get("metrics", [])
            raw_data = record_data.get("raw_data", {})
            
            # Process conversation data if available
            if conversation:
                # Calculate total conversation duration
                start_time = conversation.get("start_timestamp")
                end_time = conversation.get("end_timestamp")
                
                if start_time and end_time:
                    duration = end_time - start_time
                    duration_metric = Metric(
                        name="conversation_duration",
                        value=duration,
                        timestamp=time.time(),
                        unit="seconds",
                        labels={"record_id": record_id}
                    )
                    result_metrics.append(duration_metric)
                    
                    # Store metric
                    if "conversation_duration" in self._metrics:
                        async with self._metrics_lock:
                            self._metrics["conversation_duration"].append(duration_metric)
                
                # Process turns if available
                turns = conversation.get("turns", [])
                if turns:
                    turn_count = len(turns)
                    turn_count_metric = Metric(
                        name="conversation_turns",
                        value=turn_count,
                        timestamp=time.time(),
                        unit="count",
                        labels={"record_id": record_id}
                    )
                    result_metrics.append(turn_count_metric)
                    
                    # Store metric
                    if "conversation_turns" in self._metrics:
                        async with self._metrics_lock:
                            self._metrics["conversation_turns"].append(turn_count_metric)
            
            # Process existing metrics from record
            for metric_data in metrics_data:
                metric_name = metric_data.get("name")
                
                # Skip metrics that aren't enabled
                if metric_name not in self.metrics_config.enabled_metrics:
                    continue
                    
                # Create metric object
                metric = Metric(
                    name=metric_name,
                    value=metric_data.get("value"),
                    timestamp=metric_data.get("timestamp", time.time()),
                    unit=metric_data.get("unit"),
                    labels=metric_data.get("labels", {})
                )
                
                # Add record_id label if not present
                if "record_id" not in metric.labels:
                    metric.labels["record_id"] = record_id
                    
                result_metrics.append(metric)
                
                # Store metric
                if metric_name in self._metrics:
                    async with self._metrics_lock:
                        self._metrics[metric_name].append(metric)
            
            # Extract and calculate additional metrics from raw data
            if raw_data and "latency" in self.metrics_config.enabled_metrics:
                if "request_timestamp" in raw_data and "response_timestamp" in raw_data:
                    latency = raw_data["response_timestamp"] - raw_data["request_timestamp"]
                    latency_metric = Metric(
                        name="latency",
                        value=latency,
                        timestamp=time.time(),
                        unit="seconds",
                        labels={"record_id": record_id}
                    )
                    result_metrics.append(latency_metric)
                    
                    # Store metric
                    if "latency" in self._metrics:
                        async with self._metrics_lock:
                            self._metrics["latency"].append(latency_metric)
            
            # Publish processed metrics
            if self.communication and result_metrics:
                await self.communication.publish("metrics.processed", {
                    "processor_id": self.component_id,
                    "record_id": record_id,
                    "metrics": [m.__dict__ for m in result_metrics]
                })
                
            return result_metrics
        except Exception as e:
            self.logger.error(f"Error processing record: {e}")
            return []
    
    async def get_metrics(self, metric_names: Optional[List[str]] = None) -> Dict[str, List[Metric]]:
        """Get metrics by name.
        
        Args:
            metric_names: Optional list of metric names to get
            
        Returns:
            Dictionary mapping metric names to lists of metrics
        """
        try:
            result = {}
            
            async with self._metrics_lock:
                if metric_names:
                    # Return only requested metrics
                    for name in metric_names:
                        if name in self._metrics:
                            result[name] = self._metrics[name]
                else:
                    # Return all metrics
                    result = self._metrics.copy()
                    
            return result
        except Exception as e:
            self.logger.error(f"Error getting metrics: {e}")
            return {}
    
    async def generate_report(self, report_format: str = "json", 
                             output_path: Optional[str] = None) -> Dict[str, Any]:
        """Generate a report.
        
        Args:
            report_format: Report format (json, csv, etc.)
            output_path: Optional path to write the report to
            
        Returns:
            Dictionary with report data
        """
        try:
            report = {
                "timestamp": time.time(),
                "processor_id": self.component_id,
                "metrics_summary": {},
                "percentiles": {}
            }
            
            # Generate metrics summary
            async with self._metrics_lock:
                for metric_name, metrics in self._metrics.items():
                    if not metrics:
                        continue
                        
                    values = [m.value for m in metrics if isinstance(m.value, (int, float))]
                    
                    if not values:
                        continue
                        
                    # Calculate statistics
                    summary = {
                        "count": len(values),
                        "min": min(values),
                        "max": max(values),
                        "mean": statistics.mean(values),
                        "stddev": statistics.stdev(values) if len(values) > 1 else 0
                    }
                    
                    # Calculate percentiles
                    percentiles = {}
                    for p in [50, 90, 95, 99]:
                        percentiles[f"p{p}"] = np.percentile(values, p)
                        
                    report["metrics_summary"][metric_name] = summary
                    report["percentiles"][metric_name] = percentiles
            
            # Write report to file if output path specified
            if output_path:
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                if report_format == "json":
                    with open(output_path, 'w') as f:
                        json.dump(report, f, indent=2)
                elif report_format == "csv":
                    # Generate CSV report
                    import csv
                    with open(output_path, 'w', newline='') as f:
                        writer = csv.writer(f)
                        
                        # Write header
                        writer.writerow(["Metric", "Count", "Min", "Max", "Mean", "StdDev", "P50", "P90", "P95", "P99"])
                        
                        # Write data rows
                        for metric_name in report["metrics_summary"]:
                            summary = report["metrics_summary"][metric_name]
                            percentiles = report["percentiles"][metric_name]
                            
                            writer.writerow([
                                metric_name,
                                summary["count"],
                                summary["min"],
                                summary["max"],
                                summary["mean"],
                                summary["stddev"],
                                percentiles["p50"],
                                percentiles["p90"],
                                percentiles["p95"],
                                percentiles["p99"]
                            ])
                else:
                    self.logger.warning(f"Unsupported report format: {report_format}")
                
            return report
        except Exception as e:
            self.logger.error(f"Error generating report: {e}")
            return {"error": str(e)}
    
    async def calculate_percentile(self, metric_name: str, percentile: float) -> Optional[float]:
        """Calculate percentile for a metric.
        
        Args:
            metric_name: Metric name
            percentile: Percentile to calculate (0-100)
            
        Returns:
            Percentile value or None if metric not found
        """
        try:
            if metric_name not in self._metrics:
                return None
                
            async with self._metrics_lock:
                metrics = self._metrics[metric_name]
                if not metrics:
                    return None
                    
                values = [m.value for m in metrics if isinstance(m.value, (int, float))]
                
                if not values:
                    return None
                    
                return np.percentile(values, percentile)
        except Exception as e:
            self.logger.error(f"Error calculating percentile: {e}")
            return None

class PostProcessorRegistry(BaseManager):
    """Registry for post-processors.
    
    Manages a collection of post-processors and routes records to them.
    """
    
    def __init__(self, config: MetricsConfig, 
                 communication: Optional[Communication] = None,
                 component_id: Optional[str] = None):
        """Initialize the post processor registry.
        
        Args:
            config: Metrics configuration
            communication: Communication interface
            component_id: Optional component ID
        """
        super().__init__(component_id=component_id or f"post_processor_registry_{uuid.uuid4().hex[:8]}", 
                         config=config.__dict__)
        self.metrics_config = config
        self.communication = communication
        self._processors: Dict[str, PostProcessor] = {}
        self._processors_lock = asyncio.Lock()
        self._is_initialized = False
    
    async def initialize(self) -> bool:
        """Initialize the post processor registry.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        self.logger.info("Initializing post processor registry")
        
        try:
            # Register built-in processors
            await self._register_built_in_processors()
            
            # Set up communication if provided
            if self.communication:
                # Subscribe to relevant topics
                await self.communication.subscribe("processors.request", self._handle_processor_request)
                
                # Subscribe to record events if live metrics are enabled
                if self.metrics_config.live_metrics:
                    await self.communication.subscribe("records.events", self._handle_record_event)
                
            self._is_initialized = True
            self._is_ready = len(self._processors) > 0
            return self._is_ready
        except Exception as e:
            self.logger.error(f"Error initializing post processor registry: {e}")
            return False
    
    async def _register_built_in_processors(self) -> bool:
        """Register built-in processors.
        
        Returns:
            True if registration was successful, False otherwise
        """
        try:
            # Create default post processor
            default_processor = PostProcessor(
                config=self.metrics_config,
                communication=self.communication,
                component_id=f"default_processor_{uuid.uuid4().hex[:8]}"
            )
            
            # Initialize processor
            success = await default_processor.initialize()
            if not success:
                self.logger.error("Failed to initialize default processor")
                return False
                
            # Register processor
            await self.register_processor("default", default_processor)
            
            # Add more built-in processors here as needed
            
            return True
        except Exception as e:
            self.logger.error(f"Error registering built-in processors: {e}")
            return False
    
    async def ready_check(self) -> bool:
        """Check if the post processor registry is ready.
        
        Returns:
            True if the post processor registry is ready, False otherwise
        """
        return self._is_initialized and self._is_ready
    
    async def publish_identity(self) -> bool:
        """Publish the post processor registry's identity.
        
        Returns:
            True if identity was published successfully, False otherwise
        """
        if not self.communication:
            self.logger.warning("No communication interface available, skipping identity publication")
            return False
            
        try:
            identity = {
                "component_id": self.component_id,
                "component_type": "post_processor_registry",
                "processors": list(self._processors.keys())
            }
            
            success = await self.communication.publish("system.identity", identity)
            if success:
                self.logger.info("Published post processor registry identity")
            else:
                self.logger.warning("Failed to publish post processor registry identity")
                
            return success
        except Exception as e:
            self.logger.error(f"Error publishing post processor registry identity: {e}")
            return False
    
    async def shutdown(self) -> bool:
        """Gracefully shutdown the post processor registry and all processors.
        
        Returns:
            True if shutdown was successful, False otherwise
        """
        self.logger.info("Shutting down post processor registry")
        
        try:
            # Shutdown all processors
            async with self._processors_lock:
                for processor_id, processor in self._processors.items():
                    await processor.shutdown()
                    
            self._is_shutdown = True
            return True
        except Exception as e:
            self.logger.error(f"Error shutting down post processor registry: {e}")
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
        
        if command == "process_record":
            record = payload.get("record") if payload else None
            if record:
                metrics = await self.process_record(record)
                
                # Convert to serializable format
                serializable_metrics = {}
                for processor_id, metric_list in metrics.items():
                    serializable_metrics[processor_id] = [m.__dict__ for m in metric_list]
                    
                response = {"status": "success", "metrics": serializable_metrics}
            else:
                response = {"status": "error", "message": "No record provided"}
                
        elif command == "get_metrics":
            metric_names = payload.get("metric_names") if payload else None
            processor_id = payload.get("processor_id") if payload else None
            
            metrics = await self.get_metrics(metric_names, processor_id)
            
            # Convert to serializable format
            serializable_metrics = {}
            for processor_id, processor_metrics in metrics.items():
                serializable_metrics[processor_id] = {}
                for metric_name, metric_list in processor_metrics.items():
                    serializable_metrics[processor_id][metric_name] = [m.__dict__ for m in metric_list]
                    
            response = {"status": "success", "metrics": serializable_metrics}
            
        elif command == "generate_report":
            report_format = payload.get("format", "json") if payload else "json"
            output_path = payload.get("output_path") if payload else None
            processor_id = payload.get("processor_id") if payload else None
            
            report = await self.generate_report(report_format, output_path, processor_id)
            response = {"status": "success", "report": report}
            
        elif command == "register_processor":
            processor_id = payload.get("processor_id") if payload else None
            processor_config = payload.get("config") if payload else None
            
            if not processor_id or not processor_config:
                response = {"status": "error", "message": "Missing processor_id or config"}
            else:
                # Create processor with config
                processor = PostProcessor(
                    config=MetricsConfig(**processor_config),
                    communication=self.communication,
                    component_id=f"{processor_id}_{uuid.uuid4().hex[:8]}"
                )
                
                # Initialize and register processor
                success = await processor.initialize()
                if success:
                    success = await self.register_processor(processor_id, processor)
                    
                if success:
                    response = {"status": "success", "message": f"Processor {processor_id} registered"}
                else:
                    response = {"status": "error", "message": f"Failed to register processor {processor_id}"}
        
        return response
        
    async def _handle_processor_request(self, message: Dict[str, Any]) -> None:
        """Handle processor request message.
        
        Args:
            message: Message dictionary
        """
        if not self.communication:
            return
            
        try:
            command = message.get("command")
            payload = message.get("payload", {})
            source = message.get("source")
            
            if not source:
                self.logger.warning("Processor request missing source")
                return
                
            # Process request
            response = await self.handle_command(command, payload)
            
            # Send response
            await self.communication.publish(f"processors.response.{source}", response)
        except Exception as e:
            self.logger.error(f"Error handling processor request: {e}")
            
    async def _handle_record_event(self, message: Dict[str, Any]) -> None:
        """Handle record event message.
        
        Args:
            message: Message dictionary
        """
        try:
            event = message.get("event")
            
            if event == "record_stored":
                record_id = message.get("record_id")
                
                if record_id and self.communication:
                    # Fetch record from records manager
                    response = await self.communication.request("records_manager", {
                        "command": "get_record",
                        "record_id": record_id
                    })
                    
                    record_data = response.get("record")
                    if record_data:
                        # Process record with all processors
                        await self.process_record(record_data)
        except Exception as e:
            self.logger.error(f"Error handling record event: {e}")
    
    async def register_processor(self, processor_id: str, processor: PostProcessor) -> bool:
        """Register a processor.
        
        Args:
            processor_id: Processor ID
            processor: Processor instance
            
        Returns:
            True if the processor was registered successfully, False otherwise
        """
        try:
            async with self._processors_lock:
                self._processors[processor_id] = processor
                
            self.logger.info(f"Registered processor: {processor_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error registering processor: {e}")
            return False
    
    async def process_record(self, record_data: Dict[str, Any]) -> Dict[str, List[Metric]]:
        """Process a record with all processors.
        
        Args:
            record_data: Record data to process
            
        Returns:
            Dictionary mapping processor IDs to lists of metrics
        """
        try:
            result = {}
            
            # Process record with all processors
            async with self._processors_lock:
                for processor_id, processor in self._processors.items():
                    metrics = await processor.process_record(record_data)
                    result[processor_id] = metrics
                    
            return result
        except Exception as e:
            self.logger.error(f"Error processing record with processors: {e}")
            return {}
    
    async def get_metrics(self, metric_names: Optional[List[str]] = None, 
                         processor_id: Optional[str] = None) -> Dict[str, Dict[str, List[Metric]]]:
        """Get metrics from processors.
        
        Args:
            metric_names: Optional list of metric names to get
            processor_id: Optional processor ID to get metrics from
            
        Returns:
            Dictionary mapping processor IDs to dictionaries mapping metric names to lists of metrics
        """
        try:
            result = {}
            
            async with self._processors_lock:
                if processor_id:
                    # Get metrics from specific processor
                    if processor_id in self._processors:
                        processor = self._processors[processor_id]
                        metrics = await processor.get_metrics(metric_names)
                        result[processor_id] = metrics
                else:
                    # Get metrics from all processors
                    for processor_id, processor in self._processors.items():
                        metrics = await processor.get_metrics(metric_names)
                        result[processor_id] = metrics
                    
            return result
        except Exception as e:
            self.logger.error(f"Error getting metrics from processors: {e}")
            return {}
    
    async def generate_report(self, report_format: str = "json", 
                             output_path: Optional[str] = None,
                             processor_id: Optional[str] = None) -> Dict[str, Any]:
        """Generate a report from processors.
        
        Args:
            report_format: Report format (json, csv, etc.)
            output_path: Optional path to write the report to
            processor_id: Optional processor ID to generate report from
            
        Returns:
            Dictionary with report data
        """
        try:
            result = {
                "timestamp": time.time(),
                "registry_id": self.component_id,
                "processors": {}
            }
            
            async with self._processors_lock:
                if processor_id:
                    # Generate report from specific processor
                    if processor_id in self._processors:
                        processor = self._processors[processor_id]
                        
                        # Modify output path for specific processor if provided
                        processor_output_path = None
                        if output_path:
                            base_name, ext = os.path.splitext(output_path)
                            processor_output_path = f"{base_name}_{processor_id}{ext}"
                            
                        report = await processor.generate_report(report_format, processor_output_path)
                        result["processors"][processor_id] = report
                else:
                    # Generate reports from all processors
                    for proc_id, processor in self._processors.items():
                        # Modify output path for each processor if provided
                        processor_output_path = None
                        if output_path:
                            base_name, ext = os.path.splitext(output_path)
                            processor_output_path = f"{base_name}_{proc_id}{ext}"
                            
                        report = await processor.generate_report(report_format, processor_output_path)
                        result["processors"][proc_id] = report
                        
            # Write combined report if output path specified
            if output_path and not processor_id:
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                if report_format == "json":
                    with open(output_path, 'w') as f:
                        json.dump(result, f, indent=2)
                else:
                    self.logger.warning(f"Combined report for format {report_format} not supported")
                    
            return result
        except Exception as e:
            self.logger.error(f"Error generating report from processors: {e}")
            return {"error": str(e)}
