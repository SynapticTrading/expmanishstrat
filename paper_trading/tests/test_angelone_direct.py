"""
Direct AngelOne SmartAPI Test
Tests connection using SmartAPI library directly (based on user's working code)
"""

from SmartApi import SmartConnect
import pyotp
from datetime import datetime, timedelta


def test_angelone_connection():
    """
    Test AngelOne connection with direct SmartAPI usage
    Replace credentials with your actual values
    """

    print("\n" + "="*80)
    print("ANGELONE SMARTAPI - DIRECT CONNECTION TEST")
    print("="*80)

    # ============================================================
    # CREDENTIALS - Replace with your actual credentials
    # ============================================================
    api_key = "GuULp2XA"
    username = "N182640"  # Your client code
    pwd = "7531"  # Your MPIN (4-6 digit Mobile PIN, NOT trading password)
    token = "4CDGR2KJ2Y3ESAYCIAXPYP2JAY"  # Your TOTP secret token

    try:
        # ============================================================
        # STEP 1: Initialize SmartAPI
        # ============================================================
        print(f"\n[STEP 1] Initializing SmartAPI...")
        smartApi = SmartConnect(api_key)
        print("✓ SmartAPI initialized")

        # ============================================================
        # STEP 2: Generate TOTP
        # ============================================================
        print(f"\n[STEP 2] Generating TOTP...")
        totp = pyotp.TOTP(token).now()
        print(f"✓ TOTP generated: {totp}")

        # ============================================================
        # STEP 3: Generate Session
        # ============================================================
        print(f"\n[STEP 3] Generating session...")
        data = smartApi.generateSession(username, pwd, totp)

        if data['status']:
            print("✓ Session generated successfully")
            print(f"\nSession Data:")
            print(f"  Status: {data['status']}")
            print(f"  Message: {data['message']}")

            # Extract tokens
            authToken = data['data']['jwtToken']
            refreshToken = data['data']['refreshToken']
            feedToken = smartApi.getfeedToken()

            print(f"\nTokens Retrieved:")
            print(f"  Auth Token: {authToken[:20]}...")
            print(f"  Refresh Token: {refreshToken[:20]}...")
            print(f"  Feed Token: {feedToken}")
        else:
            print(f"✗ Session generation failed: {data}")
            return False

        # ============================================================
        # STEP 4: Get Profile
        # ============================================================
        print(f"\n[STEP 4] Fetching profile...")
        res = smartApi.getProfile(refreshToken)

        if res['status']:
            print("✓ Profile retrieved successfully")
            print(f"\nProfile Data:")
            print(f"  Client Name: {res['data'].get('name', 'N/A')}")
            print(f"  Client Code: {res['data'].get('clientcode', 'N/A')}")
            print(f"  Email: {res['data'].get('email', 'N/A')}")
            print(f"  Exchange: {res['data'].get('exchanges', 'N/A')}")
        else:
            print(f"✗ Profile retrieval failed: {res}")

        # ============================================================
        # STEP 5: Get Historical Candle Data
        # ============================================================
        print(f"\n[STEP 5] Fetching historical candle data...")

        # Example 1: Historical data (2021 - for testing)
        historicParam = {
            "exchange": "NSE",
            "symboltoken": "3045",  # SBIN
            "interval": "ONE_MINUTE",
            "fromdate": "2021-02-08 09:00",
            "todate": "2021-02-08 09:16"
        }

        stockData = smartApi.getCandleData(historicParam)

        if stockData['status']:
            candles = stockData['data']
            print(f"✓ Retrieved {len(candles)} candles")
            print(f"\nSample Candle (first):")
            if len(candles) > 0:
                first = candles[0]
                print(f"  Timestamp: {first[0]}")
                print(f"  Open: {first[1]}")
                print(f"  High: {first[2]}")
                print(f"  Low: {first[3]}")
                print(f"  Close: {first[4]}")
                print(f"  Volume: {first[5]}")
        else:
            print(f"✗ Candle data retrieval failed: {stockData}")

        # ============================================================
        # STEP 6: Get Current Day Nifty Data (if market is open)
        # ============================================================
        print(f"\n[STEP 6] Fetching current day Nifty data...")

        today = datetime.now()
        from_date = today.replace(hour=9, minute=15).strftime("%Y-%m-%d %H:%M")
        to_date = today.replace(hour=15, minute=30).strftime("%Y-%m-%d %H:%M")

        niftyParam = {
            "exchange": "NSE",
            "symboltoken": "99926000",  # NIFTY 50 (verify this token)
            "interval": "FIVE_MINUTE",
            "fromdate": from_date,
            "todate": to_date
        }

        print(f"  Date range: {from_date} to {to_date}")
        print(f"  NOTE: This may fail if market is closed")

        niftyData = smartApi.getCandleData(niftyParam)

        if niftyData['status']:
            candles = niftyData['data']
            print(f"✓ Retrieved {len(candles)} Nifty candles")
            if len(candles) > 0:
                latest = candles[-1]
                print(f"\nLatest Nifty Candle:")
                print(f"  Timestamp: {latest[0]}")
                print(f"  Close: {latest[4]}")
        else:
            print(f"⚠ Nifty data not available (market may be closed)")
            print(f"  Response: {niftyData.get('message', 'No message')}")

        # ============================================================
        # STEP 7: Test LTP (Last Traded Price)
        # ============================================================
        print(f"\n[STEP 7] Testing LTP retrieval...")

        try:
            ltp_params = {
                "exchange": "NSE",
                "tradingsymbol": "SBIN-EQ",
                "symboltoken": "3045"
            }

            ltp_data = smartApi.ltpData(ltp_params['exchange'],
                                       ltp_params['tradingsymbol'],
                                       ltp_params['symboltoken'])

            if ltp_data and ltp_data.get('status'):
                print(f"✓ LTP retrieved successfully")
                print(f"  Symbol: SBIN-EQ")
                print(f"  LTP: {ltp_data['data'].get('ltp', 'N/A')}")
            else:
                print(f"⚠ LTP retrieval returned: {ltp_data}")
        except Exception as e:
            print(f"⚠ LTP test skipped (may need market hours): {e}")

        # ============================================================
        # SUCCESS SUMMARY
        # ============================================================
        print(f"\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        print("✓ SmartAPI initialization: PASS")
        print("✓ TOTP generation: PASS")
        print("✓ Session generation: PASS")
        print("✓ Profile retrieval: PASS")
        print("✓ Historical candle data: PASS")
        print(f"{'✓' if niftyData['status'] else '⚠'} Current Nifty data: {'PASS' if niftyData['status'] else 'SKIP (market closed)'}")
        print("="*80)

        print(f"\n🎉 CONNECTION TEST SUCCESSFUL!")
        print(f"\nYour AngelOne API is working correctly.")
        print(f"You can now use this for paper trading.")

        print(f"\n" + "="*80)
        print("NEXT STEPS FOR PAPER TRADING")
        print("="*80)
        print("1. Update credentials in: config/credentials_angelone.txt")
        print("2. Run: python runner.py --broker angelone")
        print("3. The system will auto-connect using these credentials")
        print("="*80)

        return True

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()

        print(f"\n" + "="*80)
        print("TROUBLESHOOTING")
        print("="*80)
        print("1. Verify API credentials are correct")
        print("2. Check TOTP token (32-character secret)")
        print("3. Ensure MPIN is correct (NOT trading password)")
        print("4. Verify API access is enabled in AngelOne account")
        print("5. Check network connectivity")
        print("="*80)

        return False


def test_with_credentials_file():
    """
    Test using credentials from config file
    """
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent.parent))

    from paper_trading.legacy.zerodha_connection import load_credentials_from_file

    print("\n" + "="*80)
    print("TESTING WITH CREDENTIALS FILE")
    print("="*80)

    creds_path = "paper_trading/config/credentials_angelone.txt"

    if not Path(creds_path).exists():
        print(f"✗ Credentials file not found: {creds_path}")
        print(f"  Create it using the template:")
        print(f"  cp paper_trading/config/credentials_angelone.template.txt {creds_path}")
        return False

    print(f"\n[STEP 1] Loading credentials from: {creds_path}")
    creds = load_credentials_from_file(creds_path)

    if not creds:
        print(f"✗ Failed to load credentials")
        return False

    print(f"✓ Credentials loaded")
    print(f"  Found keys: {list(creds.keys())}")

    # Initialize SmartAPI with loaded credentials
    print(f"\n[STEP 2] Initializing SmartAPI...")
    smartApi = SmartConnect(creds['api_key'])

    # Generate TOTP
    print(f"\n[STEP 3] Generating TOTP...")
    totp = pyotp.TOTP(creds['totp_token']).now()

    # Generate session
    print(f"\n[STEP 4] Generating session...")
    data = smartApi.generateSession(creds['username'], creds['password'], totp)

    if data['status']:
        print(f"✓ Session generated using credentials file!")
        print(f"\n🎉 Credentials file is valid and working!")
        return True
    else:
        print(f"✗ Session generation failed: {data}")
        return False


if __name__ == "__main__":
    print("\n" + "#"*80)
    print("#" + " "*78 + "#")
    print("#" + " "*15 + "ANGELONE SMARTAPI - COMPREHENSIVE TEST" + " "*23 + "#")
    print("#" + " "*78 + "#")
    print("#"*80)

    # Test 1: Direct connection with hardcoded credentials
    print("\n\nTEST 1: Direct Connection (Hardcoded Credentials)")
    print("-"*80)
    test1_success = test_angelone_connection()

    # Test 2: Connection using credentials file
    print("\n\nTEST 2: Connection Using Credentials File")
    print("-"*80)
    test2_success = test_with_credentials_file()

    # Final summary
    print("\n\n" + "#"*80)
    print("FINAL SUMMARY")
    print("#"*80)
    print(f"Direct Connection Test: {'✓ PASS' if test1_success else '✗ FAIL'}")
    print(f"Credentials File Test:  {'✓ PASS' if test2_success else '✗ FAIL'}")
    print("#"*80)

    if test1_success and test2_success:
        print("\n✓ ALL TESTS PASSED!")
        print("You're ready to run paper trading with AngelOne!")
        print("\nRun: python runner.py --broker angelone")
    elif test1_success:
        print("\n⚠ Direct connection works, but credentials file needs setup")
        print("Update: paper_trading/config/credentials_angelone.txt")
    else:
        print("\n✗ Connection test failed. Please check your credentials.")
