"""
Logging Configuration Module
Sets up comprehensive logging for the backtesting system
"""

import logging
import os
from datetime import datetime
from pathlib import Path


def setup_logger(
    name: str = 'IntradayMomentumOI',
    log_level: str = 'INFO',
    log_dir: str = 'logs',
    console_output: bool = True
) -> logging.Logger:
    """
    Setup logger with file and console handlers

    Args:
        name: Logger name
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_dir: Directory to store log files
        console_output: Whether to output to console

    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    logger.handlers = []

    # Create log directory if it doesn't exist
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    # File handler - detailed logs
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = log_path / f'backtest_{timestamp}.log'
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)  # Always log everything to file
    file_handler.setFormatter(detailed_formatter)
    logger.addHandler(file_handler)

    # File handler - trades only
    trades_log = log_path / f'trades_{timestamp}.log'
    trades_handler = logging.FileHandler(trades_log)
    trades_handler.setLevel(logging.INFO)
    trades_handler.addFilter(TradeLogFilter())
    trades_handler.setFormatter(detailed_formatter)
    logger.addHandler(trades_handler)

    # Console handler
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, log_level.upper()))
        console_handler.setFormatter(simple_formatter)
        logger.addHandler(console_handler)

    logger.info(f"Logger initialized. Log file: {log_file}")

    return logger


class TradeLogFilter(logging.Filter):
    """Filter to only log trade-related messages"""

    def filter(self, record):
        """Only allow records with trade keywords"""
        trade_keywords = ['ENTRY', 'EXIT', 'STOP LOSS', 'TRAILING', 'POSITION']
        return any(keyword in record.getMessage() for keyword in trade_keywords)


def get_logger(name: str = 'IntradayMomentumOI') -> logging.Logger:
    """
    Get existing logger or create new one

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
