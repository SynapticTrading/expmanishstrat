#!/usr/bin/env python3
"""
Test what the historical_data API actually accepts
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

print("="*80)
print("TESTING: What does kite.historical_data() accept?")
print("="*80)

# Connect
connection = ZerodhaConnection(
    api_key=creds['api_key'],
    api_secret=creds['api_secret'],
    user_id=creds['user_id'],
    user_password=creds['user_password'],
    totp_key=creds['totp_key']
)
kite = connection.connect()
print("✓ Connected\n")

# Get instrument details
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

print(f"Instrument Details:")
print(f"  TradingSymbol: {target['tradingsymbol']}")
print(f"  Instrument Token: {target['instrument_token']}")
print(f"  Exchange Token: {target['exchange_token']}")
print()

instrument_token = target['instrument_token']
exchange_token = target['exchange_token']
tradingsymbol = target['tradingsymbol']

to_date = datetime.now()
from_date = to_date - timedelta(minutes=15)

print("="*80)
print("TEST 1: kite.historical_data() with NUMERIC instrument_token")
print("="*80)
print(f"Parameter: instrument_token={instrument_token} (numeric)")

try:
    data = kite.historical_data(
        instrument_token=instrument_token,  # Numeric: 15024642
        from_date=from_date,
        to_date=to_date,
        interval="5minute"
    )

    if data and len(data) > 0:
        print(f"✓ SUCCESS! Got {len(data)} candles")
        print(f"   Last candle: open={data[-1]['open']}, close={data[-1]['close']}, volume={data[-1]['volume']}")
    else:
        print(f"✗ FAILED - No data returned")
except Exception as e:
    print(f"✗ EXCEPTION: {e}")

print("\n" + "="*80)
print("TEST 2: kite.historical_data() with exchange_token")
print("="*80)
print(f"Parameter: instrument_token={exchange_token} (exchange token)")

try:
    data = kite.historical_data(
        instrument_token=exchange_token,  # Exchange token: 58690
        from_date=from_date,
        to_date=to_date,
        interval="5minute"
    )

    if data and len(data) > 0:
        print(f"✓ SUCCESS! Got {len(data)} candles")
    else:
        print(f"✗ FAILED - No data returned")
except Exception as e:
    print(f"✗ EXCEPTION: {e}")

print("\n" + "="*80)
print("TEST 3: kite.historical_data() with tradingsymbol")
print("="*80)
print(f"Parameter: instrument_token='{tradingsymbol}' (tradingsymbol)")

try:
    data = kite.historical_data(
        instrument_token=tradingsymbol,  # Symbol: "NIFTY26JAN25200PE"
        from_date=from_date,
        to_date=to_date,
        interval="5minute"
    )

    if data and len(data) > 0:
        print(f"✓ SUCCESS! Got {len(data)} candles")
    else:
        print(f"✗ FAILED - No data returned")
except Exception as e:
    print(f"✗ EXCEPTION: {e}")

print("\n" + "="*80)
print("CONCLUSION")
print("="*80)
