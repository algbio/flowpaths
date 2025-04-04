import logging

# Expose logging levels through fp.utils
DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL

# Define a logger for the package
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())  # Prevent issues if no handler is set

def configure_logging(
        level=logging.DEBUG, 
        log_to_console=True, 
        log_file=None, 
        file_mode="w"  # "a" for append, "w" for overwrite
    ):
    """
    Configures logging for the flowpaths package.

    Parameters:
    -----------

    - `level: int`, optional
        
        Logging level (e.g., fp.utils.logging.DEBUG, fp.utils.logging.INFO). 
        Default is fp.utils.logging.DEBUG.

    - `log_to_console: bool`, optional
    
        Whether to log to the console. Default is True.

    - `log_file: str`, optional
     
        File path to log to. If None, logging to a file is disabled. Default is None.
        If a file path is provided, the log will be written to that file.
        If the file already exists, it will be overwritten unless `file_mode` is set to "a".
    
    - `file_mode: str`, optional
        
        Mode for the log file. "a" (append) or "w" (overwrite). Default is "w".

    """
    # Remove existing handlers to avoid duplicate logs
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Set the logger level
    logger.setLevel(level)

    # Define a formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Add console handler if enabled
    if log_to_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    if file_mode not in ["a", "w"]:
        raise ValueError("file_mode must be either 'a' (append) or 'w' (overwrite)")

    # Add file handler if a file path is provided
    if log_file:
        file_handler = logging.FileHandler(log_file, mode=file_mode)  # Use file_mode
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    logger.info("Logging initialized: level=%s, console=%s, file=%s, mode=%s", 
                level, log_to_console, log_file, file_mode)