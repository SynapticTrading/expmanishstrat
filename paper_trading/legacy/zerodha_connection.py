"""
Zerodha Kite Connect Connection Module
Handles authentication and connection to Zerodha broker API
"""

import requests
import json
import pyotp
from kiteconnect import KiteConnect
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import pandas as pd


class ZerodhaConnection:
    """Manages connection to Zerodha Kite Connect API"""

    def __init__(self, api_key, api_secret, user_id, user_password, totp_key):
        """
        Initialize connection parameters

        Args:
            api_key: Zerodha API key
            api_secret: Zerodha API secret
            user_id: Zerodha user ID
            user_password: Zerodha password
            totp_key: TOTP key for 2FA
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.user_id = user_id
        self.user_password = user_password
        self.totp_key = totp_key

        self.kite = None
        self.access_token = None

    def connect(self):
        """
        Establish connection to Zerodha Kite Connect

        Returns:
            KiteConnect: Authenticated KiteConnect instance
        """
        try:
            print(f"[{datetime.now()}] Connecting to Zerodha...")

            # Create HTTP session for login
            http_session = requests.Session()

            # Get login URL
            url = http_session.get(
                url=f'https://kite.trade/connect/login?v=3&api_key={self.api_key}'
            ).url

            # Login with credentials
            response = http_session.post(
                url='https://kite.zerodha.com/api/login',
                data={'user_id': self.user_id, 'password': self.user_password}
            )
            resp_dict = json.loads(response.content)

            # Generate TOTP
            totp = pyotp.TOTP(self.totp_key).now()
            print(f"[{datetime.now()}] Generated TOTP: {totp}")

            # Submit TOTP
            http_session.post(
                url='https://kite.zerodha.com/api/twofa',
                data={
                    'user_id': self.user_id,
                    'request_id': resp_dict["data"]["request_id"],
                    'twofa_value': totp
                }
            )

            # Get request token
            # Zerodha redirects to http://127.0.0.1:80 which fails
            # But we can extract request_token from the error message
            url = url + "&skip_session=true"

            try:
                response = http_session.get(url=url, allow_redirects=True).url
                request_token = parse_qs(urlparse(response).query)['request_token'][0]
            except requests.exceptions.ConnectionError as e:
                # Extract request_token from error message
                error_str = str(e)
                if 'request_token=' in error_str:
                    import re
                    match = re.search(r'request_token=([^&\s)]+)', error_str)
                    if match:
                        request_token = match.group(1)
                        print(f"[{datetime.now()}] ✓ Request token extracted from redirect")
                    else:
                        raise Exception("Could not extract request_token from error")
                else:
                    raise

            print(f"[{datetime.now()}] Request token obtained: {request_token[:20]}...")

            # Generate session (with 30s timeout to handle slow API responses)
            self.kite = KiteConnect(api_key=self.api_key, timeout=30)
            data = self.kite.generate_session(request_token, api_secret=self.api_secret)
            self.access_token = data["access_token"]
            self.kite.set_access_token(self.access_token)

            print(f"[{datetime.now()}] ✓ Connection successful!")
            print(f"[{datetime.now()}] Access Token: {self.access_token[:20]}...")

            return self.kite

        except Exception as e:
            print(f"[{datetime.now()}] ✗ Error connecting to Zerodha: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def get_profile(self):
        """
        Get user profile information

        Returns:
            dict: User profile data
        """
        try:
            if not self.kite:
                print(f"[{datetime.now()}] ✗ Not connected. Call connect() first.")
                return None

            print(f"[{datetime.now()}] Fetching profile...")
            profile = self.kite.profile()

            print(f"[{datetime.now()}] ✓ Profile retrieved successfully")
            return profile

        except Exception as e:
            print(f"[{datetime.now()}] ✗ Error getting profile: {str(e)}")
            return None

    def get_ltp(self, instrument_token, max_retries=3):
        """
        Get Last Traded Price for instrument with retry logic

        Args:
            instrument_token: NSE:NIFTY 50 or NFO:NIFTY24DECFUT, etc.
            max_retries: Maximum number of retry attempts (default: 3)

        Returns:
            float: LTP value
        """
        import time as time_module

        if not self.kite:
            print(f"[{datetime.now()}] ✗ Not connected. Call connect() first.")
            return None

        for attempt in range(max_retries):
            try:
                ltp_data = self.kite.ltp([instrument_token])

                if ltp_data and instrument_token in ltp_data:
                    return ltp_data[instrument_token]['last_price']

                # If no data returned, retry
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"[{datetime.now()}] ⚠️  LTP data empty, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                    time_module.sleep(wait_time)

            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    print(f"[{datetime.now()}] ⚠️  Error getting LTP: {str(e)}")
                    print(f"[{datetime.now()}] ⚠️  Retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                    time_module.sleep(wait_time)
                else:
                    print(f"[{datetime.now()}] ✗ Failed to get LTP after {max_retries} attempts: {str(e)}")

        return None

    def get_quote(self, instrument_token):
        """
        Get full quote for instrument

        Args:
            instrument_token: e.g., "NSE:NIFTY 50"

        Returns:
            dict: Quote data with OHLC, volume, OI, etc.
        """
        try:
            if not self.kite:
                print(f"[{datetime.now()}] ✗ Not connected. Call connect() first.")
                return None

            quote_data = self.kite.quote([instrument_token])

            if quote_data and instrument_token in quote_data:
                return quote_data[instrument_token]

            return None

        except Exception as e:
            print(f"[{datetime.now()}] ✗ Error getting quote: {str(e)}")
            return None

    def get_historical_data(self, instrument_token, from_date, to_date, interval="5minute"):
        """
        Get historical candle data

        Args:
            instrument_token: Instrument token (numeric)
            from_date: Start date (datetime object)
            to_date: End date (datetime object)
            interval: Candle interval (minute, 3minute, 5minute, 15minute, day, etc.)

        Returns:
            DataFrame: Historical OHLCV data
        """
        try:
            if not self.kite:
                print(f"[{datetime.now()}] ✗ Not connected. Call connect() first.")
                return None

            print(f"[{datetime.now()}] Fetching historical data...")
            print(f"  Instrument: {instrument_token}")
            print(f"  From: {from_date}")
            print(f"  To: {to_date}")
            print(f"  Interval: {interval}")

            data = self.kite.historical_data(
                instrument_token=instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval=interval
            )

            if data:
                df = pd.DataFrame(data)
                print(f"[{datetime.now()}] ✓ Retrieved {len(df)} candles")
                return df

            return None

        except Exception as e:
            print(f"[{datetime.now()}] ✗ Error getting historical data: {str(e)}")
            return None

    def get_instruments(self, exchange="NFO"):
        """
        Get instrument list for exchange

        Args:
            exchange: Exchange name (NSE, NFO, BSE, etc.)

        Returns:
            DataFrame: Instrument list
        """
        try:
            if not self.kite:
                print(f"[{datetime.now()}] ✗ Not connected. Call connect() first.")
                return None

            print(f"[{datetime.now()}] Fetching instruments for {exchange}...")
            instruments = self.kite.instruments(exchange)

            if instruments:
                df = pd.DataFrame(instruments)
                print(f"[{datetime.now()}] ✓ Retrieved {len(df)} instruments")
                return df

            return None

        except Exception as e:
            print(f"[{datetime.now()}] ✗ Error getting instruments: {str(e)}")
            return None

    def logout(self):
        """Logout and invalidate token"""
        try:
            if self.kite:
                print(f"[{datetime.now()}] Logging out...")
                self.kite.invalidate_access_token()
                print(f"[{datetime.now()}] ✓ Logged out successfully")
        except Exception as e:
            print(f"[{datetime.now()}] ✗ Error during logout: {str(e)}")


def load_credentials_from_file(filepath="paper_trading/credentials.txt"):
    """
    Load credentials from file

    Args:
        filepath: Path to credentials file

    Returns:
        dict: Credentials dictionary
    """
    credentials = {}

    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue

                # Parse key = value
                if '=' in line:
                    key, value = line.split('=', 1)
                    credentials[key.strip()] = value.strip()

        return credentials

    except Exception as e:
        print(f"Error loading credentials: {e}")
        return None


# Example usage
if __name__ == "__main__":
    # Load credentials from file
    creds = load_credentials_from_file()

    if not creds:
        print("Failed to load credentials!")
        exit(1)

    # Create connection
    connection = ZerodhaConnection(
        api_key=creds['api_key'],
        api_secret=creds['api_secret'],
        user_id=creds['user_id'],
        user_password=creds['user_password'],
        totp_key=creds['totp_key']
    )

    # Connect
    kite = connection.connect()

    if kite:
        print("\n" + "="*80)
        print("PROFILE DATA:")
        print("="*80)
        profile = connection.get_profile()
        if profile:
            print(json.dumps(profile, indent=2))

        # Get Nifty LTP
        print("\n" + "="*80)
        print("NIFTY LTP:")
        print("="*80)
        ltp = connection.get_ltp("NSE:NIFTY 50")
        if ltp:
            print(f"Nifty 50 LTP: {ltp}")

        # Logout
        print("\n" + "="*80)
        connection.logout()
