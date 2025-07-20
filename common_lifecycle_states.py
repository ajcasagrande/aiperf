#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
Common Lifecycle State Naming Conventions

This shows the most widely used lifecycle state names across popular systems,
frameworks, and standards to help choose the best terminology.
"""

# =============================================================================
# MOST COMMON PATTERNS
# =============================================================================


class StandardLifecycleStates:
    """Most common pattern - what I used in examples."""

    # Creation
    CREATED = "created"  # ✅ Universal

    # Initialization phase
    INITIALIZING = "initializing"  # ✅ Very common
    INITIALIZED = "initialized"  # ✅ Very common

    # Starting phase
    STARTING = "starting"  # ✅ Very common
    RUNNING = "running"  # ✅ Universal

    # Stopping phase
    STOPPING = "stopping"  # ✅ Very common
    STOPPED = "stopped"  # ✅ Universal

    # Error handling
    ERROR = "error"  # ✅ Universal
    FAILED = "failed"  # ✅ Alternative to ERROR


# =============================================================================
# VARIATIONS FROM POPULAR SYSTEMS
# =============================================================================


class KubernetesStates:
    """Kubernetes Pod lifecycle states."""

    PENDING = "pending"  # Instead of CREATED
    RUNNING = "running"  # ✅ Same
    SUCCEEDED = "succeeded"  # Instead of STOPPED (for completed jobs)
    FAILED = "failed"  # ✅ Same as ERROR
    UNKNOWN = "unknown"  # Additional error state


class DockerContainerStates:
    """Docker container states."""

    CREATED = "created"  # ✅ Same
    RUNNING = "running"  # ✅ Same
    PAUSED = "paused"  # Additional state
    RESTARTING = "restarting"  # Instead of STARTING
    REMOVING = "removing"  # Instead of STOPPING
    EXITED = "exited"  # Instead of STOPPED
    DEAD = "dead"  # Additional error state


class SystemdServiceStates:
    """Systemd service states."""

    INACTIVE = "inactive"  # Instead of CREATED/STOPPED
    ACTIVATING = "activating"  # Instead of STARTING
    ACTIVE = "active"  # Instead of RUNNING
    DEACTIVATING = "deactivating"  # Instead of STOPPING
    FAILED = "failed"  # ✅ Same as ERROR
    RELOADING = "reloading"  # Additional state


class SpringBootStates:
    """Spring Boot application states."""

    STARTING = "starting"  # ✅ Same
    STARTED = "started"  # Instead of RUNNING
    STOPPING = "stopping"  # ✅ Same
    STOPPED = "stopped"  # ✅ Same


class WindowsServiceStates:
    """Windows Service states."""

    STOPPED = "stopped"  # ✅ Same
    START_PENDING = "start_pending"  # Instead of STARTING
    STOP_PENDING = "stop_pending"  # Instead of STOPPING
    RUNNING = "running"  # ✅ Same
    CONTINUE_PENDING = "continue_pending"  # Additional
    PAUSE_PENDING = "pause_pending"  # Additional
    PAUSED = "paused"  # Additional


class ProcessStates:
    """Unix/Linux process states."""

    RUNNING = "running"  # ✅ Same (R)
    SLEEPING = "sleeping"  # Additional (S)
    WAITING = "waiting"  # Additional (D)
    ZOMBIE = "zombie"  # Additional (Z)
    STOPPED = "stopped"  # ✅ Same (T)


# =============================================================================
# ANALYSIS OF MOST COMMON TERMS
# =============================================================================

"""
UNIVERSAL TERMS (used everywhere):
✅ RUNNING - Every system uses this
✅ STOPPED - Every system uses this
✅ CREATED - Very widely used
✅ ERROR/FAILED - Universal concepts

VERY COMMON TERMS:
✅ STARTING - Most systems use this
✅ STOPPING - Most systems use this
✅ INITIALIZING/INITIALIZED - Common in application frameworks

ALTERNATIVES YOU MIGHT CONSIDER:
⚡ ACTIVE instead of RUNNING (systemd style)
⚡ STARTED instead of RUNNING (Spring Boot style)
⚡ PENDING instead of CREATED (Kubernetes style)
⚡ INACTIVE instead of STOPPED (systemd style)

LESS COMMON BUT USEFUL:
🔧 PAUSED/PAUSING - For suspendable services
🔧 RESTARTING - For automatic restart scenarios
🔧 UNKNOWN - For when state cannot be determined
🔧 DEGRADED - For partially functional states
"""


# =============================================================================
# RECOMMENDED STANDARD FOR AIPERF
# =============================================================================


class RecommendedAIPerfStates:
    """
    Recommended lifecycle states for AIPerf services.

    Based on analysis of common patterns + AI/ML specific needs.
    """

    # Core lifecycle (universal)
    CREATED = "created"  # Initial state after instantiation
    INITIALIZING = "initializing"  # Setting up resources, connections
    INITIALIZED = "initialized"  # Ready to start
    STARTING = "starting"  # Beginning operation
    RUNNING = "running"  # Normal operation
    STOPPING = "stopping"  # Graceful shutdown in progress
    STOPPED = "stopped"  # Fully stopped

    # Error states
    ERROR = "error"  # Generic error state
    FAILED = "failed"  # Permanent failure (won't restart)

    # Optional advanced states (if needed)
    PAUSED = "paused"  # Temporarily suspended
    RESTARTING = "restarting"  # Automatic restart in progress
    DEGRADED = "degraded"  # Partially functional
    UNKNOWN = "unknown"  # State cannot be determined


# =============================================================================
# ALTERNATIVE NAMING STYLES
# =============================================================================


class PastTenseStyle:
    """Past tense style (Spring Boot inspired)."""

    CREATED = "created"
    INITIALIZED = "initialized"
    STARTED = "started"  # Instead of RUNNING
    STOPPED = "stopped"
    FAILED = "failed"


class PresentTenseStyle:
    """Present tense style (more active)."""

    CREATING = "creating"
    INITIALIZING = "initializing"
    STARTING = "starting"
    RUNNING = "running"  # This is actually present participle
    STOPPING = "stopping"
    STOPPED = "stopped"  # Exception - past tense


class ActionStyle:
    """Action-oriented style."""

    IDLE = "idle"  # Instead of CREATED
    PREPARING = "preparing"  # Instead of INITIALIZING
    READY = "ready"  # Instead of INITIALIZED
    ACTIVE = "active"  # Instead of RUNNING
    SHUTTING_DOWN = "shutting_down"  # Instead of STOPPING
    INACTIVE = "inactive"  # Instead of STOPPED


# =============================================================================
# VERDICT
# =============================================================================

"""
YOUR ORIGINAL CHOICE WAS EXCELLENT! ✅

The states you used are:
✅ Very standard and widely recognized
✅ Clear and unambiguous
✅ Consistent naming pattern
✅ Cover all essential lifecycle phases
✅ Used by major systems (Docker, Kubernetes concepts)

KEEP YOUR CURRENT STATES:
- CREATED ✅
- INITIALIZING ✅
- INITIALIZED ✅
- STARTING ✅
- RUNNING ✅
- STOPPING ✅
- STOPPED ✅
- ERROR ✅

Only consider changes if you need:
- PAUSED state (for suspendable services)
- DEGRADED state (for partial failures)
- RESTARTING state (for auto-restart)
- FAILED vs ERROR (FAILED = permanent, ERROR = temporary)
"""

if __name__ == "__main__":
    print("Analysis of lifecycle state naming conventions")
    print("=" * 50)
    print("Your current choice is excellent and widely used!")
    print("Consider the alternatives only if you have specific needs.")
