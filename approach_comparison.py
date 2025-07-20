#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
Comparison of Inheritance + Wrapping Patterns

This file compares the different approaches for combining inheritance
with automatic method wrapping (like lifecycle state management).
"""

# =============================================================================
# APPROACH COMPARISON
# =============================================================================

"""
1. TEMPLATE METHOD PATTERN (Recommended for most cases)
   ====================================================

      Pros:
   ✅ Clear separation of framework vs business logic
   ✅ Framework behavior guaranteed (state management automatic)
   ✅ Main methods (initialize/start/stop) don't need super() calls
   ✅ Easy to understand and debug
   ✅ Standard OOP pattern
   ✅ Great for consistent workflows
   ✅ Type-safe and IDE-friendly

   Cons:
   ❌ Requires separate hook methods (_initialize_impl, etc.)
   ❌ Still need super() calls in hook methods for multiple inheritance
   ❌ Slightly more verbose API
   ❌ Less flexible for complex wrapping scenarios

   Best for:
   - Lifecycle management (initialization, start, stop)
   - Transaction management
   - Consistent workflows with pre/post processing
   - When you want to guarantee framework behavior happens

   Example:
   ```python
   class MyService(BaseService):
       async def _initialize_impl(self):  # Hook method
           await super()._initialize_impl()  # Still need super() for multiple inheritance!
           # Business logic here
           pass
   ```

2. DECORATOR-BASED APPROACH
   ==========================

   Pros:
   ✅ Flexible - can wrap any method
   ✅ Reusable decorators
   ✅ Can compose multiple decorators
   ✅ Explicit about what's being wrapped
   ✅ Good for complex wrapping logic

   Cons:
   ❌ Must remember to apply decorators
   ❌ Can be overridden/forgotten in subclasses
   ❌ More complex setup
   ❌ Decorator syntax can be verbose

   Best for:
   - Complex wrapping behavior
   - When you need multiple types of wrapping
   - Reusable cross-cutting concerns
   - When template method is too rigid

   Example:
   ```python
   class MyService(BaseService):
       @lifecycle_method(from_state=CREATED, to_state=INITIALIZED)
       async def initialize(self):  # Explicitly decorated
           # Business logic here
           pass
   ```

3. METACLASS/__init_subclass__ APPROACH
   ======================================

   Pros:
   ✅ Completely automatic - no decorators needed
   ✅ Impossible to forget
   ✅ Clean subclass code
   ✅ Very DRY (Don't Repeat Yourself)
   ✅ Can handle complex scenarios

   Cons:
   ❌ More complex to understand and debug
   ❌ "Magic" behavior can be confusing
   ❌ Harder to customize per method
   ❌ More advanced Python concept
   ❌ Can interfere with other metaclass usage

   Best for:
   - When you want completely transparent wrapping
   - Large codebases with many similar classes
   - When consistency is critical
   - Advanced users comfortable with metaclasses

   Example:
   ```python
   class MyService(BaseService):  # Automatic wrapping!
       async def initialize(self):  # No decorators needed
           # Business logic here
           pass
   ```

4. SUPER() CALL PATTERN (What you had originally)
   ================================================

   Pros:
   ✅ Standard Python inheritance pattern
   ✅ Familiar to most developers
   ✅ Simple to implement
   ✅ Flexible

   Cons:
   ❌ Easy to forget super() calls
   ❌ Order of operations matters
   ❌ Can lead to bugs if super() is missed
   ❌ Framework behavior not guaranteed

   Best for:
   - Simple inheritance scenarios
   - When flexibility is more important than safety
   - Small teams with good code review

   Example:
   ```python
   class MyService(BaseService):
       async def initialize(self):
           await super().initialize()  # Easy to forget!
           # Business logic here
   ```
"""

# =============================================================================
# DECISION MATRIX
# =============================================================================

"""
WHEN TO USE WHICH APPROACH:

Template Method Pattern:
- ✅ Lifecycle management (init/start/stop)
- ✅ Database transaction wrapping
- ✅ Request/response processing
- ✅ Resource management patterns
- ✅ When consistency is critical

Decorator Approach:
- ✅ Cross-cutting concerns (logging, metrics, auth)
- ✅ Method-specific behavior
- ✅ When you need multiple wrappers
- ✅ Reusable functionality across classes

Metaclass/__init_subclass__:
- ✅ Framework development
- ✅ When you have many similar classes
- ✅ DSL-like APIs
- ✅ When transparency is key

Super() Call Pattern:
- ✅ Simple extension scenarios
- ✅ When you trust your team's discipline
- ✅ Quick prototypes
- ✅ When you need maximum flexibility
"""

# =============================================================================
# HYBRID APPROACHES
# =============================================================================

"""
You can also combine approaches! For example:

1. Template Method + Decorators:
   - Use template method for core lifecycle
   - Use decorators for additional cross-cutting concerns

2. Metaclass + Template Method:
   - Use metaclass to automatically create template methods
   - Use template method pattern for the actual implementation

3. Conditional Wrapping:
   - Use different approaches based on method names or attributes
"""


class HybridExample:
    """Example combining template method with decorators."""

    # Template method for lifecycle
    async def initialize(self):
        await self._pre_initialize()
        await self._initialize_impl()  # Hook for subclasses
        await self._post_initialize()

    # But allow additional decorators for cross-cutting concerns
    @measure_performance
    @log_calls
    async def process_data(self, data):
        # This gets both performance monitoring AND call logging
        return await self._process_data_impl(data)


# =============================================================================
# RECOMMENDATION
# =============================================================================

"""
FOR YOUR AIPERF LIFECYCLE USE CASE:

I recommend the TEMPLATE METHOD PATTERN because:

1. Lifecycle management is a perfect fit for template method
2. You want to guarantee state transitions happen
3. It's easier to understand and maintain
4. It's less "magical" than metaclass approaches
5. It provides clear extension points for subclasses
6. It's harder to make mistakes

The pattern would look like:

class AIPerfService:
    async def initialize(self):
        # Framework handles state transitions
        if self._state != LifecycleState.CREATED:
            raise ValueError(...)

        self._state = LifecycleState.INITIALIZING
        try:
            await self._initialize_impl()  # Subclass hook
            self._state = LifecycleState.INITIALIZED
        except Exception:
            self._state = LifecycleState.ERROR
            raise

    async def _initialize_impl(self):
        # Override this in subclasses
        pass

 class MyService(AIPerfService):
     async def _initialize_impl(self):
         await super()._initialize_impl()  # Still needed for multiple inheritance!
         # Business logic - state management is automatic!
         self.db = await connect_database()
"""

if __name__ == "__main__":
    print("See the comments above for detailed comparison of approaches!")
    print("\nFor lifecycle management, Template Method Pattern is recommended.")
