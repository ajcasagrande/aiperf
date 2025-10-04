import asyncio
import logging
import zmq.asyncio
from utils import (PRESENCE_CHANNEL, CONTROL_CHANNEL, TIMING_CHANNEL,
                  DATASET_CHANNEL, RESULTS_CHANNEL, create_pub_socket,
                  create_sub_socket)

class WorkerManager:
    def __init__(self):
        self.ready = False
        self.logger = logging.getLogger(self.__class__.__name__)
        self.ctx = zmq.asyncio.Context()
        self.sockets = []
        self.workers = []

    async def start(self):
        try:
            # Connect to proxy's XSUB socket for presence messages
            self.pub_presence = create_pub_socket(PRESENCE_CHANNEL, bind=False)
            self.logger.info("Connected to presence XSUB socket at %s", PRESENCE_CHANNEL)
            self.sockets.append(self.pub_presence)

            # Connect to proxy's XPUB socket for control messages
            self.sub_control = create_sub_socket(CONTROL_CHANNEL.replace("5557", "5562"), bind=False)
            self.logger.info("Connected to control XPUB socket at %s", CONTROL_CHANNEL.replace("5557", "5562"))
            self.sockets.append(self.sub_control)

            # Connect to proxy's XPUB socket for timing messages
            self.sub_timing = create_sub_socket(TIMING_CHANNEL.replace("5560", "5563"), bind=False)
            self.logger.info("Connected to timing XPUB socket at %s", TIMING_CHANNEL.replace("5560", "5563"))
            self.sockets.append(self.sub_timing)

            # Connect to proxy's XPUB socket for dataset messages
            self.sub_dataset = create_sub_socket(DATASET_CHANNEL.replace("5561", "5564"), bind=False)
            self.logger.info("Connected to dataset XPUB socket at %s", DATASET_CHANNEL.replace("5561", "5564"))
            self.sockets.append(self.sub_dataset)

            # Connect to proxy's XSUB socket for results messages
            self.pub_results = create_pub_socket(RESULTS_CHANNEL, bind=False)
            self.logger.info("Connected to results XSUB socket at %s", RESULTS_CHANNEL)
            self.sockets.append(self.pub_results)

            # Announce presence
            await self.pub_presence.send_json({"component": "worker_manager"})
            self.logger.info("Announced presence")

            # Set ready flag
            self.ready = True

            # Start control loop
            while True:
                try:
                    message = await self.sub_control.recv_string()
                    self.logger.info("Received control message: %s", message)
                    if message == "START":
                        # Start workers
                        await self.start_workers()
                    elif message == "STOP":
                        break
                except Exception as e:
                    self.logger.error("Error processing control message: %s", str(e))
                    await asyncio.sleep(1)

        except Exception as e:
            self.logger.error("Error in worker manager: %s", str(e))
            raise
        finally:
            # Clean up sockets
            for sock in self.sockets:
                try:
                    sock.close()
                except:
                    pass
            self.ctx.term()

    async def start_workers(self):
        # Start worker tasks
        for i in range(5):  # Start 5 workers
            worker = asyncio.create_task(self.worker_loop(i))
            self.workers.append(worker)
        self.logger.info("Started %d workers", len(self.workers))

    async def worker_loop(self, worker_id):
        while True:
            try:
                # Wait for timing message
                timing = await self.sub_timing.recv_string()
                self.logger.info("Worker %d received timing message: %s", worker_id, timing)

                # Wait for dataset message
                data = await self.sub_dataset.recv_string()
                self.logger.info("Worker %d received data: %s", worker_id, data)

                # Process data and send result
                result = f"Processed {data} at {timing}"
                await self.pub_results.send_string(result)
                self.logger.info("Worker %d sent result: %s", worker_id, result)

            except Exception as e:
                self.logger.error("Error in worker %d: %s", worker_id, str(e))
                break

    def is_ready(self):
        return self.ready

    async def shutdown(self):
        self.ready = False
        # Cancel all worker tasks
        for worker in self.workers:
            worker.cancel()
        # Wait for workers to finish
        await asyncio.gather(*self.workers, return_exceptions=True)
        # Clean up sockets
        for sock in self.sockets:
            try:
                sock.close()
            except:
                pass
        self.ctx.term()
        self.logger.info("Worker manager shut down")