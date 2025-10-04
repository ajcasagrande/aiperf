import zmq.asyncio
import asyncio
import logging
import time

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='[%(asctime)s] %(name)s %(levelname)s: %(message)s')
logger = logging.getLogger('zmq_test_pub')

PRESENCE_CHANNEL = "tcp://127.0.0.1:5556"  # The XSUB port

async def main():
    logger.info("Starting test publisher")
    
    context = zmq.asyncio.Context()
    socket = context.socket(zmq.PUB)
    
    logger.info(f"Connecting to {PRESENCE_CHANNEL}")
    socket.connect(PRESENCE_CHANNEL)
    logger.info("Connected")
    
    # Wait for connections to establish
    await asyncio.sleep(1)
    
    try:
        counter = 0
        while True:
            message = {"component": f"test_component", "count": counter}
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