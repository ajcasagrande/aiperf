# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


class BaseMixin:
    """Base mixin class.

    This Mixin creates a contract that Mixins should always pass **kwargs to
    super().__init__, regardless of whether they extend another mixin or not.
    This base mixin will then determine whether to call super().__init__ or not
    depending on if we are at the end of the MRO.
    """

    def __init__(self, **kwargs):
        # object.__init__ does not take any arguments
        super().__init__()
