import asyncio
import logging
import zmq.asyncio
from utils import (PRESENCE_CHANNEL, CONTROL_CHANNEL, RESULTS_CHANNEL,
                  create_pub_socket, create_sub_socket)

class PostProcessor:
    def __init__(self):
        self.ready = False
        self.logger = logging.getLogger(self.__class__.__name__)
        self.ctx = zmq.asyncio.Context()
        self.sockets = []
        self.results = []

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

            # Connect to proxy's XPUB socket for results messages
            self.sub_results = create_sub_socket(RESULTS_CHANNEL.replace("5558", "5565"), bind=False)
            self.logger.info("Connected to results XPUB socket at %s", RESULTS_CHANNEL.replace("5558", "5565"))
            self.sockets.append(self.sub_results)

            # Announce presence
            await self.pub_presence.send_json({"component": "post_processor"})
            self.logger.info("Announced presence")

            # Set ready flag
            self.ready = True

            # Start control loop
            while True:
                try:
                    message = await self.sub_control.recv_string()
                    self.logger.info("Received control message: %s", message)
                    if message == "START":
                        # Start processing results
                        await self.process_results()
                    elif message == "STOP":
                        break
                except Exception as e:
                    self.logger.error("Error processing control message: %s", str(e))
                    await asyncio.sleep(1)

        except Exception as e:
            self.logger.error("Error in post processor: %s", str(e))
            raise
        finally:
            # Clean up sockets
            for sock in self.sockets:
                try:
                    sock.close()
                except:
                    pass
            self.ctx.term()

    async def process_results(self):
        while True:
            try:
                result = await self.sub_results.recv_string()
                self.logger.info("Received result for processing: %s", result)
                self.results.append(result)
                # Process result and generate report
                self.generate_report()
            except Exception as e:
                self.logger.error("Error processing result: %s", str(e))
                break

    def generate_report(self):
        if self.results:
            self.logger.info("Generated report with %d results", len(self.results))
            # Here you would implement actual report generation logic

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
        self.logger.info("Post processor shut down") 