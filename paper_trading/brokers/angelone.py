"""
AngelOne Broker Implementation
Implements BrokerInterface for AngelOne SmartAPI
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from datetime import datetime, time, timedelta, date
import pandas as pd
import requests
import json
from paper_trading.brokers.base import BrokerInterface
from paper_trading.legacy.angelone_connection import AngelOneConnection


class AngelOneBroker(BrokerInterface):
    """AngelOne SmartAPI broker implementation"""

    def __init__(self, api_key, username, password, totp_token):
        """
        Initialize AngelOne broker

        Args:
            api_key: AngelOne API key
            username: Client code
            password: MPIN
            totp_token: TOTP token
        """
        self.connection = AngelOneConnection(
            api_key=api_key,
            username=username,
            password=password,
            totp_token=totp_token
        )
        self._connected = False
        self.nifty_symbol = "NSE:NIFTY 50"
        self.nifty_token = "99926000"  # Nifty 50 index token

        # Instrument storage
        self.nfo_instruments = None  # Full NFO instrument list
        self.nifty_options = None    # Filtered NIFTY options only
        self.token_map = {}          # tradingsymbol -> token mapping

    @property
    def name(self):
        """Broker name"""
        return "AngelOne"

    def connect(self):
        """Connect to AngelOne API"""
        session_data = self.connection.connect()
        if session_data:
            self._connected = True
            return True
        return False

    def get_spot_price(self, symbol="NIFTY 50"):
        """Get Nifty spot price"""
        if not self._connected:
            return None

        try:
            # Use SmartAPI's ltpData method directly
            ltp_data = self.connection.smart_api.ltpData("NSE", "NIFTY 50", self.nifty_token)

            if ltp_data and ltp_data.get('status'):
                ltp = ltp_data['data'].get('ltp')
                return float(ltp) if ltp else None
            else:
                print(f"[{datetime.now()}] ✗ Failed to get Nifty LTP")
                return None
        except Exception as e:
            print(f"[{datetime.now()}] ✗ Error getting spot price: {e}")
            return None

    def get_ltp(self, instrument_token):
        """Get LTP for instrument"""
        if not self._connected:
            return None
        return self.connection.get_ltp(instrument_token)

    def get_quote(self, instrument_token):
        """Get quote for instrument"""
        if not self._connected:
            return None
        return self.connection.get_quote(instrument_token)

    def get_historical_data(self, instrument_token, from_date, to_date, interval="5minute"):
        """Get historical candle data"""
        if not self._connected:
            return None

        # Map interval format
        interval_map = {
            "5minute": "FIVE_MINUTE",
            "1minute": "ONE_MINUTE",
            "15minute": "FIFTEEN_MINUTE"
        }
        angel_interval = interval_map.get(interval, "FIVE_MINUTE")

        return self.connection.get_candle_data(
            exchange="NFO",
            symbol_token=instrument_token,
            interval=angel_interval,
            from_date=from_date.strftime("%Y-%m-%d %H:%M"),
            to_date=to_date.strftime("%Y-%m-%d %H:%M")
        )

    def get_instruments(self, exchange="NFO"):
        """Get instrument list"""
        if not self._connected:
            return None
        # AngelOne doesn't have a direct instruments API like Zerodha
        # You would need to download instrument file or use searchscrip API
        # For now, return None (needs implementation)
        return None

    def get_options_chain(self, expiry, strikes):
        """Get options chain data for specified strikes"""
        try:
            if not self._connected:
                print(f"[{datetime.now()}] ✗ Not connected")
                return pd.DataFrame()

            if self.nifty_options is None or self.nifty_options.empty:
                print(f"[{datetime.now()}] ✗ Instruments not loaded. Call load_instruments() first.")
                return pd.DataFrame()

            # Convert expiry to date object for comparison
            if isinstance(expiry, str):
                expiry_date = datetime.strptime(expiry, '%Y-%m-%d').date()
            elif isinstance(expiry, datetime):
                expiry_date = expiry.date()
            elif isinstance(expiry, date):
                expiry_date = expiry
            else:
                expiry_date = expiry

            # Filter for matching expiry and strikes
            options_df = self.nifty_options[
                (self.nifty_options['expiry'] == expiry_date) &
                (self.nifty_options['strike'].isin(strikes))
            ].copy()

            if options_df.empty:
                print(f"[{datetime.now()}] ✗ No options found for expiry {expiry_date} and strikes {strikes}")
                return pd.DataFrame()

            print(f"[{datetime.now()}] Fetching quotes for {len(options_df)} options...")

            # Fetch full market data for each option (includes OI)
            # Note: AngelOne has rate limits, so we add small delays
            import time as time_module
            result_data = []

            for idx, row in options_df.iterrows():
                try:
                    # Use getMarketData for full quote (includes OI, volume, etc.)
                    # Mode: FULL for complete data
                    market_data = self.connection.smart_api.getMarketData(
                        mode="FULL",
                        exchangeTokens={
                            "NFO": [row['token']]
                        }
                    )

                    if market_data and market_data.get('status'):
                        fetched_data = market_data.get('data', {}).get('fetched', [])

                        if fetched_data and len(fetched_data) > 0:
                            quote_data = fetched_data[0]

                            # AngelOne uses 'opnInterest' and 'tradeVolume' field names
                            result_data.append({
                                'strike': row['strike'],
                                'option_type': row['option_type'],
                                'expiry': row['expiry'],
                                'close': float(quote_data.get('ltp', 0)),
                                'OI': int(quote_data.get('opnInterest', 0)),  # AngelOne field name
                                'volume': int(quote_data.get('tradeVolume', 0)),  # AngelOne field name
                                'instrument_token': row['token'],
                                'tradingsymbol': row['symbol']
                            })
                        else:
                            # No data returned, use zeros
                            print(f"[{datetime.now()}] ⚠️  No data for {row['symbol']}")
                    else:
                        print(f"[{datetime.now()}] ⚠️  Failed to fetch {row['symbol']}: {market_data.get('message', 'Unknown')}")

                    # Small delay to avoid rate limits (AngelOne: conservative ~4 req/sec)
                    time_module.sleep(0.25)  # 250ms delay = 4 req/sec (conservative)

                except Exception as e:
                    # Handle errors gracefully
                    error_msg = str(e)
                    if 'rate' in error_msg.lower() or 'Access denied' in error_msg:
                        print(f"[{datetime.now()}] ⚠️  Rate limit hit, backing off...")
                        time_module.sleep(2)  # Wait 2 seconds on rate limit before continuing
                    else:
                        print(f"[{datetime.now()}] ⚠️  Failed to fetch {row['symbol']}: {e}")
                    continue

            if not result_data:
                print(f"[{datetime.now()}] ✗ No quotes retrieved")
                return pd.DataFrame()

            result_df = pd.DataFrame(result_data)
            print(f"[{datetime.now()}] ✓ Retrieved {len(result_df)} option quotes")

            return result_df

        except Exception as e:
            print(f"[{datetime.now()}] ✗ Error getting options chain: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()

    def load_instruments(self):
        """Load instruments from AngelOne"""
        try:
            print(f"[{datetime.now()}] Loading instruments from AngelOne...")

            # Download instrument master file
            url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
            response = requests.get(url, timeout=30)

            if response.status_code != 200:
                print(f"[{datetime.now()}] ✗ Failed to download instruments: HTTP {response.status_code}")
                return False

            instruments = response.json()
            print(f"[{datetime.now()}] ✓ Downloaded {len(instruments)} instruments")

            # Convert to DataFrame
            df = pd.DataFrame(instruments)

            # Filter for NFO exchange (derivatives)
            self.nfo_instruments = df[df['exch_seg'] == 'NFO'].copy()
            print(f"[{datetime.now()}] ✓ Filtered {len(self.nfo_instruments)} NFO instruments")

            # Filter for NIFTY options only
            self.nifty_options = self.nfo_instruments[
                (self.nfo_instruments['name'] == 'NIFTY') &
                (self.nfo_instruments['instrumenttype'].isin(['OPTIDX']))
            ].copy()

            # Parse expiry dates
            self.nifty_options['expiry'] = pd.to_datetime(
                self.nifty_options['expiry'], format='%d%b%Y'
            ).dt.date

            # Extract strike prices (they're in paise, divide by 100)
            self.nifty_options['strike'] = self.nifty_options['strike'].astype(float) / 100

            # Determine CE/PE from symbol
            self.nifty_options['option_type'] = self.nifty_options['symbol'].apply(
                lambda x: 'CE' if 'CE' in x else 'PE' if 'PE' in x else None
            )

            # Filter out any non-options
            self.nifty_options = self.nifty_options[
                self.nifty_options['option_type'].notna()
            ].copy()

            # Build token map for quick lookup
            for _, row in self.nifty_options.iterrows():
                self.token_map[row['symbol']] = row['token']

            print(f"[{datetime.now()}] ✓ Loaded {len(self.nifty_options)} NIFTY options")

            # Show expiry dates available
            expiries = sorted(self.nifty_options['expiry'].unique())
            print(f"[{datetime.now()}] ✓ Available expiries: {expiries[:5]}")

            return True

        except Exception as e:
            print(f"[{datetime.now()}] ✗ Error loading instruments: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_next_expiry(self):
        """Get next weekly expiry"""
        try:
            if self.nifty_options is None or self.nifty_options.empty:
                print(f"[{datetime.now()}] ✗ Instruments not loaded. Call load_instruments() first.")
                return None

            # Get today's date
            today = date.today()

            # Find expiries that are today or in the future
            future_expiries = self.nifty_options[
                self.nifty_options['expiry'] >= today
            ]['expiry'].unique()

            if len(future_expiries) == 0:
                print(f"[{datetime.now()}] ✗ No future expiries found")
                return None

            # Sort and get the nearest expiry
            next_expiry = sorted(future_expiries)[0]

            return next_expiry

        except Exception as e:
            print(f"[{datetime.now()}] ✗ Error getting next expiry: {e}")
            return None

    def is_market_open(self):
        """Check if market is open"""
        now = datetime.now()
        current_time = now.time()

        # Market hours: 9:15 AM - 3:30 PM
        market_open = time(9, 15)
        market_close = time(15, 30)

        # Check if weekday
        is_weekday = now.weekday() < 5

        return is_weekday and market_open <= current_time <= market_close

    def wait_for_next_candle(self, interval_minutes=5):
        """Wait for next candle close"""
        import time as time_module
        from datetime import timedelta

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

    def logout(self):
        """Logout from AngelOne"""
        if self._connected:
            self.connection.logout()
            self._connected = False
