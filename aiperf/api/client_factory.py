import logging
from typing import Any, Dict, Optional, Type, Union

from .base_client import BaseClient
from .openai_client import OpenAIClient
from ..config.config_models import EndpointConfig, AuthConfig

logger = logging.getLogger(__name__)


class ClientFactory:
    """Factory for creating API clients.

    Responsible for creating the appropriate API client based on the
    API type specified in the endpoint configuration.
    """

    # Registry of API client types
    _client_types: Dict[str, Type[BaseClient]] = {
        "openai": OpenAIClient,
        # Add other client types here as they are implemented
    }

    @classmethod
    def register_client_type(
        cls, api_type: str, client_class: Type[BaseClient]
    ) -> None:
        """Register a new client type.

        Args:
            api_type: API type string
            client_class: Client class
        """
        cls._client_types[api_type] = client_class
        logger.info(f"Registered client type: {api_type}")

    @classmethod
    def create_client(
        cls,
        api_type: str,
        url: str,
        headers: Dict[str, str],
        auth: Union[Dict[str, Any], AuthConfig],
        timeout: float,
    ) -> Optional[BaseClient]:
        """Create a client for the specified API type and parameters.

        Args:
            api_type: API type string
            url: API endpoint URL
            headers: HTTP headers
            auth: Authentication parameters (either a dict or AuthConfig)
            timeout: Request timeout in seconds

        Returns:
            Client instance or None if creation failed
        """
        api_type = api_type.lower()

        if api_type not in cls._client_types:
            logger.error(f"Unknown API type: {api_type}")
            return None

        try:
            client_class = cls._client_types[api_type]
            # Handle auth being either a dict or AuthConfig object
            auth_config = auth
            if isinstance(auth, dict):
                auth_config = AuthConfig(**auth)
            elif not isinstance(auth, AuthConfig) and auth is not None:
                logger.error(f"Invalid auth type: {type(auth)}")
                return None

            config = EndpointConfig(
                name="generated",
                url=url,
                api_type=api_type,
                headers=headers,
                auth=auth_config,
                timeout=timeout,
            )
            return client_class(config)
        except Exception as e:
            logger.error(f"Error creating client for API type {api_type}: {e}")
            return None
