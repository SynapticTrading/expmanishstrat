"""
Broker Adapter Base Class

Abstract base class for all broker adapters.
Strategies use standard params -> Adapters map to broker-specific formats.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from datetime import datetime
import logging
import pandas as pd

from .types import (
    OrderRequest, OrderResponse, Quote, Position, Funds
)

logger = logging.getLogger(__name__)


class BrokerAdapter(ABC):
    """
    Base class for all broker adapters.

    Provides a unified interface for strategies to interact with any broker.
    Subclasses implement broker-specific logic while exposing a standard interface.

    Key Features:
    - Token-based instrument resolution (via ContractManager)
    - Standardized order types and responses
    - Broker-agnostic market data access
    """

    def __init__(self, credentials: dict, contract_manager=None):
        """
        Initialize the adapter.

        Args:
            credentials: Broker-specific credentials dict
            contract_manager: ContractManager instance for instrument resolution
        """
        self.credentials = credentials
        self.contract_manager = contract_manager
        self._connected = False
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    # ══════════════════════════════════════════════════════════════════════════
    # INSTRUMENT RESOLUTION (Uses ContractManager)
    # ══════════════════════════════════════════════════════════════════════════

    def _resolve_instrument(self, underlying: str, option_type: str,
                           strike: int, expiry: str) -> Optional[Dict]:
        """
        Resolve standard params to instrument token.

        Uses ContractManager for token-based lookups, eliminating
        the need to construct broker-specific symbols.

        Args:
            underlying: Underlying symbol (e.g., "NIFTY") - reserved for future use
            option_type: "CE", "PE", "FUT", or "EQ"
            strike: Strike price (0 for futures/equity)
            expiry: Expiry date string (YYYY-MM-DD)

        Returns:
            dict: {'token': '123456', 'symbol': 'NIFTY...'} or None
        """
        # Note: underlying is reserved for future multi-underlying support
        _ = underlying

        if not self.contract_manager:
            self._logger.warning("No contract manager - falling back to symbol construction")
            return None

        if option_type in ('CE', 'PE'):
            return self.contract_manager.get_option_contract(expiry, strike, option_type)
        else:
            # For futures/equity, may need different lookup
            self._logger.warning(f"Non-option instrument type: {option_type}")
            return None

    def _get_instrument_key(self, underlying: str, option_type: str,
                           strike: int, expiry: str) -> Optional[str]:
        """
        Get the instrument key for API calls.

        Prefers token-based lookups; falls back to symbol if needed.

        Args:
            underlying: Underlying symbol
            option_type: "CE", "PE", "FUT", "EQ"
            strike: Strike price
            expiry: Expiry date

        Returns:
            str: Instrument key (token or symbol) or None
        """
        contract = self._resolve_instrument(underlying, option_type, strike, expiry)
        if contract:
            return contract.get('token') or contract.get('symbol')
        return None

    # ══════════════════════════════════════════════════════════════════════════
    # CONNECTION MANAGEMENT
    # ══════════════════════════════════════════════════════════════════════════

    @abstractmethod
    def connect(self) -> bool:
        """
        Connect to the broker API.

        Returns:
            bool: True if connected successfully
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """
        Disconnect from the broker API.
        """
        pass

    def is_connected(self) -> bool:
        """
        Check if connected to broker.

        Returns:
            bool: True if connected
        """
        return self._connected

    @property
    @abstractmethod
    def broker_name(self) -> str:
        """
        Get broker name.

        Returns:
            str: Broker name (e.g., "zerodha", "angelone")
        """
        pass

    # ══════════════════════════════════════════════════════════════════════════
    # MARKET DATA
    # ══════════════════════════════════════════════════════════════════════════

    @abstractmethod
    def get_ltp(self, underlying: str, option_type: str,
                strike: int, expiry: str) -> Optional[float]:
        """
        Get Last Traded Price for an instrument.

        Args:
            underlying: "NIFTY", "BANKNIFTY"
            option_type: "CE", "PE", "FUT", "EQ"
            strike: Strike price (0 for futures/equity)
            expiry: Expiry date (YYYY-MM-DD)

        Returns:
            float: LTP or None if unavailable
        """
        pass

    @abstractmethod
    def get_quote(self, underlying: str, option_type: str,
                  strike: int, expiry: str) -> Optional[Quote]:
        """
        Get full quote for an instrument.

        Args:
            underlying: "NIFTY", "BANKNIFTY"
            option_type: "CE", "PE", "FUT", "EQ"
            strike: Strike price
            expiry: Expiry date

        Returns:
            Quote: Quote object or None
        """
        pass

    @abstractmethod
    def get_quotes(self, instruments: List[tuple]) -> Dict[tuple, Quote]:
        """
        Get quotes for multiple instruments.

        Args:
            instruments: List of (underlying, option_type, strike, expiry) tuples

        Returns:
            dict: {(underlying, option_type, strike, expiry): Quote}
        """
        pass

    @abstractmethod
    def get_option_chain(self, underlying: str, expiry: str,
                         strikes: List[int]) -> pd.DataFrame:
        """
        Get option chain data with 5-minute OHLC candles.

        Fetches actual 5-minute candle data (not just LTP) for accurate OHLC values.
        Returns the latest complete candle (second-to-last) to avoid partial data.

        Data Sources:
            - OHLC & volume: From 5-minute candle data
            - OI (Open Interest): From quote/market data API
            - Fallback: Uses LTP for OHLC if candle unavailable

        Args:
            underlying: "NIFTY", "BANKNIFTY"
            expiry: Expiry date (YYYY-MM-DD)
            strikes: List of strike prices

        Returns:
            DataFrame: Option chain with columns:
                - strike: Strike price
                - option_type: 'CE' or 'PE'
                - expiry: Expiry date
                - open: Candle open price (fallback: LTP)
                - high: Candle high price (fallback: LTP)
                - low: Candle low price (fallback: LTP)
                - close: Candle close price (NOT LTP, fallback: LTP)
                - OI: Open Interest from quotes
                - volume: Candle volume (fallback: 0)
                - instrument_token: Token identifier
                - tradingsymbol: Symbol name (Zerodha only)

        Note:
            The 'close' column contains candle close price, which may differ from
            current LTP. This provides more accurate 5-minute price action data.
        """
        pass

    @abstractmethod
    def get_historical_candles(self, underlying: str, option_type: str,
                              strike: int, expiry: str,
                              from_time: datetime, to_time: datetime) -> List[Dict]:
        """
        Fetch historical 5-minute OHLCV candles for a specific option strike.

        Used for:
        1. Initializing VWAP when strike changes mid-day
        2. Backfilling data when system starts after 9:15 AM

        Args:
            underlying: "NIFTY" or "BANKNIFTY"
            option_type: "CE" or "PE"
            strike: Strike price (e.g., 25450)
            expiry: Expiry date (YYYY-MM-DD)
            from_time: Start time (typically 9:15 AM)
            to_time: End time (current time)

        Returns:
            List[Dict]: List of candles, each with:
                {
                    'timestamp': datetime,
                    'open': float,
                    'high': float,
                    'low': float,
                    'close': float,
                    'volume': int  # Cumulative from market open
                }

            Returns empty list if:
            - No data available
            - API error
            - Invalid instrument

        Notes:
            - Volume is CUMULATIVE from 9:15 AM (not interval volume)
            - Candles are sorted chronologically (oldest first)
            - Both brokers can fetch full day (~75 candles) in one API call
        """
        pass

    @abstractmethod
    def get_spot_price(self, underlying: str = "NIFTY") -> Optional[float]:
        """
        Get spot price for underlying.

        Args:
            underlying: "NIFTY", "BANKNIFTY", etc.

        Returns:
            float: Spot price or None
        """
        pass

    @abstractmethod
    # ══════════════════════════════════════════════════════════════════════════
    # ORDER MANAGEMENT
    # ══════════════════════════════════════════════════════════════════════════

    @abstractmethod
    def place_order(self, order: OrderRequest) -> OrderResponse:
        """
        Place a new order.

        Args:
            order: OrderRequest with all order details

        Returns:
            OrderResponse: Response with order_id and status
        """
        pass

    @abstractmethod
    def modify_order(self, order_id: str, changes: dict) -> OrderResponse:
        """
        Modify an existing order.

        Args:
            order_id: Order ID to modify
            changes: Dict of fields to modify (price, quantity, trigger_price, etc.)

        Returns:
            OrderResponse: Response with updated status
        """
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> OrderResponse:
        """
        Cancel an existing order.

        Args:
            order_id: Order ID to cancel

        Returns:
            OrderResponse: Response with cancellation status
        """
        pass

    @abstractmethod
    def get_order(self, order_id: str) -> Optional[OrderResponse]:
        """
        Get order details by ID.

        Args:
            order_id: Order ID

        Returns:
            OrderResponse: Order details or None
        """
        pass

    @abstractmethod
    def get_orders(self) -> List[OrderResponse]:
        """
        Get all orders for the day.

        Returns:
            list: List of OrderResponse objects
        """
        pass

    # ══════════════════════════════════════════════════════════════════════════
    # POSITIONS & ACCOUNT
    # ══════════════════════════════════════════════════════════════════════════

    @abstractmethod
    def get_positions(self) -> List[Position]:
        """
        Get all open positions.

        Returns:
            list: List of Position objects
        """
        pass

    @abstractmethod
    def get_holdings(self) -> List[Position]:
        """
        Get all holdings (delivery positions).

        Returns:
            list: List of Position objects
        """
        pass

    @abstractmethod
    def get_funds(self) -> Optional[Funds]:
        """
        Get account funds/margin info.

        Returns:
            Funds: Account funds or None
        """
        pass

    # ══════════════════════════════════════════════════════════════════════════
    # MARKET STATUS
    # ══════════════════════════════════════════════════════════════════════════

    @abstractmethod
    def is_market_open(self) -> bool:
        """
        Check if market is currently open.

        Returns:
            bool: True if market is open
        """
        pass

    def get_next_expiry(self, underlying: str = "NIFTY") -> Optional[str]:
        """
        Get next expiry date.

        Args:
            underlying: Underlying symbol - reserved for future use

        Returns:
            str: Next expiry date (YYYY-MM-DD) or None
        """
        # Note: underlying is reserved for future multi-underlying support
        _ = underlying

        if self.contract_manager:
            return self.contract_manager.get_options_expiry('current_week')
        return None

    # ══════════════════════════════════════════════════════════════════════════
    # UTILITY METHODS
    # ══════════════════════════════════════════════════════════════════════════

    def wait_for_next_candle(self, interval_minutes: int = 5) -> None:
        """
        Wait until next candle boundary.

        Args:
            interval_minutes: Candle interval in minutes
        """
        import time
        from datetime import datetime, timedelta

        now = datetime.now()
        current_minute = now.minute
        minutes_past = current_minute % interval_minutes

        if minutes_past == 0 and now.second < 5:
            minutes_to_wait = interval_minutes
        else:
            minutes_to_wait = interval_minutes - minutes_past

        next_candle = now + timedelta(minutes=minutes_to_wait)
        next_candle = next_candle.replace(second=0, microsecond=0)

        wait_seconds = (next_candle - now).total_seconds()
        if wait_seconds < 1:
            wait_seconds = interval_minutes * 60

        self._logger.info(f"Waiting {wait_seconds:.0f}s for next candle at {next_candle.strftime('%H:%M:%S')}")
        time.sleep(wait_seconds)

    @abstractmethod
    def load_instruments(self) -> bool:
        """
        Load instrument cache for the broker.

        Returns:
            bool: True if instruments loaded successfully
        """
        pass

    @abstractmethod
    def logout(self) -> None:
        """
        Logout from the broker API.
        Alias for disconnect() for backward compatibility.
        """
        pass

    def get_options_chain(self, expiry: str, strikes: List[int]) -> pd.DataFrame:
        """
        Get option chain data (convenience method).

        This is a simplified version that defaults underlying to "NIFTY".
        Use get_option_chain() for full control.

        Args:
            expiry: Expiry date (YYYY-MM-DD)
            strikes: List of strike prices

        Returns:
            DataFrame: Option chain data
        """
        return self.get_option_chain("NIFTY", expiry, strikes)
