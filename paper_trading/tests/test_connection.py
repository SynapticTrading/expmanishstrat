"""
Test Script for AngelOne SmartAPI Connection
Run this to verify your API connection is working correctly
"""

from angelone_connection import AngelOneConnection
import json
from datetime import datetime, timedelta


def test_basic_connection():
    """Test basic connection and authentication"""
    print("="*80)
    print("TEST 1: Basic Connection")
    print("="*80)

    # Replace with your credentials
    # IMPORTANT: PASSWORD should be your AngelOne MPIN (4-6 digit PIN), NOT trading password
    API_KEY = "GuULp2XA"
    USERNAME = "N182640"
    PASSWORD = "YOUR_ACTUAL_MPIN_HERE"  # Replace with your real MPIN
    TOTP_TOKEN = "4CDGR2KJ2Y3ESAYCIAXPYP2JAY"

    connection = AngelOneConnection(API_KEY, USERNAME, PASSWORD, TOTP_TOKEN)

    # Test connection
    session_data = connection.connect()

    if session_data and session_data.get('status'):
        print("\n✓ TEST PASSED: Connection successful")
        return connection
    else:
        print("\n✗ TEST FAILED: Connection failed")
        return None


def test_profile(connection):
    """Test profile retrieval"""
    print("\n" + "="*80)
    print("TEST 2: Profile Retrieval")
    print("="*80)

    if not connection:
        print("✗ TEST SKIPPED: No connection available")
        return False

    profile = connection.get_profile()

    if profile and profile.get('status'):
        print("\n✓ TEST PASSED: Profile retrieved successfully")
        print(f"  Client Name: {profile['data'].get('name', 'N/A')}")
        print(f"  Client Code: {profile['data'].get('clientcode', 'N/A')}")
        return True
    else:
        print("\n✗ TEST FAILED: Could not retrieve profile")
        return False


def test_candle_data(connection):
    """Test historical candle data retrieval"""
    print("\n" + "="*80)
    print("TEST 3: Historical Candle Data")
    print("="*80)

    if not connection:
        print("✗ TEST SKIPPED: No connection available")
        return False

    # Test with SBIN (State Bank of India)
    candle_data = connection.get_candle_data(
        exchange="NSE",
        symbol_token="3045",  # SBIN
        interval="FIVE_MINUTE",
        from_date="2021-02-08 09:00",
        to_date="2021-02-08 10:00"
    )

    if candle_data and candle_data.get('status'):
        data_points = len(candle_data.get('data', []))
        print(f"\n✓ TEST PASSED: Retrieved {data_points} candle data points")

        # Show first candle
        if data_points > 0:
            first_candle = candle_data['data'][0]
            print(f"\n  Sample Candle (first):")
            print(f"    Timestamp: {first_candle[0]}")
            print(f"    Open: {first_candle[1]}")
            print(f"    High: {first_candle[2]}")
            print(f"    Low: {first_candle[3]}")
            print(f"    Close: {first_candle[4]}")
            print(f"    Volume: {first_candle[5]}")
        return True
    else:
        print("\n✗ TEST FAILED: Could not retrieve candle data")
        return False


def test_nifty_spot_data(connection):
    """Test Nifty spot price retrieval"""
    print("\n" + "="*80)
    print("TEST 4: Nifty Spot Price (Current Day)")
    print("="*80)

    if not connection:
        print("✗ TEST SKIPPED: No connection available")
        return False

    # Nifty 50 index token
    # Note: You may need to update the date to current/recent trading day
    today = datetime.now()
    from_date = today.replace(hour=9, minute=15).strftime("%Y-%m-%d %H:%M")
    to_date = today.replace(hour=15, minute=30).strftime("%Y-%m-%d %H:%M")

    print(f"  Attempting to fetch data for: {from_date} to {to_date}")
    print(f"  NOTE: This may fail if market is closed or date is in future")

    candle_data = connection.get_candle_data(
        exchange="NSE",
        symbol_token="99926000",  # NIFTY 50 (verify this token)
        interval="FIVE_MINUTE",
        from_date=from_date,
        to_date=to_date
    )

    if candle_data and candle_data.get('status'):
        data_points = len(candle_data.get('data', []))
        print(f"\n✓ TEST PASSED: Retrieved {data_points} Nifty candles")
        return True
    else:
        print("\n⚠ TEST WARNING: Could not retrieve Nifty data")
        print("  This is expected if market is closed or token is incorrect")
        print("  You'll need to verify the correct Nifty index token")
        return False


def run_all_tests():
    """Run all connection tests"""
    print("\n" + "#"*80)
    print("#" + " "*78 + "#")
    print("#" + " "*20 + "ANGELONE SMARTAPI CONNECTION TEST" + " "*25 + "#")
    print("#" + " "*78 + "#")
    print("#"*80 + "\n")

    # Test 1: Basic connection
    connection = test_basic_connection()

    # Test 2: Profile
    profile_ok = test_profile(connection)

    # Test 3: Historical candle data
    candle_ok = test_candle_data(connection)

    # Test 4: Nifty spot data (may fail if market closed)
    nifty_ok = test_nifty_spot_data(connection)

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Connection:      {'✓ PASS' if connection else '✗ FAIL'}")
    print(f"Profile:         {'✓ PASS' if profile_ok else '✗ FAIL'}")
    print(f"Candle Data:     {'✓ PASS' if candle_ok else '✗ FAIL'}")
    print(f"Nifty Data:      {'⚠ WARN' if not nifty_ok else '✓ PASS'}")
    print("="*80)

    # Logout
    if connection:
        print("\n")
        connection.logout()

    # Overall status
    critical_tests_passed = connection and profile_ok and candle_ok
    if critical_tests_passed:
        print("\n🎉 ALL CRITICAL TESTS PASSED! You're ready for paper trading.")
        print("\nNext steps:")
        print("1. Verify your API credentials are correct")
        print("2. Test during market hours for live data")
        print("3. Implement data feed for paper trading")
    else:
        print("\n⚠ SOME TESTS FAILED. Please check:")
        print("1. API credentials (api_key, username, password)")
        print("2. TOTP token is correct")
        print("3. Your AngelOne account has API access enabled")
        print("4. Network connection is stable")


if __name__ == "__main__":
    run_all_tests()
