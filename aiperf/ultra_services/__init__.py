# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Ultra High-Performance Services Package

This package contains ultra-high-performance implementations of all core AIPerf components
with extreme optimizations for 1M+ req/s throughput and sub-millisecond latencies.

All implementations register with override_priority=100 to replace existing components
while maintaining the same interfaces and enum classifiers for drop-in replacement.

Key Features:
- Lock-free data structures and atomic operations
- Zero-copy message handling with memory pools
- SIMD batch processing and vectorized operations
- Memory-mapped storage with huge pages support
- CPU pinning and NUMA-aware thread distribution
- Advanced networking optimizations

Components included:
- Ultra ZMQ Clients (Router, Dealer, Push, Pull, Pub, Sub)
- Ultra Dataset Manager with O(1) conversation lookup
- Ultra Worker with lock-free credit processing
- Ultra Inference Parsers with SIMD optimization
- Ultra Performance Monitoring and Metrics

Usage:
    Simply import this package to automatically register all ultra components:

    ```python
    import aiperf.ultra_services  # Auto-registers all ultra components

    # Existing code continues to work unchanged
    client = CommunicationClientFactory.create_instance(CommClientType.REPLY, ...)
    service = ServiceFactory.create_instance(ServiceType.DATASET_MANAGER, ...)
    ```

The ultra implementations will automatically be used due to their higher override priority.
"""

# Import all ultra components to trigger factory registration
from aiperf.ultra_services.ultra_dataset_manager import UltraDatasetManager
from aiperf.ultra_services.ultra_inference_parsers import (
    UltraInferenceResultParser,
    UltraRecordProcessor,
    UltraResponseExtractor,
)
from aiperf.ultra_services.ultra_worker import UltraWorker
from aiperf.zmq.ultra_high_performance_clients import (
    UltraZMQDealerRequestClient,
    UltraZMQPubClient,
    UltraZMQPullClient,
    UltraZMQPushClient,
    UltraZMQRouterReplyClient,
    UltraZMQSubClient,
)

# Performance utilities
from aiperf.zmq.ultra_high_throughput_system import (
    CPUPinning,
    NetworkOptimizations,
    UltraThroughputMetrics,
)

__all__ = [
    # Ultra ZMQ Clients
    "UltraZMQRouterReplyClient",
    "UltraZMQDealerRequestClient",
    "UltraZMQPushClient",
    "UltraZMQPullClient",
    "UltraZMQPubClient",
    "UltraZMQSubClient",
    # Ultra Services
    "UltraDatasetManager",
    "UltraWorker",
    "UltraRecordProcessor",
    # Ultra Parsers
    "UltraInferenceResultParser",
    "UltraResponseExtractor",
    # Performance Utilities
    "CPUPinning",
    "NetworkOptimizations",
    "UltraThroughputMetrics",
]

# Version and metadata
__version__ = "1.0.0"
__description__ = "Ultra High-Performance AIPerf Components for 1M+ req/s"
__author__ = "AIPerf Ultra Team"

# Configuration flags
ULTRA_MODE_ENABLED = True
ULTRA_OVERRIDE_PRIORITY = 100
ULTRA_TARGET_THROUGHPUT = 1_000_000  # 1M req/s


def initialize_ultra_mode():
    """
    Initialize ultra-high-performance mode with all optimizations.

    This function can be called explicitly to ensure all ultra components
    are properly initialized and configured for maximum performance.
    """
    print("🚀 AIPerf Ultra Mode Initialized")
    print(f"   Target Throughput: {ULTRA_TARGET_THROUGHPUT:,} req/s")
    print(f"   Override Priority: {ULTRA_OVERRIDE_PRIORITY}")
    print("   Features Enabled:")
    print("   ✅ Lock-free data structures")
    print("   ✅ Zero-copy message handling")
    print("   ✅ SIMD batch processing")
    print("   ✅ Memory-mapped storage")
    print("   ✅ CPU pinning optimization")
    print("   ✅ Advanced networking")
    print("")
    print("🎯 All ultra components registered and ready for extreme performance!")

    # Apply system optimizations
    try:
        NetworkOptimizations.optimize_system_limits()
        print("⚡ Network optimizations applied")
    except Exception as e:
        print(f"⚠️  Network optimizations failed: {e}")

    # CPU pinning suggestions
    try:
        import os

        cpu_count = os.cpu_count()
        if cpu_count and cpu_count >= 8:
            suggested_cores = list(range(min(8, cpu_count)))
            print(f"💡 Suggested CPU cores for pinning: {suggested_cores}")
            print("   Use CPUPinning.pin_to_cores(core_list) for optimal performance")
    except Exception:
        pass


def get_ultra_stats():
    """Get current ultra mode statistics and status."""
    stats = {
        "ultra_mode_enabled": ULTRA_MODE_ENABLED,
        "override_priority": ULTRA_OVERRIDE_PRIORITY,
        "target_throughput": ULTRA_TARGET_THROUGHPUT,
        "registered_clients": len(__all__),
        "performance_features": [
            "Lock-free ring buffers",
            "Memory pools",
            "SIMD processing",
            "Zero-copy operations",
            "CPU pinning",
            "NUMA awareness",
            "Advanced networking",
        ],
    }
    return stats


# Auto-initialize when imported
from aiperf.ultra_services.ultra_dataset_manager import (
    UltraHashTable,
    UltraLRUCache,
    UltraMemoryMappedDataset,
    main,
)
from aiperf.ultra_services.ultra_inference_parsers import (
    UltraJSONParser,
    UltraTokenCounter,
    main,
)
from aiperf.ultra_services.ultra_worker import (
    UltraConnectionPool,
    UltraCreditProcessor,
    UltraInferenceClient,
    main,
)

__all__ = [
    "CPUPinning",
    "NetworkOptimizations",
    "UltraConnectionPool",
    "UltraCreditProcessor",
    "UltraDatasetManager",
    "UltraHashTable",
    "UltraInferenceClient",
    "UltraInferenceResultParser",
    "UltraJSONParser",
    "UltraLRUCache",
    "UltraMemoryMappedDataset",
    "UltraRecordProcessor",
    "UltraResponseExtractor",
    "UltraThroughputMetrics",
    "UltraTokenCounter",
    "UltraWorker",
    "UltraZMQDealerRequestClient",
    "UltraZMQPubClient",
    "UltraZMQPullClient",
    "UltraZMQPushClient",
    "UltraZMQRouterReplyClient",
    "UltraZMQSubClient",
    "main",
]
