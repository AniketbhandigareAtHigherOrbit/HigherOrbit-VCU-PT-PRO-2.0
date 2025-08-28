# utils/logger.py

import logging

def setup_logger():
    """Sets up and returns a configured logger."""
    logger = logging.getLogger("VCU")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)

        logger.addHandler(ch)

    return logger
# Logger setup module
