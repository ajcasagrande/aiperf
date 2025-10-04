# run.py
import asyncio
import sys
import signal
import time
import logging
import os

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] run %(levelname)s: %(message)s')
logger = logging.getLogger('run')

# Track all processes for graceful shutdown
processes = []

async def start_component(script: str, config: str):
    # Launch a component script with the given config
    proc = await asyncio.create_subprocess_exec(
        sys.executable, script, "--config", config
    )
    processes.append(proc)
    return proc

async def shutdown(sig=None):
    """Gracefully shut down all processes"""
    if sig:
        logger.info(f"Received signal {sig.name}, shutting down...")
    else:
        logger.info("Shutting down...")
    
    # Send SIGINT to all processes in reverse order (controller last)
    for proc in reversed(processes):
        if proc.returncode is None:  # Process still running
            logger.info(f"Sending SIGINT to process {proc.pid}")
            try:
                proc.send_signal(signal.SIGINT)
            except ProcessLookupError:
                pass
    
    # Give processes time to clean up
    try:
        # Wait with timeout for all processes to exit
        logger.info("Waiting for processes to terminate...")
        # Create proper tasks for each process wait coroutine
        wait_tasks = [asyncio.create_task(proc.wait()) for proc in processes]
        done, pending = await asyncio.wait(wait_tasks, timeout=5)
        
        # Cancel any pending tasks
        for task in pending:
            task.cancel()
    except asyncio.TimeoutError:
        # Force kill any remaining processes
        logger.warning("Some processes did not terminate gracefully, forcing termination...")
        for proc in processes:
            if proc.returncode is None:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
    
    logger.info("All components terminated.")
    sys.exit(0)

async def main():
    # Set up signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown(s)))
    
    try:
        config_file = "config.yaml"
        # Components to launch before controller
        components = [
            "proxy.py",
            "dataset_manager.py",
            "timing_manager.py",
            "worker_manager.py",
            "records_manager.py",
            "post_processor.py",
        ]
        
        # Start proxy first
        logger.info("Starting proxy...")
        proxy = await start_component("proxy.py", config_file)
        logger.info("Launched proxy.py (pid %d)", proxy.pid)
        
        # Give proxy time to bind its sockets
        logger.info("Waiting for proxy to bind channels...")
        await asyncio.sleep(2)
        
        # Start system controller
        logger.info("Starting system controller...")
        controller = await start_component("system_controller.py", config_file)
        logger.info("Launched system_controller.py (pid %d)", controller.pid)
        
        # Give controller time to connect to proxy
        await asyncio.sleep(1)
        
        # Now start all manager components
        logger.info("Starting manager components...")
        for script in components[1:]:  # Skip proxy since it's already started
            logger.info("Starting %s...", script)
            proc = await start_component(script, config_file)
            logger.info("Launched %s (pid %d)", script, proc.pid)
            await asyncio.sleep(0.5)  # Small delay between component starts
        
        logger.info("All components started. Press Ctrl+C to stop.")
        
        # Wait for controller to finish or for a signal
        try:
            exit_code = await controller.wait()
            logger.info(f"System controller exited with code {exit_code}")
            # Controller finished naturally
            await shutdown()
        except asyncio.CancelledError:
            # We were cancelled by a signal handler
            pass
            
    except Exception as e:
        logger.error(f"Error in main: {e}")
        await shutdown()  # Ensure cleanup on error

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # This is a fallback in case the asyncio signal handler doesn't catch it
        print("\nKeyboard interrupt received. Exiting.")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        # Force kill any remaining processes
        for proc in processes:
            try:
                os.kill(proc.pid, signal.SIGKILL)
            except:
                pass 