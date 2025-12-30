"""
AngelOne SmartAPI Connection Module
Handles authentication and connection to AngelOne broker API
"""

from SmartApi import SmartConnect
import pyotp
import json
from datetime import datetime


class AngelOneConnection:
    """Manages connection to AngelOne SmartAPI"""

    def __init__(self, api_key, username, password, totp_token):
        """
        Initialize connection parameters

        Args:
            api_key: AngelOne API key
            username: Client code (e.g., N182640)
            password: MPIN (4-6 digit Mobile PIN, NOT trading password)
            totp_token: TOTP token for 2FA
        """
        self.api_key = api_key
        self.username = username
        self.password = password
        self.totp_token = totp_token

        self.smart_api = None
        self.auth_token = None
        self.refresh_token = None
        self.feed_token = None

    def connect(self):
        """
        Establish connection to AngelOne SmartAPI

        Returns:
            dict: Session data with tokens
        """
        try:
            # Initialize SmartConnect
            self.smart_api = SmartConnect(api_key=self.api_key)

            # Generate TOTP
            totp = pyotp.TOTP(self.totp_token).now()
            print(f"[{datetime.now()}] Generated TOTP: {totp}")

            # Generate session
            print(f"[{datetime.now()}] Connecting to AngelOne...")
            data = self.smart_api.generateSession(self.username, self.password, totp)

            if data['status']:
                print(f"[{datetime.now()}] ✓ Connection successful!")

                # Store tokens
                self.auth_token = data['data']['jwtToken']
                self.refresh_token = data['data']['refreshToken']
                self.feed_token = self.smart_api.getfeedToken()

                print(f"[{datetime.now()}] Auth Token: {self.auth_token[:20]}...")
                print(f"[{datetime.now()}] Feed Token: {self.feed_token}")

                return data
            else:
                print(f"[{datetime.now()}] ✗ Connection failed: {data.get('message', 'Unknown error')}")
                return None

        except Exception as e:
            print(f"[{datetime.now()}] ✗ Error connecting to AngelOne: {str(e)}")
            return None

    def get_profile(self):
        """
        Get user profile information

        Returns:
            dict: User profile data
        """
        try:
            if not self.refresh_token:
                print(f"[{datetime.now()}] ✗ Not connected. Call connect() first.")
                return None

            print(f"[{datetime.now()}] Fetching profile...")
            profile = self.smart_api.getProfile(self.refresh_token)

            if profile['status']:
                print(f"[{datetime.now()}] ✓ Profile retrieved successfully")
                return profile
            else:
                print(f"[{datetime.now()}] ✗ Failed to get profile: {profile.get('message', 'Unknown error')}")
                return None

        except Exception as e:
            print(f"[{datetime.now()}] ✗ Error getting profile: {str(e)}")
            return None

    def get_ltp(self, symbol):
        """
        Get Last Traded Price (LTP) for a symbol

        Args:
            symbol: Symbol in format "EXCHANGE:SYMBOL" (e.g., "NSE:SBIN-EQ", "NSE:NIFTY 50")

        Returns:
            float: Last traded price or None
        """
        try:
            if not self.smart_api:
                print(f"[{datetime.now()}] ✗ Not connected. Call connect() first.")
                return None

            # Parse symbol format
            if ":" in symbol:
                exchange, trading_symbol = symbol.split(":")
            else:
                print(f"[{datetime.now()}] ✗ Invalid symbol format. Use 'EXCHANGE:SYMBOL'")
                return None

            # Symbol-to-token mapping for common symbols
            symbol_token_map = {
                "NIFTY 50": "99926000",  # Nifty 50 index
                "NIFTY BANK": "99926009",  # Bank Nifty index
                "SBIN-EQ": "3045",  # State Bank of India
            }

            # Get token for this symbol
            token = symbol_token_map.get(trading_symbol)
            if not token:
                print(f"[{datetime.now()}] ✗ Unknown symbol: {trading_symbol}. Add to symbol_token_map.")
                return None

            # Get LTP from SmartAPI
            ltp_data = self.smart_api.ltpData(exchange, trading_symbol, token)

            if ltp_data and ltp_data.get('status'):
                ltp = ltp_data['data'].get('ltp')
                return float(ltp) if ltp else None
            else:
                print(f"[{datetime.now()}] ✗ Failed to get LTP: {ltp_data.get('message', 'Unknown error')}")
                return None

        except Exception as e:
            print(f"[{datetime.now()}] ✗ Error getting LTP: {str(e)}")
            return None

    def get_quote(self, symbol):
        """
        Get full quote for a symbol

        Args:
            symbol: Symbol in format "EXCHANGE:SYMBOL"

        Returns:
            dict: Quote data or None
        """
        try:
            if not self.smart_api:
                print(f"[{datetime.now()}] ✗ Not connected. Call connect() first.")
                return None

            # Note: Implement quote retrieval using SmartAPI
            # This needs proper symbol-to-token mapping
            print(f"[{datetime.now()}] ⚠ Quote method needs implementation")
            return None

        except Exception as e:
            print(f"[{datetime.now()}] ✗ Error getting quote: {str(e)}")
            return None

    def get_candle_data(self, exchange, symbol_token, interval, from_date, to_date):
        """
        Get historical candle data

        Args:
            exchange: Exchange name (e.g., "NSE", "NFO")
            symbol_token: Instrument token
            interval: Candle interval (ONE_MINUTE, THREE_MINUTE, FIVE_MINUTE, etc.)
            from_date: Start date/time (format: "YYYY-MM-DD HH:MM")
            to_date: End date/time (format: "YYYY-MM-DD HH:MM")

        Returns:
            dict: Candle data
        """
        try:
            if not self.smart_api:
                print(f"[{datetime.now()}] ✗ Not connected. Call connect() first.")
                return None

            historic_param = {
                "exchange": exchange,
                "symboltoken": symbol_token,
                "interval": interval,
                "fromdate": from_date,
                "todate": to_date
            }

            print(f"[{datetime.now()}] Fetching candle data...")
            print(f"  Exchange: {exchange}")
            print(f"  Symbol Token: {symbol_token}")
            print(f"  Interval: {interval}")
            print(f"  From: {from_date}")
            print(f"  To: {to_date}")

            stock_data = self.smart_api.getCandleData(historic_param)

            if stock_data['status']:
                print(f"[{datetime.now()}] ✓ Candle data retrieved successfully")
                print(f"  Data points: {len(stock_data.get('data', []))}")
                return stock_data
            else:
                print(f"[{datetime.now()}] ✗ Failed to get candle data: {stock_data.get('message', 'Unknown error')}")
                return None

        except Exception as e:
            print(f"[{datetime.now()}] ✗ Error getting candle data: {str(e)}")
            return None

    def logout(self):
        """Logout and close connection"""
        try:
            if self.smart_api:
                print(f"[{datetime.now()}] Logging out...")
                self.smart_api.terminateSession(self.username)
                print(f"[{datetime.now()}] ✓ Logged out successfully")
        except Exception as e:
            print(f"[{datetime.now()}] ✗ Error during logout: {str(e)}")


# Example usage
if __name__ == "__main__":
    # Your credentials
    # IMPORTANT: PASSWORD should be your AngelOne MPIN (4-6 digit PIN)
    API_KEY = "GuULp2XA"
    USERNAME = "N182640"
    PASSWORD = "YOUR_ACTUAL_MPIN_HERE"  # Replace with your real MPIN
    TOTP_TOKEN = "4CDGR2KJ2Y3ESAYCIAXPYP2JAY"

    # Create connection
    connection = AngelOneConnection(API_KEY, USERNAME, PASSWORD, TOTP_TOKEN)

    # Connect
    session_data = connection.connect()

    if session_data:
        print("\n" + "="*80)
        print("SESSION DATA:")
        print("="*80)
        print(json.dumps(session_data, indent=2))

        # Get profile
        print("\n" + "="*80)
        print("PROFILE DATA:")
        print("="*80)
        profile = connection.get_profile()
        if profile:
            print(json.dumps(profile, indent=2))

        # Get candle data (example: SBIN - 5 minute candles)
        print("\n" + "="*80)
        print("CANDLE DATA:")
        print("="*80)
        candle_data = connection.get_candle_data(
            exchange="NSE",
            symbol_token="3045",  # SBIN
            interval="ONE_MINUTE",
            from_date="2021-02-08 09:00",
            to_date="2021-02-08 09:16"
        )
        if candle_data:
            print(json.dumps(candle_data, indent=2))

        # Logout
        print("\n" + "="*80)
        connection.logout()
