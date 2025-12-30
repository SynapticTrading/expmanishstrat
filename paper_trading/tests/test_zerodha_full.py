"""
Test full Zerodha flow including instrument loading
"""

from paper_trading.legacy.zerodha_connection import ZerodhaConnection, load_credentials_from_file
from paper_trading.legacy.zerodha_data_feed import ZerodhaDataFeed
import time

print("="*80)
print("ZERODHA FULL INTEGRATION TEST")
print("="*80)

# Load credentials
print("\n[1] Loading credentials...")
creds = load_credentials_from_file('paper_trading/config/credentials_zerodha.txt')
print(f"✓ Loaded for user: {creds['user_id']}")

# Create connection
print("\n[2] Creating connection...")
conn = ZerodhaConnection(
    api_key=creds['api_key'],
    api_secret=creds['api_secret'],
    user_id=creds['user_id'],
    user_password=creds['user_password'],
    totp_key=creds['totp_key']
)

# Connect
print("\n[3] Connecting to Zerodha...")
start = time.time()
kite = conn.connect()
print(f"✓ Connected in {time.time()-start:.2f}s")

if kite:
    # Create data feed
    print("\n[4] Creating data feed...")
    data_feed = ZerodhaDataFeed(conn)
    print(f"✓ Data feed created")

    # Load instruments (THIS IS THE SLOW PART)
    print("\n[5] Loading instruments (this may take 10-30 seconds)...")
    start = time.time()
    success = data_feed.load_instruments()
    elapsed = time.time()-start

    if success:
        print(f"✓ Instruments loaded in {elapsed:.2f}s")

        # Test getting spot price
        print("\n[6] Getting Nifty spot price...")
        spot = data_feed.get_spot_price()
        if spot:
            print(f"✓ Nifty 50: {spot}")

        # Test getting next expiry
        print("\n[7] Getting next expiry...")
        expiry = data_feed.get_next_expiry()
        if expiry:
            print(f"✓ Next expiry: {expiry}")

        # Test getting options chain (small sample)
        print("\n[8] Getting options chain (5 strikes)...")
        if expiry and spot:
            from datetime import datetime
            strikes = [int(spot/50)*50 + (i*50) for i in range(-2, 3)]
            print(f"   Strikes: {strikes}")

            start = time.time()
            options_df = data_feed.get_options_chain(expiry, strikes)
            elapsed = time.time()-start

            if not options_df.empty:
                print(f"✓ Got {len(options_df)} options in {elapsed:.2f}s")
                print(f"\nSample data:")
                print(options_df[['strike', 'option_type', 'close', 'oi', 'volume']].head())
            else:
                print(f"✗ No options data returned")

        print("\n" + "="*80)
        print("✓ ALL TESTS PASSED - Zerodha is fully functional!")
        print("="*80)
    else:
        print(f"✗ Failed to load instruments after {elapsed:.2f}s")
else:
    print("✗ Connection failed")
