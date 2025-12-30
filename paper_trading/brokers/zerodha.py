"""
Zerodha Broker Implementation
Implements BrokerInterface for Zerodha Kite Connect
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from paper_trading.brokers.base import BrokerInterface
from paper_trading.legacy.zerodha_connection import ZerodhaConnection
from paper_trading.legacy.zerodha_data_feed import ZerodhaDataFeed


class ZerodhaBroker(BrokerInterface):
    """Zerodha Kite Connect broker implementation"""

    def __init__(self, api_key, api_secret, user_id, user_password, totp_key):
        """
        Initialize Zerodha broker

        Args:
            api_key: Zerodha API key
            api_secret: Zerodha API secret
            user_id: Zerodha user ID
            user_password: Zerodha password
            totp_key: TOTP key
        """
        self.connection = ZerodhaConnection(
            api_key=api_key,
            api_secret=api_secret,
            user_id=user_id,
            user_password=user_password,
            totp_key=totp_key
        )
        self.data_feed = None
        self._connected = False

    @property
    def name(self):
        """Broker name"""
        return "Zerodha"

    def connect(self):
        """Connect to Zerodha API"""
        kite = self.connection.connect()
        if kite:
            self.data_feed = ZerodhaDataFeed(self.connection)
            self._connected = True
            return True
        return False

    def get_spot_price(self, symbol="NIFTY 50"):
        """Get Nifty spot price"""
        if not self._connected or not self.data_feed:
            return None
        return self.data_feed.get_spot_price()

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
        return self.connection.get_historical_data(instrument_token, from_date, to_date, interval)

    def get_instruments(self, exchange="NFO"):
        """Get instrument list"""
        if not self._connected:
            return None
        return self.connection.get_instruments(exchange)

    def get_options_chain(self, expiry, strikes):
        """Get options chain data"""
        if not self._connected or not self.data_feed:
            return None
        return self.data_feed.get_options_chain(expiry, strikes)

    def load_instruments(self):
        """Load instruments cache"""
        if not self._connected or not self.data_feed:
            return False
        return self.data_feed.load_instruments()

    def get_next_expiry(self):
        """Get next weekly expiry"""
        if not self._connected or not self.data_feed:
            return None
        return self.data_feed.get_next_expiry()

    def is_market_open(self):
        """Check if market is open"""
        if not self._connected or not self.data_feed:
            return False
        return self.data_feed.is_market_open()

    def wait_for_next_candle(self, interval_minutes=5):
        """Wait for next candle"""
        if not self._connected or not self.data_feed:
            return
        self.data_feed.wait_for_next_candle(interval_minutes)

    def logout(self):
        """Logout from Zerodha"""
        if self._connected:
            self.connection.logout()
            self._connected = False
