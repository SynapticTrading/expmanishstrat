"""
Real-time Data Feed for Paper Trading
Fetches 5-min candle data from AngelOne API
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from datetime import datetime, timedelta
import pandas as pd
import time
from paper_trading.angelone_connection import AngelOneConnection


class PaperDataFeed:
    """Manages real-time data feed for paper trading"""

    def __init__(self, connection: AngelOneConnection):
        """
        Initialize data feed

        Args:
            connection: AngelOneConnection instance
        """
        self.connection = connection
        self.nifty_token = "99926000"  # NIFTY 50 index token
        self.nifty_symbol = "Nifty 50"

        print(f"[{datetime.now()}] Data feed initialized")

    def get_spot_price(self):
        """
        Get current Nifty spot price

        Returns:
            float: Current Nifty price
        """
        try:
            # Get LTP (Last Traded Price)
            ltp_data = self.connection.smart_api.ltpData(
                exchange="NSE",
                tradingsymbol=self.nifty_symbol,
                symboltoken=self.nifty_token
            )

            if ltp_data and ltp_data.get('status'):
                ltp = ltp_data['data']['ltp']
                return float(ltp)
            else:
                print(f"[{datetime.now()}] ✗ Failed to get spot price")
                return None

        except Exception as e:
            print(f"[{datetime.now()}] ✗ Error getting spot price: {e}")
            return None

    def get_5min_candle(self, symbol_token, exchange="NFO"):
        """
        Get latest 5-min candle for an instrument

        Args:
            symbol_token: Instrument token
            exchange: Exchange (NSE/NFO)

        Returns:
            dict: Candle data (open, high, low, close, volume)
        """
        try:
            # Get last 2 candles (to ensure we have the complete latest one)
            to_date = datetime.now()
            from_date = to_date - timedelta(minutes=15)

            candle_data = self.connection.get_candle_data(
                exchange=exchange,
                symbol_token=symbol_token,
                interval="FIVE_MINUTE",
                from_date=from_date.strftime("%Y-%m-%d %H:%M"),
                to_date=to_date.strftime("%Y-%m-%d %H:%M")
            )

            if candle_data and candle_data.get('status'):
                # Get last candle
                candles = candle_data['data']
                if candles:
                    last_candle = candles[-1]
                    # Format: [timestamp, open, high, low, close, volume]
                    return {
                        'timestamp': last_candle[0],
                        'open': float(last_candle[1]),
                        'high': float(last_candle[2]),
                        'low': float(last_candle[3]),
                        'close': float(last_candle[4]),
                        'volume': int(last_candle[5])
                    }

            return None

        except Exception as e:
            print(f"[{datetime.now()}] ✗ Error getting candle: {e}")
            return None

    def get_options_chain(self, expiry, strikes):
        """
        Get options chain data for specified strikes

        Args:
            expiry: Expiry date (YYYY-MM-DD or datetime)
            strikes: List of strike prices

        Returns:
            DataFrame: Options data with columns [strike, option_type, expiry, close, oi, volume]
        """
        try:
            # Note: This is a simplified version
            # In production, you would:
            # 1. Get instrument list from AngelOne
            # 2. Filter for NIFTY options with matching expiry/strikes
            # 3. Fetch LTP and OI for each option
            # 4. Build DataFrame

            # For now, returning placeholder
            # You'll need to implement proper instrument lookup and data fetching

            print(f"[{datetime.now()}] ⚠ get_options_chain() needs implementation")
            print(f"  Would fetch data for expiry: {expiry}, strikes: {strikes}")

            # Placeholder return
            return pd.DataFrame(columns=['strike', 'option_type', 'expiry', 'close', 'oi', 'volume'])

        except Exception as e:
            print(f"[{datetime.now()}] ✗ Error getting options chain: {e}")
            return pd.DataFrame()

    def wait_for_next_candle(self, interval_minutes=5):
        """
        Wait until next candle close

        Args:
            interval_minutes: Candle interval in minutes (default: 5)
        """
        now = datetime.now()

        # Calculate next candle close time
        minutes_to_wait = interval_minutes - (now.minute % interval_minutes)
        if minutes_to_wait == interval_minutes:
            minutes_to_wait = 0  # Already at candle close

        next_candle_time = now + timedelta(minutes=minutes_to_wait)
        next_candle_time = next_candle_time.replace(second=0, microsecond=0)

        wait_seconds = (next_candle_time - now).total_seconds()

        if wait_seconds > 0:
            print(f"[{now}] Waiting {wait_seconds:.0f}s for next candle at {next_candle_time.strftime('%H:%M')}")
            time.sleep(wait_seconds)

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
