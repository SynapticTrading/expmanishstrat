"""
Zerodha Broker Adapter

Implements BrokerAdapter for Zerodha Kite Connect API.
Uses instrument tokens from ContractManager for reliable lookups.

TOKEN-BASED IMPLEMENTATION:
- All API calls use instrument_token directly (no tradingsymbol conversion)
- LTP, quote, and historical data fetches use tokens
- Zerodha API accepts both tradingsymbols and tokens - we use tokens!
- Consistent with AngelOne adapter - both are pure token-based
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd

from ..base import BrokerAdapter
from ..types import (
    OrderRequest, OrderResponse, Quote, Position, Funds,
    OrderType, ProductType, OrderStatus
)

logger = logging.getLogger(__name__)


class ZerodhaAdapter(BrokerAdapter):
    """
    Zerodha Kite Connect adapter.

    Maps standard adapter interface to Zerodha-specific API calls.
    Uses ContractManager for token-based instrument resolution.
    """

    broker_name = "zerodha"

    # ══════════════════════════════════════════════════════════════════════════
    # BROKER-SPECIFIC MAPPINGS
    # ══════════════════════════════════════════════════════════════════════════

    ORDER_TYPE_MAP = {
        OrderType.MARKET: "MARKET",
        OrderType.LIMIT: "LIMIT",
        OrderType.SL: "SL",
        OrderType.SL_M: "SL-M"
    }

    PRODUCT_MAP = {
        ProductType.INTRADAY: "MIS",
        ProductType.DELIVERY: "CNC",
        ProductType.CARRYFORWARD: "NRML"
    }

    REVERSE_PRODUCT_MAP = {
        "MIS": ProductType.INTRADAY,
        "CNC": ProductType.DELIVERY,
        "NRML": ProductType.CARRYFORWARD
    }

    STATUS_MAP = {
        "PENDING": OrderStatus.PENDING,
        "OPEN": OrderStatus.OPEN,
        "COMPLETE": OrderStatus.COMPLETE,
        "REJECTED": OrderStatus.REJECTED,
        "CANCELLED": OrderStatus.CANCELLED,
        "TRIGGER PENDING": OrderStatus.TRIGGER_PENDING
    }

    def __init__(self, credentials: dict, contract_manager=None):
        """
        Initialize Zerodha adapter.

        Args:
            credentials: Dict with api_key, api_secret, user_id, user_password, totp_key
            contract_manager: ContractManager for token lookups
        """
        super().__init__(credentials, contract_manager)
        self._kite = None
        self._data_feed = None

    # ══════════════════════════════════════════════════════════════════════════
    # CONNECTION
    # ══════════════════════════════════════════════════════════════════════════

    def connect(self) -> bool:
        """Connect to Zerodha API with token-based approach."""
        try:
            # Import Zerodha connection utilities
            from paper_trading.legacy.zerodha_connection import ZerodhaConnection
            from paper_trading.legacy.zerodha_data_feed import ZerodhaDataFeed

            # Create connection
            connection = ZerodhaConnection(
                api_key=self.credentials.get('api_key'),
                api_secret=self.credentials.get('api_secret'),
                user_id=self.credentials.get('user_id'),
                user_password=self.credentials.get('user_password'),
                totp_key=self.credentials.get('totp_key')
            )

            kite = connection.connect()
            if kite:
                self._kite = kite
                self._connection = connection
                # Pass ContractManager to DataFeed for token-based lookups
                self._data_feed = ZerodhaDataFeed(connection, contract_manager=self.contract_manager)
                self._connected = True
                logger.info("Connected to Zerodha")
                logger.info("✓ PURE TOKEN-BASED MODE: All API calls use instrument_token directly")
                logger.info("✓ NO tradingsymbol lookups - tokens from contracts_cache.json")
                
                if self.contract_manager and self.contract_manager.has_instrument_tokens():
                    logger.info("✓ ContractManager ready with cached tokens")
                else:
                    logger.warning("⚠️  ContractManager has no tokens - run: python refresh_contracts.py --broker zerodha")
                
                return True

            logger.error("Failed to connect to Zerodha")
            return False

        except Exception as e:
            logger.error(f"Zerodha connection error: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from Zerodha API."""
        if self._connected and hasattr(self, '_connection'):
            try:
                self._connection.logout()
            except Exception as e:
                logger.warning(f"Error during logout: {e}")
        self._connected = False
        self._kite = None

    @property
    def broker_name(self) -> str:
        return "zerodha"

    # ══════════════════════════════════════════════════════════════════════════
    # MARKET DATA
    # ══════════════════════════════════════════════════════════════════════════
    # NOTE: 100% TOKEN-BASED API calls (NO tradingsymbols needed!)
    # - All API calls (LTP, quote, historical) use instrument_token directly
    # - Cache stores zerodha_instrument_token (pre-loaded from contracts_cache.json)
    # - Zerodha API accepts BOTH tradingsymbols AND tokens - we use tokens!
    # - No runtime symbol conversion - direct token-based lookups
    # - Consistent with AngelOne adapter - both are pure token-based
    # ══════════════════════════════════════════════════════════════════════════

    def get_ltp(self, underlying: str, option_type: str,
                strike: int, expiry: str) -> Optional[float]:
        """Get LTP using instrument_token directly (TOKEN-BASED - no symbols!)."""
        if not self._connected or not self._kite:
            return None

        try:
            contract = self._resolve_instrument(underlying, option_type, strike, expiry)
            if not contract:
                logger.warning(f"Could not resolve instrument: {underlying} {option_type} {strike} {expiry}")
                return None

            # Get instrument_token from cache
            instrument_token = contract.get('zerodha_instrument_token')
            if not instrument_token:
                logger.error(f"No zerodha_instrument_token found for {underlying} {option_type} {strike} {expiry}")
                return None

            # Direct token-based API call (NO symbol lookup needed!)
            # Zerodha accepts both tradingsymbols AND tokens
            data = self._kite.ltp([instrument_token])

            # Response key is the token as string
            token_key = str(instrument_token)
            if token_key in data:
                return data[token_key].get('last_price')

            return None

        except Exception as e:
            logger.error(f"Error getting LTP: {e}")
            return None

    def get_quote(self, underlying: str, option_type: str,
                  strike: int, expiry: str) -> Optional[Quote]:
        """Get full quote for instrument using instrument_token directly (TOKEN-BASED - no symbols!)."""
        if not self._connected or not self._kite:
            logger.error(f"get_quote: Not connected")
            return None

        try:
            logger.debug(f"get_quote: Resolving instrument - {underlying} {strike} {option_type} {expiry}")
            contract = self._resolve_instrument(underlying, option_type, strike, expiry)
            if not contract:
                logger.error(f"get_quote: Contract not found - {underlying} {strike} {option_type} {expiry}")
                return None

            logger.debug(f"get_quote: Contract found - {contract}")

            # Get instrument_token from cache
            instrument_token = contract.get('zerodha_instrument_token')
            if not instrument_token:
                logger.error(f"No zerodha_instrument_token found in cache for {strike} {option_type}")
                return None

            logger.debug(f"get_quote: Using token {instrument_token} directly (TOKEN-BASED)")

            # Direct token-based API call (NO symbol lookup needed!)
            # Zerodha accepts both tradingsymbols AND tokens
            data = self._kite.quote([instrument_token])
            logger.debug(f"get_quote: API response type: {type(data)}")

            if not data or not isinstance(data, dict):
                logger.error(f"get_quote: Invalid API response: {data}")
                return None

            # Response key is the token as string
            token_key = str(instrument_token)
            if token_key not in data:
                logger.error(f"get_quote: Token {token_key} not in response. Available keys: {list(data.keys())}")
                return None

            q = data[token_key]
            logger.debug(f"get_quote: Quote data retrieved - LTP: {q.get('last_price')}")

            return Quote(
                ltp=q.get('last_price', 0),
                open=q.get('ohlc', {}).get('open', 0),
                high=q.get('ohlc', {}).get('high', 0),
                low=q.get('ohlc', {}).get('low', 0),
                close=q.get('ohlc', {}).get('close', 0),
                volume=q.get('volume', 0),
                oi=q.get('oi', 0),
                bid=q.get('depth', {}).get('buy', [{}])[0].get('price', 0) if q.get('depth') else 0,
                ask=q.get('depth', {}).get('sell', [{}])[0].get('price', 0) if q.get('depth') else 0
            )

        except Exception as e:
            logger.error(f"Error getting quote for {strike} {option_type}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def get_quotes(self, instruments: List[tuple]) -> Dict[tuple, Quote]:
        """Get quotes for multiple instruments."""
        results = {}
        for underlying, option_type, strike, expiry in instruments:
            quote = self.get_quote(underlying, option_type, strike, expiry)
            if quote:
                results[(underlying, option_type, strike, expiry)] = quote
        return results

    def get_option_chain(self, underlying: str, expiry: str,
                         strikes: List[int]) -> pd.DataFrame:
        """Get option chain data with 5-min candles (for entry decisions)."""
        if not self._connected or not self._data_feed:
            return pd.DataFrame()

        try:
            return self._data_feed.get_options_chain(expiry, strikes)
        except Exception as e:
            logger.error(f"Error getting option chain: {e}")
            return pd.DataFrame()

    def get_spot_price(self, underlying: str = "NIFTY") -> Optional[float]:
        """Get spot price for underlying."""
        if not self._connected or not self._data_feed:
            return None

        try:
            return self._data_feed.get_spot_price()
        except Exception as e:
            logger.error(f"Error getting spot price: {e}")
            return None

    # ══════════════════════════════════════════════════════════════════════════
    # ORDER MANAGEMENT
    # ══════════════════════════════════════════════════════════════════════════

    def place_order(self, order: OrderRequest) -> OrderResponse:
        """Place order using standard params."""
        if not self._connected:
            return OrderResponse(
                success=False,
                order_id="",
                status=OrderStatus.REJECTED,
                message="Not connected to Zerodha"
            )

        try:
            # Get contract from cache using contract_manager
            if not self.contract_manager:
                return OrderResponse(
                    success=False,
                    order_id="",
                    status=OrderStatus.REJECTED,
                    message="ContractManager not available"
                )

            # Convert expiry to string format
            expiry_str = order.expiry.strftime('%Y-%m-%d') if hasattr(order.expiry, 'strftime') else str(order.expiry)
            
            contract = self.contract_manager.get_option_contract(
                expiry_str, order.strike, order.option_type
            )

            if not contract:
                return OrderResponse(
                    success=False,
                    order_id="",
                    status=OrderStatus.REJECTED,
                    message=f"Contract not found: {order.underlying} {order.option_type} {order.strike} {expiry_str}"
                )

            # Get instrument token for TOKEN-BASED order placement
            instrument_token = contract.get('zerodha_instrument_token')
            if not instrument_token:
                return OrderResponse(
                    success=False,
                    order_id="",
                    status=OrderStatus.REJECTED,
                    message=f"No instrument token found for contract"
                )

            logger.info(f"Placing order using instrument token: {instrument_token} (TOKEN-BASED)")

            # Build Zerodha order params using INSTRUMENT TOKEN
            # Zerodha API accepts instrument tokens directly (just like quotes!)
            broker_params = {
                'tradingsymbol': instrument_token,  # Use token directly (integer, not string)
                'exchange': 'NFO',
                'transaction_type': order.transaction_type.value,
                'order_type': self.ORDER_TYPE_MAP.get(order.order_type, "MARKET"),
                'product': self.PRODUCT_MAP.get(order.product_type, "MIS"),
                'quantity': order.quantity,
                'variety': 'regular'
            }

            if order.price and order.order_type in (OrderType.LIMIT, OrderType.SL):
                broker_params['price'] = order.price
            if order.trigger_price and order.order_type in (OrderType.SL, OrderType.SL_M):
                broker_params['trigger_price'] = order.trigger_price
            if order.tag:
                broker_params['tag'] = order.tag[:20]  # Zerodha max tag length

            # Place order
            order_id = self._kite.place_order(**broker_params)

            return OrderResponse(
                success=True,
                order_id=str(order_id),
                status=OrderStatus.PENDING,
                timestamp=datetime.now()
            )

        except Exception as e:
            logger.error(f"Order placement error: {e}")
            return OrderResponse(
                success=False,
                order_id="",
                status=OrderStatus.REJECTED,
                message=str(e)
            )

    def modify_order(self, order_id: str, changes: dict) -> OrderResponse:
        """Modify existing order."""
        if not self._connected:
            return OrderResponse(
                success=False,
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message="Not connected"
            )

        try:
            modify_params = {'order_id': order_id, 'variety': 'regular'}

            if 'price' in changes:
                modify_params['price'] = changes['price']
            if 'quantity' in changes:
                modify_params['quantity'] = changes['quantity']
            if 'trigger_price' in changes:
                modify_params['trigger_price'] = changes['trigger_price']

            self._kite.modify_order(**modify_params)

            return OrderResponse(
                success=True,
                order_id=order_id,
                status=OrderStatus.PENDING,
                message="Order modified"
            )

        except Exception as e:
            logger.error(f"Order modification error: {e}")
            return OrderResponse(
                success=False,
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message=str(e)
            )

    def cancel_order(self, order_id: str) -> OrderResponse:
        """Cancel existing order."""
        if not self._connected:
            return OrderResponse(
                success=False,
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message="Not connected"
            )

        try:
            self._kite.cancel_order(order_id=order_id, variety='regular')

            return OrderResponse(
                success=True,
                order_id=order_id,
                status=OrderStatus.CANCELLED,
                message="Order cancelled"
            )

        except Exception as e:
            logger.error(f"Order cancellation error: {e}")
            return OrderResponse(
                success=False,
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message=str(e)
            )

    def get_order(self, order_id: str) -> Optional[OrderResponse]:
        """Get order by ID."""
        if not self._connected:
            return None

        try:
            orders = self._kite.orders()
            for o in orders:
                if str(o.get('order_id')) == str(order_id):
                    return OrderResponse(
                        success=True,
                        order_id=str(o['order_id']),
                        status=self.STATUS_MAP.get(o.get('status', ''), OrderStatus.PENDING),
                        filled_quantity=o.get('filled_quantity', 0),
                        average_price=o.get('average_price', 0),
                        message=o.get('status_message', '')
                    )
            return None

        except Exception as e:
            logger.error(f"Error getting order: {e}")
            return None

    def get_orders(self) -> List[OrderResponse]:
        """Get all orders for the day."""
        if not self._connected:
            return []

        try:
            orders = self._kite.orders()
            return [
                OrderResponse(
                    success=True,
                    order_id=str(o['order_id']),
                    status=self.STATUS_MAP.get(o.get('status', ''), OrderStatus.PENDING),
                    filled_quantity=o.get('filled_quantity', 0),
                    average_price=o.get('average_price', 0),
                    message=o.get('status_message', '')
                )
                for o in orders
            ]

        except Exception as e:
            logger.error(f"Error getting orders: {e}")
            return []

    # ══════════════════════════════════════════════════════════════════════════
    # POSITIONS & ACCOUNT
    # ══════════════════════════════════════════════════════════════════════════

    def get_positions(self) -> List[Position]:
        """Get all open positions."""
        if not self._connected:
            return []

        try:
            positions = self._kite.positions()
            day_positions = positions.get('day', [])

            result = []
            for p in day_positions:
                if p.get('quantity', 0) == 0:
                    continue

                # Parse symbol to extract details
                symbol = p.get('tradingsymbol', '')
                result.append(Position(
                    underlying='NIFTY',  # Would need parsing for accuracy
                    option_type='CE' if 'CE' in symbol else 'PE' if 'PE' in symbol else 'FUT',
                    strike=0,  # Would need parsing
                    expiry='',
                    exchange=p.get('exchange', 'NFO'),
                    quantity=p.get('quantity', 0),
                    avg_price=p.get('average_price', 0),
                    ltp=p.get('last_price', 0),
                    pnl=p.get('pnl', 0),
                    product_type=p.get('product', 'MIS'),
                    symbol=symbol
                ))

            return result

        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    def get_holdings(self) -> List[Position]:
        """Get holdings."""
        if not self._connected:
            return []

        try:
            holdings = self._kite.holdings()
            return [
                Position(
                    underlying=h.get('tradingsymbol', ''),
                    option_type='EQ',
                    strike=0,
                    expiry='',
                    exchange='NSE',
                    quantity=h.get('quantity', 0),
                    avg_price=h.get('average_price', 0),
                    ltp=h.get('last_price', 0),
                    pnl=h.get('pnl', 0),
                    symbol=h.get('tradingsymbol', '')
                )
                for h in holdings
            ]

        except Exception as e:
            logger.error(f"Error getting holdings: {e}")
            return []

    def get_funds(self) -> Optional[Funds]:
        """Get account funds."""
        if not self._connected:
            return None

        try:
            margins = self._kite.margins()
            equity = margins.get('equity', {})

            return Funds(
                available_cash=equity.get('available', {}).get('cash', 0),
                used_margin=equity.get('utilised', {}).get('debits', 0),
                available_margin=equity.get('available', {}).get('live_balance', 0),
                total_balance=equity.get('net', 0)
            )

        except Exception as e:
            logger.error(f"Error getting funds: {e}")
            return None

    # ══════════════════════════════════════════════════════════════════════════
    # MARKET STATUS
    # ══════════════════════════════════════════════════════════════════════════

    def is_market_open(self) -> bool:
        """Check if market is open."""
        if not self._connected or not self._data_feed:
            return False
        return self._data_feed.is_market_open()

    def load_instruments(self) -> bool:
        """
        DEPRECATED: No longer needed in token-based approach.
        
        This method is kept for backward compatibility but delegates to DataFeed.
        In token-based mode, this is a no-op since all lookups use ContractManager.
        
        Returns:
            bool: Always returns True (no-op in token-based mode)
        """
        if self._data_feed:
            return self._data_feed.load_instruments()  # Returns True (no-op)
        return True

    def logout(self) -> None:
        """Logout from Zerodha API."""
        self.disconnect()

    def get_next_expiry(self) -> Optional[str]:
        """Get next weekly expiry."""
        # Try contract_manager first
        if self.contract_manager:
            return self.contract_manager.get_options_expiry('current_week')
        # Fallback to data_feed
        if self._data_feed:
            return self._data_feed.get_next_expiry()
        return None
