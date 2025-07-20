# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Comprehensive examples showing exactly how triggering mechanisms work
and how multiple instances can synchronize state.

This demonstrates:
1. How background tasks are triggered
2. How messages are triggered and routed
3. How multiple instances can coordinate state
4. Practical sync patterns
"""

import asyncio
import random
import time

from aiperf.lifecycle import (
    BackgroundTasks,
    Service,
    background_task,
    command_handler,
    message_handler,
)

# =============================================================================
# 1. Background Task Triggering Mechanisms
# =============================================================================


class TaskTriggerDemo(BackgroundTasks):
    """
    Demonstrates exactly how background tasks get triggered.

    Key Points:
    - Tasks are discovered via decorators during __init__
    - Tasks are STARTED when you call start_tasks()
    - Tasks run in their own asyncio.Task instances
    - Tasks are STOPPED when you call stop_tasks()
    """

    def __init__(self):
        super().__init__()
        self.counter = 0
        self.dynamic_interval = 1.0
        print("🔍 Constructor: Background tasks discovered via decorators")

    @background_task(interval=2.0)
    async def fixed_interval_task(self):
        """This runs every 2 seconds EXACTLY"""
        self.counter += 1
        print(f"⏰ Fixed task #{self.counter} - runs every 2.0 seconds")

    @background_task(interval=lambda self=None: self.dynamic_interval if self else 1.0)
    async def dynamic_interval_task(self):
        """This runs with a dynamic interval that can change"""
        self.dynamic_interval = random.uniform(0.5, 3.0)
        print(f"🎲 Dynamic task - next interval: {self.dynamic_interval:.1f}s")

    @background_task(run_once=True)
    async def one_time_task(self):
        """This runs ONCE when tasks start"""
        await asyncio.sleep(0.5)  # Simulate some work
        print("✅ One-time task completed")

    @background_task()  # No interval = continuous
    async def continuous_task(self):
        """This runs continuously with no delay"""
        await asyncio.sleep(0.1)  # Small delay to prevent CPU spinning
        print("🔄 Continuous task (add delay to prevent CPU spinning)")


async def demo_task_triggering():
    """Show exactly how task triggering works."""
    print("\n=== Background Task Triggering Demo ===")

    demo = TaskTriggerDemo()
    print("📋 Tasks discovered, but NOT running yet")

    # Tasks don't run until explicitly started
    await asyncio.sleep(1)
    print("⏸️  1 second passed - no tasks running")

    # NOW the tasks start
    print("🚀 Starting tasks...")
    await demo.start_tasks()

    # Let tasks run for a while
    print("⏳ Letting tasks run for 8 seconds...")
    await asyncio.sleep(8)

    # Stop the tasks
    print("🛑 Stopping tasks...")
    await demo.stop_tasks()
    print("✅ All tasks stopped")


# =============================================================================
# 2. Message Triggering Mechanisms
# =============================================================================


class MessageTriggerDemo(Service):
    """
    Demonstrates exactly how messages get triggered.

    Key Points:
    - Handlers are discovered via decorators during __init__
    - Message bus routes messages to handlers when published
    - Each handler is called independently
    - Message bus can broadcast OR target specific services
    """

    def __init__(self, service_id: str):
        super().__init__(component_id=service_id)
        self.received_messages = []

    async def start(self):
        await super().start()
        print(f"📡 {self.service_id} is listening for messages")

    @message_handler("BROADCAST_EVENT")
    async def handle_broadcast(self, message):
        """This triggers when ANYONE publishes BROADCAST_EVENT"""
        self.received_messages.append(message)
        print(f"📻 {self.service_id} received broadcast: {message.content}")

    @message_handler("USER_ACTION")
    async def handle_user_action(self, message):
        """This triggers when ANYONE publishes USER_ACTION"""
        action = message.content.get("action", "unknown")
        print(f"👤 {self.service_id} handling user action: {action}")

        # Send a response message
        await self.publish_message(
            "ACTION_PROCESSED",
            {"service": self.service_id, "action": action, "timestamp": time.time()},
        )

    @command_handler("GET_STATUS")
    async def get_status(self, command):
        """This triggers when someone sends GET_STATUS command TO THIS SERVICE"""
        return {
            "service_id": self.service_id,
            "messages_received": len(self.received_messages),
            "status": "active",
        }


async def demo_message_triggering():
    """Show exactly how message triggering works."""
    print("\n=== Message Triggering Demo ===")

    # Create multiple services
    service1 = MessageTriggerDemo("service_1")
    service2 = MessageTriggerDemo("service_2")
    service3 = MessageTriggerDemo("service_3")

    # Start all services
    for service in [service1, service2, service3]:
        await service.initialize()
        await service.start()

    print("\n📡 All services are now listening...")

    # 1. Broadcast message - ALL services will receive it
    print("\n1️⃣ Broadcasting message to ALL services:")
    await service1.publish_message("BROADCAST_EVENT", "Hello everyone!")
    await asyncio.sleep(0.1)  # Let messages process

    # 2. Targeted command - ONLY specific service receives it
    print("\n2️⃣ Sending targeted command to service_2:")
    response = await service1.send_command("GET_STATUS", "service_2")
    print(f"Response from service_2: {response}")

    # 3. Publish user action - ALL services handle it, but each responds
    print("\n3️⃣ Publishing user action (all services respond):")
    await service1.publish_message("USER_ACTION", {"action": "login", "user": "alice"})
    await asyncio.sleep(0.5)  # Let responses propagate

    # Stop all services
    for service in [service1, service2, service3]:
        await service.stop()


# =============================================================================
# 3. State Synchronization Between Multiple Instances
# =============================================================================


class SyncedCounterService(Service):
    """
    Multiple instances of this service synchronize their counter state.

    Synchronization Pattern:
    1. Each instance tracks its local counter
    2. When counter changes, broadcasts the change
    3. Other instances receive broadcast and update their state
    4. All instances stay in sync automatically
    """

    def __init__(self, instance_id: str):
        super().__init__(component_id=f"counter_{instance_id}")
        self.instance_id = instance_id
        self.local_counter = 0
        self.global_counter = 0  # Synced across all instances
        self.peer_counters: dict[str, int] = {}  # Track other instances

    async def start(self):
        await super().start()
        print(f"🔄 {self.instance_id} ready for sync")

        # Announce ourselves to other instances
        await self.publish_message(
            "INSTANCE_JOINED",
            {"instance_id": self.instance_id, "counter": self.local_counter},
        )

    @message_handler("COUNTER_UPDATE")
    async def handle_counter_update(self, message):
        """Sync counter updates from other instances"""
        sender = message.content["instance_id"]
        new_counter = message.content["counter"]

        if sender != self.instance_id:  # Don't sync with ourselves
            self.peer_counters[sender] = new_counter
            self.global_counter = max(
                self.local_counter, max(self.peer_counters.values(), default=0)
            )
            print(
                f"🔄 {self.instance_id} synced: local={self.local_counter}, global={self.global_counter}"
            )

    @message_handler("INSTANCE_JOINED")
    async def handle_instance_joined(self, message):
        """Handle new instance joining"""
        sender = message.content["instance_id"]
        counter = message.content["counter"]

        if sender != self.instance_id:
            self.peer_counters[sender] = counter
            print(f"👋 {self.instance_id} welcomes {sender}")

            # Send our current state to the new instance
            await self.publish_message(
                "COUNTER_UPDATE",
                {"instance_id": self.instance_id, "counter": self.local_counter},
            )

    async def increment_counter(self):
        """Increment counter and broadcast change"""
        self.local_counter += 1
        self.global_counter = max(self.local_counter, self.global_counter)

        print(f"➕ {self.instance_id} incremented to {self.local_counter}")

        # Broadcast the change to sync with other instances
        await self.publish_message(
            "COUNTER_UPDATE",
            {"instance_id": self.instance_id, "counter": self.local_counter},
        )

    @command_handler("GET_STATE")
    async def get_state(self, command):
        """Get current sync state"""
        return {
            "instance_id": self.instance_id,
            "local_counter": self.local_counter,
            "global_counter": self.global_counter,
            "peer_counters": self.peer_counters,
            "total_instances": len(self.peer_counters) + 1,
        }


class DistributedTaskCoordinator(Service):
    """
    Multiple instances coordinate to avoid duplicate work.

    Coordination Pattern:
    1. Instances announce what work they're doing
    2. Other instances avoid the same work
    3. If an instance fails, others can pick up the work
    """

    def __init__(self, instance_id: str):
        super().__init__(component_id=f"worker_{instance_id}")
        self.instance_id = instance_id
        self.active_workers: set[str] = set()
        self.current_task: str | None = None
        self.completed_tasks: set[str] = set()

    async def start(self):
        await super().start()
        print(f"⚡ Worker {self.instance_id} ready for coordination")

    @message_handler("WORKER_STATUS")
    async def handle_worker_status(self, message):
        """Track which workers are active on which tasks"""
        worker_id = message.content["worker_id"]
        task_id = message.content.get("task_id")
        status = message.content["status"]

        if worker_id != self.instance_id:
            if status == "started" and task_id:
                self.active_workers.add(f"{worker_id}:{task_id}")
                print(
                    f"📋 {self.instance_id} knows {worker_id} is working on {task_id}"
                )
            elif status == "completed" and task_id:
                self.active_workers.discard(f"{worker_id}:{task_id}")
                self.completed_tasks.add(task_id)
                print(
                    f"✅ {self.instance_id} knows {task_id} is completed by {worker_id}"
                )

    async def try_claim_task(self, task_id: str) -> bool:
        """Try to claim a task (only one worker should do each task)"""
        # Check if someone else is already working on it
        for active in self.active_workers:
            if task_id in active:
                print(f"⏭️  {self.instance_id} skipping {task_id} (already claimed)")
                return False

        # Check if it's already completed
        if task_id in self.completed_tasks:
            print(f"✅ {self.instance_id} skipping {task_id} (already completed)")
            return False

        # Claim the task
        self.current_task = task_id
        await self.publish_message(
            "WORKER_STATUS",
            {"worker_id": self.instance_id, "task_id": task_id, "status": "started"},
        )

        print(f"🎯 {self.instance_id} claimed task {task_id}")
        return True

    async def complete_task(self, task_id: str):
        """Mark a task as completed"""
        if self.current_task == task_id:
            self.current_task = None
            self.completed_tasks.add(task_id)

            await self.publish_message(
                "WORKER_STATUS",
                {
                    "worker_id": self.instance_id,
                    "task_id": task_id,
                    "status": "completed",
                },
            )

            print(f"🏁 {self.instance_id} completed task {task_id}")

    @background_task(interval=2.0)
    async def look_for_work(self):
        """Periodically look for work to do"""
        if self.current_task:
            return  # Already working

        # Generate a task ID to try
        task_id = f"task_{random.randint(1, 10)}"

        if await self.try_claim_task(task_id):
            # Simulate work
            work_time = random.uniform(1, 4)
            await asyncio.sleep(work_time)
            await self.complete_task(task_id)


async def demo_state_sync():
    """Show how multiple instances can synchronize state."""
    print("\n=== State Synchronization Demo ===")

    # Create multiple synced counter instances
    counter1 = SyncedCounterService("alpha")
    counter2 = SyncedCounterService("beta")
    counter3 = SyncedCounterService("gamma")

    counters = [counter1, counter2, counter3]

    # Start all instances
    for counter in counters:
        await counter.initialize()
        await counter.start()

    await asyncio.sleep(0.5)  # Let them discover each other

    print("\n🔢 Testing counter synchronization:")

    # Have different instances increment
    await counter1.increment_counter()  # alpha: 1
    await asyncio.sleep(0.2)

    await counter2.increment_counter()  # beta: 1
    await counter2.increment_counter()  # beta: 2
    await asyncio.sleep(0.2)

    await counter3.increment_counter()  # gamma: 1
    await asyncio.sleep(0.2)

    # Check sync state
    for counter in counters:
        state = await counter.send_command("GET_STATE", counter.service_id)
        print(
            f"📊 {state['instance_id']}: local={state['local_counter']}, "
            f"global={state['global_counter']}, peers={state['peer_counters']}"
        )

    # Stop counters
    for counter in counters:
        await counter.stop()

    print("\n⚡ Testing work coordination:")

    # Create coordinated workers
    worker1 = DistributedTaskCoordinator("alpha")
    worker2 = DistributedTaskCoordinator("beta")
    worker3 = DistributedTaskCoordinator("gamma")

    workers = [worker1, worker2, worker3]

    # Start all workers
    for worker in workers:
        await worker.initialize()
        await worker.start()

    # Let them coordinate work for a bit
    print("🔄 Workers coordinating for 10 seconds...")
    await asyncio.sleep(10)

    # Stop workers
    for worker in workers:
        await worker.stop()


# =============================================================================
# 4. Advanced Sync Patterns
# =============================================================================


class LeaderElectionService(Service):
    """
    Multiple instances elect a leader using messaging.

    Election Pattern:
    1. All instances announce candidacy
    2. Instance with lowest ID becomes leader
    3. Leader coordinates, others follow
    4. If leader fails, new election happens
    """

    def __init__(self, instance_id: str):
        super().__init__(component_id=f"node_{instance_id}")
        self.instance_id = instance_id
        self.is_leader = False
        self.known_nodes: set[str] = set()
        self.leader_id: str | None = None

    async def start(self):
        await super().start()

        # Start election process
        await self.publish_message(
            "ELECTION_CANDIDATE", {"candidate_id": self.instance_id}
        )

    @message_handler("ELECTION_CANDIDATE")
    async def handle_candidate(self, message):
        """Handle election candidates"""
        candidate_id = message.content["candidate_id"]
        self.known_nodes.add(candidate_id)

        # Check if we should be leader (lowest ID wins)
        potential_leader = min(self.known_nodes)

        if potential_leader != self.leader_id:
            self.leader_id = potential_leader
            self.is_leader = self.instance_id == potential_leader

            if self.is_leader:
                print(f"👑 {self.instance_id} became LEADER!")
                await self.publish_message(
                    "LEADER_ANNOUNCEMENT", {"leader_id": self.instance_id}
                )
            else:
                print(f"👥 {self.instance_id} following leader {self.leader_id}")

    @message_handler("LEADER_ANNOUNCEMENT")
    async def handle_leader_announcement(self, message):
        """Handle leader announcements"""
        announced_leader = message.content["leader_id"]
        self.leader_id = announced_leader
        self.is_leader = self.instance_id == announced_leader

    @background_task(interval=3.0)
    async def leader_heartbeat(self):
        """Leader sends periodic heartbeats"""
        if self.is_leader:
            await self.publish_message(
                "LEADER_HEARTBEAT",
                {"leader_id": self.instance_id, "timestamp": time.time()},
            )
            print(f"💓 Leader {self.instance_id} heartbeat")


async def demo_leader_election():
    """Show leader election pattern."""
    print("\n=== Leader Election Demo ===")

    # Create multiple nodes
    node1 = LeaderElectionService("charlie")  # Higher ID
    node2 = LeaderElectionService("alice")  # Lower ID - should be leader
    node3 = LeaderElectionService("bob")  # Middle ID

    nodes = [node1, node2, node3]

    # Start nodes at different times
    await node1.initialize()
    await node1.start()
    await asyncio.sleep(1)

    await node2.initialize()
    await node2.start()
    await asyncio.sleep(1)

    await node3.initialize()
    await node3.start()
    await asyncio.sleep(2)

    # Let election settle and see heartbeats
    await asyncio.sleep(8)

    # Check final states
    for node in nodes:
        status = "LEADER" if node.is_leader else f"FOLLOWER of {node.leader_id}"
        print(f"🗳️  {node.instance_id}: {status}")

    # Stop all nodes
    for node in nodes:
        await node.stop()


# =============================================================================
# Demo Runner
# =============================================================================


async def run_all_triggering_demos():
    """Run all triggering and synchronization demonstrations."""
    print("🚀 AIPerf Triggering & Synchronization Examples")
    print("=" * 60)

    await demo_task_triggering()
    await demo_message_triggering()
    await demo_state_sync()
    await demo_leader_election()

    print("\n" + "=" * 60)
    print("🎉 All triggering demos completed!")
    print("\n🎯 Key Takeaways:")
    print("   ✅ Background tasks: Triggered by start_tasks(), run in asyncio.Task")
    print("   ✅ Messages: Triggered by message bus when published")
    print("   ✅ State sync: Use publish/subscribe patterns")
    print("   ✅ Coordination: Use messaging for distributed coordination")
    print("   ✅ Each component is independent but can communicate")


if __name__ == "__main__":
    asyncio.run(run_all_triggering_demos())
