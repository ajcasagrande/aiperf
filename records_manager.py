# records_manager.py
import asyncio
import argparse
import json
import sys
import logging

import zmq.asyncio
from config import load_config
from utils import PRESENCE_CHANNEL, CONTROL_CHANNEL, RESULTS_CHANNEL, create_pub_socket, create_sub_socket

COMPONENT_NAME = "records_manager"
logger = logging.getLogger(COMPONENT_NAME)
# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(name)s %(levelname)s: %(message)s')

async def announce_presence(pub):
    await pub.send_json({"component": COMPONENT_NAME})

async def run():
    parser = argparse.ArgumentParser(description="AIPerf Records Manager")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    args = parser.parse_args()
    cfg = load_config(args.config)

    # Set up presence
    logger.info("Creating presence PUB socket connecting to %s", PRESENCE_CHANNEL)
    pub_presence = create_pub_socket(PRESENCE_CHANNEL, bind=False)
    
    # Set up control subscription
    logger.info("Creating control SUB socket connecting to %s", CONTROL_CHANNEL.replace("5557", "5562"))
    sub_control = create_sub_socket(CONTROL_CHANNEL.replace("5557", "5562"), bind=False)

    await announce_presence(pub_presence)
    logger.info("Presence announced")

    while True:
        msg = await sub_control.recv_json()
        mtype = msg.get("type")
        if mtype == "start":
            raw = msg.get("config", {})
            dataset_cfg = raw.get("dataset", {})
            expected = dataset_cfg.get("size", cfg.dataset.size)
            output_file = raw.get("records", {}).get("output_file", cfg.records.output_file)

            sub_results = create_sub_socket(RESULTS_CHANNEL)
            logger.info("Writing results to %s", output_file)
            try:
                with open(output_file, "w") as f:
                    count = 0
                    while count < expected:
                        result = await sub_results.recv_json()
                        f.write(json.dumps(result) + "\n")
                        f.flush()
                        count += 1
                        if count % 10 == 0:
                            logger.info("Recorded %d/%d results", count, expected)
                logger.info("Completed writing %d results", expected)
            except Exception as e:
                logger.error("Error writing results: %s", e)

        elif mtype == "stop":
            logger.info("Stop received, shutting down")
            break

if __name__ == "__main__":
    asyncio.run(run()) 