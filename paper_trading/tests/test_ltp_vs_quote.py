#!/usr/bin/env python3
"""
Test if both ltp() and quote() work with instrument tokens
"""
import sys
sys.path.insert(0, '/Users/Algo_Trading/manishsir_options')

from paper_trading.legacy.zerodha_connection import ZerodhaConnection

# Load credentials
creds = {}
with open("paper_trading/config/credentials_zerodha.txt", 'r') as f:
    for line in f:
        line = line.strip()
        if line and '=' in line:
            key, value = line.split('=', 1)
            creds[key.strip()] = value.strip()

# Connect
print("="*80)
print("TESTING: kite.ltp() vs kite.quote() with TOKENS")
print("="*80)
print("\nConnecting to Zerodha...")
connection = ZerodhaConnection(
    api_key=creds['api_key'],
    api_secret=creds['api_secret'],
    user_id=creds['user_id'],
    user_password=creds['user_password'],
    totp_key=creds['totp_key']
)
kite = connection.connect()
print("✓ Connected\n")

# Token for NIFTY 25200 PE 2026-01-27
instrument_token = "15024642"
key_token = f"NFO:{instrument_token}"

print("="*80)
print(f"TEST 1: kite.ltp() with TOKEN")
print("="*80)
print(f"Key: {key_token}")
try:
    ltp_response = kite.ltp([key_token])
    print(f"Response type: {type(ltp_response)}")
    print(f"Response: {ltp_response}")

    if ltp_response and key_token in ltp_response:
        print(f"✓ SUCCESS!")
        print(f"  LTP: {ltp_response[key_token]['last_price']}")
    else:
        print(f"✗ FAILED - Key not in response")
        print(f"  Available keys: {list(ltp_response.keys()) if ltp_response else 'None'}")
except Exception as e:
    print(f"✗ EXCEPTION: {e}")

print("\n" + "="*80)
print(f"TEST 2: kite.quote() with TOKEN")
print("="*80)
print(f"Key: {key_token}")
try:
    quote_response = kite.quote([key_token])
    print(f"Response type: {type(quote_response)}")
    print(f"Response: {quote_response}")

    if quote_response and key_token in quote_response:
        print(f"✓ SUCCESS!")
        print(f"  LTP: {quote_response[key_token]['last_price']}")
        print(f"  OI: {quote_response[key_token].get('oi', 'N/A')}")
    else:
        print(f"✗ FAILED - Key not in response")
        print(f"  Available keys: {list(quote_response.keys()) if quote_response else 'None'}")
except Exception as e:
    print(f"✗ EXCEPTION: {e}")

# Now test with tradingsymbol
print("\n" + "="*80)
print(f"TEST 3: kite.quote() with TRADINGSYMBOL")
print("="*80)

# Get tradingsymbol
instruments = kite.instruments("NFO")
target = None
for inst in instruments:
    if inst['instrument_token'] == int(instrument_token):
        target = inst
        break

if target:
    symbol = target['tradingsymbol']
    key_symbol = f"NFO:{symbol}"
    print(f"Key: {key_symbol}")

    try:
        quote_response = kite.quote([key_symbol])
        print(f"Response type: {type(quote_response)}")

        if quote_response and key_symbol in quote_response:
            print(f"✓ SUCCESS!")
            print(f"  LTP: {quote_response[key_symbol]['last_price']}")
            print(f"  OI: {quote_response[key_symbol].get('oi', 'N/A')}")
        else:
            print(f"✗ FAILED - Key not in response")
    except Exception as e:
        print(f"✗ EXCEPTION: {e}")
else:
    print("✗ Could not find instrument")

print("\n" + "="*80)
print("CONCLUSION")
print("="*80)
