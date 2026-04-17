import logging
import os

def setup_logging():
    level_name = os.getenv("LOG_LEVEL", "WARNING").upper()
    level = getattr(logging, level_name, logging.WARNING)
    root = logging.getLogger()
    root.setLevel(level)
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        root.addHandler(handler)
    for name in logging.Logger.manager.loggerDict:
        lg = logging.getLogger(name)
        lg.setLevel(level)
        for handler in lg.handlers:
            handler.setLevel(level)
