"""
Logging configuration for telegram-upload.

This module provides centralized logging setup with configurable
levels and formatting.
"""
import logging
import os
import sys
from typing import Optional


DEFAULT_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DEFAULT_LOG_LEVEL = logging.INFO


def setup_logging(
    level: Optional[int] = None,
    log_file: Optional[str] = None,
    format_string: Optional[str] = None
) -> logging.Logger:
    """
    Setup logging configuration for telegram-upload.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
               Can also be set via TELEGRAM_UPLOAD_LOG_LEVEL environment variable.
        log_file: Optional file path to write logs to.
                  Can also be set via TELEGRAM_UPLOAD_LOG_FILE environment variable.
        format_string: Custom log format string.

    Returns:
        Configured root logger for telegram_upload package.

    Environment Variables:
        TELEGRAM_UPLOAD_LOG_LEVEL: Set log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        TELEGRAM_UPLOAD_LOG_FILE: Path to log file (in addition to console output)

    Example:
        >>> from telegram_upload.logging_config import setup_logging
        >>> setup_logging(level=logging.DEBUG)
        >>> # Or via environment:
        >>> # export TELEGRAM_UPLOAD_LOG_LEVEL=DEBUG
        >>> setup_logging()
    """
    # Determine log level from parameter or environment
    if level is None:
        level_name = os.environ.get('TELEGRAM_UPLOAD_LOG_LEVEL', 'INFO').upper()
        level = getattr(logging, level_name, DEFAULT_LOG_LEVEL)

    # Determine log file from parameter or environment
    if log_file is None:
        log_file = os.environ.get('TELEGRAM_UPLOAD_LOG_FILE')

    # Use default format if not specified
    if format_string is None:
        format_string = DEFAULT_LOG_FORMAT

    # Get the root logger for telegram_upload package
    logger = logging.getLogger('telegram_upload')
    logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(format_string)

    # Console handler (stderr)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            logger.info(f'Logging to file: {log_file}')
        except (OSError, PermissionError) as e:
            logger.warning(f'Failed to setup file logging to {log_file}: {e}')

    # Prevent propagation to root logger to avoid duplicate logs
    logger.propagate = False

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module.

    Args:
        name: Module name (typically __name__)

    Returns:
        Logger instance for the module.

    Example:
        >>> from telegram_upload.logging_config import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info('Starting upload...')
    """
    return logging.getLogger(name)
