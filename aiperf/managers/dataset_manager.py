import asyncio
import logging
import zmq.asyncio
from utils import (PRESENCE_CHANNEL, CONTROL_CHANNEL, DATASET_CHANNEL,
                  create_pub_socket, create_sub_socket)

class DatasetManager:
    def __init__(self):
        self.datasets = []
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

            # Connect to proxy's XSUB socket for dataset messages
            self.pub_dataset = create_pub_socket(DATASET_CHANNEL, bind=False)
            self.logger.info("Connected to dataset XSUB socket at %s", DATASET_CHANNEL)
            self.sockets.append(self.pub_dataset)

            # Announce presence
            await self.pub_presence.send_json({"component": "dataset_manager"})
            self.logger.info("Announced presence")

            # Set ready flag
            self.ready = True

            # Start control loop
            while True:
                try:
                    message = await self.sub_control.recv_string()
                    self.logger.info("Received control message: %s", message)
                    if message == "START":
                        # Generate and publish dataset
                        await self.generate_and_publish_dataset()
                    elif message == "STOP":
                        break
                except Exception as e:
                    self.logger.error("Error processing control message: %s", str(e))
                    await asyncio.sleep(1)

        except Exception as e:
            self.logger.error("Error in dataset manager: %s", str(e))
            raise
        finally:
            # Clean up sockets
            for sock in self.sockets:
                try:
                    sock.close()
                except:
                    pass
            self.ctx.term()

    async def generate_and_publish_dataset(self):
        # Generate synthetic dataset
        self.datasets = [f"data_{i}" for i in range(100)]
        self.logger.info("Generated %d synthetic data points", len(self.datasets))
        
        # Publish dataset
        for data in self.datasets:
            await self.pub_dataset.send_string(data)
        self.logger.info("Published dataset")

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
        self.logger.info("Dataset manager shut down")

    def load_dataset(self, dataset_path):
        # Logic to load a dataset from the specified path
        pass
    
    def generate_synthetic_data(self, num_samples):
        # Logic to generate synthetic data
        pass
    
    def get_dataset(self):
        # Logic to return the loaded dataset
        return self.datasets
    
    def clear_datasets(self):
        # Logic to clear the loaded datasets
        self.datasets = []