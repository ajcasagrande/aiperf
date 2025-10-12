# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Simple token service for mock responses - no real tokenization."""

import re


class SimpleTokenService:
    """Minimal tokenizer that splits on word boundaries - preserves exact text when joined."""

    def tokenize(self, text: str, model_name: str = "") -> list[str]:
        """Split text into tokens (words, spaces, punctuation)."""
        return re.findall(r"\w+|\s+|[^\w\s]", text) if text else []

    def count_tokens(self, text: str, model_name: str = "") -> int:
        """Count tokens."""
        return len(self.tokenize(text))


tokenizer_service = SimpleTokenService()
