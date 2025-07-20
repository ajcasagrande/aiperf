<!--
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
-->

# 🚨 DEPRECATED FILES - Use Ultimate AIPerf Lifecycle Instead

The following files in this directory have been **SUPERSEDED** by the new **Ultimate AIPerf Lifecycle** system. They are kept for backward compatibility but should not be used for new development.

## 🎯 NEW SYSTEM: Use This Instead

```python
from aiperf.lifecycle import AIPerfService, message_handler, command_handler, background_task
from aiperf.common.enums import MessageType, CommandType, ServiceType

class MyService(AIPerfService):
    def __init__(self, service_config):
        super().__init__(
            service_id="my_service",
            service_type=ServiceType.DATASET_MANAGER,
            service_config=service_config
        )

    async def initialize(self):
        await super().initialize()  # ONE class handles everything!
        # Your business logic here

    @message_handler(MessageType.STATUS)
    async def handle_status(self, message: Message):
        # Real aiperf types with full type safety!
        pass
```

**👉 See [ULTIMATE_README.md](./ULTIMATE_README.md) for the complete new system documentation.**

## 📄 Deprecated Files

### ❌ `base.py` - SUPERSEDED
- **Old**: Complex `LifecycleService` with manual lifecycle management
- **New**: Use `AIPerfService` from `core.py` - handles everything automatically

### ❌ `service.py` - SUPERSEDED
- **Old**: `ManagedLifecycleService` with complex messaging integration
- **New**: Use `AIPerfService` from `core.py` - much simpler and more powerful

### ❌ `components.py` - SUPERSEDED
- **Old**: Complex component hierarchy (`Service`, `LifecycleWithMessaging`, etc.)
- **New**: Use `AIPerfService` from `core.py` - ONE class does everything

### ❌ `tasks.py` - SUPERSEDED
- **Old**: Manual `TaskManager` for background tasks
- **New**: Use `@background_task` decorator with `AIPerfService` - automatic management

### ❌ `messaging.py` (old version) - SUPERSEDED
- **Old**: Simple in-memory messaging with custom types
- **New**: Real ZMQ messaging with actual aiperf types in new `messaging.py`

### ❌ `examples.py` - SUPERSEDED
- **Old**: Examples using complex old system
- **New**: See `ultimate_demo.py` for examples using the new simple system

### ❌ `test_demo.py` - SUPERSEDED
- **Old**: Demo using old complex patterns
- **New**: See `ultimate_demo.py` for the new simple approach

### ❌ Legacy Plugin Files - SUPERSEDED
- `messaging_legacy.py` - Use new `messaging.py` instead
- `messaging_legacy_demo.py` - Use `ultimate_demo.py` instead
- `messaging_legacy_plugin_demo.py` - Use `ultimate_demo.py` instead
- `legacy_plugin_base.py` - Use `AIPerfService` from `core.py` instead
- All legacy README files - Use `ULTIMATE_README.md` instead

## 🔄 Migration Guide

### Instead of Old Complex Approach:
```python
@supports_hooks(AIPerfHook.initialize, AIPerfHook.start)
class OldService(BaseService, AIPerfMessagePubSubMixin, CommandMessageHandlerMixin):
    def __init__(self, service_config, **kwargs):
        super().__init__(service_config=service_config, **kwargs)

    @on_init
    async def _initialize(self):
        # Complex initialization
        pass

    @on_message(MessageType.STATUS)
    async def _handle_status(self, message):
        # Complex message handling
        pass
```

### Use New Simple Approach:
```python
class NewService(AIPerfService):
    def __init__(self, service_config, **kwargs):
        super().__init__(
            service_id="my_service",
            service_type=ServiceType.DATASET_MANAGER,
            service_config=service_config,
            **kwargs
        )

    async def initialize(self):
        await super().initialize()  # Handles everything!
        # Your business logic here

    @message_handler(MessageType.STATUS)
    async def handle_status(self, message: Message):
        # Clean, type-safe handling
        pass
```

## 🚀 Benefits of New System

- **90% less code** - Dramatically simpler
- **Real aiperf types** - Full type safety and compatibility
- **Standard inheritance** - Clean `super()` calls
- **Zero complexity** - Automatic infrastructure management
- **Better debugging** - Clear execution paths
- **Future-proof** - Built on real aiperf foundations

## ⚠️ Backward Compatibility

These deprecated files are kept for backward compatibility. However:

1. **No new features** will be added to deprecated files
2. **Bug fixes** will be minimal and only for critical issues
3. **Documentation** will focus on the new system
4. **Examples and demos** will use the new system

## 📅 Deprecation Timeline

- **Phase 1** (Current): Deprecated files remain, new system available
- **Phase 2** (Future): Deprecated files marked with warnings
- **Phase 3** (Future): Deprecated files moved to `legacy/` subdirectory
- **Phase 4** (Future): Deprecated files removed entirely

## 🎯 Recommendation

**Start using the new Ultimate AIPerf Lifecycle system immediately!**

- New projects: Use `AIPerfService` from `core.py`
- Existing projects: Migrate incrementally using the migration guide
- All development: Follow patterns in `ultimate_demo.py`

The new system is not just better - it's **transformative** for AIPerf service development!

👉 **Get started: [ULTIMATE_README.md](./ULTIMATE_README.md)**
