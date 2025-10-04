# worker_manager.py
import asyncio
import argparse
import time
import sys
import logging

import zmq.asyncio
import aiohttp

from config import load_config
from utils import (
    PRESENCE_CHANNEL, CONTROL_CHANNEL, TIMING_CHANNEL,
    DATASET_CHANNEL, RESULTS_CHANNEL,
    create_pub_socket, create_sub_socket
)

COMPONENT_NAME = "worker_manager"
logger = logging.getLogger(COMPONENT_NAME)
# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(name)s %(levelname)s: %(message)s')

async def announce_presence(pub):
    await pub.send_json({"component": COMPONENT_NAME})

class WorkerManager:
    def __init__(self, config):
        self.config = config
        self.data_queue = asyncio.Queue()
        self.credit_queue = asyncio.Queue()
        self.sem = asyncio.Semaphore(self.config.worker.concurrency)
        self.tasks = set()
        self.session = None
        self.pub_results = None
        self.running = True

    async def start(self):
        # ZMQ context implicitly via utils
        # Set up presence
        logger.info("Creating presence PUB socket connecting to %s", PRESENCE_CHANNEL)
        pub_presence = create_pub_socket(PRESENCE_CHANNEL, bind=False)
        
        # Set up control subscription
        logger.info("Creating control SUB socket connecting to %s", CONTROL_CHANNEL.replace("5557", "5562"))
        sub_control = create_sub_socket(CONTROL_CHANNEL.replace("5557", "5562"), bind=False)

        while True:
            msg = await sub_control.recv_json()
            mtype = msg.get("type")
            if mtype == "start":
                # Load updated config
                raw = msg.get("config", {})
                worker_cfg = raw.get("worker", {})
                endpoint = worker_cfg.get("endpoint", self.config.worker.endpoint)
                concurrency = worker_cfg.get("concurrency", self.config.worker.concurrency)
                self.config.worker.endpoint = endpoint
                self.config.worker.concurrency = concurrency
                # Setup HTTP session
                self.session = aiohttp.ClientSession()
                # Setup results publisher
                self.pub_results = create_pub_socket(RESULTS_CHANNEL)
                # Start listeners and dispatcher
                self.data_task = asyncio.create_task(self._listen_channel(DATASET_CHANNEL, self.data_queue))
                self.credit_task = asyncio.create_task(self._listen_channel(TIMING_CHANNEL, self.credit_queue))
                self.dispatch_task = asyncio.create_task(self._dispatch_loop())
                logger.info("Started with endpoint=%s, concurrency=%d", endpoint, concurrency)

            elif mtype == "stop":
                logger.info("Stop received, shutting down")
                self.running = False
                # Cancel tasks
                for t in (self.data_task, self.credit_task, self.dispatch_task):
                    t.cancel()
                break

        # Wait for all worker tasks to finish
        await asyncio.gather(*self.tasks, return_exceptions=True)
        if self.session:
            await self.session.close()
        logger.info("Shutdown complete")

    async def _listen_channel(self, channel, queue):
        sock = create_sub_socket(channel)
        # SUBSCRIBE to all topics by default
        while self.running:
            try:
                msg = await sock.recv_json()
                await queue.put(msg)
            except asyncio.CancelledError:
                break

    async def _dispatch_loop(self):
        while self.running:
            try:
                credit = await self.credit_queue.get()
            except asyncio.CancelledError:
                break
            # Get data to match credit
            try:
                data = await self.data_queue.get()
            except asyncio.CancelledError:
                break
            # Acquire semaphore for concurrency
            await self.sem.acquire()
            # Schedule worker
            task = asyncio.create_task(self._run_worker(credit, data))
            self.tasks.add(task)
            task.add_done_callback(self._on_task_done)

    def _on_task_done(self, task):
        # Release semaphore
        self.sem.release()
        # Remove from active tasks
        self.tasks.discard(task)
        # Log any exception
        if task.cancelled():
            return
        if task.exception():
            logger.error("Task exception: %s", task.exception())

    async def _run_worker(self, credit, data):
        start_ts = time.time()
        seq = credit.get("seq")
        data_id = data.get("id")
        payload = data.get("payload")
        # Send request
        try:
            async with self.session.post(
                self.config.worker.endpoint,
                json={"data": payload}
            ) as resp:
                try:
                    response_content = await resp.json()
                except Exception:
                    response_content = await resp.text()
        except Exception as e:
            response_content = {"error": str(e)}
        end_ts = time.time()
        latency = end_ts - start_ts
        # Publish result
        result = {
            "seq": seq,
            "data_id": data_id,
            "request_timestamp": start_ts,
            "response_timestamp": end_ts,
            "latency": latency,
            "response": response_content
        }
        await self.pub_results.send_json(result)

async def main():
    parser = argparse.ArgumentParser(description="AIPerf Worker Manager")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    args = parser.parse_args()
    config = load_config(args.config)
    manager = WorkerManager(config)
    await manager.start()

if __name__ == "__main__":
    asyncio.run(main()) 