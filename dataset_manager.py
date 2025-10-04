# dataset_manager.py
import asyncio
import argparse
import json
import sys
import logging

from config import DataConfig, TimingConfig, WorkerConfig, RecordsConfig, Config, load_config
from utils import (PRESENCE_CHANNEL, CONTROL_CHANNEL, DATASET_CHANNEL,
                   create_pub_socket, create_sub_socket)
import zmq.asyncio

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s] %(name)s %(levelname)s: %(message)s')

COMPONENT_NAME = "dataset_manager"
logger = logging.getLogger(COMPONENT_NAME)

async def announce_presence(pub):
    await pub.send_json({"component": COMPONENT_NAME})

async def run():
    parser = argparse.ArgumentParser(description="AIPerf Dataset Manager")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    args = parser.parse_args()
    # We load config to allow fallback or future extensions
    cfg = load_config(args.config)

    # Setup ZMQ sockets
    logger.info("Creating presence PUB socket connecting to %s", PRESENCE_CHANNEL)
    pub_presence = create_pub_socket(PRESENCE_CHANNEL, bind=False)
    
    # Set up control subscription
    logger.info("Creating control SUB socket connecting to %s", CONTROL_CHANNEL.replace("5557", "5562"))
    sub_control = create_sub_socket(CONTROL_CHANNEL.replace("5557", "5562"), bind=False)

    # Announce presence
    logger.info("Announcing dataset manager presence...")
    message = {"component": COMPONENT_NAME}
    logger.debug("Sending presence message: %s", message)
    await pub_presence.send_json(message)
    logger.info("Dataset manager presence announced")

    # Control loop
    while True:
        msg = await sub_control.recv_json()
        mtype = msg.get("type")
        if mtype == "start":
            raw = msg.get("config", {})
            data_cfg = raw.get("dataset", {})
            size = data_cfg.get("size", cfg.dataset.size)
            synthetic = data_cfg.get("synthetic", cfg.dataset.synthetic)

            # Create dataset publisher
            pub_data = create_pub_socket(DATASET_CHANNEL)

            # Generate or load dataset
            for i in range(size):
                if synthetic:
                    data = {"id": i, "payload": f"payload-{i}"}
                else:
                    # No real dataset path provided
                    logger.error("Real dataset not supported: synthetic=False")
                    sys.exit(1)
                # Publish data as JSON
                await pub_data.send_json(data)
            logger.info("Published %d data items", size)

        elif mtype == "stop":
            logger.info("Stop received, shutting down")
            break

if __name__ == "__main__":
    asyncio.run(run()) 