import asyncio
import logging
from managers.system_controller import SystemController
from managers.dataset_manager import DatasetManager
from managers.timing_manager import TimingManager
from managers.worker_manager import WorkerManager
from managers.records_manager import RecordsManager
from managers.post_processor import PostProcessor
from proxy import run as run_proxy

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(name)s %(levelname)s: %(message)s')
logger = logging.getLogger('main')

async def main():
    try:
        # Start the proxy first
        logger.info("Starting proxy...")
        proxy_task = asyncio.create_task(run_proxy())
        
        # Give the proxy a moment to start
        await asyncio.sleep(1)
        
        # Initialize components
        logger.info("Initializing components...")
        system_controller = SystemController()
        dataset_manager = DatasetManager()
        timing_manager = TimingManager()
        worker_manager = WorkerManager()
        records_manager = RecordsManager()
        post_processor = PostProcessor()
        
        # Register components with system controller
        system_controller.register_component("dataset_manager", dataset_manager)
        system_controller.register_component("timing_manager", timing_manager)
        system_controller.register_component("worker_manager", worker_manager)
        system_controller.register_component("records_manager", records_manager)
        system_controller.register_component("post_processor", post_processor)
        
        # Setup system controller sockets
        logger.info("Setting up system controller sockets...")
        await system_controller.setup_sockets()
        
        # Start components
        logger.info("Starting components...")
        await asyncio.gather(
            dataset_manager.run(),
            timing_manager.run(),
            worker_manager.start(),
            records_manager.run(),
            post_processor.run()
        )
        
        # Wait for all components to be ready
        while not system_controller.check_readiness():
            logger.info("Waiting for components to be ready...")
            await asyncio.sleep(1)
        
        # Start the benchmarking process
        logger.info("All components ready, starting benchmarking...")
        await system_controller.start()
        
        # Wait for completion
        await asyncio.sleep(10)  # Adjust as needed
        
        # Shutdown
        logger.info("Shutting down...")
        await system_controller.shutdown()
        proxy_task.cancel()
        try:
            await proxy_task
        except asyncio.CancelledError:
            pass
        
    except Exception as e:
        logger.error("Error in main: %s", str(e))
        raise

if __name__ == "__main__":
    asyncio.run(main()) 