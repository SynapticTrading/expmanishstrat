#!/usr/bin/env python3
"""
Direct test of Zerodha quote API to debug the issue
"""
import sys
sys.path.insert(0, '/Users/Algo_Trading/manishsir_options')

# Connect to Zerodha
from paper_trading.legacy.zerodha_connection import ZerodhaConnection

# Load credentials
def load_credentials():
    creds_file = "paper_trading/config/credentials_zerodha.txt"
    credentials = {}
    with open(creds_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and '=' in line:
                key, value = line.split('=', 1)
                credentials[key.strip()] = value.strip()
    return credentials

print("=" * 80)
print("ZERODHA QUOTE API DIRECT TEST")
print("=" * 80)

# Load credentials
creds = load_credentials()
print(f"\n1. Loaded credentials for user: {creds['user_id']}")

# Connect
print("\n2. Connecting to Zerodha...")
connection = ZerodhaConnection(
    api_key=creds['api_key'],
    api_secret=creds['api_secret'],
    user_id=creds['user_id'],
    user_password=creds['user_password'],
    totp_key=creds['totp_key']
)
kite = connection.connect()
if not kite:
    print("ERROR: Could not connect!")
    sys.exit(1)

print("   ✓ Connected successfully")

# Test 1: Nifty spot (this should work)
print("\n3. Testing Nifty 50 spot quote...")
try:
    spot_quote = kite.quote(["NSE:NIFTY 50"])
    print(f"   ✓ Spot quote works!")
    print(f"   LTP: {spot_quote['NSE:NIFTY 50']['last_price']}")
except Exception as e:
    print(f"   ✗ Spot quote failed: {e}")

# Test 2: Option using instrument_token
print("\n4. Testing option quote using instrument_token...")
token = "15024642"  # NIFTY 25200 PE 2026-01-27
key = f"NFO:{token}"
print(f"   Token: {token}")
print(f"   Key: {key}")

try:
    option_quote = kite.quote([key])
    print(f"   API Response Type: {type(option_quote)}")
    print(f"   API Response: {option_quote}")

    if option_quote and isinstance(option_quote, dict):
        if key in option_quote:
            print(f"   ✓ Option quote works!")
            print(f"   LTP: {option_quote[key]['last_price']}")
            print(f"   OI: {option_quote[key].get('oi', 'N/A')}")
        else:
            print(f"   ✗ Key {key} not in response")
            print(f"   Available keys: {list(option_quote.keys())}")
    else:
        print(f"   ✗ Invalid response (not a dict or empty)")

except Exception as e:
    print(f"   ✗ Option quote failed: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Try with tradingsymbol instead
print("\n5. Testing option quote using tradingsymbol...")
symbol = "NIFTY26127P25200"  # NIFTY Jan 27, 2026, PUT, 25200
key2 = f"NFO:{symbol}"
print(f"   Symbol: {symbol}")
print(f"   Key: {key2}")

try:
    option_quote2 = kite.quote([key2])
    print(f"   API Response Type: {type(option_quote2)}")

    if option_quote2 and isinstance(option_quote2, dict):
        if key2 in option_quote2:
            print(f"   ✓ Option quote works!")
            print(f"   LTP: {option_quote2[key2]['last_price']}")
        else:
            print(f"   ✗ Key {key2} not in response")
            print(f"   Available keys: {list(option_quote2.keys())}")
    else:
        print(f"   ✗ Invalid response")

except Exception as e:
    print(f"   ✗ Option quote failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
