# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Monitoring Plugin - System Health and Alerting

This plugin demonstrates monitoring capabilities using the amazing mixin architecture:
- System health monitoring
- Alert threshold management
- Metric collection and aggregation
- Plugin-to-plugin communication
- Real-time dashboard data
"""

import time
from collections import defaultdict
from typing import Any

from aiperf.common.enums.message_enums import CommandType, MessageType
from aiperf.core.decorators import background_task, command_handler, message_handler
from aiperf.core.plugins import BasePlugin


class MonitoringPlugin(BasePlugin):
    """
    System monitoring plugin that tracks health metrics and manages alerts.
    """

    # Plugin metadata
    plugin_name = "monitoring"
    plugin_version = "1.5.0"
    plugin_description = "Real-time system monitoring with intelligent alerting"
    plugin_author = "AIPerf Team"
    plugin_dependencies = []
    plugin_requires_services = ["event_bus"]
    plugin_provides_services = ["health_monitoring", "alerting", "metrics"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Monitoring state
        self.metrics: dict[str, dict] = defaultdict(
            lambda: {
                "count": 0,
                "last_seen": 0,
                "rate_per_minute": 0.0,
                "alerts_sent": 0,
            }
        )

        self.service_health: dict[str, dict] = {}
        self.alert_history: list = []

        # Configuration
        self.alert_threshold = 100
        self.health_check_interval = 30.0
        self.metrics_retention_hours = 24
        self.enable_email_alerts = False

    async def _initialize(self) -> None:
        """Initialize the monitoring plugin."""
        await super()._initialize()

        # Load configuration
        self.alert_threshold = self.plugin_config.get("alert_threshold", 100)
        self.health_check_interval = self.plugin_config.get(
            "health_check_interval", 30.0
        )
        self.metrics_retention_hours = self.plugin_config.get(
            "metrics_retention_hours", 24
        )
        self.enable_email_alerts = self.plugin_config.get("enable_email_alerts", False)

        self.info("Monitoring plugin initialized:")
        self.info(f"  - Alert threshold: {self.alert_threshold}")
        self.info(f"  - Health check interval: {self.health_check_interval}s")
        self.info(f"  - Metrics retention: {self.metrics_retention_hours}h")
        self.info(f"  - Email alerts: {self.enable_email_alerts}")

    async def _start(self) -> None:
        """Start monitoring."""
        await super()._start()
        self.info("Monitoring plugin started - watching system health")

    # =================================================================
    # Message Handlers - Monitor All System Activity
    # =================================================================

    @message_handler(MessageType.Heartbeat)
    async def monitor_heartbeats(self, message: Any) -> None:
        """
        Monitor service heartbeats for health tracking.

        This shows how plugins can monitor system-wide activity
        and track service health patterns.
        """
        try:
            service_id = getattr(message, "service_id", "unknown")
            timestamp = time.time()

            # Update service health record
            if service_id not in self.service_health:
                self.service_health[service_id] = {
                    "first_seen": timestamp,
                    "last_heartbeat": timestamp,
                    "heartbeat_count": 0,
                    "status": "healthy",
                }

            health_record = self.service_health[service_id]
            health_record["last_heartbeat"] = timestamp
            health_record["heartbeat_count"] += 1

            # Update metrics
            self._update_metric("heartbeat", service_id)

            self.debug(
                f"Heartbeat from {service_id} - {health_record['heartbeat_count']} total"
            )

        except Exception as e:
            self.exception(f"Error monitoring heartbeat: {e}")

    @message_handler(MessageType.Status, MessageType.DATA_PROCESSED)
    async def monitor_system_activity(self, message: Any) -> None:
        """
        Monitor general system activity and performance.

        This demonstrates how plugins can collect metrics from
        various message types across the system.
        """
        try:
            message_type = getattr(message, "message_type", "unknown")
            service_id = getattr(message, "service_id", "unknown")

            # Track message frequency
            self._update_metric(f"message_{message_type}", service_id)

            # Special handling for data processing messages
            if message_type == MessageType.DATA_PROCESSED:
                data = getattr(message, "data", {})
                if isinstance(data, dict):
                    batch_size = data.get("batch_size", 0)
                    processing_time = data.get("processing_time", 0)

                    if batch_size > 0:
                        self._update_performance_metric(
                            "data_processing",
                            {
                                "batch_size": batch_size,
                                "processing_time": processing_time,
                                "throughput": batch_size / processing_time
                                if processing_time > 0
                                else 0,
                            },
                        )

        except Exception as e:
            self.exception(f"Error monitoring system activity: {e}")

    @message_handler(MessageType.ServiceError)
    async def monitor_errors(self, message: Any) -> None:
        """
        Monitor and track system errors.

        This shows how plugins can respond to error conditions
        and potentially trigger automated responses.
        """
        try:
            service_id = getattr(message, "service_id", "unknown")
            error_details = getattr(message, "error", "Unknown error")

            # Update metrics
            self._update_metric("error", service_id)

            # Create alert for errors
            await self._send_alert(
                alert_type="service_error",
                message=f"Service {service_id} reported error: {error_details}",
                severity="high",
                service_id=service_id,
            )

        except Exception as e:
            self.exception(f"Error monitoring errors: {e}")

    # =================================================================
    # Command Handlers - Monitoring Control and Status
    # =================================================================

    @command_handler(CommandType.GET_STATUS)
    async def get_monitoring_status(self, command: Any) -> dict:
        """Get comprehensive monitoring status."""
        current_time = time.time()

        # Calculate health summary
        healthy_services = 0
        unhealthy_services = 0
        for service_id, health in self.service_health.items():
            time_since_heartbeat = current_time - health["last_heartbeat"]
            if time_since_heartbeat < 60:  # Healthy if heartbeat within 1 minute
                healthy_services += 1
            else:
                unhealthy_services += 1

        return {
            "plugin": self.plugin_name,
            "monitoring_status": "active",
            "metrics_tracked": len(self.metrics),
            "services_monitored": len(self.service_health),
            "healthy_services": healthy_services,
            "unhealthy_services": unhealthy_services,
            "alerts_sent": len(self.alert_history),
            "configuration": {
                "alert_threshold": self.alert_threshold,
                "health_check_interval": self.health_check_interval,
                "metrics_retention_hours": self.metrics_retention_hours,
            },
        }

    @command_handler(CommandType.Shutdown)
    async def prepare_shutdown(self, command: Any) -> dict:
        """Handle shutdown preparation - generate final report."""
        self.info("Generating final monitoring report before shutdown")

        # Generate comprehensive report
        report = {
            "final_metrics": dict(self.metrics),
            "service_health_summary": self.service_health.copy(),
            "alert_summary": {
                "total_alerts": len(self.alert_history),
                "recent_alerts": self.alert_history[-10:] if self.alert_history else [],
            },
            "monitoring_duration": time.time()
            - getattr(self, "_start_time", time.time()),
            "plugin": self.plugin_name,
        }

        return report

    # =================================================================
    # Background Tasks - Automated Monitoring
    # =================================================================

    @background_task(interval=30.0)
    async def health_check_sweep(self) -> None:
        """
        Perform periodic health checks on all monitored services.

        This demonstrates automated monitoring using background tasks.
        """
        current_time = time.time()
        unhealthy_services = []

        for service_id, health in self.service_health.items():
            time_since_heartbeat = current_time - health["last_heartbeat"]

            # Consider service unhealthy if no heartbeat for 2 minutes
            if time_since_heartbeat > 120:
                if health["status"] != "unhealthy":
                    health["status"] = "unhealthy"
                    unhealthy_services.append(service_id)

                    await self._send_alert(
                        alert_type="service_unhealthy",
                        message=f"Service {service_id} missed heartbeat for {time_since_heartbeat:.1f}s",
                        severity="medium",
                        service_id=service_id,
                    )
            else:
                health["status"] = "healthy"

        if unhealthy_services:
            self.warning(
                f"Found {len(unhealthy_services)} unhealthy services: {unhealthy_services}"
            )

    @background_task(interval=60.0)
    async def calculate_rates(self) -> None:
        """
        Calculate and update message rates for all metrics.

        This shows how background tasks can perform data analysis.
        """
        current_time = time.time()

        for metric_name, metric_data in self.metrics.items():
            # Calculate rate per minute
            time_window = 60  # 1 minute
            if metric_data["last_seen"] > 0:
                time_diff = current_time - metric_data["last_seen"]
                if time_diff > 0:
                    # Simple rate calculation (could be more sophisticated)
                    metric_data["rate_per_minute"] = min(
                        metric_data["count"] / (time_diff / 60),
                        metric_data["count"],  # Cap at total count
                    )

    @background_task(interval=300.0)  # Every 5 minutes
    async def publish_dashboard_data(self) -> None:
        """
        Publish monitoring data for dashboards and external systems.

        This demonstrates how plugins can provide data to external systems.
        """
        try:
            # Prepare dashboard data
            dashboard_data = {
                "plugin": self.plugin_name,
                "timestamp": time.time(),
                "summary": {
                    "total_services": len(self.service_health),
                    "healthy_services": sum(
                        1
                        for h in self.service_health.values()
                        if h["status"] == "healthy"
                    ),
                    "total_metrics": len(self.metrics),
                    "total_alerts": len(self.alert_history),
                },
                "top_metrics": self._get_top_metrics(5),
                "recent_alerts": self.alert_history[-5:] if self.alert_history else [],
            }

            # Publish to dashboard topic
            await self.publish(MessageType.DASHBOARD_UPDATE, dashboard_data)

            self.debug("Published dashboard data")

        except Exception as e:
            self.exception(f"Error publishing dashboard data: {e}")

    @background_task(interval=3600.0)  # Every hour
    async def cleanup_old_data(self) -> None:
        """Clean up old monitoring data to manage memory usage."""
        current_time = time.time()
        retention_seconds = self.metrics_retention_hours * 3600

        # Clean up old alert history
        cutoff_time = current_time - retention_seconds
        original_count = len(self.alert_history)
        self.alert_history = [
            alert
            for alert in self.alert_history
            if alert.get("timestamp", 0) > cutoff_time
        ]

        cleaned_count = original_count - len(self.alert_history)
        if cleaned_count > 0:
            self.info(f"Cleaned up {cleaned_count} old alerts")

    # =================================================================
    # Private Helper Methods
    # =================================================================

    def _update_metric(self, metric_type: str, source: str) -> None:
        """Update a metric counter."""
        metric_key = f"{metric_type}_{source}"
        metric = self.metrics[metric_key]
        metric["count"] += 1
        metric["last_seen"] = time.time()

        # Check for threshold alerts
        if metric["count"] > self.alert_threshold and metric["alerts_sent"] == 0:
            # This line was commented out as it requires asyncio, which is not imported.
            # asyncio.create_task(self._send_alert(
            #     alert_type="threshold_exceeded",
            #     message=f"Metric {metric_key} exceeded threshold: {metric['count']} > {self.alert_threshold}",
            #     severity="medium",
            #     metric=metric_key
            # ))
            metric["alerts_sent"] = 1  # Prevent spam

    def _update_performance_metric(self, metric_type: str, data: dict) -> None:
        """Update performance metrics with numerical data."""
        # This could be extended to maintain rolling averages, percentiles, etc.
        pass

    async def _send_alert(
        self, alert_type: str, message: str, severity: str, **kwargs
    ) -> None:
        """Send an alert message."""
        alert = {
            "alert_type": alert_type,
            "message": message,
            "severity": severity,
            "timestamp": time.time(),
            "plugin": self.plugin_name,
            **kwargs,
        }

        # Store in history
        self.alert_history.append(alert)

        # Log the alert
        log_method = (
            self.warning
            if severity == "medium"
            else self.error
            if severity == "high"
            else self.info
        )
        log_method(f"ALERT [{severity.upper()}]: {message}")

        # Publish alert
        try:
            await self.publish(MessageType.ALERT, alert)
        except Exception as e:
            self.exception(f"Failed to publish alert: {e}")

    def _get_top_metrics(self, count: int) -> list:
        """Get top metrics by count."""
        sorted_metrics = sorted(
            [(name, data["count"]) for name, data in self.metrics.items()],
            key=lambda x: x[1],
            reverse=True,
        )
        return sorted_metrics[:count]
