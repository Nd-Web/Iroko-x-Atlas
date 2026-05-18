"""
core/logging.py — Structured logging configuration for Iroko AI.

Provides a single ``get_logger(name)`` factory that returns a standard-library
logger pre-configured with a clean formatter writing to stdout.

Usage::

    from core.logging import get_logger
    logger = get_logger(__name__)
    logger.info("Server started on port 8000")

Output format::

    [INFO] 2026-05-13 12:34:56 — Server started on port 8000
"""

import logging
import sys

# ── Formatter ─────────────────────────────────────────────────────────────────

_FORMAT = "[%(levelname)s] %(asctime)s — %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"

_formatter = logging.Formatter(fmt=_FORMAT, datefmt=_DATE_FMT)

# ── Shared stdout handler (created once, reused across loggers) ───────────────

_handler = logging.StreamHandler(stream=sys.stdout)
_handler.setFormatter(_formatter)

# ── Root configuration ────────────────────────────────────────────────────────
# Apply once so third-party loggers (uvicorn, sqlalchemy, etc.) also
# pick up the formatter.  Additional calls to get_logger() are cheap.

logging.basicConfig(
    level=logging.INFO,
    format=_FORMAT,
    datefmt=_DATE_FMT,
    handlers=[_handler],
    force=True,
)


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger with the Iroko AI formatter attached.

    Parameters
    ----------
    name : str
        Typically ``__name__`` of the calling module.

    Returns
    -------
    logging.Logger
    """
    logger = logging.getLogger(name)
    # Prevent duplicate handlers if get_logger is called multiple times
    # for the same name.
    if not logger.handlers:
        logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    return logger
