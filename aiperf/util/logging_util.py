import logging
import sys
import os
from typing import Optional

def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> None:
    """Set up logging configuration.
    
    Args:
        log_level: Log level
        log_file: Optional path to log file
    """
    # Convert log level string to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Create file handler if log file specified
    if log_file:
        # Ensure directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Log the configuration
    logging.info(f"Logging configured with level {log_level}")
    if log_file:
        logging.info(f"Logging to file: {log_file}")

def get_logger(name: str, log_level: Optional[str] = None) -> logging.Logger:
    """Get a logger with the specified name.
    
    Args:
        name: Logger name
        log_level: Optional log level override
        
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    
    if log_level:
        numeric_level = getattr(logging, log_level.upper(), None)
        if numeric_level:
            logger.setLevel(numeric_level)
    
    return logger 