import uuid
import asyncio
import logging
import time
import random
import math
import numpy as np
from abc import abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union, Callable, Set

from ..common.base_manager import BaseManager
from ..common.models import TimingCredit, DistributionType
from ..config.config_models import TimingConfig
from ..common.communication import Communication

class TimingManager(BaseManager):
    """Timing manager for AIPerf.
    
    Responsible for managing timing schedules, including:
    - Fixed schedules
    - Distributions (Poisson, Normal, Uniform)
    - Delay-based start times
    - Concurrency and request rate management
    """
    
    def __init__(self, config: TimingConfig, 
                 communication: Optional[Communication] = None,
                 component_id: Optional[str] = None):
        """Initialize the timing manager.
        
        Args:
            config: Timing configuration
            communication: Communication interface
            component_id: Optional component ID
        """
        super().__init__(component_id=component_id or f"timing_manager_{uuid.uuid4().hex[:8]}", 
                         config=config.__dict__)
        self.timing_config = config
        self.communication = communication
        self._schedule: List[TimingCredit] = []
        self._pending_credits: Set[str] = set()
        self._consumed_credits: Set[str] = set()
        self._schedule_lock = asyncio.Lock()
        self._running = False
        self._is_initialized = False
        self._credit_consumers: List[Callable[[TimingCredit], None]] = []
        self._start_time: Optional[float] = None
        self._stop_time: Optional[float] = None
        self._timer_task: Optional[asyncio.Task] = None
    
    async def initialize(self) -> bool:
        """Initialize the timing manager.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        self.logger.info(f"Initializing timing manager: {self.timing_config.schedule_type}")
        
        try:
            # Initialize schedule based on configuration
            if self.timing_config.schedule_type == "fixed":
                await self._initialize_fixed_schedule()
            elif self.timing_config.schedule_type == "poisson":
                await self._initialize_poisson_schedule()
            elif self.timing_config.schedule_type == "normal":
                await self._initialize_normal_schedule()
            elif self.timing_config.schedule_type == "uniform":
                await self._initialize_uniform_schedule()
            else:
                self.logger.error(f"Unsupported schedule type: {self.timing_config.schedule_type}")
                return False
                
            # Set up communication if provided
            if self.communication:
                # Subscribe to relevant topics
                await self.communication.subscribe(f"timing.request", self._handle_timing_request)
                await self.communication.subscribe(f"timing.credit.consumed", self._handle_credit_consumed)
                
            self._is_initialized = True
            self._is_ready = True
            return True
        except Exception as e:
            self.logger.error(f"Error initializing timing manager: {e}")
            return False
    
    async def _initialize_fixed_schedule(self) -> bool:
        """Initialize fixed schedule.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        self.logger.info("Initializing fixed schedule")
        
        try:
            params = self.timing_config.parameters
            request_rate = params.get("request_rate") or self.timing_config.request_rate
            duration = params.get("duration") or self.timing_config.duration
            
            if not request_rate or not duration:
                self.logger.error("Fixed schedule requires request_rate and duration")
                return False
                
            # Calculate total number of requests
            total_requests = int(request_rate * duration)
            
            # Calculate time delta between requests
            time_delta = 1.0 / request_rate
            
            # Create schedule
            async with self._schedule_lock:
                self._schedule = []
                for i in range(total_requests):
                    credit = TimingCredit(
                        credit_id=f"credit_{uuid.uuid4().hex[:8]}",
                        target_timestamp=time.time() + self.timing_config.start_delay + (i * time_delta),
                        credit_type="request",
                        parameters={"index": i}
                    )
                    self._schedule.append(credit)
                    self._pending_credits.add(credit.credit_id)
                    
            self.logger.info(f"Created fixed schedule with {len(self._schedule)} credits")
            return True
        except Exception as e:
            self.logger.error(f"Error initializing fixed schedule: {e}")
            return False
        
    async def _initialize_poisson_schedule(self) -> bool:
        """Initialize Poisson schedule.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        self.logger.info("Initializing Poisson schedule")
        
        try:
            params = self.timing_config.parameters
            request_rate = params.get("request_rate") or self.timing_config.request_rate  # lambda parameter
            duration = params.get("duration") or self.timing_config.duration
            
            if not request_rate or not duration:
                self.logger.error("Poisson schedule requires request_rate and duration")
                return False
                
            # Generate Poisson arrival times
            arrival_times = []
            current_time = 0.0
            while current_time < duration:
                # Time to next arrival follows exponential distribution
                next_time = random.expovariate(request_rate)
                current_time += next_time
                if current_time < duration:
                    arrival_times.append(current_time)
            
            # Create schedule
            async with self._schedule_lock:
                self._schedule = []
                for i, arrival_time in enumerate(arrival_times):
                    credit = TimingCredit(
                        credit_id=f"credit_{uuid.uuid4().hex[:8]}",
                        target_timestamp=time.time() + self.timing_config.start_delay + arrival_time,
                        credit_type="request",
                        parameters={"index": i}
                    )
                    self._schedule.append(credit)
                    self._pending_credits.add(credit.credit_id)
                    
            self.logger.info(f"Created Poisson schedule with {len(self._schedule)} credits")
            return True
        except Exception as e:
            self.logger.error(f"Error initializing Poisson schedule: {e}")
            return False
        
    async def _initialize_normal_schedule(self) -> bool:
        """Initialize Normal schedule.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        self.logger.info("Initializing Normal schedule")
        
        try:
            params = self.timing_config.parameters
            request_rate = params.get("request_rate") or self.timing_config.request_rate
            duration = params.get("duration") or self.timing_config.duration
            mean = params.get("mean", 1.0 / request_rate)
            stddev = params.get("stddev", mean / 4.0)  # Default stddev is 25% of mean
            
            if not request_rate or not duration:
                self.logger.error("Normal schedule requires request_rate and duration")
                return False
                
            # Generate arrival times
            arrival_times = []
            current_time = 0.0
            while current_time < duration:
                # Time to next arrival follows normal distribution (truncated to positive values)
                next_time = max(0.001, random.normalvariate(mean, stddev))
                current_time += next_time
                if current_time < duration:
                    arrival_times.append(current_time)
            
            # Create schedule
            async with self._schedule_lock:
                self._schedule = []
                for i, arrival_time in enumerate(arrival_times):
                    credit = TimingCredit(
                        credit_id=f"credit_{uuid.uuid4().hex[:8]}",
                        target_timestamp=time.time() + self.timing_config.start_delay + arrival_time,
                        credit_type="request",
                        parameters={"index": i}
                    )
                    self._schedule.append(credit)
                    self._pending_credits.add(credit.credit_id)
                    
            self.logger.info(f"Created Normal schedule with {len(self._schedule)} credits")
            return True
        except Exception as e:
            self.logger.error(f"Error initializing Normal schedule: {e}")
            return False
        
    async def _initialize_uniform_schedule(self) -> bool:
        """Initialize Uniform schedule.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        self.logger.info("Initializing Uniform schedule")
        
        try:
            params = self.timing_config.parameters
            request_rate = params.get("request_rate") or self.timing_config.request_rate
            duration = params.get("duration") or self.timing_config.duration
            min_time = params.get("min_time", 0.5 / request_rate)
            max_time = params.get("max_time", 1.5 / request_rate)
            
            if not request_rate or not duration:
                self.logger.error("Uniform schedule requires request_rate and duration")
                return False
                
            # Generate arrival times
            arrival_times = []
            current_time = 0.0
            while current_time < duration:
                # Time to next arrival follows uniform distribution
                next_time = random.uniform(min_time, max_time)
                current_time += next_time
                if current_time < duration:
                    arrival_times.append(current_time)
            
            # Create schedule
            async with self._schedule_lock:
                self._schedule = []
                for i, arrival_time in enumerate(arrival_times):
                    credit = TimingCredit(
                        credit_id=f"credit_{uuid.uuid4().hex[:8]}",
                        target_timestamp=time.time() + self.timing_config.start_delay + arrival_time,
                        credit_type="request",
                        parameters={"index": i}
                    )
                    self._schedule.append(credit)
                    self._pending_credits.add(credit.credit_id)
                    
            self.logger.info(f"Created Uniform schedule with {len(self._schedule)} credits")
            return True
        except Exception as e:
            self.logger.error(f"Error initializing Uniform schedule: {e}")
            return False
    
    async def ready_check(self) -> bool:
        """Check if the timing manager is ready.
        
        Returns:
            True if the timing manager is ready, False otherwise
        """
        return self._is_initialized and self._is_ready
    
    async def publish_identity(self) -> bool:
        """Publish the timing manager's identity.
        
        Returns:
            True if identity was published successfully, False otherwise
        """
        if not self.communication:
            self.logger.warning("No communication interface available, skipping identity publication")
            return False
            
        try:
            identity = {
                "component_id": self.component_id,
                "component_type": "timing_manager",
                "schedule_type": self.timing_config.schedule_type,
                "credits_count": len(self._schedule)
            }
            
            success = await self.communication.publish("system.identity", identity)
            if success:
                self.logger.info("Published timing manager identity")
            else:
                self.logger.warning("Failed to publish timing manager identity")
                
            return success
        except Exception as e:
            self.logger.error(f"Error publishing timing manager identity: {e}")
            return False
    
    async def shutdown(self) -> bool:
        """Gracefully shutdown the timing manager.
        
        Returns:
            True if shutdown was successful, False otherwise
        """
        self.logger.info("Shutting down timing manager")
        
        try:
            # Stop timing
            await self.stop_timing()
            
            # Clear schedule
            async with self._schedule_lock:
                self._schedule = []
                self._pending_credits.clear()
                self._consumed_credits.clear()
                
            self._is_shutdown = True
            return True
        except Exception as e:
            self.logger.error(f"Error shutting down timing manager: {e}")
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
        
        if command == "start":
            success = await self.start_timing()
            if success:
                response = {"status": "success", "message": "Timing started"}
            else:
                response = {"status": "error", "message": "Failed to start timing"}
                
        elif command == "stop":
            success = await self.stop_timing()
            if success:
                response = {"status": "success", "message": "Timing stopped"}
            else:
                response = {"status": "error", "message": "Failed to stop timing"}
                
        elif command == "get_stats":
            stats = await self.get_timing_stats()
            response = {"status": "success", "stats": stats}
            
        elif command == "register_consumer":
            consumer_id = payload.get("consumer_id") if payload else None
            if not consumer_id:
                response = {"status": "error", "message": "Missing consumer_id"}
            else:
                # In a real implementation, we would store a reference to the consumer
                # and call it directly when a credit is issued.
                # For now, just acknowledge the registration.
                response = {"status": "success", "message": f"Consumer {consumer_id} registered"}
                
        return response
        
    async def _handle_timing_request(self, message: Dict[str, Any]) -> None:
        """Handle timing request message.
        
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
                self.logger.warning("Timing request missing source")
                return
                
            # Process request
            response = await self.handle_command(command, payload)
            
            # Send response
            await self.communication.publish(f"timing.response.{source}", response)
        except Exception as e:
            self.logger.error(f"Error handling timing request: {e}")
            
    async def _handle_credit_consumed(self, message: Dict[str, Any]) -> None:
        """Handle credit consumed message.
        
        Args:
            message: Message dictionary
        """
        try:
            credit_id = message.get("credit_id")
            consumer_id = message.get("consumer_id")
            
            if not credit_id:
                self.logger.warning("Credit consumed message missing credit_id")
                return
                
            self.logger.debug(f"Credit {credit_id} consumed by {consumer_id}")
            
            async with self._schedule_lock:
                if credit_id in self._pending_credits:
                    self._pending_credits.remove(credit_id)
                    self._consumed_credits.add(credit_id)
        except Exception as e:
            self.logger.error(f"Error handling credit consumed message: {e}")
    
    async def start_timing(self) -> bool:
        """Start issuing timing credits.
        
        Returns:
            True if timing started successfully, False otherwise
        """
        if self._running:
            self.logger.warning("Timing already running")
            return True
            
        try:
            self._running = True
            self._start_time = time.time()
            
            # Start background task for issuing credits
            self._timer_task = asyncio.create_task(self._issue_credits())
            
            # Announce timing start
            if self.communication:
                await self.communication.publish("timing.events", {
                    "event": "timing_started",
                    "timestamp": self._start_time,
                    "manager_id": self.component_id
                })
                
            self.logger.info("Timing started")
            return True
        except Exception as e:
            self.logger.error(f"Error starting timing: {e}")
            self._running = False
            return False
    
    async def stop_timing(self) -> bool:
        """Stop issuing timing credits.
        
        Returns:
            True if timing stopped successfully, False otherwise
        """
        if not self._running:
            self.logger.warning("Timing not running")
            return True
            
        try:
            self._running = False
            self._stop_time = time.time()
            
            # Cancel timer task
            if self._timer_task and not self._timer_task.done():
                self._timer_task.cancel()
                try:
                    await self._timer_task
                except asyncio.CancelledError:
                    pass
                    
            # Announce timing stop
            if self.communication:
                await self.communication.publish("timing.events", {
                    "event": "timing_stopped",
                    "timestamp": self._stop_time,
                    "manager_id": self.component_id,
                    "stats": await self.get_timing_stats()
                })
                
            self.logger.info("Timing stopped")
            return True
        except Exception as e:
            self.logger.error(f"Error stopping timing: {e}")
            return False
    
    async def _issue_credits(self) -> None:
        """Background task for issuing timing credits."""
        try:
            self.logger.info("Starting credit issuer task")
            
            # Sort schedule by target timestamp
            async with self._schedule_lock:
                sorted_schedule = sorted(self._schedule, key=lambda c: c.target_timestamp)
                
            for credit in sorted_schedule:
                if not self._running:
                    break
                    
                # Skip already consumed credits
                if credit.credit_id not in self._pending_credits:
                    continue
                    
                # Calculate time to wait
                now = time.time()
                wait_time = max(0, credit.target_timestamp - now)
                
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    
                if not self._running:
                    break
                    
                # Issue credit
                await self._issue_credit(credit)
                
            self.logger.info("Credit issuer task completed")
            
            # If all credits have been issued, stop timing
            if self._running:
                await self.stop_timing()
                
        except asyncio.CancelledError:
            self.logger.info("Credit issuer task cancelled")
        except Exception as e:
            self.logger.error(f"Error in credit issuer task: {e}")
            
    async def _issue_credit(self, credit: TimingCredit) -> None:
        """Issue a timing credit.
        
        Args:
            credit: Timing credit to issue
        """
        # Call registered consumers
        for consumer in self._credit_consumers:
            try:
                consumer(credit)
            except Exception as e:
                self.logger.error(f"Error calling credit consumer: {e}")
                
        # Publish credit if communication is available
        if self.communication:
            try:
                await self.communication.publish("timing.credit", {
                    "credit": credit.__dict__,
                    "manager_id": self.component_id
                })
            except Exception as e:
                self.logger.error(f"Error publishing credit: {e}")
    
    async def register_credit_consumer(self, consumer: Callable[[TimingCredit], None]) -> bool:
        """Register a consumer for timing credits.
        
        Args:
            consumer: Function to call when a credit is issued
            
        Returns:
            True if registration was successful, False otherwise
        """
        try:
            self._credit_consumers.append(consumer)
            self.logger.info(f"Registered credit consumer")
            return True
        except Exception as e:
            self.logger.error(f"Error registering credit consumer: {e}")
            return False
    
    async def get_next_credit(self) -> Optional[TimingCredit]:
        """Get the next timing credit.
        
        Returns:
            TimingCredit object or None if no more credits
        """
        try:
            async with self._schedule_lock:
                # Find the next pending credit
                pending_credits = [c for c in self._schedule if c.credit_id in self._pending_credits]
                if not pending_credits:
                    return None
                    
                # Sort by target timestamp
                sorted_credits = sorted(pending_credits, key=lambda c: c.target_timestamp)
                return sorted_credits[0]
        except Exception as e:
            self.logger.error(f"Error getting next credit: {e}")
            return None
    
    async def get_timing_stats(self) -> Dict[str, Any]:
        """Get timing statistics.
        
        Returns:
            Dictionary with timing statistics
        """
        try:
            now = time.time()
            
            stats = {
                "schedule_type": self.timing_config.schedule_type,
                "total_credits": len(self._schedule),
                "pending_credits": len(self._pending_credits),
                "consumed_credits": len(self._consumed_credits),
                "is_running": self._running,
                "elapsed_time": 0
            }
            
            if self._start_time:
                end_time = self._stop_time if self._stop_time else now
                stats["start_time"] = self._start_time
                stats["elapsed_time"] = end_time - self._start_time
                stats["credits_per_second"] = stats["consumed_credits"] / max(0.001, stats["elapsed_time"])
                
            return stats
        except Exception as e:
            self.logger.error(f"Error getting timing stats: {e}")
            return {"error": str(e)}
