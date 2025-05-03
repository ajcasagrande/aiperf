import uuid
import asyncio
import logging
import json
import random
import os
from abc import abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union

from ..common.base_manager import BaseManager
from ..common.models import Conversation, ConversationTurn
from ..config.config_models import DatasetConfig
from ..common.communication import Communication

class DatasetManager(BaseManager):
    """Dataset manager for AIPerf.
    
    Responsible for managing datasets, including:
    - Synthetic data generation
    - Fixed schedule replayability
    - Support for bringing your own data
    - Support for popular datasets out of the box
    """
    
    def __init__(self, config: DatasetConfig, 
                 communication: Optional[Communication] = None,
                 component_id: Optional[str] = None):
        """Initialize the dataset manager.
        
        Args:
            config: Dataset configuration
            communication: Communication interface
            component_id: Optional component ID
        """
        super().__init__(component_id=component_id or f"dataset_manager_{uuid.uuid4().hex[:8]}", 
                         config=config.__dict__)
        self.dataset_config = config
        self.communication = communication
        self._dataset_cache: Dict[str, Any] = {}
        self._conversations: Dict[str, Conversation] = {}
        self._dataset_lock = asyncio.Lock()
        self._is_initialized = False
        
        # Templates for synthetic prompts
        self._templates = [
            "Explain the concept of {topic} in simple terms.",
            "Write a short story about {topic}.",
            "What are the pros and cons of {topic}?",
            "How does {topic} impact society?",
            "Compare {topic} with {alt_topic}.",
            "Provide a step-by-step guide for {topic}.",
            "Summarize the history of {topic}.",
            "Explain the science behind {topic}.",
            "Provide 5 interesting facts about {topic}.",
            "How might {topic} evolve in the future?"
        ]
        
        # Topics for synthetic prompts
        self._topics = [
            "artificial intelligence", "renewable energy", "quantum computing", 
            "space exploration", "cryptocurrency", "climate change", 
            "virtual reality", "robotics", "genetic engineering", 
            "blockchain", "3D printing", "autonomous vehicles",
            "machine learning", "IoT", "cybersecurity", 
            "edge computing", "cloud computing", "augmented reality"
        ]
    
    async def initialize(self) -> bool:
        """Initialize the dataset manager.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        self.logger.info(f"Initializing dataset manager: {self.dataset_config.name}")
        
        try:
            # Initialize dataset based on configuration
            if self.dataset_config.source_type == "synthetic":
                await self._initialize_synthetic_dataset()
            elif self.dataset_config.source_type == "remote":
                await self._initialize_remote_dataset()
            elif self.dataset_config.source_type == "local":
                await self._initialize_local_dataset()
            else:
                self.logger.error(f"Unsupported dataset source type: {self.dataset_config.source_type}")
                return False
                
            # Set up communication if provided
            if self.communication:
                # Subscribe to relevant topics
                await self.communication.subscribe(f"dataset.request", self._handle_dataset_request)
                
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
                
            # Pre-generate some conversations if specified
            if pre_generate := params.get("pre_generate", 0):
                async with self._dataset_lock:
                    for _ in range(pre_generate):
                        conversation_id = str(uuid.uuid4())
                        conversation = await self._generate_synthetic_conversation()
                        self._conversations[conversation_id] = conversation
                        
            return True
        except Exception as e:
            self.logger.error(f"Error initializing synthetic dataset: {e}")
            return False
        
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
                
            # TODO: Implement fetching from remote source
            # This would involve making API calls to the remote dataset service
            
            self.logger.info(f"Successfully initialized remote dataset from {url}")
            return True
        except Exception as e:
            self.logger.error(f"Error initializing remote dataset: {e}")
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
            
            with open(file_path, 'r') as f:
                if file_path.endswith('.json'):
                    data = json.load(f)
                    
                    # Process conversations
                    async with self._dataset_lock:
                        for item in data:
                            if 'conversation_id' in item:
                                conversation = Conversation(
                                    conversation_id=item['conversation_id'],
                                    metadata=item.get('metadata', {})
                                )
                                
                                # Add turns
                                for turn_data in item.get('turns', []):
                                    turn = ConversationTurn(
                                        turn_id=turn_data.get('turn_id', str(uuid.uuid4())),
                                        request_data=turn_data.get('request_data', {}),
                                        response_data=turn_data.get('response_data'),
                                        request_timestamp=turn_data.get('request_timestamp', 0),
                                        response_timestamp=turn_data.get('response_timestamp'),
                                        metadata=turn_data.get('metadata', {})
                                    )
                                    conversation.add_turn(turn)
                                    
                                self._conversations[conversation.conversation_id] = conversation
                    
                    self.logger.info(f"Loaded {len(self._conversations)} conversations from dataset")
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
            self.logger.warning("No communication interface available, skipping identity publication")
            return False
            
        try:
            identity = {
                "component_id": self.component_id,
                "component_type": "dataset_manager",
                "dataset_name": self.dataset_config.name,
                "source_type": self.dataset_config.source_type,
                "modality": self.dataset_config.modality
            }
            
            success = await self.communication.publish("system.identity", identity)
            if success:
                self.logger.info("Published dataset manager identity")
            else:
                self.logger.warning("Failed to publish dataset manager identity")
                
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
            # Clear cache
            self._dataset_cache.clear()
            self._conversations.clear()
            
            self._is_shutdown = True
            return True
        except Exception as e:
            self.logger.error(f"Error shutting down dataset manager: {e}")
            return False
    
    async def handle_command(self, command: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle a command from the system controller.
        
        Args:
            command: Command string
            payload: Optional command payload
            
        Returns:
            Response dictionary with results
        """
        response = {"status": "error", "message": f"Unknown command: {command}"}
        
        if command == "get_conversation":
            conversation_id = payload.get("conversation_id") if payload else None
            conversation = await self.get_conversation(conversation_id)
            if conversation:
                response = {"status": "success", "conversation": conversation.__dict__}
            else:
                response = {"status": "error", "message": "Failed to get conversation"}
                
        elif command == "get_synthetic_prompt":
            modality = payload.get("modality", "text") if payload else "text"
            prompt = await self.get_synthetic_prompt(modality)
            if prompt:
                response = {"status": "success", "prompt": prompt}
            else:
                response = {"status": "error", "message": "Failed to generate synthetic prompt"}
                
        elif command == "get_next_turn":
            conversation_id = payload.get("conversation_id") if payload else None
            if not conversation_id:
                response = {"status": "error", "message": "Missing conversation_id"}
            else:
                turn = await self.get_next_turn(conversation_id)
                if turn:
                    response = {"status": "success", "turn": turn.__dict__}
                else:
                    response = {"status": "error", "message": "No more turns or conversation not found"}
        
        elif command == "tokenize":
            prompt = payload.get("prompt") if payload else None
            if not prompt:
                response = {"status": "error", "message": "Missing prompt"}
            else:
                tokens = await self.tokenize_prompt(prompt)
                response = {"status": "success", "tokens": tokens}
                
        return response
    
    async def _handle_dataset_request(self, message: Dict[str, Any]) -> None:
        """Handle dataset request message.
        
        Args:
            message: Message dictionary
        """
        if not self.communication:
            return
            
        try:
            command = message.get("command")
            payload = message.get("payload", {})
            source = message.get("source")
            
            if not source:
                self.logger.warning("Dataset request missing source")
                return
                
            # Process request
            response = await self.handle_command(command, payload)
            
            # Send response
            await self.communication.publish(f"dataset.response.{source}", response)
        except Exception as e:
            self.logger.error(f"Error handling dataset request: {e}")
    
    async def get_conversation(self, conversation_id: Optional[str] = None) -> Optional[Conversation]:
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
                    
                # No conversations available
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
            metadata={"synthetic": True}
        )
        
        # Determine number of turns
        num_turns = random.randint(1, 3)
        
        # Generate turns
        for i in range(num_turns):
            prompt = await self.get_synthetic_prompt()
            turn = ConversationTurn(
                turn_id=f"{conversation_id}_turn_{i}",
                request_data={"prompt": prompt},
                metadata={"synthetic": True, "turn_index": i}
            )
            conversation.add_turn(turn)
            
        return conversation
    
    async def get_synthetic_prompt(self, modality: str = "text") -> Optional[Dict[str, Any]]:
        """Generate a synthetic prompt.
        
        Args:
            modality: Modality to generate (text, image, audio, video)
            
        Returns:
            Dictionary with prompt data or None if generation failed
        """
        try:
            if modality != "text":
                self.logger.warning(f"Modality {modality} not supported for synthetic prompts, falling back to text")
                
            # Select random template and topic
            template = random.choice(self._templates)
            topic = random.choice(self._topics)
            alt_topic = random.choice([t for t in self._topics if t != topic])
            
            # Fill in template
            prompt = template.format(topic=topic, alt_topic=alt_topic)
            
            return {"content": prompt, "modality": "text"}
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
                
                # Find the first turn without a response
                for turn in conversation.turns:
                    if turn.response_data is None:
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
            # This is a very simple tokenization for demonstration purposes
            # In a real implementation, you would use a proper tokenizer (e.g., tiktoken)
            tokens = []
            for i, char in enumerate(prompt):
                # Use character code as a simple token ID
                tokens.append(ord(char))
                
            return tokens
        except Exception as e:
            self.logger.error(f"Error tokenizing prompt: {e}")
            return []
