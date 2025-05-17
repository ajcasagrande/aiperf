#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
import asyncio
import logging

from dynamo.sdk import DYNAMO_IMAGE, service
from dynamo.sdk.core.decorators.endpoint import dynamo_endpoint
from dynamo.sdk.lib.config import ServiceConfig as DynamoServiceConfig
from dynamo.sdk.lib.decorators import async_on_start
from pydantic import BaseModel

from aiperf.common.config.service_config import ServiceConfig
from aiperf.services.records_manager.records_manager import RecordsManager

logger = logging.getLogger(__name__)


@service(
    dynamo={
        "namespace": "aiperf",
    },
    resource={"cpu": 1, "memory": "500Mi"},
    workers=10,
    image=DYNAMO_IMAGE,
    static=True,
)
class DynamoRecordsManager:
    def __init__(self) -> None:
        logger.info("Starting records manager")
        config = DynamoServiceConfig.get_instance()
        self.message = config.get("RecordsManager", {}).get(
            "message", "records_manager"
        )
        logger.info(f"Records manager config message: {self.message}")
        self.records_manager = RecordsManager(ServiceConfig())

    @async_on_start
    async def init(self):
        await asyncio.create_task(self.records_manager.run())

    @dynamo_endpoint()
    async def initialize(self, input: BaseModel) -> BaseModel:
        await self.records_manager.initialize()
        return BaseModel()

    @dynamo_endpoint()
    async def start(self, input: BaseModel) -> BaseModel:
        await self.records_manager.start()
        return BaseModel()

    @dynamo_endpoint()
    async def run(self, input: BaseModel) -> BaseModel:
        await asyncio.create_task(self.records_manager.run())
        return BaseModel()

    @dynamo_endpoint()
    async def stop(self, input: BaseModel) -> BaseModel:
        await self.records_manager.stop()
        return BaseModel()
