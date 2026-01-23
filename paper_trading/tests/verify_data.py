#!/usr/bin/env python3
"""
Data Verification Script
Fetches live data from Zerodha to verify what the trading system is receiving
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from datetime import datetime, timedelta
from paper_trading.legacy.zerodha_connection import ZerodhaConnection
from paper_trading.legacy.zerodha_data_feed import ZerodhaDataFeed
import json

def load_credentials():
    """Load Zerodha credentials"""
    cred_file = Path(__file__).parent / 'paper_trading' / 'config' / 'credentials_zerodha.txt'

    with open(cred_file, 'r') as f:
        lines = f.readlines()

    creds = {}
    for line in lines:
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            key, value = line.split('=', 1)
            creds[key.strip()] = value.strip()

    return creds

def main():
    print("="*80)
    print("DATA VERIFICATION - Zerodha Live Feed")
    print("="*80)
    print(f"Timestamp: {datetime.now()}")
    print()

    # Connect to Zerodha
    print("Connecting to Zerodha...")
    creds = load_credentials()

    connection = ZerodhaConnection(
        api_key=creds.get('api_key'),
        api_secret=creds.get('api_secret'),
        user_id=creds.get('user_id'),
        user_password=creds.get('user_password'),
        totp_key=creds.get('totp_key')
    )

    kite = connection.connect()
    if not kite:
        print("Failed to connect to Zerodha")
        return

    print("✓ Connected to Zerodha\n")

    # Create data feed
    data_feed = ZerodhaDataFeed(connection)
    data_feed.load_instruments()

    # Load contract cache to get the exact option we're tracking
    with open('contracts_cache.json', 'r') as f:
        cache = json.load(f)

    # Get PUT 25250 expiry 2026-01-27
    put_25250 = cache['options']['instruments']['2026-01-27']['25250']['PE']
    zerodha_token = put_25250['zerodha_instrument_token']

    print("Target Option: NIFTY PUT 25250 (Expiry: 2026-01-27)")
    print(f"Zerodha Instrument Token: {zerodha_token}")
    print()

    # Get spot price
    spot = data_feed.get_spot_price()
    print(f"NIFTY Spot: {spot:.2f}")
    print()

    # Fetch 5-minute candle
    print("-"*80)
    print("FETCHING 5-MINUTE CANDLE DATA")
    print("-"*80)

    candle = data_feed.get_5min_candle(zerodha_token)

    if candle:
        print(f"✓ Candle retrieved successfully\n")
        print(f"Timestamp: {candle['timestamp']}")
        print(f"Open:      ₹{candle['open']:.2f}")
        print(f"High:      ₹{candle['high']:.2f}")
        print(f"Low:       ₹{candle['low']:.2f}")
        print(f"Close:     ₹{candle['close']:.2f}")
        print(f"Volume:    {candle['volume']:,}")
    else:
        print("✗ Failed to fetch candle data")

    print()

    # Fetch quote (for OI)
    print("-"*80)
    print("FETCHING QUOTE DATA (OI)")
    print("-"*80)

    # Get the trading symbol - search by strike, type, and expiry
    nfo_instruments = data_feed.nfo_instruments

    # Find NIFTY 25250 PE expiry 2026-01-27
    from datetime import date
    expiry_date = date(2026, 1, 27)

    option_rows = nfo_instruments[
        (nfo_instruments['name'] == 'NIFTY') &
        (nfo_instruments['strike'] == 25250) &
        (nfo_instruments['instrument_type'] == 'PE') &
        (nfo_instruments['expiry'] == expiry_date)
    ]

    if option_rows.empty:
        print(f"✗ Could not find NIFTY 25250 PE expiry 2026-01-27")
        print("Cannot fetch quote")
        trading_symbol = None
        quote_key = None
    else:
        option_row = option_rows.iloc[0]
        trading_symbol = option_row['tradingsymbol']
        actual_token = option_row['instrument_token']
        print(f"Trading Symbol: {trading_symbol}")
        print(f"Actual Token: {actual_token}")
        if actual_token != zerodha_token:
            print(f"⚠️ Token mismatch! Cache: {zerodha_token}, Actual: {actual_token}")
        quote_key = f"NFO:{trading_symbol}"

    print()

    if quote_key:
        quotes = kite.quote([quote_key])
    else:
        quotes = {}

    if quote_key in quotes:
        q = quotes[quote_key]
        print(f"✓ Quote retrieved successfully\n")
        print(f"LTP:       ₹{q['last_price']:.2f}")
        print(f"Open:      ₹{q['ohlc']['open']:.2f} (day)")
        print(f"High:      ₹{q['ohlc']['high']:.2f} (day)")
        print(f"Low:       ₹{q['ohlc']['low']:.2f} (day)")
        print(f"Close:     ₹{q['ohlc']['close']:.2f} (prev day)")
        print(f"Volume:    {q['volume']:,}")
        print(f"OI:        {q['oi']:,}")
        print(f"OI Change: {q.get('oi_day_high', 0) - q.get('oi_day_low', 0):,}")
    else:
        print("✗ Failed to fetch quote")

    print()
    print("="*80)
    print("COMPARISON WITH YOUR SYSTEM")
    print("="*80)
    print("Your system shows:")
    print("  Price: ₹81.10")
    print("  OI: 11,676,210")
    print("  VWAP: ₹81.10")
    print()

    if candle and quote_key in quotes:
        q = quotes[quote_key]
        print("Live Zerodha data:")
        print(f"  Candle Close: ₹{candle['close']:.2f}")
        print(f"  LTP: ₹{q['last_price']:.2f}")
        print(f"  OI: {q['oi']:,}")
        print()

        # Compare
        price_diff = abs(candle['close'] - 81.10)
        oi_diff = abs(q['oi'] - 11676210)

        print("Differences:")
        print(f"  Price diff: ₹{price_diff:.2f}")
        print(f"  OI diff: {oi_diff:,}")

        if price_diff < 5:
            print("\n✓ Price data MATCHES (within ₹5 tolerance)")
        else:
            print("\n⚠️ Price data MISMATCH")

        if oi_diff < 100000:
            print("✓ OI data MATCHES (within 100K tolerance)")
        else:
            print("⚠️ OI data MISMATCH")

    print()
    print("="*80)

    # Logout
    connection.logout()

if __name__ == "__main__":
    main()
