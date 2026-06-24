# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio

import pytest

from aiperf.timing.inner_semaphore import InnerSessionLimiter


@pytest.mark.asyncio
async def test_cap_blocks_beyond_peak():
    lim = InnerSessionLimiter()
    lim.open_tree("t", 2)
    a = await lim.acquire("t")
    b = await lim.acquire("t")
    assert lim.in_flight("t") == 2
    # third acquire would block; schedule it and confirm it doesn't complete
    task = asyncio.ensure_future(lim.acquire("t"))
    await asyncio.sleep(0)
    assert not task.done()
    lim.release(a)
    c = await task
    assert lim.in_flight("t") == 2
    lim.release(b)
    lim.release(c)
    assert lim.in_flight("t") == 0


@pytest.mark.asyncio
async def test_idempotent_release_no_overflow():
    lim = InnerSessionLimiter()
    lim.open_tree("t", 1)
    tok = await lim.acquire("t")
    lim.release(tok)
    lim.release(tok)  # double release must be a no-op
    assert lim.in_flight("t") == 0
    # capacity is still exactly 1, not 2
    await lim.acquire("t")
    assert lim.in_flight("t") == 1


@pytest.mark.asyncio
async def test_unknown_tree_is_noop_unbounded():
    lim = InnerSessionLimiter()
    tok = await lim.acquire("missing")  # no open_tree -> no cap
    assert tok is None
    lim.release(tok)  # no-op


@pytest.mark.asyncio
async def test_queued_count_tracks_waiters():
    lim = InnerSessionLimiter()
    lim.open_tree("t", 1)
    await lim.acquire("t")
    task = asyncio.ensure_future(lim.acquire("t"))
    await asyncio.sleep(0)
    assert lim.queued("t") == 1
    task.cancel()
