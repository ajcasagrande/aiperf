import uuid
import asyncio
import logging
import json
import random
import os
import time
import tiktoken  # For proper tokenization
from typing import Any, Dict, List, Optional, Tuple, Union

from ..common.base_manager import BaseManager
from ..common.models import Conversation, ConversationTurn
from ..config.config_models import DatasetConfig
from ..common.communication import Communication

# Import transformers for HuggingFace tokenizer support
try:
    from transformers import AutoTokenizer

    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False


class EnhancedDatasetManager(BaseManager):
    """Enhanced dataset manager for AIPerf.

    This is a full implementation that properly handles component registration
    and communication with other AIPerf components.

    Responsible for managing datasets, including:
    - Synthetic data generation
    - Fixed schedule replayability
    - Support for bringing your own data
    - Support for popular datasets out of the box
    """

    def __init__(
        self,
        config: DatasetConfig,
        communication: Optional[Communication] = None,
        component_id: Optional[str] = None,
    ):
        """Initialize the dataset manager.

        Args:
            config: Dataset configuration
            communication: Communication interface
            component_id: Optional component ID
        """
        super().__init__(
            component_id=component_id or f"dataset_manager_{uuid.uuid4().hex[:8]}",
            config=config.__dict__,
        )
        self.dataset_config = config
        self.communication = communication
        self._dataset_cache: Dict[str, Any] = {}
        self._conversations: Dict[str, Conversation] = {}
        self._dataset_lock = asyncio.Lock()
        self._is_initialized = False
        self._is_ready = False
        self._tokenizer = None
        self._hf_tokenizer = None
        self._load_fixtures()

    def _load_fixtures(self):
        """Load pre-defined fixtures for synthetic data generation."""
        try:
            fixtures_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "fixtures",
                "synthetic_prompts.json",
            )
            if os.path.exists(fixtures_path):
                with open(fixtures_path, "r") as f:
                    data = json.load(f)
                    self._templates = data.get("templates", [])
                    self._topics = data.get("topics", [])
                    self._pre_generated_prompts = data.get("pre_generated_prompts", [])
                    self._pre_generated_conversations = data.get(
                        "pre_generated_conversations", []
                    )
                    self.logger.info(f"Loaded fixtures from {fixtures_path}")
            else:
                # Default templates if file not found
                self._templates = [
                    "Explain the concept of {topic} in simple terms.",
                    "Write a short story about {topic}.",
                    "What are the pros and cons of {topic}?",
                    "How does {topic} impact society?",
                    "Compare {topic} with {alt_topic}.",
                ]
                self._topics = [
                    "artificial intelligence",
                    "machine learning",
                    "neural networks",
                    "climate change",
                    "blockchain",
                ]
                self._pre_generated_prompts = []
                self._pre_generated_conversations = []
                self.logger.warning(
                    f"Fixtures file not found at {fixtures_path}, using defaults"
                )
        except Exception as e:
            self.logger.error(f"Error loading fixtures: {e}")
            # Fallback templates
            self._templates = [
                "Explain the concept of {topic} in simple terms.",
                "Write a short story about {topic}.",
            ]
            self._topics = ["artificial intelligence", "machine learning"]
            self._pre_generated_prompts = []
            self._pre_generated_conversations = []

    async def initialize(self) -> bool:
        """Initialize the dataset manager.

        Returns:
            True if initialization was successful, False otherwise
        """
        self.logger.info(
            f"Initializing enhanced dataset manager: {self.dataset_config.name}"
        )

        try:
            # Initialize tokenizers for proper token counting
            # Try HuggingFace tokenizer first
            model_name = self.dataset_config.parameters.get("tokenizer_model", "gpt2")
            cache_dir = self.dataset_config.cache_dir

            if HAS_TRANSFORMERS:
                try:
                    self.logger.info(
                        f"Trying to load HuggingFace tokenizer: {model_name}"
                    )
                    if cache_dir:
                        # Create cache directory if it doesn't exist
                        os.makedirs(cache_dir, exist_ok=True)
                        self.logger.info(f"Using cache directory: {cache_dir}")
                        self._hf_tokenizer = AutoTokenizer.from_pretrained(
                            model_name, cache_dir=cache_dir
                        )
                    else:
                        self._hf_tokenizer = AutoTokenizer.from_pretrained(model_name)
                    self.logger.info(f"Using HuggingFace tokenizer: {model_name}")
                except Exception as e:
                    self.logger.warning(
                        f"HuggingFace tokenizer initialization failed: {e}"
                    )
                    self._hf_tokenizer = None

            # Try Tiktoken as fallback
            try:
                encoding_name = self.dataset_config.parameters.get(
                    "tiktoken_encoding", "cl100k_base"
                )
                self._tokenizer = tiktoken.get_encoding(
                    encoding_name
                )  # Default to GPT-4 encoding
                self.logger.info(
                    f"Using tiktoken for tokenization with encoding {encoding_name}"
                )
            except Exception as e:
                self.logger.warning(
                    f"tiktoken initialization failed: {e}, fallback tokenization will be used if needed"
                )
                self._tokenizer = None

            # Initialize dataset based on configuration
            if self.dataset_config.source_type == "synthetic":
                await self._initialize_synthetic_dataset()
            elif self.dataset_config.source_type == "remote":
                await self._initialize_remote_dataset()
            elif self.dataset_config.source_type == "local":
                await self._initialize_local_dataset()
            else:
                self.logger.error(
                    f"Unsupported dataset source type: {self.dataset_config.source_type}"
                )
                return False

            # Set up communication if provided
            if self.communication:
                # Subscribe to relevant topics
                await self.communication.subscribe(
                    "dataset.request", self._handle_dataset_request
                )
                self.logger.info(
                    f"Subscribed to dataset.request topic with client ID: {self.communication.client_id}"
                )

                # Announce our presence to the system
                await self.publish_identity()
                self.logger.info("Published dataset manager identity")

            self._is_initialized = True
            self._is_ready = True
            return True
        except Exception as e:
            self.logger.error(f"Error initializing dataset: {e}")
            return False

    async def _initialize_synthetic_dataset(self) -> bool:
        """Initialize synthetic dataset.

        Returns:
            True if initialization was successful, False otherwise
        """
        self.logger.info("Initializing synthetic dataset")

        try:
            # Set up synthetic parameters
            params = self.dataset_config.synthetic_params or {}

            # If we have a seed, use it
            if seed := params.get("seed") or self.config.get("seed"):
                random.seed(seed)
                self.logger.info(f"Using seed: {seed} for synthetic data generation")

            # Pre-load conversations from fixtures if available
            if self._pre_generated_conversations:
                async with self._dataset_lock:
                    for conv_data in self._pre_generated_conversations:
                        conversation = self._create_conversation_from_dict(conv_data)
                        self._conversations[conversation.conversation_id] = conversation
                    self.logger.info(
                        f"Loaded {len(self._conversations)} pre-generated conversations"
                    )

            # Pre-generate some conversations if specified
            if pre_generate := params.get("pre_generate", 0):
                to_generate = max(0, pre_generate - len(self._conversations))
                if to_generate > 0:
                    self.logger.info(
                        f"Pre-generating {to_generate} synthetic conversations"
                    )
                    async with self._dataset_lock:
                        for _ in range(to_generate):
                            conversation_id = str(uuid.uuid4())
                            conversation = await self._generate_synthetic_conversation()
                            self._conversations[conversation_id] = conversation

            self.logger.info(
                f"Synthetic dataset initialized with {len(self._conversations)} conversations"
            )
            return True
        except Exception as e:
            self.logger.error(f"Error initializing synthetic dataset: {e}")
            return False

    def _create_conversation_from_dict(self, data: Dict[str, Any]) -> Conversation:
        """Create a Conversation object from dictionary data.

        Args:
            data: Dictionary containing conversation data

        Returns:
            A Conversation object
        """
        conversation = Conversation(
            conversation_id=data.get("conversation_id", str(uuid.uuid4())),
            metadata=data.get("metadata", {}),
        )

        # Add turns
        for turn_data in data.get("turns", []):
            turn = ConversationTurn(
                request=turn_data.get("request", ""),
                response=turn_data.get("response", ""),
                success=turn_data.get("success", True),
                tokens=turn_data.get("tokens", {}),
                latency=turn_data.get("latency"),
                timestamp=turn_data.get("timestamp", time.time()),
                metadata=turn_data.get("metadata", {}),
            )
            conversation.turns.append(turn)

        return conversation

    async def _initialize_remote_dataset(self) -> bool:
        """Initialize remote dataset.

        Returns:
            True if initialization was successful, False otherwise
        """
        self.logger.info("Initializing remote dataset")

        try:
            # Get dataset parameters
            params = self.dataset_config.parameters
            url = params.get("url")
            api_key = params.get("api_key")

            if not url:
                self.logger.error("Remote dataset requires a URL")
                return False

            # Create cache directory if it doesn't exist
            if self.dataset_config.cache_dir:
                os.makedirs(self.dataset_config.cache_dir, exist_ok=True)

            # Implement fetching from remote source
            import aiohttp
            import tempfile

            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers) as response:
                        if response.status != 200:
                            self.logger.error(
                                f"Failed to fetch dataset from {url}: {response.status}"
                            )
                            return False

                        data = await response.json()

                        # Cache the data if cache_dir is specified
                        if self.dataset_config.cache_dir:
                            cache_path = os.path.join(
                                self.dataset_config.cache_dir,
                                f"dataset_cache_{uuid.uuid4().hex[:8]}.json",
                            )
                            with open(cache_path, "w") as f:
                                json.dump(data, f)
                            self.logger.info(f"Cached remote dataset to {cache_path}")

                        # Process conversations from data
                        async with self._dataset_lock:
                            count = 0
                            for item in data:
                                if isinstance(item, dict) and "conversation_id" in item:
                                    conversation = self._create_conversation_from_dict(
                                        item
                                    )
                                    self._conversations[
                                        conversation.conversation_id
                                    ] = conversation
                                    count += 1

                            self.logger.info(
                                f"Loaded {count} conversations from remote dataset"
                            )
            except aiohttp.ClientError as e:
                self.logger.error(f"Error fetching remote dataset: {e}")
                # If cache dir is available, try to load from there as fallback
                if self.dataset_config.cache_dir:
                    return await self._load_from_cache()
                return False

            self.logger.info(f"Successfully initialized remote dataset from {url}")
            return True
        except Exception as e:
            self.logger.error(f"Error initializing remote dataset: {e}")
            return False

    async def _load_from_cache(self) -> bool:
        """Load dataset from cache as fallback.

        Returns:
            True if loading from cache was successful, False otherwise
        """
        if not self.dataset_config.cache_dir or not os.path.exists(
            self.dataset_config.cache_dir
        ):
            return False

        try:
            # Find the most recent cache file
            cache_files = [
                f
                for f in os.listdir(self.dataset_config.cache_dir)
                if f.startswith("dataset_cache_") and f.endswith(".json")
            ]
            if not cache_files:
                return False

            # Sort by modification time, newest first
            cache_files.sort(
                key=lambda x: os.path.getmtime(
                    os.path.join(self.dataset_config.cache_dir, x)
                ),
                reverse=True,
            )
            latest_cache = os.path.join(self.dataset_config.cache_dir, cache_files[0])

            self.logger.info(f"Loading dataset from cache: {latest_cache}")

            with open(latest_cache, "r") as f:
                data = json.load(f)

                # Process conversations from data
                async with self._dataset_lock:
                    for item in data:
                        if "conversation_id" in item:
                            conversation = self._create_conversation_from_dict(item)
                            self._conversations[conversation.conversation_id] = (
                                conversation
                            )

                self.logger.info(
                    f"Loaded {len(self._conversations)} conversations from cache"
                )
                return True
        except Exception as e:
            self.logger.error(f"Error loading from cache: {e}")
            return False

    async def _initialize_local_dataset(self) -> bool:
        """Initialize local dataset.

        Returns:
            True if initialization was successful, False otherwise
        """
        self.logger.info("Initializing local dataset")

        try:
            # Get dataset parameters
            params = self.dataset_config.parameters
            file_path = params.get("file_path")

            if not file_path:
                self.logger.error("Local dataset requires a file path")
                return False

            if not os.path.exists(file_path):
                self.logger.error(f"Local dataset file not found: {file_path}")
                return False

            # Load dataset from file
            self.logger.info(f"Loading dataset from {file_path}")

            with open(file_path, "r") as f:
                if file_path.endswith(".json"):
                    data = json.load(f)

                    # Process conversations
                    async with self._dataset_lock:
                        for item in data:
                            if "conversation_id" in item:
                                conversation = self._create_conversation_from_dict(item)
                                self._conversations[conversation.conversation_id] = (
                                    conversation
                                )

                    self.logger.info(
                        f"Loaded {len(self._conversations)} conversations from dataset"
                    )
                else:
                    self.logger.error(f"Unsupported file format: {file_path}")
                    return False

            return True
        except Exception as e:
            self.logger.error(f"Error initializing local dataset: {e}")
            return False

    async def ready_check(self) -> bool:
        """Check if the dataset manager is ready.

        Returns:
            True if the dataset manager is ready, False otherwise
        """
        return self._is_initialized and self._is_ready

    async def publish_identity(self) -> bool:
        """Publish the dataset manager's identity.

        Returns:
            True if identity was published successfully, False otherwise
        """
        if not self.communication:
            self.logger.warning(
                "No communication interface available, skipping identity publication"
            )
            return False

        try:
            identity = {
                "component_id": self.component_id,
                "component_type": "dataset_manager",
                "dataset_name": self.dataset_config.name,
                "source_type": self.dataset_config.source_type,
                "modality": self.dataset_config.modality,
                "conversation_count": len(self._conversations),
                "has_tokenizer": self._tokenizer is not None,
            }

            # Publish identity to system.identity topic
            success = await self.communication.publish("system.identity", identity)
            if success:
                self.logger.info(
                    f"Published dataset manager identity: {self.component_id}"
                )
            else:
                self.logger.warning("Failed to publish dataset manager identity")

            # Also create a specific topic for this component
            success = await self.communication.publish(
                f"dataset.identity.{self.component_id}", identity
            )

            return success
        except Exception as e:
            self.logger.error(f"Error publishing dataset manager identity: {e}")
            return False

    async def shutdown(self) -> bool:
        """Gracefully shutdown the dataset manager.

        Returns:
            True if shutdown was successful, False otherwise
        """
        self.logger.info("Shutting down dataset manager")

        try:
            # Clear in-memory datasets
            async with self._dataset_lock:
                self._conversations.clear()
                self._dataset_cache.clear()

            # Announce shutdown
            if self.communication:
                try:
                    await self.communication.publish(
                        "system.events",
                        {
                            "event_type": "component_shutdown",
                            "component_id": self.component_id,
                            "component_type": "dataset_manager",
                            "timestamp": time.time(),
                        },
                    )
                except Exception as e:
                    self.logger.error(f"Error publishing shutdown event: {e}")

            self._is_shutdown = True
            self._is_ready = False
            self._is_initialized = False
            return True
        except Exception as e:
            self.logger.error(f"Error shutting down dataset manager: {e}")
            self._is_shutdown = True  # Mark as shutdown even on error
            return False

    async def _handle_dataset_request(self, message: Dict[str, Any]) -> None:
        """Handle dataset request message.

        Args:
            message: Message dictionary
        """
        if not self.communication:
            return

        try:
            # Extract data from message
            data = message.get("data", {})
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    data = {"error": "Invalid JSON in message data"}

            command = data.get("command")
            payload = data.get("payload", {})

            # For compatibility with both styles of messaging
            source = message.get("source") or message.get("client_id")
            request_id = data.get("request_id") or str(uuid.uuid4())

            if not source:
                self.logger.warning("Dataset request missing source/client_id")
                return

            self.logger.info(f"Received dataset request: {command} from {source}")

            # Process request
            response = await self.handle_command(command, payload)
            response["request_id"] = request_id

            # Send response
            success = False

            # Try both formats of response
            try:
                # First try direct response if request has client_id
                if "client_id" in message:
                    success = await self.communication.respond(
                        message["client_id"], response
                    )
                    if success:
                        self.logger.info(
                            f"Sent direct response to {message['client_id']}"
                        )

                # If that fails or wasn't available, try topic-based response
                if not success:
                    if "source" in message:
                        success = await self.communication.publish(
                            f"dataset.response.{source}", response
                        )
                        if success:
                            self.logger.info(
                                f"Published response to dataset.response.{source}"
                            )
                    else:
                        # Fallback to generic response topic
                        success = await self.communication.publish(
                            "dataset.response",
                            {
                                **response,
                                "target": source,
                            },
                        )
                        self.logger.info(
                            f"Published response to dataset.response with target={source}"
                        )
            except Exception as e:
                self.logger.error(f"Error sending response: {e}")
                # Try one last fallback
                try:
                    await self.communication.publish(
                        "system.events",
                        {
                            "event_type": "dataset_response_error",
                            "component_id": self.component_id,
                            "error": str(e),
                            "target": source,
                            "request_id": request_id,
                        },
                    )
                except:
                    pass
        except Exception as e:
            self.logger.error(f"Error handling dataset request: {e}")

    async def handle_command(
        self, command: str, payload: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Handle a command from the system controller.

        Args:
            command: Command string
            payload: Optional command payload

        Returns:
            Response dictionary with results
        """
        response = {"status": "error", "message": f"Unknown command: {command}"}
        payload = payload or {}

        if command == "get_conversation":
            conversation_id = payload.get("conversation_id")
            conversation = await self.get_conversation(conversation_id)
            if conversation:
                # Convert to serializable format
                conv_dict = conversation.__dict__.copy()
                conv_dict["turns"] = [turn.__dict__ for turn in conversation.turns]
                response = {"status": "success", "conversation": conv_dict}
            else:
                response = {"status": "error", "message": "Failed to get conversation"}

        elif command == "get_synthetic_prompt":
            modality = payload.get("modality", "text")
            prompt = await self.get_synthetic_prompt(modality)
            if prompt:
                response = {"status": "success", "prompt": prompt}
            else:
                response = {
                    "status": "error",
                    "message": "Failed to generate synthetic prompt",
                }

        elif command == "get_next_turn":
            conversation_id = payload.get("conversation_id")
            if not conversation_id:
                response = {"status": "error", "message": "Missing conversation_id"}
            else:
                turn = await self.get_next_turn(conversation_id)
                if turn:
                    response = {"status": "success", "turn": turn.__dict__}
                else:
                    response = {
                        "status": "error",
                        "message": "No more turns or conversation not found",
                    }

        elif command == "tokenize":
            prompt = payload.get("prompt")
            if not prompt:
                response = {"status": "error", "message": "Missing prompt"}
            else:
                tokens = await self.tokenize_prompt(prompt)
                response = {"status": "success", "tokens": tokens}

        elif command == "get_status":
            status = await self.get_status()
            response = {"status": "success", "data": status}

        elif command == "reload":
            force = payload.get("force", False)
            success = await self.reload(force)
            if success:
                response = {
                    "status": "success",
                    "message": "Dataset reloaded successfully",
                }
            else:
                response = {"status": "error", "message": "Failed to reload dataset"}

        return response

    async def get_status(self) -> Dict[str, Any]:
        """Get status information about the dataset manager.

        Returns:
            Dictionary with status information
        """
        return {
            "component_id": self.component_id,
            "component_type": "dataset_manager",
            "is_ready": self._is_ready,
            "is_initialized": self._is_initialized,
            "dataset_name": self.dataset_config.name,
            "source_type": self.dataset_config.source_type,
            "conversation_count": len(self._conversations),
            "has_tokenizer": self._tokenizer is not None,
            "uptime": time.time() - self.start_time
            if hasattr(self, "start_time")
            else 0,
        }

    async def reload(self, force: bool = False) -> bool:
        """Reload the dataset.

        Args:
            force: If True, clear the existing dataset first

        Returns:
            True if reload was successful, False otherwise
        """
        try:
            if force:
                async with self._dataset_lock:
                    self._conversations.clear()
                    self._dataset_cache.clear()

            if self.dataset_config.source_type == "synthetic":
                return await self._initialize_synthetic_dataset()
            elif self.dataset_config.source_type == "remote":
                return await self._initialize_remote_dataset()
            elif self.dataset_config.source_type == "local":
                return await self._initialize_local_dataset()
            else:
                self.logger.error(
                    f"Unsupported dataset source type: {self.dataset_config.source_type}"
                )
                return False

        except Exception as e:
            self.logger.error(f"Error reloading dataset: {e}")
            return False

    async def get_conversation(
        self, conversation_id: Optional[str] = None
    ) -> Optional[Conversation]:
        """Get a conversation from the dataset.

        Args:
            conversation_id: Optional conversation ID

        Returns:
            Conversation object or None if not found
        """
        try:
            async with self._dataset_lock:
                # If conversation_id is provided, try to get that specific conversation
                if conversation_id and conversation_id in self._conversations:
                    return self._conversations[conversation_id]

                # If conversation_id is not provided or not found, generate a new one based on source type
                if self.dataset_config.source_type == "synthetic":
                    # Generate a new synthetic conversation
                    conversation = await self._generate_synthetic_conversation()
                    conversation_id = conversation.conversation_id
                    self._conversations[conversation_id] = conversation
                    return conversation
                elif self._conversations:
                    # Return a random existing conversation
                    conversation_id = random.choice(list(self._conversations.keys()))
                    return self._conversations[conversation_id]

                # No conversations available, generate at least one
                if self.dataset_config.source_type == "synthetic":
                    conversation = await self._generate_synthetic_conversation()
                    conversation_id = conversation.conversation_id
                    self._conversations[conversation_id] = conversation
                    return conversation

                # No conversations available and can't generate
                return None
        except Exception as e:
            self.logger.error(f"Error getting conversation: {e}")
            return None

    async def _generate_synthetic_conversation(self) -> Conversation:
        """Generate a synthetic conversation.

        Returns:
            Synthetic conversation
        """
        conversation_id = str(uuid.uuid4())
        conversation = Conversation(
            conversation_id=conversation_id,
            metadata={
                "synthetic": True,
                "created_at": time.time(),
                "updated_at": time.time(),
            },
        )

        # Determine number of turns (1-3)
        num_turns = random.randint(1, 3)

        # If we have pre-generated conversations, use one of those occasionally
        if self._pre_generated_conversations and random.random() < 0.3:
            conv_data = random.choice(self._pre_generated_conversations)
            return self._create_conversation_from_dict(conv_data)

        # Generate turns
        for i in range(num_turns):
            # Get prompt
            prompt_data = await self.get_synthetic_prompt()
            if prompt_data:
                prompt_content = prompt_data.get("content", "")

                # Generate a relatively realistic response
                topics = [
                    "AI",
                    "machine learning",
                    "neural networks",
                    "data science",
                    "computer vision",
                    "natural language processing",
                    "reinforcement learning",
                ]
                response_content = (
                    f"This is a synthetic response about {random.choice(topics)}. "
                )
                response_content += f"The question was about {prompt_data.get('metadata', {}).get('topic', 'unknown topic')}. "
                response_content += "Here is some additional information to make the response seem more realistic and detailed. "
                response_content += "This allows for better testing of metrics like token counting and timing."

                # Generate realistic token counts
                prompt_tokens = await self.tokenize_prompt(prompt_content)
                completion_tokens = await self.tokenize_prompt(response_content)

                turn = ConversationTurn(
                    request=prompt_content,
                    response=response_content,
                    success=True,
                    tokens={
                        "prompt_tokens": len(prompt_tokens),
                        "completion_tokens": len(completion_tokens),
                        "total_tokens": len(prompt_tokens) + len(completion_tokens),
                    },
                    latency=random.uniform(0.5, 2.0),  # Realistic latency
                    timestamp=time.time(),
                    metadata={"synthetic": True, "turn_index": i},
                )
                conversation.turns.append(turn)

        return conversation

    async def get_synthetic_prompt(
        self, modality: str = "text"
    ) -> Optional[Dict[str, Any]]:
        """Get a synthetic prompt.

        Args:
            modality: Modality of the prompt

        Returns:
            Dictionary with prompt data
        """
        try:
            if modality == "text":
                # If we have pre-generated prompts, use one occasionally
                if self._pre_generated_prompts and random.random() < 0.5:
                    return random.choice(self._pre_generated_prompts)

                # Get random template and topic
                template = random.choice(self._templates)
                topic = random.choice(self._topics)

                # If template requires alt_topic, select a different one
                alt_topic = None
                if "{alt_topic}" in template:
                    alt_topics = [t for t in self._topics if t != topic]
                    if alt_topics:
                        alt_topic = random.choice(alt_topics)
                    else:
                        alt_topic = "other topic"  # Fallback

                # Format template
                prompt = template.format(topic=topic, alt_topic=alt_topic)

                return {
                    "content": prompt,
                    "modality": modality,
                    "metadata": {
                        "template": template,
                        "topic": topic,
                        "alt_topic": alt_topic if "{alt_topic}" in template else None,
                        "synthetic": True,
                    },
                }
            else:
                self.logger.warning(
                    f"Unsupported modality for synthetic prompts: {modality}"
                )
                return None
        except Exception as e:
            self.logger.error(f"Error generating synthetic prompt: {e}")
            return None

    async def get_next_turn(self, conversation_id: str) -> Optional[ConversationTurn]:
        """Get the next turn for a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            ConversationTurn object or None if no more turns
        """
        try:
            async with self._dataset_lock:
                if conversation_id not in self._conversations:
                    return None

                conversation = self._conversations[conversation_id]

                # Check if we have any turns with no response
                for turn in conversation.turns:
                    if not turn.response:
                        return turn

                # All turns have responses, return None
                return None
        except Exception as e:
            self.logger.error(f"Error getting next turn: {e}")
            return None

    async def tokenize_prompt(self, prompt: str) -> List[int]:
        """Tokenize a prompt.

        Args:
            prompt: Prompt to tokenize

        Returns:
            List of token IDs
        """
        try:
            # Use HuggingFace tokenizer if available
            if self._hf_tokenizer:
                return self._hf_tokenizer.encode(prompt)

            # Use tiktoken if available as fallback
            if self._tokenizer:
                return self._tokenizer.encode(prompt)

            # Simple tokenization fallback
            tokens = []
            for i, char in enumerate(prompt):
                # Use character code as a simple token ID
                tokens.append(ord(char))

            return tokens
        except Exception as e:
            self.logger.error(f"Error tokenizing prompt: {e}")
            return []
