"""
Real-time Data Feed for Paper Trading - Zerodha Version
Fetches 5-min candle data from Zerodha Kite Connect API
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from datetime import datetime, timedelta, time
import pandas as pd
import time as time_module
from paper_trading.legacy.zerodha_connection import ZerodhaConnection


class ZerodhaDataFeed:
    """Manages real-time data feed for paper trading using Zerodha"""

    def __init__(self, connection: ZerodhaConnection, contract_manager=None):
        """
        Initialize data feed

        Args:
            connection: ZerodhaConnection instance
            contract_manager: Optional ContractManager for token-based lookups
        """
        self.connection = connection
        self.kite = connection.kite
        self.contract_manager = contract_manager

        # Cache for instruments
        self.nfo_instruments = None
        self.nse_instruments = None

        # Nifty 50 instrument
        self.nifty_symbol = "NSE:NIFTY 50"
        self.nifty_token = None

        print(f"[{datetime.now()}] Zerodha data feed initialized")

    def load_instruments(self):
        """Load instrument lists and cache them"""
        try:
            print(f"[{datetime.now()}] Loading instruments...")

            # Load NFO instruments (for options)
            self.nfo_instruments = self.connection.get_instruments("NFO")

            # Load NSE instruments (for Nifty index)
            self.nse_instruments = self.connection.get_instruments("NSE")

            # Find Nifty 50 token
            if self.nse_instruments is not None:
                nifty_row = self.nse_instruments[
                    self.nse_instruments['tradingsymbol'] == 'NIFTY 50'
                ]
                if not nifty_row.empty:
                    self.nifty_token = nifty_row.iloc[0]['instrument_token']
                    print(f"[{datetime.now()}] ✓ Nifty 50 token: {self.nifty_token}")

            print(f"[{datetime.now()}] ✓ Instruments loaded")
            return True

        except Exception as e:
            print(f"[{datetime.now()}] ✗ Error loading instruments: {e}")
            return False

    def get_spot_price(self, max_retries=3):
        """
        Get current Nifty spot price with retry logic

        Args:
            max_retries: Maximum number of retry attempts (default: 3)

        Returns:
            float: Current Nifty price
        """
        for attempt in range(max_retries):
            try:
                ltp = self.connection.get_ltp(self.nifty_symbol)
                if ltp is not None:
                    return ltp

                # If None returned, retry
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    print(f"[{datetime.now()}] ⚠️  Spot price returned None, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                    time_module.sleep(wait_time)

            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    print(f"[{datetime.now()}] ⚠️  Error getting spot price: {e}")
                    print(f"[{datetime.now()}] ⚠️  Retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                    time_module.sleep(wait_time)
                else:
                    print(f"[{datetime.now()}] ✗ Failed to get spot price after {max_retries} attempts: {e}")

        return None

    def get_5min_candle(self, instrument_token):
        """
        Get latest COMPLETE 5-min candle for an instrument

        Fetches data up to the last completed 5-minute boundary and returns
        the LAST candle only (not second-to-last).

        Args:
            instrument_token: Instrument token (numeric)

        Returns:
            dict: Candle data (timestamp, open, high, low, close, volume) or None
        """
        try:
            # Calculate last completed 5-minute boundary
            # Round DOWN current time to nearest 5-min boundary = end time of last complete candle
            # Example: 12:37:23 -> 12:35:00 (fetch 12:30-12:35 candle)
            #          12:35:00 -> 12:35:00 (fetch 12:30-12:35 candle that just completed)
            now = datetime.now()
            current_minute = now.minute

            # Round down to nearest 5-minute boundary
            boundary_minute = (current_minute // 5) * 5
            last_complete_boundary = now.replace(minute=boundary_minute, second=0, microsecond=0)

            # This boundary is the END time of the last complete candle
            # Fetch that candle: [boundary - 5 min, boundary]
            to_date = last_complete_boundary
            from_date = last_complete_boundary - timedelta(minutes=5)

            df = self.connection.get_historical_data(
                instrument_token=instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval="5minute"
            )

            if df is not None and not df.empty:
                # Use the LAST candle (should be exactly 1 candle)
                last_candle = df.iloc[-1]
                return {
                    'timestamp': last_candle['date'],
                    'open': float(last_candle['open']),
                    'high': float(last_candle['high']),
                    'low': float(last_candle['low']),
                    'close': float(last_candle['close']),
                    'volume': int(last_candle['volume'])
                }

            return None

        except Exception as e:
            print(f"[{datetime.now()}] ✗ Error getting candle: {e}")
            return None

    def get_options_chain(self, expiry, strikes):
        """
        Get options chain data using real-time quotes (OPTIMIZED - no candle fetches!)

        Fetches quote data (LTP, OI, Volume) in a single batch call.
        Uses LTP for price and cumulative volume for VWAP calculations.

        Args:
            expiry: Expiry date (YYYY-MM-DD format or datetime)
            strikes: List of strike prices

        Returns:
            DataFrame: Options data with columns [strike, option_type, expiry, open, high, low, close, OI, volume, instrument_token, tradingsymbol]
                      Note: open/high/low/close all set to LTP (quote-based, not candle-based)
        """
        try:
            if self.nfo_instruments is None:
                print(f"[{datetime.now()}] ✗ Instruments not loaded. Call load_instruments() first.")
                return pd.DataFrame()

            # Convert expiry to date object for comparison
            from datetime import date
            if isinstance(expiry, str):
                expiry_date = datetime.strptime(expiry, '%Y-%m-%d').date()
            elif isinstance(expiry, datetime):
                expiry_date = expiry.date()
            elif isinstance(expiry, date):
                expiry_date = expiry
            else:
                expiry_date = expiry

            # Filter for NIFTY options with matching expiry
            options_df = self.nfo_instruments[
                (self.nfo_instruments['name'] == 'NIFTY') &
                (self.nfo_instruments['instrument_type'].isin(['CE', 'PE'])) &
                (self.nfo_instruments['expiry'] == expiry_date)
            ].copy()

            if options_df.empty:
                print(f"[{datetime.now()}] ✗ No options found for expiry: {expiry_date}")
                return pd.DataFrame()

            # Filter for specified strikes
            options_df = options_df[options_df['strike'].isin(strikes)]

            if options_df.empty:
                print(f"[{datetime.now()}] ✗ No options found for strikes: {strikes}")
                return pd.DataFrame()

            # Build token map for efficient lookup (TOKEN-BASED)
            token_to_option_map = {}
            instrument_tokens = []
            for _, row in options_df.iterrows():
                token = row['instrument_token']
                symbol = row['tradingsymbol']
                # Use tokens directly instead of tradingsymbols
                instrument_tokens.append(token)
                token_to_option_map[token] = (
                    row['strike'],
                    row['instrument_type'],
                    symbol,
                    row['expiry']
                )

            print(f"[{datetime.now()}] Fetching quotes for {len(instrument_tokens)} options (TOKEN-BASED)...")

            # BATCH fetch all quotes for OI using TOKENS (optimization)
            quotes = None
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    quotes = self.kite.quote(instrument_tokens)
                    break  # Success, exit retry loop
                except Exception as e:
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                        print(f"[{datetime.now()}] ⚠️  Error fetching quotes: {e}")
                        print(f"[{datetime.now()}] ⚠️  Retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                        time_module.sleep(wait_time)
                    else:
                        print(f"[{datetime.now()}] ✗ Failed to fetch quotes after {max_retries} attempts: {e}")
                        return pd.DataFrame()

            if quotes is None:
                return pd.DataFrame()

            # OPTIMIZED: Use quote data directly (LTP + OI + Volume)
            # No need for individual candle fetches!
            result_data = []

            for token, (strike, option_type, symbol, expiry) in token_to_option_map.items():
                try:
                    # Get quote for this token
                    token_key = str(token)
                    quote = quotes.get(token_key, {})

                    if not quote:
                        print(f"[{datetime.now()}] ⚠️  No quote data for {symbol}")
                        continue

                    # Use LTP from quote (fast, no candle fetch needed!)
                    ltp = quote.get('last_price', 0)
                    volume = quote.get('volume', 0)  # Cumulative volume
                    oi = quote.get('oi', 0)

                    # Convert expiry to string format if it's a date object
                    expiry_str = expiry.strftime('%Y-%m-%d') if hasattr(expiry, 'strftime') else str(expiry)

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
                        'instrument_token': token,
                        'tradingsymbol': symbol
                    })

                except Exception as e:
                    print(f"[{datetime.now()}] ✗ Error processing quote for {symbol}: {e}")
                    continue

            result_df = pd.DataFrame(result_data)
            print(f"[{datetime.now()}] ✓ Retrieved {len(result_df)} option quotes")

            return result_df

        except Exception as e:
            print(f"[{datetime.now()}] ✗ Error getting options chain: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()

    def get_next_expiry(self):
        """
        Get next weekly expiry date for NIFTY

        Returns:
            datetime: Next expiry date
        """
        try:
            if self.nfo_instruments is None:
                print(f"[{datetime.now()}] ✗ Instruments not loaded.")
                return None

            # Get all NIFTY option expiries
            nifty_options = self.nfo_instruments[
                (self.nfo_instruments['name'] == 'NIFTY') &
                (self.nfo_instruments['instrument_type'].isin(['CE', 'PE']))
            ]

            if nifty_options.empty:
                return None

            # Get unique expiries and sort
            expiries = nifty_options['expiry'].unique()
            expiries = sorted([e for e in expiries if e >= datetime.now().date()])

            if expiries:
                return expiries[0]

            return None

        except Exception as e:
            print(f"[{datetime.now()}] ✗ Error getting next expiry: {e}")
            return None

    def wait_for_next_candle(self, interval_minutes=5):
        """
        Wait until next candle close

        Args:
            interval_minutes: Candle interval in minutes (default: 5)
        """
        now = datetime.now()

        # Calculate minutes until next candle boundary
        current_minute = now.minute
        minutes_past_boundary = current_minute % interval_minutes

        if minutes_past_boundary == 0 and now.second < 5:
            # We're within first 5 seconds of a new candle - wait for next one
            minutes_to_wait = interval_minutes
        else:
            # Wait until next boundary
            minutes_to_wait = interval_minutes - minutes_past_boundary

        # Calculate exact next candle time
        next_candle_time = now + timedelta(minutes=minutes_to_wait)
        next_candle_time = next_candle_time.replace(second=0, microsecond=0)

        wait_seconds = (next_candle_time - now).total_seconds()

        # Always wait at least 1 second to avoid tight loops
        if wait_seconds < 1:
            wait_seconds = interval_minutes * 60

        print(f"[{now.strftime('%H:%M:%S')}] Waiting {wait_seconds:.0f}s for next candle at {next_candle_time.strftime('%H:%M:%S')}")
        time_module.sleep(wait_seconds)

    def is_market_open(self):
        """
        Check if market is open.

        Supports both regular weekdays and special trading days (e.g., Union Budget sessions).
        Special trading days are configured in config.yaml under market.special_trading_days.

        Returns:
            bool: True if market is open
        """
        now = datetime.now()
        current_time = now.time()
        current_date = now.date()

        # Market hours: 9:15 AM - 3:30 PM
        market_open = time(9, 15)
        market_close = time(15, 30)

        # Check if weekday (Monday=0, Sunday=6)
        is_weekday = now.weekday() < 5

        # Check if it's a special trading day (e.g., Union Budget on Sunday)
        is_special_day = False
        try:
            # Try to load special trading days from config
            from pathlib import Path
            import yaml

            config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
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
                                print(f"Special trading day detected: {current_date}")
                                break
                        except (ValueError, TypeError):
                            continue
        except Exception as e:
            # Silently fail if config cannot be read
            pass

        # Market is open if it's either a weekday OR a special trading day, and within trading hours
        is_trading_day = is_weekday or is_special_day
        return is_trading_day and market_open <= current_time <= market_close
