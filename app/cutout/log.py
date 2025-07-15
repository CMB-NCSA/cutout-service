import logging
import os


def get_logger(name):
    # Configure logging
    logging.basicConfig(
        format='%(asctime)s [%(name)-12s] %(levelname)-8s %(message)s',
    )
    logger = logging.getLogger(name)
    logger.setLevel(os.getenv('CE_LOG_LEVEL', logging.DEBUG))
    return logger
