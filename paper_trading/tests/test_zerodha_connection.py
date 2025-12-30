"""
Test Zerodha Connection
Verifies that Zerodha API credentials work correctly
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from datetime import datetime, timedelta
import json
from paper_trading.legacy.zerodha_connection import ZerodhaConnection, load_credentials_from_file


def test_connection():
    """Test Zerodha connection"""

    print(f"\n{'='*80}")
    print(f"ZERODHA CONNECTION TEST")
    print(f"{'='*80}\n")

    # Load credentials
    print(f"[{datetime.now()}] Loading credentials from file...")
    creds = load_credentials_from_file("paper_trading/credentials.txt")

    if not creds:
        print(f"[{datetime.now()}] ✗ TEST FAILED: Could not load credentials")
        return False

    required_keys = ['api_key', 'api_secret', 'user_id', 'user_password', 'totp_key']
    missing_keys = [key for key in required_keys if key not in creds]

    if missing_keys:
        print(f"[{datetime.now()}] ✗ TEST FAILED: Missing credentials: {missing_keys}")
        return False

    print(f"[{datetime.now()}] ✓ Credentials loaded successfully")
    print(f"  API Key: {creds['api_key'][:10]}...")
    print(f"  User ID: {creds['user_id']}")

    # Create connection
    print(f"\n[{datetime.now()}] Creating connection...")
    connection = ZerodhaConnection(
        api_key=creds['api_key'],
        api_secret=creds['api_secret'],
        user_id=creds['user_id'],
        user_password=creds['user_password'],
        totp_key=creds['totp_key']
    )

    # Test 1: Connect
    print(f"\n{'='*80}")
    print(f"TEST 1: Connection")
    print(f"{'='*80}")

    kite = connection.connect()

    if not kite:
        print(f"[{datetime.now()}] ✗ TEST FAILED: Could not connect to Zerodha")
        return False

    print(f"[{datetime.now()}] ✓ TEST PASSED: Connection successful")

    # Test 2: Get Profile
    print(f"\n{'='*80}")
    print(f"TEST 2: Profile Retrieval")
    print(f"{'='*80}")

    profile = connection.get_profile()

    if not profile:
        print(f"[{datetime.now()}] ✗ TEST FAILED: Could not retrieve profile")
        return False

    print(f"[{datetime.now()}] ✓ TEST PASSED: Profile retrieved successfully")
    print(f"\nProfile Data:")
    print(json.dumps(profile, indent=2))

    # Test 3: Get Nifty LTP
    print(f"\n{'='*80}")
    print(f"TEST 3: Get Nifty LTP")
    print(f"{'='*80}")

    ltp = connection.get_ltp("NSE:NIFTY 50")

    if not ltp:
        print(f"[{datetime.now()}] ✗ TEST FAILED: Could not get Nifty LTP")
        print(f"  (This is expected if market is closed)")
    else:
        print(f"[{datetime.now()}] ✓ TEST PASSED: Nifty LTP retrieved")
        print(f"  Nifty 50 LTP: {ltp}")

    # Test 4: Get Nifty Quote
    print(f"\n{'='*80}")
    print(f"TEST 4: Get Nifty Quote")
    print(f"{'='*80}")

    quote = connection.get_quote("NSE:NIFTY 50")

    if not quote:
        print(f"[{datetime.now()}] ✗ TEST FAILED: Could not get Nifty quote")
        print(f"  (This is expected if market is closed)")
    else:
        print(f"[{datetime.now()}] ✓ TEST PASSED: Nifty quote retrieved")
        print(f"\nQuote Data:")
        print(f"  Last Price: {quote.get('last_price', 'N/A')}")
        print(f"  OHLC: O={quote.get('ohlc', {}).get('open', 'N/A')}, H={quote.get('ohlc', {}).get('high', 'N/A')}, L={quote.get('ohlc', {}).get('low', 'N/A')}, C={quote.get('ohlc', {}).get('close', 'N/A')}")
        print(f"  Volume: {quote.get('volume', 'N/A'):,}")

    # Test 5: Get Instruments
    print(f"\n{'='*80}")
    print(f"TEST 5: Get NFO Instruments")
    print(f"{'='*80}")

    instruments = connection.get_instruments("NFO")

    if instruments is None or instruments.empty:
        print(f"[{datetime.now()}] ✗ TEST FAILED: Could not get instruments")
        return False

    print(f"[{datetime.now()}] ✓ TEST PASSED: Retrieved {len(instruments)} instruments")

    # Filter for NIFTY options
    nifty_options = instruments[
        (instruments['name'] == 'NIFTY') &
        (instruments['instrument_type'].isin(['CE', 'PE']))
    ]

    if not nifty_options.empty:
        print(f"  NIFTY Options: {len(nifty_options)}")
        print(f"  Sample options:")
        for i, row in nifty_options.head(3).iterrows():
            print(f"    {row['tradingsymbol']} - Strike: {row['strike']}, Expiry: {row['expiry']}")

    # Test 6: Get Historical Data
    print(f"\n{'='*80}")
    print(f"TEST 6: Get Historical Data")
    print(f"{'='*80}")

    # Get Nifty 50 token
    nse_instruments = connection.get_instruments("NSE")
    nifty_row = nse_instruments[nse_instruments['tradingsymbol'] == 'NIFTY 50']

    if nifty_row.empty:
        print(f"[{datetime.now()}] ✗ TEST FAILED: Could not find Nifty 50 token")
    else:
        nifty_token = nifty_row.iloc[0]['instrument_token']

        # Get last 5 days of 5-min data
        to_date = datetime.now()
        from_date = to_date - timedelta(days=5)

        hist_data = connection.get_historical_data(
            instrument_token=nifty_token,
            from_date=from_date,
            to_date=to_date,
            interval="5minute"
        )

        if hist_data is None or hist_data.empty:
            print(f"[{datetime.now()}] ✗ TEST FAILED: Could not get historical data")
            print(f"  (This is expected if requesting data outside market hours)")
        else:
            print(f"[{datetime.now()}] ✓ TEST PASSED: Retrieved {len(hist_data)} candles")
            print(f"\nLast 3 candles:")
            print(hist_data[['date', 'open', 'high', 'low', 'close', 'volume']].tail(3).to_string())

    # Logout
    print(f"\n{'='*80}")
    print(f"LOGOUT")
    print(f"{'='*80}")
    connection.logout()

    # Summary
    print(f"\n{'='*80}")
    print(f"TEST SUMMARY")
    print(f"{'='*80}")
    print(f"✓ Connection successful")
    print(f"✓ Profile retrieved")
    print(f"✓ Instruments loaded")
    print(f"✓ All critical tests passed!")
    print(f"\nYou can now run paper trading with:")
    print(f"  python paper_trading/zerodha_paper_runner.py")
    print(f"{'='*80}\n")

    return True


if __name__ == "__main__":
    try:
        success = test_connection()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n[{datetime.now()}] ✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
