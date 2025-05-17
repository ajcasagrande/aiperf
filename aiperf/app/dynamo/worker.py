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

from dynamo.sdk import DYNAMO_IMAGE, dynamo_endpoint, service
from dynamo.sdk.lib.config import ServiceConfig as DynamoServiceConfig
from dynamo.sdk.lib.decorators import async_on_start
from pydantic import BaseModel

from aiperf.common.config.service_config import ServiceConfig
from aiperf.services.worker.worker import Worker


class RequestType(BaseModel):
    text: str


class ResponseType(BaseModel):
    text: str


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
class DynamoWorker:
    def __init__(self) -> None:
        logger.info("Starting worker")
        config = DynamoServiceConfig.get_instance()
        self.message = config.get("Worker", {}).get("message", "worker")
        logger.info(f"Worker config message: {self.message}")
        self.worker = Worker(ServiceConfig())

    @async_on_start
    async def init(self):
        await asyncio.create_task(self.worker.run())

    @dynamo_endpoint()
    async def run(self, input: RequestType) -> ResponseType:
        await asyncio.create_task(self.worker.run())
        return ResponseType(text=input.text)

    @dynamo_endpoint()
    async def start(self, input: RequestType) -> ResponseType:
        await asyncio.create_task(self.worker.start())
        return ResponseType(text=input.text)
