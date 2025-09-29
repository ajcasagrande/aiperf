# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""OpenAI request converter plugins."""

from aiperf.clients.openai.plugins.chat_plugin import (
    DEFAULT_ROLE,
    OpenAIChatPlugin,
)
from aiperf.clients.openai.plugins.completions_plugin import (
    OpenAICompletionsPlugin,
)
from aiperf.clients.openai.plugins.embeddings_plugin import (
    OpenAIEmbeddingsPlugin,
)
from aiperf.clients.openai.plugins.rankings_plugin import (
    OpenAIRankingsPlugin,
)
from aiperf.clients.openai.plugins.responses_plugin import (
    OpenAIResponsesPlugin,
)

__all__ = [
    "DEFAULT_ROLE",
    "OpenAIChatPlugin",
    "OpenAICompletionsPlugin",
    "OpenAIEmbeddingsPlugin",
    "OpenAIRankingsPlugin",
    "OpenAIResponsesPlugin",
]
