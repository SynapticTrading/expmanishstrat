"""
Broker Adapter Package

Provides a unified, broker-agnostic interface for trading strategies.

Usage:
    from paper_trading.brokers.adapter import create_adapter, BrokerAdapter

    # Create adapter with auto-detection
    adapter = create_adapter(credentials, contract_manager=cm)

    # Or specify broker explicitly
    adapter = create_adapter(credentials, broker='zerodha', contract_manager=cm)

    # Connect and use
    adapter.connect()
    ltp = adapter.get_ltp("NIFTY", "CE", 23000, "2026-01-20")
    order_resp = adapter.place_order(OrderRequest(...))
"""

from .base import BrokerAdapter
from .factory import create_adapter, get_available_brokers, register_adapter
from .types import (
    Exchange,
    TransactionType,
    OrderType,
    ProductType,
    OrderStatus,
    OptionType,
    OrderRequest,
    OrderResponse,
    Quote,
    Position,
    Holding,
    Funds,
    InstrumentInfo,
    OptionChainRow
)

__all__ = [
    # Factory
    'create_adapter',
    'get_available_brokers',
    'register_adapter',

    # Base class
    'BrokerAdapter',

    # Enums
    'Exchange',
    'TransactionType',
    'OrderType',
    'ProductType',
    'OrderStatus',
    'OptionType',

    # Data classes
    'OrderRequest',
    'OrderResponse',
    'Quote',
    'Position',
    'Holding',
    'Funds',
    'InstrumentInfo',
    'OptionChainRow'
]
