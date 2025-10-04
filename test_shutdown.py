#!/usr/bin/env python3
import asyncio
import sys
import signal
import logging
import time

logging.basicConfig(level=logging.DEBUG, 
                    format='[%(asctime)s] %(name)s %(levelname)s: %(message)s')
logger = logging.getLogger('shutdown_test')

# Track all processes
processes = []

async def start_component(script: str):
    # Launch a component script
    logger.info(f"Starting {script}...")
    proc = await asyncio.create_subprocess_exec(
        sys.executable, script,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    processes.append(proc)
    logger.info(f"Launched {script} (pid {proc.pid})")
    return proc

async def log_output(proc, name):
    """Log output from the process"""
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        logger.info(f"{name} stdout: {line.decode().strip()}")

async def shutdown(sig=None):
    """Gracefully shut down all processes with detailed logging"""
    if sig:
        logger.info(f"Received signal {sig.name}, shutting down...")
    else:
        logger.info("Shutting down...")
    
    # Send SIGINT to all processes in reverse order
    for proc in reversed(processes):
        if proc.returncode is None:  # Process still running
            logger.info(f"Sending SIGINT to process {proc.pid}")
            try:
                proc.send_signal(signal.SIGINT)
            except ProcessLookupError:
                logger.warning(f"Process {proc.pid} not found when sending SIGINT")
    
    # Give processes time to clean up with detailed status logging
    try:
        logger.info("Waiting for processes to terminate gracefully...")
        
        # Create tasks for all wait operations
        wait_tasks = [asyncio.create_task(proc.wait()) for proc in processes]
        
        # First try to wait 5 seconds for all processes to exit
        start_time = time.time()
        while time.time() - start_time < 5:
            # Check each process
            all_done = True
            for i, proc in enumerate(processes):
                if proc.returncode is None:
                    all_done = False
                    logger.debug(f"Process {proc.pid} still running after {time.time() - start_time:.2f} seconds")
                else:
                    if not hasattr(proc, '_shutdown_reported'):
                        logger.info(f"Process {proc.pid} exited with code {proc.returncode}")
                        proc._shutdown_reported = True
            
            if all_done:
                logger.info("All processes terminated gracefully")
                break
                
            await asyncio.sleep(0.5)
        
        # If not all done, use asyncio.wait with timeout
        if not all_done:
            logger.warning("Some processes still running, waiting with timeout...")
            done, pending = await asyncio.wait(wait_tasks, timeout=2)
            
            # Log results
            logger.info(f"Wait completed: {len(done)} done, {len(pending)} pending")
            
            # Cancel any pending tasks
            for task in pending:
                task.cancel()
                logger.debug(f"Cancelled task: {task}")
            
            # Force kill any remaining processes
            for proc in processes:
                if proc.returncode is None:
                    logger.warning(f"Process {proc.pid} did not exit, killing...")
                    try:
                        proc.kill()
                        await proc.wait()
                        logger.info(f"Process {proc.pid} forcibly terminated")
                    except ProcessLookupError:
                        logger.warning(f"Process {proc.pid} not found when killing")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
        # Force kill as last resort
        for proc in processes:
            if proc.returncode is None:
                try:
                    proc.kill()
                except:
                    pass
    
    logger.info("All components terminated.")

async def main():
    # Set up signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown(s)))
    
    try:
        # Start components in order
        logger.info("Starting components...")
        
        # Start proxy first
        proxy = await start_component("proxy.py")
        # Start monitoring its output
        asyncio.create_task(log_output(proxy, "proxy"))
        
        # Wait for proxy to initialize
        await asyncio.sleep(2)
        
        # Start system controller
        controller = await start_component("system_controller.py")
        asyncio.create_task(log_output(controller, "controller"))
        
        # Wait for controller to initialize
        await asyncio.sleep(1)
        
        # Start other components
        components = [
            "dataset_manager.py",
            "timing_manager.py",
            "worker_manager.py",
            "records_manager.py",
            "post_processor.py",
        ]
        
        for script in components:
            proc = await start_component(script)
            asyncio.create_task(log_output(proc, script))
            await asyncio.sleep(0.5)
        
        logger.info("All components started. Running for 10 seconds, then will initiate shutdown...")
        
        # Run for 10 seconds then initiate shutdown
        await asyncio.sleep(10)
        logger.info("Testing automatic shutdown...")
        await shutdown()
            
    except asyncio.CancelledError:
        logger.info("Main task cancelled")
        # Cleanup is handled by the shutdown task
    except Exception as e:
        logger.error(f"Error in main: {e}")
        await shutdown()  # Ensure cleanup on error

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # This is a fallback for keyboard interrupts
        print("\nKeyboard interrupt received. Exiting.")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}") 