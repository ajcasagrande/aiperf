# system_controller.py
import asyncio
import argparse
import json
from dataclasses import asdict
import logging
import time
import signal

import zmq.asyncio

from config import load_config
from utils import (PRESENCE_CHANNEL, CONTROL_CHANNEL, RESULTS_CHANNEL,
                   create_pub_socket, create_sub_socket)

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(name)s %(levelname)s: %(message)s')

COMPONENT_NAME = "system_controller"
logger = logging.getLogger(COMPONENT_NAME)

async def announce_presence(pub_presence):
    # Announce this component's presence
    await pub_presence.send_json({"component": COMPONENT_NAME})

async def wait_for_components(sub_presence, required):
    present = {COMPONENT_NAME}
    # Subscribe to all presence messages
    sub_presence.setsockopt_string(zmq.SUBSCRIBE, "")
    logger.info("Waiting for components: %s", required - present)
    
    # Set a timeout of 60 seconds for all components to respond
    timeout = 60
    start_time = time.time()
    
    while present != required:
        try:
            # No timeout for debugging
            logger.debug("Waiting for next presence message...")
            try:
                msg = await sub_presence.recv_json()
                logger.info("Received presence message: %s", msg)
                comp = msg.get("component")
                if comp in required and comp not in present:
                    present.add(comp)
                    logger.info("%s is ready", comp)
                    logger.info("Still waiting for: %s", required - present)
                elif comp not in required:
                    logger.warning("Received presence from unknown component: %s", comp)
            except json.JSONDecodeError as e:
                logger.error("Received invalid JSON message on presence channel: %s", e)
            except Exception as e:
                logger.error("Error processing presence message: %s", e)
                # Continue rather than raising to allow for all debug messages
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("Outer exception in wait_for_components: %s", e)
            # Continue rather than raising
            await asyncio.sleep(1)
    
    logger.info("All components are ready")

async def orchestrate(config):
    ctx = zmq.asyncio.Context.instance()
    sockets = []
    
    # Set up signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()
    
    async def shutdown(sig=None):
        if sig:
            logger.info(f"Received signal {sig.name}, shutting down...")
        else:
            logger.info("Shutting down...")
        
        # Send stop message to all components
        try:
            stop_msg = {"type": "stop"}
            await pub_control.send_json(stop_msg)
            logger.info("Sent stop message to all components")
        except Exception as e:
            logger.error(f"Error sending stop message: {e}")
        
        # Clean up sockets
        for sock in sockets:
            try:
                sock.close()
            except:
                pass
        
        # Set shutdown event
        shutdown_event.set()
    
    # Register signal handlers
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown(s)))
    
    try:
        logger.info("Setting up ZMQ sockets...")
        
        # Connect to proxy's XSUB socket for control messages (publish)
        logger.info("Creating control PUB socket connecting to %s", CONTROL_CHANNEL)
        pub_control = create_pub_socket(CONTROL_CHANNEL, bind=False)
        sockets.append(pub_control)
        
        # Connect to proxy's XPUB socket for presence messages (subscribe)
        logger.info("Creating presence SUB socket connecting to %s", PRESENCE_CHANNEL.replace("5556", "5559"))
        sub_presence = create_sub_socket(PRESENCE_CHANNEL.replace("5556", "5559"), bind=False)
        # Create the subscription directly on the socket to ensure it works
        sub_presence.setsockopt_string(zmq.SUBSCRIBE, "")  
        sockets.append(sub_presence)
        logger.info("Subscribed to all presence messages")
        
        # Connect to proxy's XPUB socket for results
        logger.info("Creating results SUB socket connecting to %s", RESULTS_CHANNEL.replace("5558", "5565"))
        sub_results = create_sub_socket(RESULTS_CHANNEL.replace("5558", "5565"), bind=False)
        sockets.append(sub_results)
    
        # Define required components
        required = set([
            "dataset_manager",
            "timing_manager",
            "worker_manager",
            "records_manager",
            "post_processor",
        ]) | {COMPONENT_NAME}
    
        logger.info("Waiting for all components to announce presence")
        # Wait for all to announce
        await wait_for_components(sub_presence, required)
        logger.info("All components are ready")
    
        # Broadcast start with configuration
        logger.info("Broadcasting start message")
        start_msg = {"type": "start", "config": asdict(config)}
        await pub_control.send_json(start_msg)
        logger.info("Sent start message")
    
        # If we're here, we're in normal operation mode
        count = 0
        expected = config.dataset.size
        logger.info("Waiting for %d results to stop...", expected)
        
        # Create a task to receive results
        async def receive_results():
            nonlocal count
            while count < expected and not shutdown_event.is_set():
                try:
                    await sub_results.recv_json()
                    count += 1
                    if count % 10 == 0:
                        logger.info("Received %d/%d results", count, expected)
                except asyncio.CancelledError:
                    logger.info("Result receiving task cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error receiving result: {e}")
                    await asyncio.sleep(1)
            
            # If we completed collecting all results, trigger shutdown
            if count >= expected and not shutdown_event.is_set():
                logger.info("Received all %d results. Initiating shutdown.", expected)
                await shutdown()
        
        # Start receiving results in background
        results_task = asyncio.create_task(receive_results())
        
        # Wait for shutdown event
        await shutdown_event.wait()
        
        # Cancel results task if still running
        if not results_task.done():
            results_task.cancel()
            try:
                await results_task
            except asyncio.CancelledError:
                pass
            
        logger.info("Shutdown complete.")
        
    except asyncio.CancelledError:
        logger.info("Orchestrate function cancelled")
        await shutdown()
    except Exception as e:
        logger.error(f"Error in orchestrate: {e}")
        await shutdown()

async def main():
    try:
        parser = argparse.ArgumentParser(description="AIPerf System Controller")
        parser.add_argument("--config", default="config.yaml", help="Path to config file")
        args = parser.parse_args()
        config = load_config(args.config)
        await orchestrate(config)
    except asyncio.CancelledError:
        logger.info("Main function cancelled")
    except Exception as e:
        logger.error(f"Error in main: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received. Exiting controller.")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        # Force clean up
        try:
            ctx = zmq.asyncio.Context.instance()
            ctx.term()
        except:
            pass 