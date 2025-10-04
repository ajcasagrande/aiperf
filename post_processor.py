# post_processor.py
import os
import argparse
import json
import time
import statistics
import sys
import logging

import zmq.asyncio
from config import load_config
from utils import PRESENCE_CHANNEL, CONTROL_CHANNEL, RESULTS_CHANNEL, create_pub_socket, create_sub_socket

COMPONENT_NAME = "post_processor"
logger = logging.getLogger(COMPONENT_NAME)
# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(name)s %(levelname)s: %(message)s')

async def announce_presence(pub):
    await pub.send_json({"component": COMPONENT_NAME})

async def run():
    parser = argparse.ArgumentParser(description="AIPerf Post Processor")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    args = parser.parse_args()
    cfg = load_config(args.config)

    # Report file can be overridden via env for Kubernetes
    report_file = os.getenv("AIPERF_REPORT_FILE", "report.json")

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

            sub_results = create_sub_socket(RESULTS_CHANNEL)
            logger.info("Collecting %d results for analysis", expected)

            results = []
            count = 0
            # Collect expected results
            while count < expected:
                try:
                    res = await sub_results.recv_json()
                except Exception as e:
                    logger.error("Error receiving result: %s", e)
                    break
                results.append(res)
                count += 1
            if not results:
                logger.warning("No results collected, skipping metrics")
                continue

            # Compute metrics
            latencies = [r.get("latency", 0) for r in results]
            req_ts = [r.get("request_timestamp", 0) for r in results]
            resp_ts = [r.get("response_timestamp", 0) for r in results]
            total_time = max(resp_ts) - min(req_ts) if resp_ts and req_ts else 0

            metrics = {}
            metrics["count"] = len(latencies)
            metrics["min_latency"] = min(latencies)
            metrics["max_latency"] = max(latencies)
            metrics["avg_latency"] = statistics.mean(latencies)
            metrics["median_latency"] = statistics.median(latencies)
            # percentiles
            sorted_lat = sorted(latencies)
            n = len(sorted_lat)
            def percentile(p):
                idx = int(p * n)
                if idx < 0:
                    idx = 0
                if idx >= n:
                    idx = n - 1
                return sorted_lat[idx]
            metrics["p90_latency"] = percentile(0.90)
            metrics["p99_latency"] = percentile(0.99)
            metrics["total_duration"] = total_time
            metrics["throughput"] = len(latencies) / total_time if total_time > 0 else None

            # Write report
            try:
                with open(report_file, "w") as f:
                    json.dump(metrics, f, indent=2)
                logger.info("Metrics written to %s", report_file)
                logger.info(json.dumps(metrics, indent=2))
            except Exception as e:
                logger.error("Error writing report: %s", e)

        elif mtype == "stop":
            logger.info("Stop received, shutting down")
            break

if __name__ == "__main__":
    import asyncio
    asyncio.run(run()) 