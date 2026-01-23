#!/usr/bin/env python3
"""
Compare candle data between AngelOne and Zerodha for the same option
"""
import sys
import json
sys.path.insert(0, '/Users/Algo_Trading/manishsir_options')

from paper_trading.legacy.angelone_connection import AngelOneConnection
from paper_trading.legacy.zerodha_connection import ZerodhaConnection
from datetime import datetime, timedelta

# Load credentials
angelone_creds = {}
with open("paper_trading/config/credentials_angelone.txt", 'r') as f:
    for line in f:
        line = line.strip()
        if line and '=' in line:
            key, value = line.split('=', 1)
            angelone_creds[key.strip()] = value.strip()

zerodha_creds = {}
with open("paper_trading/config/credentials_zerodha.txt", 'r') as f:
    for line in f:
        line = line.strip()
        if line and '=' in line:
            key, value = line.split('=', 1)
            zerodha_creds[key.strip()] = value.strip()

print("="*80)
print("CANDLE COMPARISON: AngelOne vs Zerodha")
print("Option: NIFTY 25200 PE 2026-01-27")
print("="*80)

# Get token from cache
with open('contracts_cache.json', 'r') as f:
    cache = json.load(f)

angelone_token = cache['options']['instruments']['2026-01-27']['25200']['PE']['token']
zerodha_token = cache['options']['instruments']['2026-01-27']['25200']['PE']['zerodha_instrument_token']

print(f"\nTokens:")
print(f"  AngelOne exchange token: {angelone_token}")
print(f"  Zerodha instrument token: {zerodha_token}")
print()

# Connect to AngelOne
print("Connecting to AngelOne...")
angelone_conn = AngelOneConnection(
    api_key=angelone_creds['api_key'],
    username=angelone_creds['username'],
    password=angelone_creds['password'],
    totp_token=angelone_creds['totp_token']
)
angelone_conn.connect()
print("✓ AngelOne connected")

# Connect to Zerodha
print("\nConnecting to Zerodha...")
zerodha_conn = ZerodhaConnection(
    api_key=zerodha_creds['api_key'],
    api_secret=zerodha_creds['api_secret'],
    user_id=zerodha_creds['user_id'],
    user_password=zerodha_creds['user_password'],
    totp_key=zerodha_creds['totp_key']
)
zerodha_conn.connect()
print("✓ Zerodha connected")

# Fetch candles
to_date = datetime.now()
from_date = to_date - timedelta(minutes=15)

print("\n" + "="*80)
print("ANGELONE CANDLES")
print("="*80)
print(f"Fetching from {from_date.strftime('%Y-%m-%d %H:%M')} to {to_date.strftime('%Y-%m-%d %H:%M')}")

angelone_response = angelone_conn.get_candle_data(
    exchange="NFO",
    symbol_token=angelone_token,
    interval="FIVE_MINUTE",
    from_date=from_date.strftime("%Y-%m-%d %H:%M"),
    to_date=to_date.strftime("%Y-%m-%d %H:%M")
)

if angelone_response and angelone_response.get('status'):
    candles = angelone_response.get('data', [])
    print(f"Got {len(candles)} candles:\n")
    for i, candle in enumerate(candles):
        # AngelOne format: [timestamp, O, H, L, C, V]
        timestamp = candle[0]
        print(f"  Candle {i+1}: {timestamp} | O={candle[1]:.2f}, H={candle[2]:.2f}, L={candle[3]:.2f}, C={candle[4]:.2f}, V={candle[5]}")

    # Which one is used?
    selected_index = -2 if len(candles) >= 2 else -1
    selected = candles[selected_index]
    print(f"\n✓ SELECTED (index {selected_index}): {selected[0]} | Close={selected[4]:.2f}")

print("\n" + "="*80)
print("ZERODHA CANDLES")
print("="*80)
print(f"Fetching from {from_date} to {to_date}")

zerodha_data = zerodha_conn.get_historical_data(
    instrument_token=int(zerodha_token),
    from_date=from_date,
    to_date=to_date,
    interval="5minute"
)

if zerodha_data is not None and not zerodha_data.empty:
    print(f"Got {len(zerodha_data)} candles:\n")
    for i, row in zerodha_data.iterrows():
        print(f"  Candle {i+1}: {row['date']} | O={row['open']:.2f}, H={row['high']:.2f}, L={row['low']:.2f}, C={row['close']:.2f}, V={row['volume']}")

    # Which one is used?
    selected_index = -2 if len(zerodha_data) >= 2 else -1
    selected = zerodha_data.iloc[selected_index]
    print(f"\n✓ SELECTED (index {selected_index}): {selected['date']} | Close={selected['close']:.2f}")

print("\n" + "="*80)
print("ANALYSIS")
print("="*80)
