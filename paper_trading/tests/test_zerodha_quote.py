#!/usr/bin/env python3
"""
Quick test to verify Zerodha quote API is working
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from paper_trading.brokers.adapter.plugins.zerodha import ZerodhaAdapter

def load_credentials():
    """Load credentials from file"""
    creds_file = "paper_trading/config/credentials_zerodha.txt"
    credentials = {}

    with open(creds_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and '=' in line:
                key, value = line.split('=', 1)
                credentials[key.strip()] = value.strip()

    return credentials

def test_quote():
    """Test quote fetching"""
    print("="*80)
    print("Testing Zerodha Quote API")
    print("="*80)

    # Load credentials
    credentials = load_credentials()
    print(f"\n✓ Loaded credentials (user_id: {credentials.get('user_id')})")

    # Create adapter
    adapter = ZerodhaAdapter(credentials=credentials)
    print("✓ Adapter created")

    # Connect
    print("\nConnecting to Zerodha...")
    if not adapter.connect():
        print("✗ Connection failed!")
        return False
    print("✓ Connected successfully")

    # Test quote for NIFTY 25200 PE expiring 2026-01-27
    print("\nTesting quote fetch for: NIFTY 25200 PE 2026-01-27")
    quote = adapter.get_quote(
        underlying='NIFTY',
        option_type='PE',
        strike=25200,
        expiry='2026-01-27'
    )

    if quote:
        print(f"✓ Quote received!")
        print(f"  LTP: ₹{quote.ltp:.2f}")
        print(f"  OI: {quote.oi}")
        print(f"  Volume: {quote.volume}")
        return True
    else:
        print("✗ Quote fetch failed!")
        print("\nTrying to get Nifty 50 spot price to verify connection...")

        # Try to fetch Nifty spot as a sanity check
        try:
            spot_data = adapter._kite.quote(["NSE:NIFTY 50"])
            print(f"Nifty spot quote response: {spot_data}")
        except Exception as e:
            print(f"Nifty spot quote also failed: {e}")

        return False

if __name__ == "__main__":
    success = test_quote()
    sys.exit(0 if success else 1)
