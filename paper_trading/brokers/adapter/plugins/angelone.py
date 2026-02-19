"""
AngelOne Broker Adapter

Implements BrokerAdapter for AngelOne SmartAPI.
Uses instrument tokens from ContractManager for reliable lookups.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, time, date, timedelta
import pandas as pd
import requests
import time as time_module

from ..base import BrokerAdapter
from ..types import (
    OrderRequest, OrderResponse, Quote, Position, Funds,
    OrderType, ProductType, OrderStatus
)

logger = logging.getLogger(__name__)


class AngelOneAdapter(BrokerAdapter):
    """
    AngelOne SmartAPI adapter.

    Maps standard adapter interface to AngelOne-specific API calls.
    Uses ContractManager for token-based instrument resolution.
    """

    broker_name = "angelone"

    # ══════════════════════════════════════════════════════════════════════════
    # BROKER-SPECIFIC MAPPINGS
    # ══════════════════════════════════════════════════════════════════════════

    ORDER_TYPE_MAP = {
        OrderType.MARKET: "MARKET",
        OrderType.LIMIT: "LIMIT",
        OrderType.SL: "STOPLOSS_LIMIT",
        OrderType.SL_M: "STOPLOSS_MARKET"
    }

    PRODUCT_MAP = {
        ProductType.INTRADAY: "INTRADAY",
        ProductType.DELIVERY: "DELIVERY",
        ProductType.CARRYFORWARD: "CARRYFORWARD"
    }

    STATUS_MAP = {
        "pending": OrderStatus.PENDING,
        "open": OrderStatus.OPEN,
        "complete": OrderStatus.COMPLETE,
        "rejected": OrderStatus.REJECTED,
        "cancelled": OrderStatus.CANCELLED,
        "trigger pending": OrderStatus.TRIGGER_PENDING
    }

    # AngelOne Nifty index token
    NIFTY_TOKEN = "99926000"

    def __init__(self, credentials: dict, contract_manager=None):
        """
        Initialize AngelOne adapter.

        Args:
            credentials: Dict with api_key, username (client_code), password, totp_token
            contract_manager: ContractManager for token lookups
        """
        super().__init__(credentials, contract_manager)
        self._smart_api = None
        self._connection = None

        # Instrument storage
        self.nfo_instruments = None
        self.nifty_options = None
        self.token_map = {}

    # ══════════════════════════════════════════════════════════════════════════
    # CONNECTION
    # ══════════════════════════════════════════════════════════════════════════

    def connect(self) -> bool:
        """Connect to AngelOne API and load instruments."""
        try:
            from paper_trading.legacy.angelone_connection import AngelOneConnection
            import pandas as pd
            import requests

            self._connection = AngelOneConnection(
                api_key=self.credentials.get('api_key'),
                username=self.credentials.get('username'),
                password=self.credentials.get('password'),
                totp_token=self.credentials.get('totp_token')
            )

            session_data = self._connection.connect()
            if session_data:
                self._smart_api = self._connection.smart_api
                self._connected = True
                
                # Load AngelOne master instruments for token->symbol lookup
                try:
                    logger.info("Loading AngelOne master instruments for token lookup...")
                    url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
                    response = requests.get(url, timeout=10)
                    instruments = response.json()
                    df = pd.DataFrame(instruments)

                    # Filter for NFO (F&O) instruments only
                    self.nfo_instruments = df[df['exch_seg'] == 'NFO'].copy()
                    logger.info(f"Loaded {len(self.nfo_instruments)} NFO instruments")

                    # Extract NIFTY options for refresh_contracts.py
                    # Filter for NIFTY options (OPTIDX with name='NIFTY')
                    nifty_opts = self.nfo_instruments[
                        (self.nfo_instruments['name'] == 'NIFTY') &
                        (self.nfo_instruments['instrumenttype'] == 'OPTIDX')
                    ].copy()

                    if not nifty_opts.empty:
                        # Parse expiry dates
                        nifty_opts['expiry'] = pd.to_datetime(nifty_opts['expiry'], format='%d%b%Y', errors='coerce').dt.date

                        # Extract option type (CE/PE) from symbol
                        # AngelOne format: "NIFTY30JAN2623500CE" -> last 2 chars are CE/PE
                        nifty_opts['option_type'] = nifty_opts['symbol'].str[-2:]

                        # Convert strike to numeric
                        nifty_opts['strike'] = pd.to_numeric(nifty_opts['strike'], errors='coerce')

                        self.nifty_options = nifty_opts
                        logger.info(f"Extracted {len(self.nifty_options)} NIFTY options")
                    else:
                        logger.warning("No NIFTY options found in master instruments")
                        self.nifty_options = None

                except Exception as e:
                    logger.warning(f"Could not load master instruments: {e}")
                    self.nfo_instruments = None
                    self.nifty_options = None
                
                logger.info("Connected to AngelOne")
                return True

            logger.error("Failed to connect to AngelOne")
            return False

        except Exception as e:
            logger.error(f"AngelOne connection error: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from AngelOne API."""
        if self._connected and self._connection:
            try:
                self._connection.logout()
            except Exception as e:
                logger.warning(f"Error during logout: {e}")
        self._connected = False
        self._smart_api = None

    @property
    def broker_name(self) -> str:
        return "angelone"

    def _get_symbol_from_token(self, token: str) -> Optional[str]:
        """
        Get trading symbol from AngelOne master instruments using token.
        This eliminates the need for manual symbol construction.
        
        Args:
            token: Exchange token (e.g., '58661')
        
        Returns:
            Trading symbol string (e.g., 'NIFTY27JAN2625000CE') or None
        """
        try:
            # Use AngelOne's searchScrip API to get symbol by token
            # Or query from loaded instruments if available
            if hasattr(self, 'nfo_instruments') and self.nfo_instruments is not None:
                # Search in cached instruments
                result = self.nfo_instruments[self.nfo_instruments['token'] == token]
                if not result.empty:
                    return result.iloc[0]['symbol']
            
            # If not cached, try API search (if available)
            # For now, return None and let caller handle
            logger.warning(f"Could not find symbol for token {token} in cached instruments")
            return None
            
        except Exception as e:
            logger.error(f"Error getting symbol from token {token}: {e}")
            return None

    # ══════════════════════════════════════════════════════════════════════════
    # MARKET DATA
    # ══════════════════════════════════════════════════════════════════════════

    def get_ltp(self, underlying: str, option_type: str,
                strike: int, expiry: str) -> Optional[float]:
        """Get LTP using token-based lookup (TOKEN-ONLY, no symbols!)."""
        if not self._connected:
            return None

        try:
            contract = self._resolve_instrument(underlying, option_type, strike, expiry)
            if not contract:
                logger.warning(f"Could not resolve instrument: {underlying} {option_type} {strike} {expiry}")
                return None

            token = contract.get('token')
            if not token:
                logger.error(f"No token found for {underlying} {option_type} {strike} {expiry}")
                return None

            # AngelOne market data call (TOKEN-BASED - no symbol needed!)
            market_data = self._smart_api.getMarketData(
                mode="LTP",  # Use LTP mode for faster response
                exchangeTokens={"NFO": [token]}
            )

            if market_data and market_data.get('status'):
                fetched = market_data.get('data', {}).get('fetched', [])
                if fetched and len(fetched) > 0:
                    return float(fetched[0].get('ltp', 0))

            return None

        except Exception as e:
            logger.error(f"Error getting LTP: {e}")
            return None

    def get_quote(self, underlying: str, option_type: str,
                  strike: int, expiry: str) -> Optional[Quote]:
        """Get full quote for instrument (TOKEN-ONLY, no symbols!)."""
        if not self._connected:
            return None

        try:
            contract = self._resolve_instrument(underlying, option_type, strike, expiry)
            if not contract:
                return None

            token = contract.get('token')
            if not token:
                logger.error(f"No token found in cache")
                return None

            # AngelOne full market data (TOKEN-BASED - no symbol needed!)
            market_data = self._smart_api.getMarketData(
                mode="FULL",
                exchangeTokens={"NFO": [token]}
            )

            if market_data and market_data.get('status'):
                fetched = market_data.get('data', {}).get('fetched', [])
                if fetched:
                    q = fetched[0]
                    return Quote(
                        ltp=float(q.get('ltp', 0)),
                        open=float(q.get('open', 0)),
                        high=float(q.get('high', 0)),
                        low=float(q.get('low', 0)),
                        close=float(q.get('close', 0)),
                        volume=int(q.get('tradeVolume', 0)),
                        oi=int(q.get('opnInterest', 0)),
                        bid=float(q.get('totBuyQuan', 0)),
                        ask=float(q.get('totSellQuan', 0))
                    )

            return None

        except Exception as e:
            logger.error(f"Error getting quote: {e}")
            return None

    def get_quotes(self, instruments: List[tuple]) -> Dict[tuple, Quote]:
        """Get quotes for multiple instruments."""
        results = {}

        # Batch requests to avoid rate limits
        for underlying, option_type, strike, expiry in instruments:
            quote = self.get_quote(underlying, option_type, strike, expiry)
            if quote:
                results[(underlying, option_type, strike, expiry)] = quote
            time_module.sleep(0.25)  # Rate limit protection

        return results

    def get_historical_candles(self, underlying: str, option_type: str,
                              strike: int, expiry: str,
                              from_time: datetime, to_time: datetime) -> List[Dict]:
        """
        Fetch historical 5-min candles from AngelOne SmartAPI.

        API Limits:
        - Max 1000+ candles per call (intraday = ~75 candles) ✓
        - Rate limit: ~10 req/sec (we only call once per strike change)
        """
        if not self._connected or not self._smart_api:
            logger.error("Not connected to AngelOne")
            return []

        try:
            # Step 1: Resolve instrument token
            contract = self._resolve_instrument(underlying, option_type, strike, expiry)
            if not contract:
                logger.warning(f"Could not resolve instrument: {option_type} {strike} {expiry}")
                return []

            token = contract.get('token')
            if not token:
                logger.error(f"No token for {option_type} {strike}")
                return []

            logger.info(f"Fetching historical candles: {option_type} {strike} from {from_time} to {to_time}")
            logger.info(f"Using token: {token}")

            # Step 2: Format dates for AngelOne API
            from_date_str = from_time.strftime("%Y-%m-%d %H:%M")
            to_date_str = to_time.strftime("%Y-%m-%d %H:%M")

            # Step 3: Fetch candle data from AngelOne API
            historic_param = {
                "exchange": "NFO",
                "symboltoken": str(token),
                "interval": "FIVE_MINUTE",
                "fromdate": from_date_str,
                "todate": to_date_str
            }

            response = self._smart_api.getCandleData(historic_param)

            if not response or response.get('status') != True:
                logger.warning(f"No candle data returned for {option_type} {strike}")
                logger.warning(f"Response: {response}")
                return []

            candle_data = response.get('data', [])
            if not candle_data:
                logger.warning(f"Empty candle data for {option_type} {strike}")
                return []

            logger.info(f"✓ Fetched {len(candle_data)} candles for {option_type} {strike}")

            # Step 4: Fetch OI data separately (AngelOne requires separate API call)
            oi_param = {
                "exchange": "NFO",
                "symboltoken": str(token),
                "interval": "FIVE_MINUTE",
                "fromdate": from_date_str,
                "todate": to_date_str
            }

            oi_data = {}
            try:
                oi_response = self._smart_api.getOIData(oi_param)
                if oi_response and oi_response.get('status'):
                    oi_list = oi_response.get('data', [])
                    # Create OI lookup map: timestamp -> OI value
                    # AngelOne OI format: [timestamp, open_interest]
                    for oi_entry in oi_list:
                        timestamp_str = oi_entry[0]
                        oi_value = int(oi_entry[1])
                        oi_data[timestamp_str] = oi_value
                    logger.info(f"✓ Fetched OI data for {len(oi_list)} candles")
                else:
                    logger.warning(f"Could not fetch OI data, will use 0 as default")
            except Exception as e:
                logger.warning(f"Error fetching OI data: {e}, will use 0 as default")

            # Step 5: Convert to standard format and merge with OI
            # AngelOne format: [timestamp, open, high, low, close, volume]
            candles = []
            for candle in candle_data:
                try:
                    # Parse timestamp (format: "2026-02-16T09:20:00+05:30")
                    timestamp_str = candle[0]
                    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S%z")

                    # Get OI for this timestamp (default to 0 if not found)
                    oi_value = oi_data.get(timestamp_str, 0)

                    candles.append({
                        'timestamp': timestamp.replace(tzinfo=None),  # Remove timezone
                        'open': float(candle[1]),
                        'high': float(candle[2]),
                        'low': float(candle[3]),
                        'close': float(candle[4]),
                        'volume': int(candle[5]),  # Volume from AngelOne (auto-detected as interval/cumulative)
                        'oi': oi_value  # OI fetched from separate getOIData() call
                    })
                except Exception as e:
                    logger.error(f"Error parsing candle: {candle}, error: {e}")
                    continue

            return candles

        except Exception as e:
            logger.error(f"Error fetching historical candles from AngelOne: {e}")
            import traceback
            traceback.print_exc()
            return []

    def get_option_chain(self, underlying: str, expiry: str,
                         strikes: List[int]) -> pd.DataFrame:
        """
        Get option chain data using real-time quotes (OPTIMIZED - no candle fetches!)

        Fetches quote data (LTP, OI, Volume) in batched calls using TOKEN-BASED lookups.
        Uses LTP for price and cumulative volume for VWAP calculations.

        NO SYMBOLS - uses only pre-cached tokens from contracts_cache.json

        Returns:
            DataFrame with columns: strike, option_type, expiry, open, high, low, close, OI, volume, instrument_token
            Note: open/high/low/close all set to LTP (quote-based, not candle-based)
        """
        if not self._connected:
            return pd.DataFrame()

        try:
            if not self.contract_manager:
                logger.error("ContractManager not available - cannot fetch options chain")
                logger.error("Token-based approach REQUIRES ContractManager")
                return pd.DataFrame()

            # Convert expiry to string format (YYYY-MM-DD)
            if isinstance(expiry, datetime):
                expiry_str = expiry.strftime('%Y-%m-%d')
            elif isinstance(expiry, date):
                expiry_str = expiry.strftime('%Y-%m-%d')
            else:
                expiry_str = expiry

            # Build token list for batch quote fetching
            token_list = []
            strike_map = {}  # Map token -> (strike, option_type)

            for strike in strikes:
                for option_type in ['CE', 'PE']:
                    # Get contract from cache (contains universal exchange token)
                    contract = self.contract_manager.get_option_contract(expiry_str, strike, option_type)

                    if not contract:
                        logger.warning(f"No contract found in cache: {strike} {option_type} {expiry_str}")
                        continue

                    # Get universal exchange token (AngelOne uses 'token', not 'zerodha_instrument_token')
                    token = contract.get('token')

                    if not token:
                        logger.error(f"No token for {strike} {option_type}")
                        logger.error("Run: python refresh_contracts.py --broker angelone")
                        continue

                    token_list.append(token)
                    strike_map[token] = (strike, option_type)

            if not token_list:
                logger.error(f"No valid tokens found for strikes: {strikes}")
                logger.error("Cache may be missing tokens")
                logger.error("Run: python refresh_contracts.py --broker angelone")
                return pd.DataFrame()

            logger.info(f"Fetching quotes for {len(token_list)} options (TOKEN-BASED)...")

            # BATCH fetch quotes for OI (optimization)
            quotes_map = {}  # token -> quote_data
            chunk_size = 10
            for i in range(0, len(token_list), chunk_size):
                chunk_tokens = token_list[i:i+chunk_size]

                try:
                    market_data = self._smart_api.getMarketData(
                        mode="FULL",
                        exchangeTokens={"NFO": chunk_tokens}
                    )

                    if market_data and market_data.get('status'):
                        fetched = market_data.get('data', {}).get('fetched', [])
                        for q in fetched:
                            token = q.get('symbolToken', '')
                            quotes_map[token] = q

                    time_module.sleep(0.5)  # Rate limit protection

                except Exception as e:
                    logger.error(f"Error fetching quote chunk: {e}")
                    if 'rate' in str(e).lower():
                        time_module.sleep(2)
                    continue

            # OPTIMIZED: Use quote data directly (LTP + OI + Volume)
            # No need for individual candle fetches!
            result_data = []

            for token in token_list:
                try:
                    strike, option_type = strike_map[token]
                    quote = quotes_map.get(token, {})

                    if not quote:
                        logger.warning(f"No quote data for token {token}")
                        continue

                    # Use LTP from quote (fast, no candle fetch needed!)
                    ltp = float(quote.get('ltp', 0))
                    volume = int(quote.get('tradeVolume', 0))  # Cumulative volume
                    oi = int(quote.get('opnInterest', 0))

                    result_data.append({
                        'strike': strike,
                        'option_type': option_type,
                        'expiry': expiry_str,
                        'open': ltp,   # Use LTP for all OHLC fields
                        'high': ltp,
                        'low': ltp,
                        'close': ltp,  # This is what matters for entry/VWAP
                        'OI': oi,
                        'volume': volume,  # Cumulative volume (VWAP handles this now)
                        'instrument_token': token
                    })

                except Exception as e:
                    logger.error(f"Error processing quote for token {token}: {e}")
                    continue

            result_df = pd.DataFrame(result_data) if result_data else pd.DataFrame()
            logger.info(f"✓ Retrieved {len(result_df)} option quotes (TOKEN-BASED)")

            return result_df

        except Exception as e:
            logger.error(f"Error getting option chain: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()

    def _add_ltp_fallback(self, result_data: list, strike: int, option_type: str,
                          expiry_str: str, token: str, quote: dict):
        """
        DEPRECATED: No longer used after quote-based optimization.

        Previously used as fallback when candle data was unavailable.
        Now all data uses quotes directly (no candles fetched).

        Args:
            result_data: List to append fallback record to
            strike: Strike price
            option_type: 'CE' or 'PE'
            expiry_str: Expiry date string
            token: Instrument token
            quote: Quote data dict
        """
        ltp = float(quote.get('ltp', 0))
        logger.warning(f"No candle for {strike} {option_type}, using LTP fallback")
        result_data.append({
            'strike': strike,
            'option_type': option_type,
            'expiry': expiry_str,
            'open': ltp,
            'high': ltp,
            'low': ltp,
            'close': ltp,
            'OI': int(quote.get('opnInterest', 0)),
            'volume': 0,
            'instrument_token': token
        })

    def get_spot_price(self, underlying: str = "NIFTY") -> Optional[float]:
        """
        Get spot price for underlying.
        Includes retry mechanism for network errors.
        """
        if not self._connected:
            return None

        # Retry configuration
        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                ltp_data = self._smart_api.ltpData("NSE", "NIFTY 50", self.NIFTY_TOKEN)

                if ltp_data and ltp_data.get('status'):
                    return float(ltp_data['data'].get('ltp', 0))

                return None

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Spot price fetch failed (attempt {attempt + 1}/{max_retries}): {e}")
                    logger.info(f"Retrying in {retry_delay}s...")
                    import time as time_module
                    time_module.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.error(f"Error getting spot price after {max_retries} attempts: {e}")
                    return None

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
                message="Not connected to AngelOne"
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

            # Get token (AngelOne uses 'token', not 'zerodha_instrument_token')
            token = contract.get('token')
            if not token:
                return OrderResponse(
                    success=False,
                    order_id="",
                    status=OrderStatus.REJECTED,
                    message=f"No token found for contract"
                )

            # Get trading symbol from token (using AngelOne's master instruments)
            # This is more reliable than manual construction
            trading_symbol = self._get_symbol_from_token(token)
            
            if not trading_symbol:
                return OrderResponse(
                    success=False,
                    order_id="",
                    status=OrderStatus.REJECTED,
                    message=f"Could not resolve trading symbol for token {token}"
                )
            
            logger.info(f"Placing order: {trading_symbol} (token: {token}) [TOKEN LOOKUP]")

            # Build AngelOne order params
            # AngelOne requires BOTH tradingsymbol AND symboltoken (cannot use token alone)
            # IMPORTANT: For stop loss orders, variety must be "STOPLOSS", not "NORMAL"
            variety = 'STOPLOSS' if order.order_type in [OrderType.SL, OrderType.SL_M] else 'NORMAL'

            order_params = {
                'variety': variety,
                'tradingsymbol': trading_symbol,  # Actual symbol (e.g., "NIFTY27JAN2625000CE")
                'symboltoken': str(token),         # Token from cache
                'transactiontype': order.transaction_type.value,
                'exchange': 'NFO',
                'ordertype': self.ORDER_TYPE_MAP.get(order.order_type, "MARKET"),
                'producttype': self.PRODUCT_MAP.get(order.product_type, "INTRADAY"),
                'duration': 'DAY',
                'quantity': str(order.quantity)
            }

            if order.price:
                order_params['price'] = str(order.price)
            else:
                order_params['price'] = "0"

            if order.trigger_price:
                order_params['triggerprice'] = str(order.trigger_price)
            else:
                order_params['triggerprice'] = "0"

            # Log order params being sent (INFO level for debugging)
            logger.info(f"Place order params being sent to AngelOne API:")
            logger.info(f"  variety: {order_params.get('variety')}")
            logger.info(f"  ordertype: {order_params.get('ordertype')}")
            logger.info(f"  tradingsymbol: {order_params.get('tradingsymbol')}")
            logger.info(f"  triggerprice: {order_params.get('triggerprice')}")
            logger.info(f"  price: {order_params.get('price')}")
            logger.info(f"  quantity: {order_params.get('quantity')}")
            logger.info(f"  producttype: {order_params.get('producttype')}")

            # Place order
            response = self._smart_api.placeOrder(order_params)

            logger.info(f"Place order response: {response}")
            logger.debug(f"Order response type: {type(response)}, value: {response}")

            # Handle different response types
            if isinstance(response, dict):
                if response.get('status'):
                    return OrderResponse(
                        success=True,
                        order_id=str(response.get('data', {}).get('orderid', '')),
                        status=OrderStatus.PENDING,
                        timestamp=datetime.now()
                    )
                else:
                    return OrderResponse(
                        success=False,
                        order_id="",
                        status=OrderStatus.REJECTED,
                        message=response.get('message', 'Order placement failed')
                    )
            elif isinstance(response, str):
                # Sometimes AngelOne returns order ID directly as string
                logger.info(f"Order placed successfully, ID: {response}")
                return OrderResponse(
                    success=True,
                    order_id=response,
                    status=OrderStatus.PENDING,
                    timestamp=datetime.now()
                )
            else:
                return OrderResponse(
                    success=False,
                    order_id="",
                    status=OrderStatus.REJECTED,
                    message=f"Unexpected response type: {type(response)}"
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
        """
        Modify existing order.

        FIXED VERSION - Includes all required AngelOne API fields.

        Args:
            order_id: Order ID to modify
            changes: Dict with fields to modify ('price', 'quantity', 'trigger_price')

        Returns:
            OrderResponse with success status

        Note:
            This method fetches the full order details from order book first,
            then includes all required fields in the modify request.
        """
        if not self._connected:
            return OrderResponse(
                success=False,
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message="Not connected"
            )

        try:
            # Fetch full order book to get current order details
            # Add retry logic for rate limiting
            logger.debug(f"Fetching order book to get details for order {order_id}")

            max_retries = 3
            retry_delay = 2
            orders = None

            for attempt in range(max_retries):
                try:
                    orders = self._smart_api.orderBook()
                    break  # Success, exit retry loop
                except Exception as e:
                    if 'rate' in str(e).lower() and attempt < max_retries - 1:
                        logger.warning(f"Rate limit hit, retrying in {retry_delay}s... (attempt {attempt + 1}/{max_retries})")
                        time_module.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        raise  # Re-raise if not rate limit or last attempt

            if not orders or not orders.get('status'):
                return OrderResponse(
                    success=False,
                    order_id=order_id,
                    status=OrderStatus.REJECTED,
                    message="Could not fetch order book"
                )

            # Find our order in the order book
            order_data = None
            for o in orders.get('data', []):
                if str(o.get('orderid')) == str(order_id):
                    order_data = o
                    break

            if not order_data:
                return OrderResponse(
                    success=False,
                    order_id=order_id,
                    status=OrderStatus.REJECTED,
                    message=f"Order {order_id} not found in order book"
                )

            logger.debug(f"Found order {order_id} in order book")
            logger.debug(f"Current order data: tradingsymbol={order_data.get('tradingsymbol')}, "
                        f"ordertype={order_data.get('ordertype')}, "
                        f"producttype={order_data.get('producttype')}")

            # Build modify_params with ALL required fields from current order
            modify_params = {
                'variety': order_data.get('variety', 'NORMAL'),
                'orderid': order_id,
                'tradingsymbol': order_data.get('tradingsymbol'),
                'symboltoken': order_data.get('symboltoken'),
                'exchange': order_data.get('exchange', 'NFO'),
                'ordertype': order_data.get('ordertype', 'MARKET'),
                'producttype': order_data.get('producttype', 'INTRADAY'),
                'duration': order_data.get('duration', 'DAY'),
                'quantity': str(order_data.get('quantity', 0))
            }

            # Get current prices from order data (for logging)
            current_price = order_data.get('price', 0)
            current_trigger = order_data.get('triggerprice', 0)

            # Apply modifications
            if 'price' in changes:
                modify_params['price'] = str(changes['price'])
                logger.info(f"Modifying price: {current_price} -> {changes['price']}")
            else:
                modify_params['price'] = str(current_price)

            if 'trigger_price' in changes:
                modify_params['triggerprice'] = str(changes['trigger_price'])
                logger.info(f"Modifying trigger price: {current_trigger} -> {changes['trigger_price']}")
            else:
                modify_params['triggerprice'] = str(current_trigger)

            if 'quantity' in changes:
                modify_params['quantity'] = str(changes['quantity'])
                logger.info(f"Modifying quantity: {order_data.get('quantity')} -> {changes['quantity']}")

            # Log all parameters being sent (INFO level so it shows in output)
            logger.info(f"Modify order params being sent to AngelOne API:")
            logger.info(f"  variety: {modify_params.get('variety')}")
            logger.info(f"  orderid: {modify_params.get('orderid')}")
            logger.info(f"  tradingsymbol: {modify_params.get('tradingsymbol')}")
            logger.info(f"  symboltoken: {modify_params.get('symboltoken')}")
            logger.info(f"  exchange: {modify_params.get('exchange')}")
            logger.info(f"  ordertype: {modify_params.get('ordertype')}")
            logger.info(f"  producttype: {modify_params.get('producttype')}")
            logger.info(f"  duration: {modify_params.get('duration')}")
            logger.info(f"  price: {modify_params.get('price')}")
            logger.info(f"  triggerprice: {modify_params.get('triggerprice')}")
            logger.info(f"  quantity: {modify_params.get('quantity')}")

            # Add delay to avoid rate limiting (2 seconds between API calls)
            time_module.sleep(2)

            # Send modification request with retry logic
            max_retries = 3
            retry_delay = 2
            response = None

            for attempt in range(max_retries):
                try:
                    response = self._smart_api.modifyOrder(modify_params)
                    break  # Success, exit retry loop
                except Exception as e:
                    if 'rate' in str(e).lower() and attempt < max_retries - 1:
                        logger.warning(f"Rate limit hit on modify, retrying in {retry_delay}s... (attempt {attempt + 1}/{max_retries})")
                        time_module.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        raise  # Re-raise if not rate limit or last attempt

            logger.info(f"Modify response from AngelOne: {response}")

            if response and response.get('status'):
                return OrderResponse(
                    success=True,
                    order_id=order_id,
                    status=OrderStatus.PENDING,
                    message="Order modified successfully"
                )
            else:
                error_msg = response.get('message', 'Modification failed')
                logger.error(f"Modification failed: {error_msg}")
                return OrderResponse(
                    success=False,
                    order_id=order_id,
                    status=OrderStatus.REJECTED,
                    message=error_msg
                )

        except Exception as e:
            logger.error(f"Order modification error: {e}")
            import traceback
            traceback.print_exc()
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
            response = self._smart_api.cancelOrder(order_id, 'NORMAL')

            if response and response.get('status'):
                return OrderResponse(
                    success=True,
                    order_id=order_id,
                    status=OrderStatus.CANCELLED,
                    message="Order cancelled"
                )
            else:
                return OrderResponse(
                    success=False,
                    order_id=order_id,
                    status=OrderStatus.REJECTED,
                    message=response.get('message', 'Cancellation failed')
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
            orders = self._smart_api.orderBook()
            if orders and orders.get('status'):
                for o in orders.get('data', []):
                    if str(o.get('orderid')) == str(order_id):
                        return OrderResponse(
                            success=True,
                            order_id=str(o['orderid']),
                            status=self.STATUS_MAP.get(o.get('orderstatus', '').lower(), OrderStatus.PENDING),
                            filled_quantity=int(o.get('filledshares', 0)),
                            average_price=float(o.get('averageprice', 0)),
                            message=o.get('text', '')
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
            orders = self._smart_api.orderBook()
            if orders and orders.get('status'):
                return [
                    OrderResponse(
                        success=True,
                        order_id=str(o['orderid']),
                        status=self.STATUS_MAP.get(o.get('orderstatus', '').lower(), OrderStatus.PENDING),
                        filled_quantity=int(o.get('filledshares', 0)),
                        average_price=float(o.get('averageprice', 0)),
                        message=o.get('text', '')
                    )
                    for o in orders.get('data', [])
                ]
            return []

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
            positions = self._smart_api.position()
            if positions and positions.get('status'):
                result = []
                for p in positions.get('data', []):
                    qty = int(p.get('netqty', 0))
                    if qty == 0:
                        continue

                    symbol = p.get('tradingsymbol', '')
                    result.append(Position(
                        underlying='NIFTY',
                        option_type='CE' if 'CE' in symbol else 'PE' if 'PE' in symbol else 'FUT',
                        strike=0,
                        expiry='',
                        exchange=p.get('exchange', 'NFO'),
                        quantity=qty,
                        avg_price=float(p.get('netprice', 0)),
                        ltp=float(p.get('ltp', 0)),
                        pnl=float(p.get('unrealised', 0)),
                        product_type=p.get('producttype', 'INTRADAY'),
                        symbol=symbol,
                        token=p.get('symboltoken', '')
                    ))

                return result

            return []

        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    def get_holdings(self) -> List[Position]:
        """Get holdings."""
        if not self._connected:
            return []

        try:
            holdings = self._smart_api.holding()
            if holdings and holdings.get('status'):
                return [
                    Position(
                        underlying=h.get('tradingsymbol', ''),
                        option_type='EQ',
                        strike=0,
                        expiry='',
                        exchange='NSE',
                        quantity=int(h.get('quantity', 0)),
                        avg_price=float(h.get('averageprice', 0)),
                        ltp=float(h.get('ltp', 0)),
                        pnl=float(h.get('profitandloss', 0)),
                        symbol=h.get('tradingsymbol', '')
                    )
                    for h in holdings.get('data', [])
                ]
            return []

        except Exception as e:
            logger.error(f"Error getting holdings: {e}")
            return []

    def get_funds(self) -> Optional[Funds]:
        """Get account funds."""
        if not self._connected:
            return None

        try:
            rms = self._smart_api.rmsLimit()
            if rms and rms.get('status'):
                data = rms.get('data', {})
                return Funds(
                    available_cash=float(data.get('availablecash', 0)),
                    used_margin=float(data.get('utiliseddebits', 0)),
                    available_margin=float(data.get('availablelimitmargin', 0)),
                    total_balance=float(data.get('net', 0))
                )
            return None

        except Exception as e:
            logger.error(f"Error getting funds: {e}")
            return None

    # ══════════════════════════════════════════════════════════════════════════
    # MARKET STATUS
    # ══════════════════════════════════════════════════════════════════════════

    def is_market_open(self) -> bool:
        """
        Check if market is open.

        Supports both regular weekdays and special trading days (e.g., Union Budget sessions).
        Special trading days are configured in config.yaml under market.special_trading_days.
        """
        now = datetime.now()
        current_time = now.time()
        current_date = now.date()

        market_open = time(9, 15)
        market_close = time(15, 30)

        # Check if it's a regular weekday (Monday-Friday)
        is_weekday = now.weekday() < 5

        # Check if it's a special trading day (e.g., Union Budget on Sunday)
        is_special_day = False
        try:
            # Try to load special trading days from config
            from pathlib import Path
            import yaml

            config_path = Path(__file__).parent.parent.parent.parent / "config" / "config.yaml"
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                    special_days = config.get('market', {}).get('special_trading_days', [])

                    # Convert special days to date objects for comparison
                    for special_day_str in special_days:
                        try:
                            if isinstance(special_day_str, str):
                                special_day = datetime.strptime(special_day_str, '%Y-%m-%d').date()
                            else:
                                # Already a date object
                                special_day = special_day_str

                            if current_date == special_day:
                                is_special_day = True
                                logger.info(f"Special trading day detected: {current_date}")
                                break
                        except (ValueError, TypeError):
                            continue
        except Exception as e:
            logger.debug(f"Could not check special trading days: {e}")

        # Market is open if it's either a weekday OR a special trading day, and within trading hours
        is_trading_day = is_weekday or is_special_day
        return is_trading_day and market_open <= current_time <= market_close

    def load_instruments(self) -> bool:
        """
        DEPRECATED: No longer needed in token-based approach.
        
        This method is kept for backward compatibility but does nothing.
        All token lookups now go through ContractManager → contracts_cache.json
        
        Returns:
            bool: Always returns True (no-op)
        """
        logger.info("load_instruments() called - SKIPPED (using token-based approach)")
        logger.info("All lookups use ContractManager → contracts_cache.json")
        return True

    def logout(self) -> None:
        """Logout from AngelOne API."""
        self.disconnect()

    def get_next_expiry(self) -> Optional[str]:
        """Get next weekly expiry."""
        # Try contract_manager first
        if self.contract_manager:
            return self.contract_manager.get_options_expiry('current_week')

        # Fallback to loaded instruments
        if self.nifty_options is not None and not self.nifty_options.empty:
            today = date.today()
            future_expiries = self.nifty_options[
                self.nifty_options['expiry'] >= today
            ]['expiry'].unique()

            if len(future_expiries) > 0:
                next_exp = sorted(future_expiries)[0]
                return next_exp.strftime('%Y-%m-%d') if hasattr(next_exp, 'strftime') else str(next_exp)

        return None
