import os
import sys
import logging
import logging.handlers

from comp3000bot.config import LOG_FILE


def get_logger(logger='comp3000bot'):
    """
    Get a handle to the logger.
    """
    return logging.getLogger('comp3000bot')


# Get the logger
logger = get_logger()

# Make logfile parent directory
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

# Configure logging
formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
formatter.datefmt = '%Y-%m-%d %H:%M:%S'

# TODO: add a debug mode?
logger.setLevel(logging.INFO)

# Log to rotating file
handler = logging.handlers.RotatingFileHandler(
    LOG_FILE,
    maxBytes=(1024 ** 3),
    backupCount=12,
)
handler.setFormatter(formatter)
logger.addHandler(handler)

# Also log to stderr
handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(formatter)
logger.addHandler(handler)


def _exception_logger(_type, value, traceback):
    """
    Register this with sys.excepthook to log all uncaught exceptions.
    """
    if issubclass(_type, KeyboardInterrupt):
        sys.__excepthook__(_type, value, traceback)
        return
    logger.error(
        f"Uncaught exception: {str(value)}", exc_info=(_type, value, traceback)
    )


# Register _exception_logger
sys.excepthook = _exception_logger
