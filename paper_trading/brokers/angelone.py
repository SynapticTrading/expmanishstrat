"""
AngelOne Broker Implementation
Implements BrokerInterface for AngelOne SmartAPI
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from datetime import datetime, time
import pandas as pd
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
        self.nfo_instruments = None

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
        return self.connection.get_ltp(self.nifty_symbol)

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
        """Get options chain data"""
        if not self._connected:
            return pd.DataFrame()

        # Note: AngelOne doesn't have direct options chain API
        # You need to:
        # 1. Get instrument tokens for each strike/option type
        # 2. Fetch quotes for each
        # 3. Build DataFrame
        # This is a placeholder - needs full implementation
        return pd.DataFrame()

    def load_instruments(self):
        """Load instruments cache"""
        # Placeholder - implement instrument loading for AngelOne
        # Download from: https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json
        return True

    def get_next_expiry(self):
        """Get next weekly expiry"""
        # Placeholder - needs implementation
        # Parse from instruments or calculate based on date
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
