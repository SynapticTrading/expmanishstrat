"""
Broker Adapter Types - Standard enums and dataclasses

These types provide a broker-agnostic interface for strategies.
Strategies use these standard types; adapters translate to broker-specific formats.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List
from datetime import datetime


class Exchange(Enum):
    """Supported exchanges"""
    NSE = "NSE"
    NFO = "NFO"
    BSE = "BSE"
    MCX = "MCX"


class TransactionType(Enum):
    """Order transaction type"""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    """Order type"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "SL"           # Stop-loss limit
    SL_M = "SL_M"       # Stop-loss market


class ProductType(Enum):
    """Product type for position"""
    INTRADAY = "INTRADAY"       # MIS in Zerodha, INTRADAY in AngelOne
    DELIVERY = "DELIVERY"       # CNC in Zerodha, DELIVERY in AngelOne
    CARRYFORWARD = "CARRYFORWARD"  # NRML in Zerodha, CARRYFORWARD in AngelOne


class OrderStatus(Enum):
    """Order status"""
    PENDING = "PENDING"
    OPEN = "OPEN"
    COMPLETE = "COMPLETE"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    TRIGGER_PENDING = "TRIGGER_PENDING"


class OptionType(Enum):
    """Option type"""
    CE = "CE"
    PE = "PE"
    FUT = "FUT"
    EQ = "EQ"


@dataclass
class OrderRequest:
    """
    Standard order request format.
    Strategies create these; adapters translate to broker-specific params.
    """
    underlying: str           # "NIFTY", "BANKNIFTY"
    option_type: str          # "CE", "PE", "FUT", "EQ"
    strike: int               # 25000 (0 for futures/equity)
    expiry: str               # "2025-01-30" format
    exchange: Exchange
    transaction_type: TransactionType
    order_type: OrderType
    quantity: int
    price: Optional[float] = None       # For LIMIT orders
    trigger_price: Optional[float] = None  # For SL orders
    product_type: ProductType = ProductType.INTRADAY
    tag: str = ""             # Optional order tag for tracking


@dataclass
class OrderResponse:
    """
    Standard order response format.
    Adapters return these from place_order, modify_order, etc.
    """
    success: bool
    order_id: str
    status: OrderStatus
    message: str = ""
    filled_quantity: int = 0
    average_price: float = 0.0
    timestamp: Optional[datetime] = None


@dataclass
class Quote:
    """
    Standard quote/market data format.
    """
    ltp: float                # Last traded price
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0
    oi: int = 0               # Open interest
    bid: float = 0.0
    ask: float = 0.0
    bid_qty: int = 0
    ask_qty: int = 0
    timestamp: Optional[str] = None
    change: float = 0.0       # Change from previous close
    change_pct: float = 0.0   # Change percentage


@dataclass
class Position:
    """
    Standard position format.
    """
    underlying: str
    option_type: str          # "CE", "PE", "FUT", "EQ"
    strike: int
    expiry: str
    exchange: str
    quantity: int             # Positive for long, negative for short
    avg_price: float          # Average entry price
    ltp: float = 0.0          # Current LTP
    pnl: float = 0.0          # Unrealized P&L
    pnl_pct: float = 0.0      # P&L percentage
    product_type: str = "INTRADAY"
    token: str = ""           # Instrument token
    symbol: str = ""          # Trading symbol


@dataclass
class Holding:
    """
    Standard holding format (for delivery positions).
    """
    symbol: str
    quantity: int
    avg_price: float
    ltp: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0


@dataclass
class Funds:
    """
    Standard account funds format.
    """
    available_cash: float     # Cash available for trading
    used_margin: float        # Margin currently used
    available_margin: float   # Total available margin
    total_balance: float = 0.0  # Total account balance
    realized_pnl: float = 0.0   # Today's realized P&L


@dataclass
class InstrumentInfo:
    """
    Standard instrument information.
    """
    token: str                # Instrument token
    symbol: str               # Trading symbol
    underlying: str           # "NIFTY", "BANKNIFTY"
    option_type: str          # "CE", "PE", "FUT", "EQ"
    strike: int
    expiry: str
    exchange: str = "NFO"
    lot_size: int = 1
    tick_size: float = 0.05


@dataclass
class OptionChainRow:
    """
    Single row in an option chain.
    """
    strike: int
    expiry: str
    ce_ltp: float = 0.0
    ce_oi: int = 0
    ce_volume: int = 0
    ce_bid: float = 0.0
    ce_ask: float = 0.0
    ce_token: str = ""
    pe_ltp: float = 0.0
    pe_oi: int = 0
    pe_volume: int = 0
    pe_bid: float = 0.0
    pe_ask: float = 0.0
    pe_token: str = ""
