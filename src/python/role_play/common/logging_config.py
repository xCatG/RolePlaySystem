"""Logging configuration for the Role Play System."""

import logging
import logging.config
import os
import sys
import json
from typing import Any, Dict


class StructuredFormatter(logging.Formatter):
    """Custom formatter that outputs structured JSON logs for Cloud Logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Base log entry
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "severity": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)
        
        # Add environment info
        try:
            from .environment import environment_name
            log_entry["environment"] = environment_name()
        except Exception:
            log_entry["environment"] = os.getenv("ENV", "unknown")
        log_entry["service"] = os.getenv("SERVICE_NAME", "rps")
        log_entry["version"] = os.getenv("GIT_VERSION", "unknown")
        
        return json.dumps(log_entry)


def setup_logging(log_level: str = "INFO", use_structured: bool = True) -> None:
    """
    Configure logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        use_structured: Whether to use structured JSON logging (for cloud environments)
    """
    # Convert string log level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    
    try:
        from .environment import resolve_environment
        is_dev = (resolve_environment().value == "dev")
    except Exception:
        is_dev = (os.getenv("ENV", "dev") == "dev")

    if use_structured and not is_dev:
        # Use structured JSON logging for non-dev environments
        formatter = StructuredFormatter()
    else:
        # Use simple format for development
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Set specific logger levels
    # Reduce noise from libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    # Log the configuration
    logger = logging.getLogger(__name__)
    try:
        from .environment import environment_name as _env_name
        env_name_value = _env_name()
    except Exception:
        env_name_value = os.getenv("ENV", "dev")

    logger.info(
        "Logging configured",
        extra={
            "extra_fields": {
                "log_level": log_level,
                "use_structured": use_structured,
                "environment": env_name_value,
            }
        }
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)
