"""Project-wide logging setup.

Use ``get_logger(__name__)`` in every module instead of ``logging.getLogger``
directly so that all modules share a consistent format and level.
"""

from __future__ import annotations

import logging
import os
import sys

_LOG_FORMAT = "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def _configure() -> None:
    global _configured
    if _configured:
        return

    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    # NB: only attach our handler if the root has none yet. uvicorn / pytest
    # install their own handlers; wiping them (the previous behaviour) caused
    # uvicorn access logs to disappear and pytest log capture to break.
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
        root.addHandler(handler)
    root.setLevel(level)

    # Quiet down noisy third-party libraries unless we are at DEBUG.
    if level > logging.DEBUG:
        for noisy in ("urllib3", "binance", "asyncio"):
            logging.getLogger(noisy).setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    _configure()
    return logging.getLogger(name)
