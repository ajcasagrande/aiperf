<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Chapter 45: Custom Dataset Development

## Overview

This chapter covers creating custom dataset loaders and composers for AIPerf. Learn how to support new dataset formats, implement validation, and integrate with AIPerf's dataset system.

## Table of Contents

- [Dataset System Architecture](#dataset-system-architecture)
- [Custom Dataset Loaders](#custom-dataset-loaders)
- [Custom Dataset Composers](#custom-dataset-composers)
- [Data Validation](#data-validation)
- [Integration with AIPerf](#integration-with-aiperf)
- [Complete Examples](#complete-examples)

---

## Dataset System Architecture

### Dataset Flow

```
┌────────────────────────────────────────────────────────────┐
│                    Dataset Processing Flow                  │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  Raw Data File                                              │
│       │                                                     │
│       ▼                                                     │
│  ┌──────────────┐                                          │
│  │   Loader     │ ← Load and parse file                    │
│  └───────┬──────┘                                          │
│          │                                                  │
│          ▼                                                  │
│  ┌──────────────┐                                          │
│  │  Converter   │ ← Convert to Conversation objects        │
│  └───────┬──────┘                                          │
│          │                                                  │
│          ▼                                                  │
│  ┌──────────────┐                                          │
│  │  Composer    │ ← Finalize with metadata                 │
│  └───────┬──────┘                                          │
│          │                                                  │
│          ▼                                                  │
│  Final Dataset (list[Conversation])                        │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

### Key Components

**Location**: `/home/anthony/nvidia/projects/aiperf/aiperf/dataset/`

- **Loaders**: Parse files and convert to structured data
- **Composers**: Orchestrate loading and add metadata
- **Models**: Data structures (Conversation, Turn, etc.)

---

## Custom Dataset Loaders

### Loader Protocol

```python
from typing import Protocol
from aiperf.common.models import Conversation


class CustomDatasetLoaderProtocol(Protocol):
    """Protocol for custom dataset loaders"""

    def load_dataset(self) -> dict:
        """Load raw dataset from source"""
        ...

    def convert_to_conversations(self, data: dict) -> list[Conversation]:
        """Convert raw data to conversations"""
        ...
```

### Basic Loader Implementation

**Example**: CSV dataset loader

```python
from aiperf.common.factories import CustomDatasetFactory
from aiperf.common.enums import CustomDatasetType
from aiperf.common.models import Conversation, Turn, Text
import csv


@CustomDatasetFactory.register(CustomDatasetType.CSV)
class CSVDatasetLoader:
    """Load dataset from CSV file"""

    def __init__(self, filename: str):
        self.filename = filename

    def load_dataset(self) -> dict[str, list[dict]]:
        """Load CSV file into structured data"""
        data = {}
        with open(self.filename, 'r') as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader):
                session_id = row.get('session_id', f'session_{idx}')
                if session_id not in data:
                    data[session_id] = []
                data[session_id].append(row)
        return data

    def convert_to_conversations(
        self,
        data: dict[str, list[dict]]
    ) -> list[Conversation]:
        """Convert CSV rows to conversations"""
        conversations = []

        for session_id, rows in data.items():
            turns = []
            for row in rows:
                # Create turn from row
                turn = Turn(
                    texts=[Text(contents=[row['prompt']])],
                    role=row.get('role', 'user'),
                    images=[],
                    audios=[]
                )
                turns.append(turn)

            # Create conversation
            conversation = Conversation(
                session_id=session_id,
                turns=turns
            )
            conversations.append(conversation)

        return conversations
```

### Advanced Loader with Validation

**Example**: JSON dataset loader with schema validation

```python
import json
from pydantic import BaseModel, Field, field_validator
from aiperf.common.factories import CustomDatasetFactory
from aiperf.common.enums import CustomDatasetType
from aiperf.common.models import Conversation, Turn, Text
from aiperf.common.exceptions import DatasetLoaderError


class JSONRecordSchema(BaseModel):
    """Schema for JSON dataset records"""

    session_id: str = Field(description="Session identifier")
    prompt: str = Field(description="User prompt")
    role: str = Field(default="user")
    timestamp: float | None = Field(default=None)
    metadata: dict = Field(default_factory=dict)

    @field_validator('role')
    @classmethod
    def validate_role(cls, v):
        if v not in ['user', 'assistant', 'system']:
            raise ValueError(f"Invalid role: {v}")
        return v


@CustomDatasetFactory.register(CustomDatasetType.JSON)
class JSONDatasetLoader:
    """Load dataset from JSONL file with validation"""

    def __init__(self, filename: str):
        self.filename = filename

    def load_dataset(self) -> dict[str, list[JSONRecordSchema]]:
        """Load and validate JSONL file"""
        data = {}

        try:
            with open(self.filename, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    if not line.strip():
                        continue

                    try:
                        # Parse and validate
                        record = JSONRecordSchema.model_validate_json(line)

                        # Group by session
                        session_id = record.session_id
                        if session_id not in data:
                            data[session_id] = []
                        data[session_id].append(record)

                    except Exception as e:
                        raise DatasetLoaderError(
                            f"Error parsing line {line_num}: {e}"
                        )

        except FileNotFoundError:
            raise DatasetLoaderError(f"File not found: {self.filename}")

        return data

    def convert_to_conversations(
        self,
        data: dict[str, list[JSONRecordSchema]]
    ) -> list[Conversation]:
        """Convert validated records to conversations"""
        conversations = []

        for session_id, records in data.items():
            turns = []

            for record in records:
                # Create turn
                turn = Turn(
                    texts=[Text(contents=[record.prompt])],
                    role=record.role,
                    images=[],
                    audios=[],
                    timestamp=record.timestamp
                )
                turns.append(turn)

            # Create conversation
            conversation = Conversation(
                session_id=session_id,
                turns=turns,
                metadata=records[0].metadata if records else {}
            )
            conversations.append(conversation)

        return conversations
```

### Multi-Modal Loader

**Example**: Loader supporting text, images, and audio

```python
from pathlib import Path
from aiperf.dataset.loader.mixins import MediaConversionMixin
from aiperf.common.models import Conversation, Turn, Text, Image, Audio
from aiperf.common.factories import CustomDatasetFactory
from aiperf.common.enums import CustomDatasetType, MediaType


@CustomDatasetFactory.register(CustomDatasetType.MULTIMODAL)
class MultiModalDatasetLoader(MediaConversionMixin):
    """Load multimodal dataset with text, images, and audio"""

    def __init__(self, filename: str, media_base_path: str = "."):
        self.filename = filename
        self.media_base_path = Path(media_base_path)

    def load_dataset(self) -> dict[str, list[dict]]:
        """Load multimodal data"""
        import json

        data = {}
        with open(self.filename, 'r') as f:
            for line in f:
                if not line.strip():
                    continue

                record = json.loads(line)
                session_id = record.get('session_id', 'default')

                if session_id not in data:
                    data[session_id] = []

                data[session_id].append(record)

        return data

    def convert_to_conversations(
        self,
        data: dict[str, list[dict]]
    ) -> list[Conversation]:
        """Convert to conversations with media"""
        conversations = []

        for session_id, records in data.items():
            turns = []

            for record in records:
                # Process text
                texts = []
                if 'text' in record:
                    texts.append(Text(contents=[record['text']]))

                # Process images
                images = []
                if 'images' in record:
                    for img_path in record['images']:
                        # Convert image to base64
                        full_path = self.media_base_path / img_path
                        encoded = self._encode_image(
                            str(full_path),
                            MediaType.PNG
                        )
                        images.append(Image(contents=[encoded]))

                # Process audio
                audios = []
                if 'audios' in record:
                    for audio_path in record['audios']:
                        # Convert audio to base64
                        full_path = self.media_base_path / audio_path
                        encoded = self._encode_audio(
                            str(full_path),
                            MediaType.MP3
                        )
                        audios.append(Audio(contents=[encoded]))

                # Create turn
                turn = Turn(
                    texts=texts,
                    images=images,
                    audios=audios,
                    role=record.get('role', 'user')
                )
                turns.append(turn)

            # Create conversation
            conversation = Conversation(
                session_id=session_id,
                turns=turns
            )
            conversations.append(conversation)

        return conversations

    def _encode_image(self, path: str, media_type: MediaType) -> str:
        """Encode image file to base64"""
        import base64
        with open(path, 'rb') as f:
            encoded = base64.b64encode(f.read()).decode('utf-8')
        return f"data:image/{media_type.value};base64,{encoded}"

    def _encode_audio(self, path: str, media_type: MediaType) -> str:
        """Encode audio file to base64"""
        import base64
        with open(path, 'rb') as f:
            encoded = base64.b64encode(f.read()).decode('utf-8')
        return f"{media_type.value},{encoded}"
```

---

## Custom Dataset Composers

### Composer Pattern

```python
from aiperf.dataset.composer.base import BaseDatasetComposer
from aiperf.common.factories import ComposerFactory
from aiperf.common.enums import ComposerType
from aiperf.common.config import UserConfig
from aiperf.common.tokenizer import Tokenizer
from aiperf.common.models import Conversation


@ComposerFactory.register(ComposerType.CUSTOM)
class CustomDatasetComposer(BaseDatasetComposer):
    """Custom dataset composer"""

    def __init__(self, config: UserConfig, tokenizer: Tokenizer):
        super().__init__(config, tokenizer)

    def create_dataset(self) -> list[Conversation]:
        """Create and finalize dataset"""
        # Load dataset
        loader = self._create_loader()
        data = loader.load_dataset()

        # Convert to conversations
        conversations = loader.convert_to_conversations(data)

        # Finalize (add metadata, tokenize, etc.)
        self._finalize_conversations(conversations)

        return conversations

    def _create_loader(self):
        """Create appropriate loader"""
        from aiperf.common.factories import CustomDatasetFactory

        return CustomDatasetFactory.create_instance(
            self.config.input.custom_dataset_type,
            filename=self.config.input.file
        )

    def _finalize_conversations(
        self,
        conversations: list[Conversation]
    ) -> None:
        """Add metadata and tokenization"""
        for conversation in conversations:
            for turn in conversation.turns:
                # Add token counts
                self._finalize_turn(turn)
```

---

## Data Validation

### Input Validation

```python
from pydantic import BaseModel, Field, field_validator
from typing import Literal


class DatasetRecord(BaseModel):
    """Validated dataset record"""

    session_id: str
    prompt: str = Field(min_length=1, max_length=10000)
    role: Literal['user', 'assistant', 'system'] = 'user'
    timestamp: float | None = None

    @field_validator('prompt')
    @classmethod
    def validate_prompt(cls, v):
        """Ensure prompt is not empty or whitespace"""
        if not v or not v.strip():
            raise ValueError("Prompt cannot be empty")
        return v.strip()

    @field_validator('timestamp')
    @classmethod
    def validate_timestamp(cls, v):
        """Ensure timestamp is non-negative"""
        if v is not None and v < 0:
            raise ValueError("Timestamp must be non-negative")
        return v
```

### Output Validation

```python
def validate_conversations(
    conversations: list[Conversation]
) -> None:
    """Validate generated conversations"""

    if not conversations:
        raise ValueError("No conversations generated")

    for idx, conv in enumerate(conversations):
        # Validate conversation has turns
        if not conv.turns:
            raise ValueError(f"Conversation {idx} has no turns")

        # Validate each turn
        for turn_idx, turn in enumerate(conv.turns):
            # Must have at least one content type
            if not turn.texts and not turn.images and not turn.audios:
                raise ValueError(
                    f"Turn {turn_idx} in conversation {idx} has no content"
                )

            # Validate text content
            for text in turn.texts:
                if not text.contents:
                    raise ValueError("Text has no contents")
```

---

## Integration with AIPerf

### Registration

```python
# Register custom dataset type
from aiperf.common.enums import CustomDatasetType, ComposerType

# Add to enum (in your code, not AIPerf core)
class MyCustomDatasetType(CustomDatasetType):
    MY_FORMAT = "my_format"

# Register loader
@CustomDatasetFactory.register(MyCustomDatasetType.MY_FORMAT)
class MyFormatLoader:
    # Implementation
    pass
```

### Usage

```bash
# Command line
aiperf profile \
  --model Qwen/Qwen3-0.6B \
  --url http://localhost:8000 \
  --endpoint-type chat \
  --input-file dataset.jsonl \
  --custom-dataset-type my_format
```

```python
# Programmatic
from aiperf.common.config import UserConfig, InputConfig

input_config = InputConfig(
    file='dataset.jsonl',
    custom_dataset_type='my_format'
)

user_config = UserConfig(
    endpoint=endpoint_config,
    loadgen=loadgen_config,
    input=input_config
)
```

---

## Complete Examples

### Example 1: Database Loader

```python
from aiperf.common.factories import CustomDatasetFactory
from aiperf.common.enums import CustomDatasetType
from aiperf.common.models import Conversation, Turn, Text
import sqlite3


@CustomDatasetFactory.register(CustomDatasetType.DATABASE)
class DatabaseDatasetLoader:
    """Load dataset from SQLite database"""

    def __init__(self, db_path: str, query: str = None):
        self.db_path = db_path
        self.query = query or "SELECT * FROM conversations"

    def load_dataset(self) -> dict[str, list[dict]]:
        """Query database"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Access by column name

        cursor = conn.execute(self.query)
        rows = cursor.fetchall()

        # Group by session_id
        data = {}
        for row in rows:
            row_dict = dict(row)
            session_id = row_dict.get('session_id', 'default')

            if session_id not in data:
                data[session_id] = []

            data[session_id].append(row_dict)

        conn.close()
        return data

    def convert_to_conversations(
        self,
        data: dict[str, list[dict]]
    ) -> list[Conversation]:
        """Convert database rows to conversations"""
        conversations = []

        for session_id, rows in data.items():
            turns = []

            for row in rows:
                turn = Turn(
                    texts=[Text(contents=[row['prompt']])],
                    role=row.get('role', 'user'),
                    images=[],
                    audios=[]
                )
                turns.append(turn)

            conversation = Conversation(
                session_id=session_id,
                turns=turns
            )
            conversations.append(conversation)

        return conversations
```

### Example 2: API Loader

```python
import aiohttp
from aiperf.common.factories import CustomDatasetFactory
from aiperf.common.enums import CustomDatasetType
from aiperf.common.models import Conversation, Turn, Text


@CustomDatasetFactory.register(CustomDatasetType.API)
class APIDatasetLoader:
    """Load dataset from REST API"""

    def __init__(self, api_url: str, auth_token: str = None):
        self.api_url = api_url
        self.auth_token = auth_token

    async def fetch_data(self) -> dict:
        """Fetch data from API"""
        headers = {}
        if self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'

        async with aiohttp.ClientSession() as session:
            async with session.get(self.api_url, headers=headers) as response:
                response.raise_for_status()
                return await response.json()

    def load_dataset(self) -> dict[str, list[dict]]:
        """Load dataset from API (sync wrapper)"""
        import asyncio
        return asyncio.run(self.fetch_data())

    def convert_to_conversations(
        self,
        data: dict[str, list[dict]]
    ) -> list[Conversation]:
        """Convert API response to conversations"""
        conversations = []

        for session_id, records in data.items():
            turns = []

            for record in records:
                turn = Turn(
                    texts=[Text(contents=[record['text']])],
                    role=record.get('role', 'user'),
                    images=[],
                    audios=[]
                )
                turns.append(turn)

            conversation = Conversation(
                session_id=session_id,
                turns=turns
            )
            conversations.append(conversation)

        return conversations
```

---

## Key Takeaways

1. **Loaders**: Parse files and convert to Conversation objects
2. **Composers**: Orchestrate loading and add metadata
3. **Validation**: Use Pydantic for schema validation
4. **Factory Registration**: Register custom loaders with factory
5. **Multi-Modal Support**: Handle text, images, and audio
6. **Flexible Sources**: Support files, databases, APIs
7. **Error Handling**: Validate data and handle failures gracefully

---

## Navigation

- [Previous Chapter: Chapter 44 - Custom Metrics Development](chapter-44-custom-metrics-development.md)
- [Next Chapter: Chapter 46 - Custom Endpoints](chapter-46-custom-endpoints.md)
- [Return to Index](INDEX.md)

---

**Document Information**
- **File**: `/home/anthony/nvidia/projects/aiperf/guidebook/chapter-45-custom-dataset-development.md`
- **Purpose**: Guide to creating custom dataset loaders
- **Target Audience**: Developers adding dataset support
- **Related Files**:
  - `/home/anthony/nvidia/projects/aiperf/aiperf/dataset/loader/`
  - `/home/anthony/nvidia/projects/aiperf/aiperf/dataset/composer/`
