"""Payload-free diagnostics for background execution boundaries."""
from __future__ import annotations

import logging
import traceback


def failure_stack(exc: BaseException) -> str:
    # Keep frame locations, but omit messages, source text and locals: any of
    # those can contain private payloads or sensitive subprocess arguments.
    frames = traceback.extract_tb(exc.__traceback__)
    return "\n".join(f"{frame.filename}:{frame.lineno} in {frame.name}" for frame in frames)


def log_failure(logger: logging.Logger, phase: str, exc: BaseException) -> None:
    logger.error("phase=%s error_type=%s\n%s", phase, type(exc).__name__, failure_stack(exc))
