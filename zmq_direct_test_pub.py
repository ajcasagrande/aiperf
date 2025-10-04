import zmq.asyncio
import asyncio
import logging
import time

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='[%(asctime)s] %(name)s %(levelname)s: %(message)s')
logger = logging.getLogger('zmq_direct_test_pub')

DIRECT_CHANNEL = "tcp://127.0.0.1:5999"  # Direct channel, not via proxy

async def main():
    logger.info("Starting direct test publisher")
    
    context = zmq.asyncio.Context()
    socket = context.socket(zmq.PUB)
    
    logger.info(f"Binding to {DIRECT_CHANNEL}")
    socket.bind(DIRECT_CHANNEL)
    logger.info("Bound, waiting for subscribers...")
    
    # Wait for connections to establish
    await asyncio.sleep(1)
    
    try:
        counter = 0
        while True:
            message = {"component": f"direct_test_component", "count": counter}
            logger.info(f"Sending message: {message}")
            await socket.send_json(message)
            counter += 1
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down")
    finally:
        socket.close()
        context.term()
        logger.info("Closed")

if __name__ == "__main__":
    asyncio.run(main()) 