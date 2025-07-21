# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
AIPerf Core - Amazing Mixin Architecture with Plugin System

This module provides the core building blocks for AIPerf services:

Core Mixins:
- LifecycleMixin: State management and lifecycle hooks
- MessageBusMixin: Message handling with inheritance support
- BackgroundTasksMixin: Background task management
- CommunicationMixin: Real aiperf communication infrastructure

Plugin System:
- BasePlugin: Plugin base class using all mixins
- PluginManagerMixin: Auto-loading and lifecycle management
- PluginMetadata: Plugin information and dependencies

Base Classes:
- BaseService: Complete service with all mixins

All built on your amazing mixin architecture for maximum flexibility!
"""

# Core mixins - the foundation of everything
from .background_tasks import BackgroundTasksMixin

# Complete base service
from .base_service import BaseService
from .communication_mixins import CommunicationMixin, MessageBusMixin

# Decorators for dynamic behavior
from .decorators import (
    background_task,
    command_handler,
    command_types,
    message_handler,
    # Legacy aliases
    message_types,
    periodic_task,
)
from .lifecycle import LifecycleMixin, LifecycleState

# Plugin system - built on the amazing mixins
from .plugins import (
    BasePlugin,
    PluginError,
    PluginInitError,
    PluginInstance,
    PluginLoadError,
    PluginManagerMixin,
    PluginMetadata,
)

# Profile and service lifecycle
from .profile_lifecycle import ProfileLifecycle

__all__ = [
    # Core mixins
    "LifecycleMixin",
    "LifecycleState",
    "CommunicationMixin",
    "MessageBusMixin",
    "BackgroundTasksMixin",
    "ProfileLifecycle",
    # Base service
    "BaseService",
    # Plugin system
    "BasePlugin",
    "PluginManagerMixin",
    "PluginMetadata",
    "PluginInstance",
    "PluginError",
    "PluginLoadError",
    "PluginInitError",
    # Decorators
    "message_handler",
    "command_handler",
    "background_task",
    "message_types",
    "command_types",
    "periodic_task",
]
