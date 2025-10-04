import zmq.asyncio
import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='[%(asctime)s] %(name)s %(levelname)s: %(message)s')
logger = logging.getLogger('zmq_test_sub')

PRESENCE_CHANNEL = "tcp://127.0.0.1:5559"  # The XPUB port

async def main():
    logger.info("Starting test subscriber")
    
    context = zmq.asyncio.Context()
    socket = context.socket(zmq.SUB)
    socket.setsockopt_string(zmq.SUBSCRIBE, "")  # Subscribe to all messages
    
    logger.info(f"Connecting to {PRESENCE_CHANNEL}")
    socket.connect(PRESENCE_CHANNEL)
    logger.info("Connected, waiting for messages...")
    
    try:
        while True:
            logger.debug("Waiting for message...")
            try:
                message = await socket.recv_json()
                logger.info(f"Received message: {message}")
            except Exception as e:
                logger.error(f"Error receiving message: {e}")
                await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down")
    finally:
        socket.close()
        context.term()
        logger.info("Closed")

if __name__ == "__main__":
    asyncio.run(main()) 