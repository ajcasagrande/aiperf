# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import random
import time

from fastapi import FastAPI

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.base_component_service import BaseComponentService
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import ComposerType, ServiceType
from aiperf.common.enums.command_enums import CommandType
from aiperf.common.exceptions import AIPerfError
from aiperf.common.factories import ComposerFactory, ServiceFactory
from aiperf.common.hooks import on_command, on_start
from aiperf.common.messages import (
    DatasetConfiguredNotification,
    ProfileConfigureCommand,
)
from aiperf.common.models import Conversation
from aiperf.common.models.dataset_models import Turn
from aiperf.common.protocols import ServiceProtocol
from aiperf.common.tokenizer import Tokenizer

DATASET_CONFIGURATION_TIMEOUT = 300.0


app = FastAPI()


_dataset: dict[str, Conversation] = {}
_session_ids_cache: list[str] = []
_conversation_query_random = random.Random(0)
_dataset_configured = asyncio.Event()
_logger = AIPerfLogger(__name__)


@implements_protocol(ServiceProtocol)
@ServiceFactory.register(ServiceType.DATASET_MANAGER, override_priority=100)
class DatasetManagerFastAPI(BaseComponentService):
    """
    The DatasetManager primary responsibility is to manage the data generation or acquisition.
    For synthetic generation, it contains the code to generate the prompts or tokens.
    It will have an API for dataset acquisition of a dataset if available in a remote repository or database.
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig,
        service_id: str | None = None,
    ) -> None:
        super().__init__(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
        )
        _logger.debug("Dataset manager __init__")
        self.user_config = user_config
        self.tokenizer: Tokenizer | None = None

    @on_start
    async def _start_fastapi(self) -> None:
        """Start the dataset manager."""
        _logger.notice("Dataset manager _start_fastapi")
        from uvicorn.config import Config
        from uvicorn.server import Server

        config = Config(app, host="0.0.0.0", port=9090, access_log=False, workers=10)
        server = Server(config=config)
        await server.serve()

    @on_command(CommandType.PROFILE_CONFIGURE)
    async def _profile_configure_command(
        self, message: ProfileConfigureCommand
    ) -> None:
        """Configure the dataset."""
        _logger.info(f"Configuring dataset for {self.service_id}")
        begin = time.perf_counter()
        await self._configure_dataset()
        _logger.info(f"Dataset configured in {time.perf_counter() - begin:.2f} seconds")

    async def _configure_dataset(self) -> None:
        if self.user_config is None:
            raise self._service_error("User config is required for dataset manager")

        _dataset_configured.clear()
        if self.user_config.input.file:
            composer_type = ComposerType.CUSTOM
            _logger.debug(
                f"Detected input file '{self.user_config.input.file}'. Setting the composer type to {ComposerType.CUSTOM}."
            )
        else:
            composer_type = ComposerType.SYNTHETIC
            _logger.debug(
                f"No input file detected. Setting the composer type to {ComposerType.SYNTHETIC}."
            )

        tokenizer_name = self.user_config.tokenizer.name
        if tokenizer_name is None:
            # TODO: What do we do if there are multiple models?
            # How will we know which tokenizer to use?
            tokenizer_name = self.user_config.endpoint.model_names[0]

        tokenizer = Tokenizer.from_pretrained(
            tokenizer_name,
            trust_remote_code=self.user_config.tokenizer.trust_remote_code,
            revision=self.user_config.tokenizer.revision,
        )
        composer = ComposerFactory.create_instance(
            composer_type,
            config=self.user_config,
            tokenizer=tokenizer,
        )
        conversations = composer.create_dataset()
        global _dataset
        global _session_ids_cache
        _dataset = {conv.session_id: conv for conv in conversations}
        _session_ids_cache = list(_dataset.keys())

        _dataset_configured.set()
        await self.publish(
            DatasetConfiguredNotification(
                service_id=self.service_id,
            ),
        )

    # @staticmethod
    # @app.get("/conversation/None")
    # async def _handle_any_conversation_request() -> Conversation:
    #     """Handle a conversation request."""
    #     return DatasetManagerFastAPI._return_any_conversation()

    @staticmethod
    @app.get("/conversation/{conversation_id}")
    async def _handle_conversation_request(
        conversation_id: str | None = None,
    ) -> Conversation:
        """Handle a conversation request."""
        # _logger.info(
        #     f"Handling conversation request: {conversation_id}"
        # )

        if conversation_id is None or conversation_id == "None":
            response = DatasetManagerFastAPI._return_any_conversation()
        else:
            response = DatasetManagerFastAPI._return_conversation_by_id(
                conversation_id=conversation_id,
            )
        return response

    @staticmethod
    def _return_any_conversation() -> Conversation:
        """Return any conversation from the dataset based on the user specified method."""

        # TODO: Implement the user specified method (random, round robin, etc.)
        session_id = _conversation_query_random.choice(_session_ids_cache)
        conversation = _dataset[session_id]
        return conversation

    @staticmethod
    def _return_conversation_by_id(conversation_id: str) -> Conversation:
        """Return a conversation if it exists, otherwise raise an error."""

        if conversation_id not in _dataset:
            raise AIPerfError(
                f"Conversation {conversation_id} not found in dataset.",
            )

        conversation = _dataset[conversation_id]
        return conversation

    @staticmethod
    @app.get("/conversation/{conversation_id}/turn/{turn_index}")
    async def _handle_conversation_turn_request(
        conversation_id: str, turn_index: int
    ) -> Turn:
        """Handle a turn request."""
        _logger.debug(f"Handling turn request: {conversation_id}, {turn_index}")

        if conversation_id not in _dataset:
            raise AIPerfError(
                f"Conversation {conversation_id} not found in dataset.",
            )

        conversation = _dataset[conversation_id]
        if turn_index >= len(conversation.turns):
            raise AIPerfError(
                f"Turn index {turn_index} is out of range for conversation {conversation_id}.",
            )

        turn = conversation.turns[turn_index]

        return turn

    @staticmethod
    @app.get("/dataset/timing")
    async def _handle_dataset_timing_request() -> list[tuple[int, str]]:
        """Handle a dataset timing request."""
        _logger.info("Handling dataset timing request")

        await DatasetManagerFastAPI._wait_for_dataset_configuration()

        if not _dataset:
            raise AIPerfError(
                "Dataset is empty and must be configured before handling timing requests.",
            )

        timing_dataset = []
        for conversation_id, conversation in _dataset.items():
            for turn in conversation.turns:
                timing_dataset.append((turn.timestamp, conversation_id))

        return timing_dataset

    @staticmethod
    async def _wait_for_dataset_configuration() -> None:
        """Wait for the dataset to be configured if it is not already."""
        if not _dataset_configured.is_set():
            _logger.info(
                "Dataset not configured. Waiting for dataset to be configured..."
            )
            await asyncio.wait_for(
                _dataset_configured.wait(),
                timeout=DATASET_CONFIGURATION_TIMEOUT,
            )


def main() -> None:
    """Main entry point for the dataset manager."""

    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(DatasetManagerFastAPI)


if __name__ == "__main__":
    main()
