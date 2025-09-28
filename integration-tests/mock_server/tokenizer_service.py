# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tokenizer service for handling different model tokenizers."""

import logging
import random
from typing import Literal

from transformers import AutoTokenizer
from transformers.tokenization_utils import PreTrainedTokenizer

logger = logging.getLogger(__name__)


class TokenizerService:
    """Service for managing tokenizers for different models."""

    def __init__(self):
        self._tokenizers: dict[str, PreTrainedTokenizer] = {}
        self._fallback_tokenizer: str | None = None
        self._use_fake_dataset: bool = False
        self._fake_dataset_mode: Literal["random", "predefined"] = "random"
        self._predefined_tokens: list[str] = [
            "Hello",
            " there",
            "!",
            " How",
            " are",
            " you",
            " today",
            "?",
            " I",
            " am",
            " doing",
            " well",
            ",",
            " thank",
            " you",
            " for",
            " asking",
            ".",
            " The",
            " weather",
            " is",
            " nice",
            " and",
            " sunny",
            ".",
            " What",
            " would",
            " you",
            " like",
            " to",
            " talk",
            " about",
            "?",
            " I",
            " can",
            " help",
            " with",
            " many",
            " different",
            " topics",
            " and",
            " questions",
            ".",
            " Please",
            " let",
            " me",
            " know",
            " how",
            " I",
            " can",
            " assist",
            " you",
            " today",
            ".",
            " Have",
            " a",
            " great",
            " day",
            "!",
            " Thank",
            " you",
            " very",
            " much",
            ".",
        ]
        self._random_words: list[str] = [
            "the",
            "quick",
            "brown",
            "fox",
            "jumps",
            "over",
            "lazy",
            "dog",
            "hello",
            "world",
            "python",
            "code",
            "test",
            "data",
            "model",
            "token",
            "response",
            "request",
            "server",
            "client",
            "api",
            "endpoint",
            "service",
            "function",
            "method",
            "class",
            "object",
            "string",
            "number",
            "boolean",
            "array",
            "list",
            "dict",
            "json",
            "http",
            "https",
            "get",
            "post",
            "put",
            "delete",
            "patch",
            "status",
            "error",
            "success",
            "failure",
            "timeout",
            "retry",
        ]

    def load_tokenizers(self, model_names: list[str]) -> None:
        """Pre-load tokenizers for one or more models.

        Args:
            model_names: List of model names to load tokenizers for
        """
        for model_name in model_names:
            try:
                logger.info(f"Pre-loading tokenizer for model: {model_name}")
                self._tokenizers[model_name] = AutoTokenizer.from_pretrained(
                    model_name, trust_remote_code=True
                )
            except Exception as e:
                logger.exception(f"Failed to load tokenizer for {model_name}: {e}")

    def get_tokenizer(self, model_name: str) -> PreTrainedTokenizer:
        """Get or create a tokenizer for the specified model."""
        if model_name not in self._tokenizers:
            raise ValueError(f"No tokenizer loaded for {model_name}")

        return self._tokenizers[model_name]

    def tokenize(self, text: str, model_name: str) -> list[str]:
        """Tokenize text using the specified model's tokenizer or fake dataset."""
        if self._use_fake_dataset:
            # Use fake dataset instead of real tokenization
            estimated_length = self._estimate_token_count(text)
            return self._generate_fake_tokens(estimated_length)

        # Real tokenization (original behavior)
        tokenizer = self.get_tokenizer(model_name)

        # Encode and decode to get actual tokens as they would appear
        token_ids = tokenizer.encode(text, add_special_tokens=False)
        tokens = []

        for token_id in token_ids:
            token_text = tokenizer.decode([token_id], skip_special_tokens=False)
            tokens.append(token_text)

        return tokens

    def count_tokens(self, text: str, model_name: str) -> int:
        """Count the number of tokens in the text for the specified model."""
        if self._use_fake_dataset:
            # Use fake estimation instead of real tokenization
            return self._estimate_token_count(text)

        # Real tokenization (original behavior)
        tokenizer = self.get_tokenizer(model_name)
        return len(tokenizer.encode(text, add_special_tokens=False))

    def set_fallback_tokenizer(self, fallback_tokenizer: str) -> None:
        """Set the fallback tokenizer to use if the requested tokenizer is not found."""
        self._fallback_tokenizer = fallback_tokenizer

    def enable_fake_dataset(
        self,
        mode: Literal["random", "predefined"] = "random",
        custom_tokens: list[str] | None = None,
    ) -> None:
        """Enable fake dataset generation instead of real tokenization.

        Args:
            mode: Either "random" for random word combinations or "predefined" for fixed tokens
            custom_tokens: Optional custom token list to use instead of defaults
        """
        self._use_fake_dataset = True
        self._fake_dataset_mode = mode
        if custom_tokens is not None:
            if mode == "predefined":
                self._predefined_tokens = custom_tokens
            else:
                self._random_words = custom_tokens
        logger.info(f"Fake dataset enabled with mode: {mode}")

    def disable_fake_dataset(self) -> None:
        """Disable fake dataset generation and return to real tokenization."""
        self._use_fake_dataset = False
        logger.info("Fake dataset disabled, using real tokenization")

    def _generate_fake_tokens(self, target_length: int) -> list[str]:
        """Generate fake tokens based on the configured mode.

        Args:
            target_length: Approximate number of tokens to generate

        Returns:
            List of fake tokens
        """
        if self._fake_dataset_mode == "predefined":
            # Cycle through predefined tokens to reach target length
            tokens = []
            while len(tokens) < target_length:
                remaining = target_length - len(tokens)
                if remaining >= len(self._predefined_tokens):
                    tokens.extend(self._predefined_tokens)
                else:
                    tokens.extend(self._predefined_tokens[:remaining])
            return tokens
        else:
            # Generate random word combinations
            tokens = []
            for _ in range(target_length):
                word = random.choice(self._random_words)
                # Add space prefix to some tokens to simulate real tokenization
                if random.random() < 0.7 and tokens:  # 70% chance of space prefix
                    tokens.append(f" {word}")
                else:
                    tokens.append(word)
            return tokens

    def _estimate_token_count(self, text: str) -> int:
        """Estimate token count based on text length (rough approximation).

        Args:
            text: Input text

        Returns:
            Estimated number of tokens
        """
        # Rough estimation: ~4 characters per token on average
        return max(1, len(text) // 4)


# Global tokenizer service instance
tokenizer_service = TokenizerService()
