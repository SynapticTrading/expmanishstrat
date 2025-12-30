"""
Check Zerodha expiry format in instruments
"""

from paper_trading.legacy.zerodha_connection import ZerodhaConnection, load_credentials_from_file
import pandas as pd

# Load credentials
creds = load_credentials_from_file('paper_trading/config/credentials_zerodha.txt')

# Create connection
conn = ZerodhaConnection(
    api_key=creds['api_key'],
    api_secret=creds['api_secret'],
    user_id=creds['user_id'],
    user_password=creds['user_password'],
    totp_key=creds['totp_key']
)

# Connect
print("Connecting...")
kite = conn.connect()

if kite:
    print("\nFetching NFO instruments...")
    nfo_instruments = conn.get_instruments("NFO")

    # Filter for NIFTY options
    nifty_options = nfo_instruments[
        (nfo_instruments['name'] == 'NIFTY') &
        (nfo_instruments['instrument_type'].isin(['CE', 'PE']))
    ]

    print(f"\nTotal NIFTY options: {len(nifty_options)}")

    # Check expiry format
    print("\nExpiry column type:", nifty_options['expiry'].dtype)
    print("\nSample expiry values:")
    print(nifty_options['expiry'].unique()[:5])

    # Get unique expiries
    expiries = sorted(nifty_options['expiry'].unique())
    print(f"\nAll unique expiries ({len(expiries)} total):")
    for exp in expiries[:10]:  # First 10
        print(f"  {exp} (type: {type(exp)})")

    # Check strikes for first expiry
    first_expiry = expiries[0]
    print(f"\nOptions for expiry {first_expiry}:")
    exp_options = nifty_options[nifty_options['expiry'] == first_expiry]
    print(f"  Count: {len(exp_options)}")
    print(f"  Strikes: {sorted(exp_options['strike'].unique())[:10]}")

    # Sample row
    print("\nSample option row:")
    sample = exp_options.iloc[0]
    print(f"  Trading Symbol: {sample['tradingsymbol']}")
    print(f"  Strike: {sample['strike']}")
    print(f"  Expiry: {sample['expiry']} (type: {type(sample['expiry'])})")
    print(f"  Instrument Type: {sample['instrument_type']}")
    print(f"  Token: {sample['instrument_token']}")
