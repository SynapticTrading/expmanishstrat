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

    def __init__(self, connection: ZerodhaConnection):
        """
        Initialize data feed

        Args:
            connection: ZerodhaConnection instance
        """
        self.connection = connection
        self.kite = connection.kite

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
        Get latest 5-min candle for an instrument

        Args:
            instrument_token: Instrument token (numeric)

        Returns:
            dict: Candle data (timestamp, open, high, low, close, volume)
        """
        try:
            # Get last 2 candles (to ensure we have the complete latest one)
            to_date = datetime.now()
            from_date = to_date - timedelta(minutes=15)

            df = self.connection.get_historical_data(
                instrument_token=instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval="5minute"
            )

            if df is not None and not df.empty:
                # Get last candle
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
        Get options chain data for specified strikes

        Args:
            expiry: Expiry date (YYYY-MM-DD format or datetime)
            strikes: List of strike prices

        Returns:
            DataFrame: Options data with columns [strike, option_type, expiry, close, oi, volume, instrument_token]
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

            # Get quotes for all options with retry logic
            instrument_tokens = [f"NFO:{row['tradingsymbol']}" for _, row in options_df.iterrows()]

            print(f"[{datetime.now()}] Fetching quotes for {len(instrument_tokens)} options...")

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

            # Build result DataFrame
            if quotes is None:
                return pd.DataFrame()

            result_data = []

            for _, row in options_df.iterrows():
                instrument_key = f"NFO:{row['tradingsymbol']}"

                if instrument_key not in quotes:
                    continue

                quote = quotes[instrument_key]

                # Keep CE/PE format to match backtest (OI analyzer expects 'CE'/'PE')
                option_type = row['instrument_type']  # CE or PE

                result_data.append({
                    'strike': row['strike'],
                    'option_type': option_type,
                    'expiry': row['expiry'],
                    'close': quote['last_price'],
                    'OI': quote.get('oi', 0),  # Uppercase to match backtest
                    'volume': quote.get('volume', 0),
                    'instrument_token': row['instrument_token'],
                    'tradingsymbol': row['tradingsymbol']
                })

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
        Check if market is open

        Returns:
            bool: True if market is open
        """
        now = datetime.now()
        current_time = now.time()

        # Market hours: 9:15 AM - 3:30 PM
        market_open = time(9, 15)
        market_close = time(15, 30)

        # Check if weekday (Monday=0, Sunday=6)
        is_weekday = now.weekday() < 5

        return is_weekday and market_open <= current_time <= market_close
