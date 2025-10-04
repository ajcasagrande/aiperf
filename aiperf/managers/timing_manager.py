import asyncio
import logging
import zmq.asyncio
from utils import (PRESENCE_CHANNEL, CONTROL_CHANNEL, TIMING_CHANNEL,
                  create_pub_socket, create_sub_socket)

class TimingManager:
    def __init__(self):
        self.ready = False
        self.logger = logging.getLogger(self.__class__.__name__)
        self.ctx = zmq.asyncio.Context()
        self.sockets = []

    async def run(self):
        try:
            # Connect to proxy's XSUB socket for presence messages
            self.pub_presence = create_pub_socket(PRESENCE_CHANNEL, bind=False)
            self.logger.info("Connected to presence XSUB socket at %s", PRESENCE_CHANNEL)
            self.sockets.append(self.pub_presence)

            # Connect to proxy's XPUB socket for control messages
            self.sub_control = create_sub_socket(CONTROL_CHANNEL.replace("5557", "5562"), bind=False)
            self.logger.info("Connected to control XPUB socket at %s", CONTROL_CHANNEL.replace("5557", "5562"))
            self.sockets.append(self.sub_control)

            # Connect to proxy's XSUB socket for timing messages
            self.pub_timing = create_pub_socket(TIMING_CHANNEL, bind=False)
            self.logger.info("Connected to timing XSUB socket at %s", TIMING_CHANNEL)
            self.sockets.append(self.pub_timing)

            # Announce presence
            await self.pub_presence.send_json({"component": "timing_manager"})
            self.logger.info("Announced presence")

            # Set ready flag
            self.ready = True

            # Start control loop
            while True:
                try:
                    message = await self.sub_control.recv_string()
                    self.logger.info("Received control message: %s", message)
                    if message == "START":
                        # Start sending timing messages
                        await self.send_timing_messages()
                    elif message == "STOP":
                        break
                except Exception as e:
                    self.logger.error("Error processing control message: %s", str(e))
                    await asyncio.sleep(1)

        except Exception as e:
            self.logger.error("Error in timing manager: %s", str(e))
            raise
        finally:
            # Clean up sockets
            for sock in self.sockets:
                try:
                    sock.close()
                except:
                    pass
            self.ctx.term()

    async def send_timing_messages(self):
        # Send timing messages every second
        while True:
            try:
                await self.pub_timing.send_string("TIMING")
                self.logger.info("Sent timing message")
                await asyncio.sleep(1)
            except Exception as e:
                self.logger.error("Error sending timing message: %s", str(e))
                break

    def is_ready(self):
        return self.ready

    async def shutdown(self):
        self.ready = False
        # Clean up sockets
        for sock in self.sockets:
            try:
                sock.close()
            except:
                pass
        self.ctx.term()
        self.logger.info("Timing manager shut down")