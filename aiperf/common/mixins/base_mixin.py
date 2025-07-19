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
        super().__init__()
        # if len(self.__class__.__bases__) > 0:
        #     print(f"BaseMixin __init__ {self.__class__.__name__}, {self.__class__.__bases__}")
        #     # Keep calling super as long as we are not at the end of the MRO
        #     super().__init__(**kwargs)
        # else:
        #     print(f"BaseMixin __init__ {self.__class__.__name__}, did not call super: {self.__class__.__bases__}")
