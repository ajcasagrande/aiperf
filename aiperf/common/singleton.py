# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import threading

from typing_extensions import Self


class BaseSingleton:
    """
    Thread-safe base class for all singletons.

    This class is used to create a thread-safe singleton pattern for a class.

    Example:
    ```python
    class MySingleton(BaseSingleton):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if not self._initialized:
                # do initialization here
                self._initialized = True
    ```
    """

    _initialized = False
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs) -> Self:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
