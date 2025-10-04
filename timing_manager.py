# timing_manager.py
import logging
import asyncio
import argparse
import random
import time
import sys

import zmq.asyncio
from config import load_config
from utils import PRESENCE_CHANNEL, CONTROL_CHANNEL, TIMING_CHANNEL, create_pub_socket, create_sub_socket

COMPONENT_NAME = "timing_manager"
logger = logging.getLogger(COMPONENT_NAME)
# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(name)s %(levelname)s: %(message)s')

async def announce_presence(pub):
    await pub.send_json({"component": COMPONENT_NAME})

async def generate_credits(distribution: str, rate: float, pub_timing: zmq.asyncio.Socket):
    seq = 0
    logger.info("Generating %s credits at %s per second", distribution, rate)
    try:
        while True:
            if distribution == "poisson":
                interval = random.expovariate(rate)
            elif distribution == "uniform":
                interval = random.uniform(0, 2.0 / rate)
            elif distribution == "normal":
                mean = 1.0 / rate
                std = mean / 3.0
                interval = max(0.0, random.gauss(mean, std))
            else:
                logger.error("Unknown distribution '%s'", distribution)
                return
            await asyncio.sleep(interval)
            timestamp = time.time()
            await pub_timing.send_json({"seq": seq, "timestamp": timestamp})
            seq += 1
    except asyncio.CancelledError:
        logger.info("Credit generation cancelled")
        raise

async def run():
    parser = argparse.ArgumentParser(description="AIPerf Timing Manager")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    args = parser.parse_args()
    cfg = load_config(args.config)

    # Set up presence
    logger.info("Creating presence PUB socket connecting to %s", PRESENCE_CHANNEL)
    pub_presence = create_pub_socket(PRESENCE_CHANNEL, bind=False)
    
    # Set up control subscription
    logger.info("Creating control SUB socket connecting to %s", CONTROL_CHANNEL.replace("5557", "5562"))
    sub_control = create_sub_socket(CONTROL_CHANNEL.replace("5557", "5562"), bind=False)

    # Announce presence
    await announce_presence(pub_presence)
    logger.info("Presence announced")

    gen_task = None
    try:
        while True:
            msg = await sub_control.recv_json()
            mtype = msg.get("type")
            if mtype == "start":
                # Cancel any existing generator
                if gen_task:
                    gen_task.cancel()
                    await gen_task

                raw = msg.get("config", {})
                timing_cfg = raw.get("timing", {})
                distribution = timing_cfg.get("distribution", cfg.timing.distribution)
                rate = timing_cfg.get("rate", cfg.timing.rate)
                pub_timing = create_pub_socket(TIMING_CHANNEL)

                # Start credit generation
                gen_task = asyncio.create_task(generate_credits(distribution, rate, pub_timing))

            elif mtype == "stop":
                logger.info("Stop received, shutting down")
                if gen_task:
                    gen_task.cancel()
                    await gen_task
                break
    except asyncio.CancelledError:
        pass

if __name__ == "__main__":
    asyncio.run(run()) 