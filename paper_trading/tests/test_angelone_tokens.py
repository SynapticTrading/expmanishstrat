#!/usr/bin/env python3
"""
Test what AngelOne uses for 5-min candles vs 1-min LTP
"""
import sys
import json
sys.path.insert(0, '/Users/Algo_Trading/manishsir_options')

from paper_trading.legacy.angelone_connection import AngelOneConnection
from datetime import datetime, timedelta

# Load credentials
creds = {}
with open("paper_trading/config/credentials_angelone.txt", 'r') as f:
    for line in f:
        line = line.strip()
        if line and '=' in line:
            key, value = line.split('=', 1)
            creds[key.strip()] = value.strip()

print("="*80)
print("TESTING: AngelOne - What's used for candles vs LTP?")
print("="*80)

# Connect
connection = AngelOneConnection(
    api_key=creds['api_key'],
    username=creds['username'],
    password=creds['password'],
    totp_token=creds['totp_token']
)
connection.connect()
smart_api = connection.smart_api
print("✓ Connected\n")

# Get token from cache
with open('contracts_cache.json', 'r') as f:
    cache = json.load(f)

# Get NIFTY 25200 PE 2026-01-27
contract = cache['options']['instruments']['2026-01-27']['25200']['PE']
token = contract['token']

print(f"Using contract: NIFTY 25200 PE 2026-01-27")
print(f"Token (exchange token): {token}")
print()

print("="*80)
print("TEST 1: get_candle_data() - What does it use?")
print("="*80)
print(f"Parameter: symbol_token={token}")

try:
    to_date = datetime.now()
    from_date = to_date - timedelta(minutes=15)

    result = connection.get_candle_data(
        exchange="NFO",
        symbol_token=token,  # Using token directly
        interval="FIVE_MINUTE",
        from_date=from_date.strftime("%Y-%m-%d %H:%M"),
        to_date=to_date.strftime("%Y-%m-%d %H:%M")
    )

    if result and result.get('status'):
        candles = result.get('data', [])
        print(f"✓ SUCCESS! Got {len(candles)} candles")
        if candles:
            last = candles[-1]
            print(f"   Last candle: open={last[1]}, close={last[4]}, volume={last[5]}")
    else:
        print(f"✗ FAILED: {result}")
except Exception as e:
    print(f"✗ EXCEPTION: {e}")

print("\n" + "="*80)
print("TEST 2: getMarketData() for LTP - What does it use?")
print("="*80)
print(f"Parameter: exchangeTokens={{'NFO': ['{token}']}}")

try:
    result = smart_api.getMarketData(
        mode="LTP",
        exchangeTokens={"NFO": [token]}  # Using token directly
    )

    if result and result.get('status'):
        fetched = result.get('data', {}).get('fetched', [])
        if fetched:
            print(f"✓ SUCCESS! LTP: {fetched[0].get('ltp')}")
        else:
            print(f"✗ FAILED - No data in response")
    else:
        print(f"✗ FAILED: {result}")
except Exception as e:
    print(f"✗ EXCEPTION: {e}")

print("\n" + "="*80)
print("TEST 3: getMarketData() for FULL quote - What does it use?")
print("="*80)
print(f"Parameter: exchangeTokens={{'NFO': ['{token}']}}")

try:
    result = smart_api.getMarketData(
        mode="FULL",
        exchangeTokens={"NFO": [token]}  # Using token directly
    )

    if result and result.get('status'):
        fetched = result.get('data', {}).get('fetched', [])
        if fetched:
            q = fetched[0]
            print(f"✓ SUCCESS!")
            print(f"   LTP: {q.get('ltp')}")
            print(f"   OI: {q.get('opnInterest')}")
            print(f"   Volume: {q.get('tradeVolume')}")
        else:
            print(f"✗ FAILED - No data in response")
    else:
        print(f"✗ FAILED: {result}")
except Exception as e:
    print(f"✗ EXCEPTION: {e}")

print("\n" + "="*80)
print("CONCLUSION")
print("="*80)
print("AngelOne uses TOKENS (exchange tokens) for:")
print("  ✓ Historical candle data (getCandleData)")
print("  ✓ LTP (getMarketData with mode=LTP)")
print("  ✓ Full quotes (getMarketData with mode=FULL)")
print()
print("Unlike Zerodha:")
print("  - Zerodha uses numeric instrument_token for candles")
print("  - Zerodha uses tradingsymbols for LTP/quotes")
print("="*80)
