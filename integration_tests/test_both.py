#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import asyncio

from integration_tests.aiohttp_test import main as aiohttp_main
from integration_tests.httpx_test import main as httpx_main


async def main():
    print("\nRunning aiohttp test...")
    await aiohttp_main()
    print("\nRunning httpx test...")
    await httpx_main()


if __name__ == "__main__":
    asyncio.run(main())
