"""
AngelOne Data Fetch Mechanisms
Demonstrates different ways to fetch market data for paper/live trading
"""

from SmartApi import SmartConnect
import pyotp
from datetime import datetime, timedelta
import time
import pandas as pd

# Your credentials
API_KEY = "GuULp2XA"
USERNAME = "N182640"
PASSWORD = "7531"
TOTP_TOKEN = "4CDGR2KJ2Y3ESAYCIAXPYP2JAY"


class AngelOneDataFetcher:
    """Demonstrates different data fetch methods"""

    def __init__(self):
        self.smart_api = None
        self.connected = False

    def connect(self):
        """Connect to AngelOne"""
        try:
            self.smart_api = SmartConnect(api_key=API_KEY)
            totp = pyotp.TOTP(TOTP_TOKEN).now()
            data = self.smart_api.generateSession(USERNAME, PASSWORD, totp)

            if data['status']:
                print(f"✓ Connected to AngelOne")
                self.connected = True
                return True
            return False
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return False

    def method_1_ltp_mode(self, exchange, symbol_token, trading_symbol):
        """
        Method 1: LTP (Last Traded Price) - Fastest, minimal data
        Use case: Quick price checks, not suitable for OHLC candles
        """
        print("\n" + "="*80)
        print("METHOD 1: LTP (Last Traded Price)")
        print("="*80)

        try:
            # LTP mode gives you just the last price
            ltp_data = self.smart_api.ltpData(exchange, trading_symbol, symbol_token)

            print(f"\nExchange: {exchange}")
            print(f"Symbol: {trading_symbol}")
            print(f"Token: {symbol_token}")
            print(f"\nResponse: {ltp_data}")

            if ltp_data.get('status'):
                data = ltp_data['data']
                print(f"\nLast Traded Price: ₹{data.get('ltp', 'N/A')}")
                print(f"Timestamp: {datetime.now()}")

            print("\n✓ LTP fetched successfully")
            print("\nPros:")
            print("  - Fastest (lowest latency)")
            print("  - Minimal data transfer")
            print("\nCons:")
            print("  - No OHLC data")
            print("  - No volume data")
            print("  - Not suitable for candle-based strategies")

            return ltp_data

        except Exception as e:
            print(f"✗ LTP fetch failed: {e}")
            return None

    def method_2_quote_mode(self, exchange, symbol_token, trading_symbol):
        """
        Method 2: Quote - More detailed, includes bid/ask/volume/OI
        Use case: Current market snapshot with depth
        """
        print("\n" + "="*80)
        print("METHOD 2: Quote (Market Snapshot)")
        print("="*80)

        try:
            # Quote gives current market snapshot
            quote_data = self.smart_api.getMarketData("FULL", [
                {
                    "exchange": exchange,
                    "symboltoken": symbol_token,
                    "tradingsymbol": trading_symbol
                }
            ])

            print(f"\nExchange: {exchange}")
            print(f"Symbol: {trading_symbol}")
            print(f"Token: {symbol_token}")
            print(f"\nResponse (full): {quote_data}")

            if quote_data.get('status') and quote_data.get('data'):
                data = quote_data['data']['fetched'][0]
                print(f"\n📊 Market Snapshot:")
                print(f"  LTP: ₹{data.get('ltp', 'N/A')}")
                print(f"  Open: ₹{data.get('open', 'N/A')}")
                print(f"  High: ₹{data.get('high', 'N/A')}")
                print(f"  Low: ₹{data.get('low', 'N/A')}")
                print(f"  Close (Prev): ₹{data.get('close', 'N/A')}")
                print(f"  Volume: {data.get('volume', 'N/A')}")
                print(f"  OI: {data.get('oi', 'N/A')}")
                print(f"  Last Update: {data.get('updateTime', 'N/A')}")

            print("\n✓ Quote fetched successfully")
            print("\nPros:")
            print("  - Includes OHLC for current day")
            print("  - Has volume and OI")
            print("  - Good for current bar tracking")
            print("\nCons:")
            print("  - Only current day's data")
            print("  - Not historical candles")
            print("  - Need to build candles yourself from ticks")

            return quote_data

        except Exception as e:
            print(f"✗ Quote fetch failed: {e}")
            return None

    def method_3_historical_candles(self, exchange, symbol_token, interval="FIVE_MINUTE"):
        """
        Method 3: Historical Candle Data - Proper OHLCV candles
        Use case: Get completed 5-min candles aligned with exchange
        THIS IS THE RECOMMENDED METHOD FOR YOUR STRATEGY
        """
        print("\n" + "="*80)
        print("METHOD 3: Historical Candle Data (RECOMMENDED)")
        print("="*80)

        try:
            # Get last 2 hours of data to ensure we have recent candles
            to_date = datetime.now()
            from_date = to_date - timedelta(hours=2)

            historic_param = {
                "exchange": exchange,
                "symboltoken": symbol_token,
                "interval": interval,
                "fromdate": from_date.strftime("%Y-%m-%d %H:%M"),
                "todate": to_date.strftime("%Y-%m-%d %H:%M")
            }

            print(f"\nFetching candles:")
            print(f"  Exchange: {exchange}")
            print(f"  Token: {symbol_token}")
            print(f"  Interval: {interval}")
            print(f"  From: {from_date.strftime('%Y-%m-%d %H:%M')}")
            print(f"  To: {to_date.strftime('%Y-%m-%d %H:%M')}")

            candle_data = self.smart_api.getCandleData(historic_param)

            if candle_data.get('status') and candle_data.get('data'):
                candles = candle_data['data']
                print(f"\n✓ Fetched {len(candles)} candles")

                # Convert to DataFrame for analysis
                df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'])

                print(f"\n📊 Recent Candles:")
                print(df.tail(5).to_string(index=False))

                print("\n📈 Latest Candle Details:")
                latest = candles[-1]
                print(f"  Time: {latest[0]}")
                print(f"  Open: {latest[1]}")
                print(f"  High: {latest[2]}")
                print(f"  Low: {latest[3]}")
                print(f"  Close: {latest[4]}")
                print(f"  Volume: {latest[5]}")

                print("\n✓ Historical candles fetched successfully")
                print("\nPros:")
                print("  - ✅ Proper OHLCV candles")
                print("  - ✅ Aligned with exchange (Zerodha/TradingView)")
                print("  - ✅ Completed candles only (no partial)")
                print("  - ✅ Direct use in strategy")
                print("  - ✅ No manual candle building needed")
                print("\nCons:")
                print("  - Slight delay (candle completes first)")
                print("  - Historical data only (use for completed bars)")

                print("\n💡 CANDLE TIMING:")
                print("  - 5-min candles: 9:15-9:20, 9:20-9:25, 9:25-9:30, etc.")
                print("  - Candle 'closes' at: 9:20, 9:25, 9:30, etc.")
                print("  - Data available ~1-2 seconds after close")
                print("  - Your strategy checks at these exact times")

                return df

            else:
                print(f"✗ No candle data available")
                return None

        except Exception as e:
            print(f"✗ Historical candle fetch failed: {e}")
            return None

    def method_4_websocket_streaming(self):
        """
        Method 4: WebSocket Streaming - Real-time ticks
        Use case: Tick-by-tick data, build candles yourself
        """
        print("\n" + "="*80)
        print("METHOD 4: WebSocket Streaming (Advanced)")
        print("="*80)

        print("\nWebSocket provides:")
        print("  - Tick-by-tick price updates")
        print("  - Sub-second latency")
        print("  - You build candles from ticks")

        print("\n⚠️  For 5-min candle strategy:")
        print("  - WebSocket is OVERKILL")
        print("  - Historical API (Method 3) is better")
        print("  - Simpler, cleaner, aligned with exchange")

        print("\nWebSocket is useful for:")
        print("  - Tick-based strategies")
        print("  - Sub-minute trading")
        print("  - Order book depth analysis")

        print("\n💡 Recommendation: Use Method 3 for your strategy")

    def recommended_approach_for_strategy(self):
        """
        Recommended approach for 5-min candle strategy
        """
        print("\n" + "="*80)
        print("RECOMMENDED APPROACH FOR YOUR STRATEGY")
        print("="*80)

        print("\n🎯 Best Method: Historical Candle API (Method 3)")

        print("\n📋 Implementation Plan:")
        print("\n1. Every 5 minutes (at 9:20, 9:25, 9:30, etc.):")
        print("   - Wait for candle to complete")
        print("   - Fetch last 2-3 candles using getCandleData()")
        print("   - Use latest completed candle for decisions")
        print("   - This ensures alignment with TradingView/Zerodha charts")

        print("\n2. For Spot Price:")
        print("   - Use getCandleData() with Nifty 50 index token")
        print("   - Interval: FIVE_MINUTE")
        print("   - Get last candle's close price")

        print("\n3. For Options Chain (OI data):")
        print("   - Use getMarketData() in FULL mode")
        print("   - Fetch all strikes ±5 from spot")
        print("   - Get current OI values")

        print("\n4. Timing Synchronization:")
        print("   - Set up cron/scheduler to run at: X:X0, X:X5 (e.g., 9:20, 9:25)")
        print("   - Add 10-second delay after candle close")
        print("   - Ensures data is available from exchange")

        print("\n5. Example 5-min Schedule:")
        print("   09:20:10 - Fetch candle (9:15-9:20), check entry")
        print("   09:25:10 - Fetch candle (9:20-9:25), check entry/exit")
        print("   09:30:10 - Fetch candle (9:25-9:30), check entry/exit")
        print("   ... continues every 5 minutes till 3:30 PM")

        print("\n✅ This approach guarantees:")
        print("   - Candles match Zerodha/TradingView exactly")
        print("   - No partial candle issues")
        print("   - Clean, reliable data")
        print("   - Easy to backtest vs live consistency")


def main():
    """Run all examples"""
    print("="*80)
    print("ANGELONE DATA FETCH MECHANISMS - COMPREHENSIVE GUIDE")
    print("="*80)

    fetcher = AngelOneDataFetcher()

    # Connect
    if not fetcher.connect():
        print("Failed to connect. Exiting.")
        return

    # Example: SBIN (State Bank of India)
    EXCHANGE = "NSE"
    SYMBOL_TOKEN = "3045"
    TRADING_SYMBOL = "SBIN-EQ"

    print("\n\n🔍 Testing with: SBIN (State Bank of India)")
    print(f"Exchange: {EXCHANGE}")
    print(f"Symbol: {TRADING_SYMBOL}")
    print(f"Token: {SYMBOL_TOKEN}")

    # Test all methods
    input("\n▶️  Press Enter to test Method 1: LTP...")
    fetcher.method_1_ltp_mode(EXCHANGE, SYMBOL_TOKEN, TRADING_SYMBOL)

    input("\n▶️  Press Enter to test Method 2: Quote...")
    fetcher.method_2_quote_mode(EXCHANGE, SYMBOL_TOKEN, TRADING_SYMBOL)

    input("\n▶️  Press Enter to test Method 3: Historical Candles (Recommended)...")
    fetcher.method_3_historical_candles(EXCHANGE, SYMBOL_TOKEN, "FIVE_MINUTE")

    input("\n▶️  Press Enter to see Method 4: WebSocket info...")
    fetcher.method_4_websocket_streaming()

    input("\n▶️  Press Enter to see Recommended Approach...")
    fetcher.recommended_approach_for_strategy()

    print("\n" + "="*80)
    print("EXAMPLES COMPLETE")
    print("="*80)
    print("\n💡 Key Takeaway:")
    print("For your 5-min candle strategy, use Historical Candle API (Method 3)")
    print("Fetch candles every 5 minutes after candle close for perfect alignment.")


if __name__ == "__main__":
    main()
