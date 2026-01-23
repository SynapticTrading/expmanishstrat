#!/usr/bin/env python3
"""
Comprehensive test: Can we use tokens for LTP and historical data?
"""
import sys
sys.path.insert(0, '/Users/Algo_Trading/manishsir_options')

from paper_trading.legacy.zerodha_connection import ZerodhaConnection
from datetime import datetime, timedelta

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
print("COMPREHENSIVE TOKEN TEST")
print("="*80)
print("\nConnecting...")
connection = ZerodhaConnection(
    api_key=creds['api_key'],
    api_secret=creds['api_secret'],
    user_id=creds['user_id'],
    user_password=creds['user_password'],
    totp_key=creds['totp_key']
)
kite = connection.connect()
print("✓ Connected\n")

# Get instrument info
instruments = kite.instruments("NFO")
target = None
for inst in instruments:
    if (inst['name'] == 'NIFTY' and
        inst['strike'] == 25200 and
        inst['instrument_type'] == 'PE' and
        inst['expiry'].strftime('%Y-%m-%d') == '2026-01-27'):
        target = inst
        break

if not target:
    print("✗ Instrument not found!")
    sys.exit(1)

print(f"Found instrument:")
print(f"  TradingSymbol: {target['tradingsymbol']}")
print(f"  Instrument Token: {target['instrument_token']}")
print(f"  Exchange Token: {target['exchange_token']}")
print()

instrument_token = target['instrument_token']
exchange_token = target['exchange_token']
tradingsymbol = target['tradingsymbol']

print("="*80)
print("TEST 1: Historical Data (5-min candles)")
print("="*80)

# Test historical with instrument_token (numeric)
print(f"\n1a. Using NUMERIC instrument_token ({instrument_token}):")
try:
    to_date = datetime.now()
    from_date = to_date - timedelta(minutes=15)

    df = connection.get_historical_data(
        instrument_token=instrument_token,
        from_date=from_date,
        to_date=to_date,
        interval="5minute"
    )

    if df is not None and not df.empty:
        print(f"   ✓ SUCCESS! Got {len(df)} candles")
        print(f"   Last candle: {df.iloc[-1][['open', 'high', 'low', 'close', 'volume']].to_dict()}")
    else:
        print(f"   ✗ FAILED - No data returned")
except Exception as e:
    print(f"   ✗ EXCEPTION: {e}")

# Test historical with exchange_token (numeric)
print(f"\n1b. Using exchange_token ({exchange_token}):")
try:
    df = connection.get_historical_data(
        instrument_token=exchange_token,
        from_date=from_date,
        to_date=to_date,
        interval="5minute"
    )

    if df is not None and not df.empty:
        print(f"   ✓ SUCCESS! Got {len(df)} candles")
    else:
        print(f"   ✗ FAILED - No data returned")
except Exception as e:
    print(f"   ✗ EXCEPTION: {e}")

print("\n" + "="*80)
print("TEST 2: LTP Methods")
print("="*80)

# Test ltp() with instrument_token
print(f"\n2a. kite.ltp() with NFO:{instrument_token}:")
try:
    key = f"NFO:{instrument_token}"
    result = kite.ltp([key])
    if result and key in result:
        print(f"   ✓ SUCCESS! LTP: {result[key]['last_price']}")
    else:
        print(f"   ✗ FAILED - Key not in response: {list(result.keys())}")
except Exception as e:
    print(f"   ✗ EXCEPTION: {e}")

# Test ltp() with exchange_token
print(f"\n2b. kite.ltp() with NFO:{exchange_token}:")
try:
    key = f"NFO:{exchange_token}"
    result = kite.ltp([key])
    if result and key in result:
        print(f"   ✓ SUCCESS! LTP: {result[key]['last_price']}")
    else:
        print(f"   ✗ FAILED - Key not in response: {list(result.keys())}")
except Exception as e:
    print(f"   ✗ EXCEPTION: {e}")

# Test ltp() with tradingsymbol (we know this works)
print(f"\n2c. kite.ltp() with NFO:{tradingsymbol}:")
try:
    key = f"NFO:{tradingsymbol}"
    result = kite.ltp([key])
    if result and key in result:
        print(f"   ✓ SUCCESS! LTP: {result[key]['last_price']}")
    else:
        print(f"   ✗ FAILED")
except Exception as e:
    print(f"   ✗ EXCEPTION: {e}")

print("\n" + "="*80)
print("TEST 3: Quote Methods")
print("="*80)

# Test quote() with instrument_token
print(f"\n3a. kite.quote() with NFO:{instrument_token}:")
try:
    key = f"NFO:{instrument_token}"
    result = kite.quote([key])
    if result and key in result:
        print(f"   ✓ SUCCESS! LTP: {result[key]['last_price']}, OI: {result[key].get('oi', 'N/A')}")
    else:
        print(f"   ✗ FAILED - Key not in response: {list(result.keys())}")
except Exception as e:
    print(f"   ✗ EXCEPTION: {e}")

# Test quote() with exchange_token
print(f"\n3b. kite.quote() with NFO:{exchange_token}:")
try:
    key = f"NFO:{exchange_token}"
    result = kite.quote([key])
    if result and key in result:
        print(f"   ✓ SUCCESS! LTP: {result[key]['last_price']}, OI: {result[key].get('oi', 'N/A')}")
    else:
        print(f"   ✗ FAILED - Key not in response: {list(result.keys())}")
except Exception as e:
    print(f"   ✗ EXCEPTION: {e}")

# Test quote() with tradingsymbol
print(f"\n3c. kite.quote() with NFO:{tradingsymbol}:")
try:
    key = f"NFO:{tradingsymbol}"
    result = kite.quote([key])
    if result and key in result:
        print(f"   ✓ SUCCESS! LTP: {result[key]['last_price']}, OI: {result[key].get('oi', 'N/A')}")
    else:
        print(f"   ✗ FAILED")
except Exception as e:
    print(f"   ✗ EXCEPTION: {e}")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print("Historical Data API: Uses NUMERIC instrument_token ✓")
print("LTP/Quote APIs: ???")
print("="*80)
