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

    # ══════════════════════════════════════════════════════════════════════════
    # CONNECTION
    # ══════════════════════════════════════════════════════════════════════════

    def connect(self) -> bool:
        """Connect to Zerodha API with token-based approach."""
        try:
            # Import Zerodha connection utilities
            from paper_trading.legacy.zerodha_connection import ZerodhaConnection
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
                self._connected = True
                logger.info("Connected to Zerodha")
                logger.info("✓ PURE TOKEN-BASED MODE: All API calls use instrument_token directly")
                logger.info("✓ NO tradingsymbol lookups - tokens from contracts_cache.json")
                logger.info("✓ NO legacy data feed - pure adapter + ContractManager architecture")
                
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
        """
        Get option chain data using token-based approach.

        Uses ContractManager + Kite API directly (no legacy data feed).
        Fetches LTP, OI, and volume for all strikes in a single batch call.
        """
        if not self._connected or not self._kite:
            logger.error("Not connected to Zerodha")
            return pd.DataFrame()

        try:
            # Build list of contracts to fetch
            contracts = []
            for strike in strikes:
                for option_type in ['CE', 'PE']:
                    contracts.append((expiry, strike, option_type))

            # Batch resolve instrument tokens using ContractManager
            contract_data = self.contract_manager.batch_get_instrument_tokens(contracts)

            # Collect tokens for batch quote fetch
            token_map = {}  # token -> (strike, option_type, expiry)
            instrument_tokens = []

            for (exp, strike, opt_type), contract in contract_data.items():
                if contract:
                    token = contract.get('zerodha_instrument_token')
                    if token:
                        instrument_tokens.append(str(token))
                        token_map[str(token)] = (strike, opt_type, exp)

            if not instrument_tokens:
                logger.warning(f"No valid tokens found for expiry {expiry}")
                return pd.DataFrame()

            logger.info(f"Fetching quotes for {len(instrument_tokens)} options (TOKEN-BASED)...")

            # Batch fetch all quotes using tokens with retry
            max_retries = 3
            retry_delay = 1
            quotes = None

            for attempt in range(max_retries):
                try:
                    quotes = self._kite.quote(instrument_tokens)
                    break  # Success
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Quote fetch failed (attempt {attempt + 1}/{max_retries}): {e}")
                        logger.info(f"Retrying in {retry_delay}s...")
                        import time as time_module
                        time_module.sleep(retry_delay)
                        retry_delay *= 2
                    else:
                        logger.error(f"Quote fetch failed after {max_retries} attempts: {e}")
                        raise

            if not quotes:
                logger.warning("No quotes returned")
                return pd.DataFrame()

            # Build result DataFrame
            result_data = []
            for token_str, (strike, option_type, expiry_str) in token_map.items():
                quote = quotes.get(token_str, {})
                if quote:
                    ltp = quote.get('last_price', 0)
                    volume = quote.get('volume', 0)
                    oi = quote.get('oi', 0)

                    result_data.append({
                        'strike': strike,
                        'option_type': option_type,
                        'expiry': expiry_str,
                        'open': ltp,
                        'high': ltp,
                        'low': ltp,
                        'close': ltp,
                        'OI': oi,
                        'volume': volume,
                        'instrument_token': token_str
                    })

            result_df = pd.DataFrame(result_data)
            logger.info(f"✓ Retrieved {len(result_df)} option quotes")

            return result_df

        except Exception as e:
            logger.error(f"Error getting option chain: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()

    def get_spot_price(self, underlying: str = "NIFTY") -> Optional[float]:
        """
        Get spot price using Kite API directly (token-based).

        NIFTY 50 Index Token: 256265 (NSE:NIFTY 50)
        Includes retry mechanism for network errors.
        """
        if not self._connected or not self._kite:
            return None

        # NIFTY 50 index token (hardcoded, doesn't change)
        nifty_token = "NSE:NIFTY 50"

        # Retry configuration
        max_retries = 3
        retry_delay = 1  # seconds

        for attempt in range(max_retries):
            try:
                quote = self._kite.quote([nifty_token])

                if quote and nifty_token in quote:
                    return quote[nifty_token].get('last_price')

                return None

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Spot price fetch failed (attempt {attempt + 1}/{max_retries}): {e}")
                    logger.info(f"Retrying in {retry_delay}s...")
                    import time as time_module
                    time_module.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error(f"Error getting spot price after {max_retries} attempts: {e}")
                    return None

        return None

    def get_historical_candles(self, underlying: str, option_type: str,
                              strike: int, expiry: str,
                              from_time: datetime, to_time: datetime) -> List[Dict]:
        """
        Fetch historical 5-min candles from Zerodha Kite API.

        API Limits:
        - Max 2000 candles per call (intraday = ~75 candles) ✓
        - Rate limit: 3 req/sec (we only call once per strike change)
        """
        if not self._connected or not self._kite:
            logger.error("Not connected to Zerodha")
            return []

        try:
            # Step 1: Resolve instrument token
            contract = self._resolve_instrument(underlying, option_type, strike, expiry)
            if not contract:
                logger.warning(f"Could not resolve instrument: {option_type} {strike} {expiry}")
                return []

            instrument_token = contract.get('zerodha_instrument_token')
            if not instrument_token:
                logger.error(f"No instrument token for {option_type} {strike}")
                return []

            logger.info(f"Fetching historical candles: {option_type} {strike} from {from_time} to {to_time}")
            logger.info(f"Using instrument token: {instrument_token}")

            # Step 2: Fetch historical data from Kite API with retry
            # NOTE: historical_data() returns a list of dicts, not a DataFrame
            max_retries = 3
            retry_delay = 1
            historical_data = None

            for attempt in range(max_retries):
                try:
                    historical_data = self._kite.historical_data(
                        instrument_token=int(instrument_token),
                        from_date=from_time,
                        to_date=to_time,
                        interval="5minute",
                        oi=True  # Include Open Interest data
                    )
                    break  # Success
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Historical data fetch failed (attempt {attempt + 1}/{max_retries}): {e}")
                        logger.info(f"Retrying in {retry_delay}s...")
                        import time as time_module
                        time_module.sleep(retry_delay)
                        retry_delay *= 2
                    else:
                        logger.error(f"Historical data fetch failed after {max_retries} attempts: {e}")
                        raise

            if not historical_data:
                logger.warning(f"No historical data returned for {option_type} {strike}")
                return []

            logger.info(f"✓ Fetched {len(historical_data)} candles for {option_type} {strike}")

            # Step 3: Convert to standard format
            candles = []
            for candle in historical_data:
                candles.append({
                    'timestamp': candle['date'],
                    'open': float(candle['open']),
                    'high': float(candle['high']),
                    'low': float(candle['low']),
                    'close': float(candle['close']),
                    'volume': int(candle['volume']),  # INTERVAL volume (per-candle, not cumulative)
                    'oi': int(candle.get('oi', 0))  # Open Interest (if available)
                })

            return candles

        except Exception as e:
            logger.error(f"Error fetching historical candles from Zerodha: {e}")
            import traceback
            traceback.print_exc()
            return []

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
        """
        Check if market is open based on IST time.

        Market hours: 9:15 AM - 3:30 PM IST (Mon-Fri)
        """
        if not self._connected:
            return False

        try:
            from datetime import datetime, time
            import pytz

            ist = pytz.timezone('Asia/Kolkata')
            now = datetime.now(ist)

            # Check if weekday (Monday=0, Sunday=6)
            if now.weekday() >= 5:  # Saturday or Sunday
                return False

            current_time = now.time()
            market_open = time(9, 15)
            market_close = time(15, 30)

            return market_open <= current_time <= market_close

        except Exception as e:
            logger.error(f"Error checking market hours: {e}")
            return False

    def load_instruments(self) -> bool:
        """
        NO-OP in token-based mode.

        ContractManager handles all instrument lookups via contracts_cache.json.
        No need to load Zerodha's full instrument CSV.

        Returns:
            bool: Always returns True (no-op in token-based mode)
        """
        logger.info("Token-based mode: Using ContractManager (no instrument CSV needed)")
        return True

    def logout(self) -> None:
        """Logout from Zerodha API."""
        self.disconnect()

    def get_next_expiry(self) -> Optional[str]:
        """
        Get next weekly expiry using ContractManager.

        Returns:
            str: Expiry date (YYYY-MM-DD) or None
        """
        if self.contract_manager:
            return self.contract_manager.get_options_expiry('current_week')

        logger.warning("No contract manager available for expiry lookup")
        return None
