#!/usr/bin/env python3
"""Quick LTP fetch for NIFTY 25250 PUT using Zerodha"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from datetime import datetime
from paper_trading.legacy.zerodha_connection import ZerodhaConnection
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
    print("="*60)
    print(f"NIFTY 25250 PUT LTP - {datetime.now()}")
    print("="*60)

    # Connect
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
        print("Failed to connect")
        return

    print("✓ Connected to Zerodha\n")

    # Get contract details from cache
    with open('contracts_cache.json', 'r') as f:
        cache = json.load(f)

    # Find NIFTY 25250 PE
    put_contract = cache['options']['instruments']['2026-01-27']['25250']['PE']
    zerodha_token = put_contract['zerodha_instrument_token']

    # Load instruments to get symbol
    from paper_trading.legacy.zerodha_data_feed import ZerodhaDataFeed
    data_feed = ZerodhaDataFeed(connection)
    data_feed.load_instruments()

    # Find symbol
    from datetime import date
    expiry_date = date(2026, 1, 27)
    nfo_instruments = data_feed.nfo_instruments

    option_row = nfo_instruments[
        (nfo_instruments['name'] == 'NIFTY') &
        (nfo_instruments['strike'] == 25250) &
        (nfo_instruments['instrument_type'] == 'PE') &
        (nfo_instruments['expiry'] == expiry_date)
    ].iloc[0]

    symbol = option_row['tradingsymbol']

    print(f"Contract: {symbol}")
    print(f"Strike: 25250 PUT")
    print(f"Expiry: 2026-01-27")
    print(f"Token: {zerodha_token}")
    print()

    # Get quote
    quote_key = f"NFO:{symbol}"
    quotes = kite.quote([quote_key])

    if quote_key in quotes:
        q = quotes[quote_key]

        print("="*60)
        print("QUOTE DATA")
        print("="*60)
        print(f"LTP:           ₹{q['last_price']:.2f}")
        print(f"Open (day):    ₹{q['ohlc']['open']:.2f}")
        print(f"High (day):    ₹{q['ohlc']['high']:.2f}")
        print(f"Low (day):     ₹{q['ohlc']['low']:.2f}")
        print(f"Close (prev):  ₹{q['ohlc']['close']:.2f}")
        print(f"Volume:        {q['volume']:,}")
        print(f"OI:            {q['oi']:,}")
        print(f"Change:        {q.get('change', 0):+.2f}%")
        print("="*60)

        # Also get 5-min candle for comparison
        print("\nLatest 5-Min Candle:")
        candle = data_feed.get_5min_candle(zerodha_token)
        if candle:
            print(f"Timestamp:     {candle['timestamp']}")
            print(f"Open:          ₹{candle['open']:.2f}")
            print(f"High:          ₹{candle['high']:.2f}")
            print(f"Low:           ₹{candle['low']:.2f}")
            print(f"Close:         ₹{candle['close']:.2f}")
            print(f"Volume:        {candle['volume']:,}")
            print()
            print(f"Difference (LTP - Candle Close): ₹{q['last_price'] - candle['close']:.2f}")
    else:
        print("Failed to fetch quote")

    print()
    connection.logout()

if __name__ == "__main__":
    main()
