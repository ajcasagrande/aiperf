#!/usr/bin/env python3
import asyncio
import logging
import zmq.asyncio
import json
import time
import sys
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] test %(levelname)s: %(message)s')
logger = logging.getLogger('auto_shutdown_test')

# ZMQ addresses - match the ones used in utils.py
PRESENCE_CHANNEL = "tcp://127.0.0.1:5556"
RESULTS_CHANNEL = "tcp://127.0.0.1:5558"

async def simulate_worker(num_results=10, delay=0.5):
    """Simulate a worker publishing results to trigger auto-shutdown"""
    ctx = zmq.asyncio.Context.instance()
    
    # Create presence socket
    presence_pub = ctx.socket(zmq.PUB)
    presence_pub.connect(PRESENCE_CHANNEL)
    logger.info(f"Connected to presence channel: {PRESENCE_CHANNEL}")
    
    # Create results socket
    results_pub = ctx.socket(zmq.PUB)
    results_pub.connect(RESULTS_CHANNEL)
    logger.info(f"Connected to results channel: {RESULTS_CHANNEL}")
    
    try:
        # First announce our presence
        component_name = "test_component"
        logger.info(f"Announcing presence as {component_name}")
        
        # Wait a bit to ensure the subscriber is ready
        await asyncio.sleep(1)
        
        # Send initial presence message
        await presence_pub.send_json({"component": component_name, "count": 0})
        
        # Wait to make sure system controller has time to receive the message
        await asyncio.sleep(2)
        
        # Send presence messages periodically
        for i in range(1, 6):
            msg = {"component": component_name, "count": i}
            logger.info(f"Sending presence message: {msg}")
            await presence_pub.send_json(msg)
            await asyncio.sleep(1)
        
        # Now simulate sending all expected results
        logger.info(f"Sending {num_results} result messages to trigger auto-shutdown")
        for i in range(num_results):
            result = {
                "seq": i,
                "data_id": i,
                "request_timestamp": time.time() - delay,
                "response_timestamp": time.time(),
                "latency": delay,
                "response": {"status": "success", "value": i}
            }
            logger.info(f"Sending result {i+1}/{num_results}")
            await results_pub.send_json(result)
            await asyncio.sleep(delay)
        
        logger.info("All results sent. Waiting for system to auto-shutdown...")
        # Keep sending presence messages to show we're still alive
        for i in range(6, 20):
            msg = {"component": component_name, "count": i}
            logger.info(f"Sending presence message: {msg}")
            await presence_pub.send_json(msg)
            await asyncio.sleep(1)
    
    finally:
        # Clean up
        presence_pub.close()
        results_pub.close()
        logger.info("Test complete")

async def main():
    parser = argparse.ArgumentParser(description="Test auto-shutdown functionality")
    parser.add_argument("--num-results", type=int, default=10, help="Number of results to simulate")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between results")
    args = parser.parse_args()
    
    logger.info("Starting auto-shutdown test")
    logger.info(f"Will send {args.num_results} results with {args.delay}s delay")
    logger.info("Run the AIPerf system (python run.py) in another terminal first")
    logger.info("The system should auto-shutdown after receiving all results")
    
    # Give user time to read instructions
    await asyncio.sleep(3)
    
    # Start the simulation
    await simulate_worker(args.num_results, args.delay)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        logger.error(f"Error in test: {e}") 