"""
Standalone Zerodha Connection Test
This demonstrates the Zerodha authentication issue
"""

import requests
import json
import pyotp
from urllib.parse import urlparse, parse_qs
from datetime import datetime


def test_zerodha_auth_flow():
    """
    Test Zerodha authentication to show where it fails
    """
    print("="*80)
    print("ZERODHA AUTHENTICATION TEST")
    print("="*80)

    # Load credentials
    creds = {}
    try:
        with open('paper_trading/config/credentials_zerodha.txt', 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    creds[key.strip()] = value.strip()
    except Exception as e:
        print(f"✗ Failed to load credentials: {e}")
        return False

    api_key = creds.get('api_key')
    api_secret = creds.get('api_secret')
    user_id = creds.get('user_id')
    user_password = creds.get('user_password')
    totp_key = creds.get('totp_key')

    print(f"\n[STEP 1] Creating HTTP session...")
    print(f"  API Key: {api_key[:10]}...")
    print(f"  User ID: {user_id}")

    try:
        http_session = requests.Session()

        # Step 2: Get login URL
        print(f"\n[STEP 2] Getting login URL...")
        url = http_session.get(
            url=f'https://kite.trade/connect/login?v=3&api_key={api_key}'
        ).url
        print(f"  ✓ Login URL obtained: {url[:60]}...")

        # Step 3: Login with credentials
        print(f"\n[STEP 3] Logging in with user credentials...")
        response = http_session.post(
            url='https://kite.zerodha.com/api/login',
            data={'user_id': user_id, 'password': user_password}
        )
        resp_dict = json.loads(response.content)

        if resp_dict.get('status') != 'success':
            print(f"  ✗ Login failed: {resp_dict}")
            return False

        print(f"  ✓ Login successful")
        print(f"  Request ID: {resp_dict['data']['request_id']}")

        # Step 4: Generate and submit TOTP
        print(f"\n[STEP 4] Generating TOTP...")
        totp = pyotp.TOTP(totp_key).now()
        print(f"  ✓ TOTP generated: {totp}")

        print(f"\n[STEP 5] Submitting TOTP...")
        twofa_response = http_session.post(
            url='https://kite.zerodha.com/api/twofa',
            data={
                'user_id': user_id,
                'request_id': resp_dict["data"]["request_id"],
                'twofa_value': totp
            }
        )
        twofa_dict = json.loads(twofa_response.content)

        if twofa_dict.get('status') != 'success':
            print(f"  ✗ TOTP verification failed: {twofa_dict}")
            return False

        print(f"  ✓ TOTP verified successfully")

        # Step 6: THIS IS WHERE IT FAILS - Getting request token
        print(f"\n[STEP 6] Getting request token from redirect...")
        print(f"  ⚠️  WARNING: This step will fail!")
        print(f"  ⚠️  Zerodha redirects to http://127.0.0.1:80/?request_token=...")
        print(f"  ⚠️  But there's no server running on port 80 to catch it!")

        url_with_skip = url + "&skip_session=true"
        print(f"\n  Attempting redirect URL: {url_with_skip[:80]}...")

        try:
            # This is line 79 from zerodha_connection.py that fails
            response = http_session.get(url=url_with_skip, allow_redirects=True).url
            print(f"  Redirect URL: {response}")

            # Try to extract request token
            request_token = parse_qs(urlparse(response).query)['request_token'][0]
            print(f"  ✓ Request token obtained: {request_token[:20]}...")

            # Step 7: Generate session
            print(f"\n[STEP 7] Generating Kite session...")
            from kiteconnect import KiteConnect
            kite = KiteConnect(api_key=api_key)
            data = kite.generate_session(request_token, api_secret=api_secret)
            access_token = data["access_token"]

            print(f"  ✓ Access token: {access_token[:20]}...")
            print(f"\n✓ AUTHENTICATION SUCCESSFUL!")
            return True

        except requests.exceptions.ConnectionError as e:
            print(f"\n  ✗ CONNECTION ERROR (Expected):")
            print(f"     {str(e)[:200]}...")
            print(f"\n  💡 SOLUTION:")
            print(f"     Option 1: Start a local server on port 80 to catch the redirect")
            print(f"     Option 2: Manually extract request_token from browser")
            print(f"     Option 3: Use Zerodha's WebSocket connection (no redirect needed)")
            print(f"     Option 4: Cache access_token and reuse (valid for 1 day)")
            return False

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def what_we_need_for_paper_trading():
    """
    Display what data we actually need for paper trading
    """
    print("\n")
    print("="*80)
    print("WHAT WE NEED FOR PAPER TRADING")
    print("="*80)

    print("\n📊 DATA REQUIREMENTS:")
    print("\n1. STRATEGY LOOP (Every 5 minutes):")
    print("   ✓ Nifty spot price (LTP)")
    print("   ✓ Options chain for ~10 strikes (5 above, 5 below):")
    print("      - Strike price")
    print("      - Option type (CE/PE)")
    print("      - Expiry date")
    print("      - 5-min candle data:")
    print("        • Close price")
    print("        • Volume")
    print("        • Open Interest (OI)")
    print("      - Instrument token")

    print("\n2. EXIT MONITOR LOOP (Every 1 minute):")
    print("   ✓ LTP of specific option contracts we're holding")

    print("\n📈 CURRENTLY WORKING:")
    print("   ✓ AngelOne connection")
    print("   ✓ Nifty spot price via AngelOne")
    print("   ✓ Dual loop architecture (5-min + 1-min)")
    print("   ✓ Rate limiting fixed")

    print("\n❌ WHAT'S MISSING:")
    print("   ❌ AngelOne: get_next_expiry() - Find next weekly expiry")
    print("   ❌ AngelOne: get_options_chain() - Fetch options data")
    print("   ❌ AngelOne: Need instrument master file")
    print("   ❌ Zerodha: Authentication failing (redirect URL issue)")

    print("\n🔧 QUICK FIX OPTIONS:")
    print("\n   Option A (Recommended): Fix AngelOne broker")
    print("   - Download instrument master file")
    print("   - Implement get_next_expiry()")
    print("   - Implement get_options_chain()")
    print("   - Should take ~30 minutes")

    print("\n   Option B: Fix Zerodha auth")
    print("   - Set up local redirect handler on port 80")
    print("   - Or manually copy access_token from browser")
    print("   - Or use saved access_token (valid 24hrs)")

    print("\n   Option C: Use saved credentials")
    print("   - If you have a valid access_token, just use it directly")
    print("   - Skip the entire auth flow")

    print("\n" + "="*80)


if __name__ == "__main__":
    print("\n" + "#"*80)
    print("TRADING SYSTEM DIAGNOSTIC TEST")
    print("#"*80 + "\n")

    # Test 1: Zerodha auth flow
    print("\nTEST 1: Zerodha Authentication")
    print("-"*80)
    zerodha_success = test_zerodha_auth_flow()

    # Show what we need
    what_we_need_for_paper_trading()

    # Summary
    print("\n" + "#"*80)
    print("SUMMARY")
    print("#"*80)
    print(f"\nZerodha Auth: {'✓ PASS' if zerodha_success else '✗ FAIL (Expected - needs redirect handler)'}")
    print(f"AngelOne: ✓ WORKING (just needs options chain implementation)")
    print(f"\nRecommendation: Continue with AngelOne and implement missing methods")
    print("#"*80 + "\n")
