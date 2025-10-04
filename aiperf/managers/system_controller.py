import sys
import logging
import zmq.asyncio
import asyncio
from utils import (PRESENCE_CHANNEL, CONTROL_CHANNEL, RESULTS_CHANNEL,
                  create_pub_socket, create_sub_socket)

class SystemController:
    def __init__(self):
        self.components = {}
        self.ready = False
        # Configure logger
        self.logger = logging.getLogger(self.__class__.__name__)
        self.ctx = zmq.asyncio.Context()
        self.sockets = []

    async def setup_sockets(self):
        try:
            # Connect to proxy's XPUB socket for presence messages
            self.presence_sub = create_sub_socket(PRESENCE_CHANNEL.replace("5556", "5559"), bind=False)
            self.logger.info("Connected to presence XPUB socket at %s", PRESENCE_CHANNEL.replace("5556", "5559"))
            self.sockets.append(self.presence_sub)

            # Connect to proxy's XSUB socket for control messages
            self.control_pub = create_pub_socket(CONTROL_CHANNEL, bind=False)
            self.logger.info("Connected to control XSUB socket at %s", CONTROL_CHANNEL)
            self.sockets.append(self.control_pub)

            # Connect to proxy's XPUB socket for results
            self.results_sub = create_sub_socket(RESULTS_CHANNEL.replace("5558", "5565"), bind=False)
            self.logger.info("Connected to results XPUB socket at %s", RESULTS_CHANNEL.replace("5558", "5565"))
            self.sockets.append(self.results_sub)

            # Start listening for presence messages
            asyncio.create_task(self.listen_for_presence())
        except Exception as e:
            self.logger.error("Error setting up sockets: %s", str(e))
            raise

    async def listen_for_presence(self):
        while True:
            try:
                message = await self.presence_sub.recv_json()
                self.logger.info("Received presence message: %s", message)
                # Process presence message
                component_name = message.get("component")
                if component_name in self.components:
                    self.components[component_name].set_ready(True)
                    self.logger.info("Component %s is ready", component_name)
            except Exception as e:
                self.logger.error("Error receiving presence message: %s", str(e))
                await asyncio.sleep(1)

    def register_component(self, name, component):
        self.components[name] = component

    def check_readiness(self):
        self.ready = all(component.is_ready() for component in self.components.values())
        return self.ready

    async def start(self):
        if not self.check_readiness():
            raise RuntimeError("Not all components are ready.")
        # Logic to start the benchmarking process
        self.logger.info("Starting the benchmarking process...")
        # Broadcast start message
        await self.control_pub.send_string("START")

    async def shutdown(self):
        for component in self.components.values():
            await component.shutdown()
        # Clean up sockets
        for sock in self.sockets:
            try:
                sock.close()
            except:
                pass
        self.ctx.term()
        self.logger.info("System has been shut down gracefully.")