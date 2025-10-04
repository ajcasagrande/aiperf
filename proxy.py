# proxy.py
import asyncio
import logging
import zmq.asyncio
import json
import signal
from utils import (PRESENCE_CHANNEL, CONTROL_CHANNEL, TIMING_CHANNEL,
                  DATASET_CHANNEL, RESULTS_CHANNEL)

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='[%(asctime)s] %(name)s %(levelname)s: %(message)s')
logger = logging.getLogger('proxy')

# Track resources for cleanup
sockets = []
tasks = []

# Signal handler for graceful shutdown
async def shutdown(sig=None):
    """Gracefully shut down the proxy"""
    if sig:
        logger.info(f"Received signal {sig.name}, shutting down...")
    else:
        logger.info("Shutting down...")
    
    # Cancel all tasks
    for task in tasks:
        if not task.done():
            task.cancel()
    
    # Give tasks time to clean up
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    
    # Clean up sockets
    for sock in sockets:
        try:
            sock.close()
        except:
            pass
    
    # Terminate ZMQ context
    ctx = zmq.asyncio.Context.instance()
    ctx.term()
    logger.info("Proxy has been shut down gracefully.")

# Custom proxy implementation to see message flow
async def custom_proxy(xsub_socket, xpub_socket, name):
    logger.info(f"Starting custom {name} proxy")
    poller = zmq.asyncio.Poller()
    poller.register(xsub_socket, zmq.POLLIN)
    poller.register(xpub_socket, zmq.POLLIN)
    
    try:
        while True:
            events = dict(await poller.poll(timeout=1000))  # 1 second timeout
            
            # Handle messages from publishers
            if xsub_socket in events:
                message = await xsub_socket.recv_multipart()
                logger.debug(f"{name} proxy received from XSUB: {message}")
                try:
                    # Try to extract JSON if it's a data message (not subscription)
                    if len(message) >= 2 and message[0] == b'':
                        try:
                            data = json.loads(message[1])
                            logger.info(f"{name} proxy received message: {data}")
                        except:
                            pass
                except Exception as e:
                    logger.error(f"Error parsing message: {e}")
                    
                await xpub_socket.send_multipart(message)
                logger.debug(f"{name} proxy forwarded to XPUB")
            
            # Handle subscription messages
            if xpub_socket in events:
                message = await xpub_socket.recv_multipart()
                logger.debug(f"{name} proxy received from XPUB: {message}")
                
                # Check if it's a subscription message
                if message and len(message) > 0:
                    if message[0][0] == 1:  # Subscription
                        logger.info(f"{name} proxy: New subscription: {message}")
                    elif message[0][0] == 0:  # Unsubscription
                        logger.info(f"{name} proxy: Unsubscription: {message}")
                        
                await xsub_socket.send_multipart(message)
                logger.debug(f"{name} proxy forwarded to XSUB")
    except asyncio.CancelledError:
        logger.info(f"{name} proxy task cancelled")
    except Exception as e:
        logger.error(f"Error in {name} proxy: {e}")
        raise

async def run():
    global sockets, tasks
    
    # Set up signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown(s)))
    
    ctx = zmq.asyncio.Context.instance()
    
    try:
        # Create XSUB sockets for publishers to connect to
        presence_xsub = ctx.socket(zmq.XSUB)
        try:
            presence_xsub.bind(PRESENCE_CHANNEL)
            logger.info("Presence XSUB socket bound to %s", PRESENCE_CHANNEL)
            sockets.append(presence_xsub)
        except zmq.error.ZMQError as e:
            if e.errno == zmq.EADDRINUSE:
                logger.error("Address %s already in use. Is another proxy running?", PRESENCE_CHANNEL)
                return
            raise
        
        control_xsub = ctx.socket(zmq.XSUB)
        try:
            control_xsub.bind(CONTROL_CHANNEL)
            logger.info("Control XSUB socket bound to %s", CONTROL_CHANNEL)
            sockets.append(control_xsub)
        except zmq.error.ZMQError as e:
            if e.errno == zmq.EADDRINUSE:
                logger.error("Address %s already in use. Is another proxy running?", CONTROL_CHANNEL)
                return
            raise
        
        timing_xsub = ctx.socket(zmq.XSUB)
        try:
            timing_xsub.bind(TIMING_CHANNEL)
            logger.info("Timing XSUB socket bound to %s", TIMING_CHANNEL)
            sockets.append(timing_xsub)
        except zmq.error.ZMQError as e:
            if e.errno == zmq.EADDRINUSE:
                logger.error("Address %s already in use. Is another proxy running?", TIMING_CHANNEL)
                return
            raise
        
        dataset_xsub = ctx.socket(zmq.XSUB)
        try:
            dataset_xsub.bind(DATASET_CHANNEL)
            logger.info("Dataset XSUB socket bound to %s", DATASET_CHANNEL)
            sockets.append(dataset_xsub)
        except zmq.error.ZMQError as e:
            if e.errno == zmq.EADDRINUSE:
                logger.error("Address %s already in use. Is another proxy running?", DATASET_CHANNEL)
                return
            raise
        
        results_xsub = ctx.socket(zmq.XSUB)
        try:
            results_xsub.bind(RESULTS_CHANNEL)
            logger.info("Results XSUB socket bound to %s", RESULTS_CHANNEL)
            sockets.append(results_xsub)
        except zmq.error.ZMQError as e:
            if e.errno == zmq.EADDRINUSE:
                logger.error("Address %s already in use. Is another proxy running?", RESULTS_CHANNEL)
                return
            raise
        
        # Create XPUB sockets for subscribers to connect to
        presence_xpub = ctx.socket(zmq.XPUB)
        presence_xpub.setsockopt(zmq.XPUB_VERBOSE, 1)  # To see all subscription events
        try:
            presence_xpub.bind(PRESENCE_CHANNEL.replace("5556", "5559"))
            logger.info("Presence XPUB socket bound to %s", PRESENCE_CHANNEL.replace("5556", "5559"))
            sockets.append(presence_xpub)
        except zmq.error.ZMQError as e:
            if e.errno == zmq.EADDRINUSE:
                logger.error("Address %s already in use. Is another proxy running?", PRESENCE_CHANNEL.replace("5556", "5559"))
                return
            raise
        
        control_xpub = ctx.socket(zmq.XPUB)
        control_xpub.setsockopt(zmq.XPUB_VERBOSE, 1)
        try:
            control_xpub.bind(CONTROL_CHANNEL.replace("5557", "5562"))
            logger.info("Control XPUB socket bound to %s", CONTROL_CHANNEL.replace("5557", "5562"))
            sockets.append(control_xpub)
        except zmq.error.ZMQError as e:
            if e.errno == zmq.EADDRINUSE:
                logger.error("Address %s already in use. Is another proxy running?", CONTROL_CHANNEL.replace("5557", "5562"))
                return
            raise
        
        timing_xpub = ctx.socket(zmq.XPUB)
        timing_xpub.setsockopt(zmq.XPUB_VERBOSE, 1)
        try:
            timing_xpub.bind(TIMING_CHANNEL.replace("5560", "5563"))
            logger.info("Timing XPUB socket bound to %s", TIMING_CHANNEL.replace("5560", "5563"))
            sockets.append(timing_xpub)
        except zmq.error.ZMQError as e:
            if e.errno == zmq.EADDRINUSE:
                logger.error("Address %s already in use. Is another proxy running?", TIMING_CHANNEL.replace("5560", "5563"))
                return
            raise
        
        dataset_xpub = ctx.socket(zmq.XPUB)
        dataset_xpub.setsockopt(zmq.XPUB_VERBOSE, 1)
        try:
            dataset_xpub.bind(DATASET_CHANNEL.replace("5561", "5564"))
            logger.info("Dataset XPUB socket bound to %s", DATASET_CHANNEL.replace("5561", "5564"))
            sockets.append(dataset_xpub)
        except zmq.error.ZMQError as e:
            if e.errno == zmq.EADDRINUSE:
                logger.error("Address %s already in use. Is another proxy running?", DATASET_CHANNEL.replace("5561", "5564"))
                return
            raise
        
        results_xpub = ctx.socket(zmq.XPUB)
        results_xpub.setsockopt(zmq.XPUB_VERBOSE, 1)
        try:
            results_xpub.bind(RESULTS_CHANNEL.replace("5558", "5565"))
            logger.info("Results XPUB socket bound to %s", RESULTS_CHANNEL.replace("5558", "5565"))
            sockets.append(results_xpub)
        except zmq.error.ZMQError as e:
            if e.errno == zmq.EADDRINUSE:
                logger.error("Address %s already in use. Is another proxy running?", RESULTS_CHANNEL.replace("5558", "5565"))
                return
            raise
        
        # Create and start custom proxies
        logger.info("Starting custom proxies...")
        tasks.append(asyncio.create_task(custom_proxy(presence_xsub, presence_xpub, "presence")))
        tasks.append(asyncio.create_task(custom_proxy(control_xsub, control_xpub, "control")))
        tasks.append(asyncio.create_task(custom_proxy(timing_xsub, timing_xpub, "timing")))
        tasks.append(asyncio.create_task(custom_proxy(dataset_xsub, dataset_xpub, "dataset")))
        tasks.append(asyncio.create_task(custom_proxy(results_xsub, results_xpub, "results")))
        
        # Wait for all tasks to complete
        try:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            # If any task completes (likely due to error), we should shut down
            for task in done:
                if task.exception():
                    logger.error(f"Task failed with exception: {task.exception()}")
                else:
                    logger.warning(f"Task completed unexpectedly with result: {task.result()}")
                await shutdown()
        except asyncio.CancelledError:
            # This coroutine was cancelled by signal handler
            pass
        
    except Exception as e:
        logger.error(f"Error in proxy: {e}")
    finally:
        # Ensure clean shutdown
        await shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        # Fallback in case the asyncio signal handler doesn't catch it
        print("\nKeyboard interrupt received. Exiting proxy.")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        # Force clean up
        ctx = zmq.asyncio.Context.instance()
        ctx.term() 