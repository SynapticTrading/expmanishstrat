"""
Quick LTP Check Script

Fast script to check LTP, quote, and basic fetching for a specific contract.

Usage:
    python paper_trading/test_adapter/quick_check_ltp.py --broker zerodha --strike 23500
    python paper_trading/test_adapter/quick_check_ltp.py --broker angelone --strike 23500 --expiry current_week
"""

import sys
import argparse
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from paper_trading.brokers.adapter.factory import create_adapter
from paper_trading.core.contract_manager import ContractManager
import yaml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def quick_check(broker_name, strike, expiry_type='current_week'):
    """Quick check of LTP and quote for a specific strike."""

    # Load config
    config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    credentials = config['brokers'][broker_name]

    # Initialize
    print(f"\n🔧 Initializing {broker_name.upper()} adapter...")
    contract_manager = ContractManager()
    adapter = create_adapter(credentials, broker_name, contract_manager)

    # Connect
    print(f"🔗 Connecting to {broker_name}...")
    if not adapter.connect():
        print(f"❌ Failed to connect")
        return

    print(f"✅ Connected to {broker_name}")

    try:
        # Get expiry
        expiry = contract_manager.get_options_expiry(expiry_type)
        print(f"\n📅 Expiry: {expiry}")
        print(f"🎯 Strike: {strike}")

        # Check if contract exists in cache
        print(f"\n🔍 Checking cache for contracts...")
        ce_contract = contract_manager.get_option_contract(expiry, strike, 'CE')
        pe_contract = contract_manager.get_option_contract(expiry, strike, 'PE')

        if not ce_contract:
            print(f"❌ CE contract not found in cache for strike {strike}")
            print(f"   Available strikes in cache:")
            # Show available strikes
            current_week = contract_manager.cache['options']['mapping'].get('current_week', {})
            if 'CE' in current_week:
                strikes = [c['strike'] for c in current_week['CE'][:10]]
                print(f"   {strikes}")
            return

        if not pe_contract:
            print(f"❌ PE contract not found in cache for strike {strike}")
            return

        print(f"✅ Contracts found in cache")

        # Verify tokens
        if broker_name == 'zerodha':
            token_field = 'zerodha_instrument_token'
        else:
            token_field = 'token'

        print(f"\n🔑 Token Verification:")
        print(f"   CE {token_field}: {ce_contract.get(token_field, 'MISSING')}")
        print(f"   PE {token_field}: {pe_contract.get(token_field, 'MISSING')}")

        # Fetch spot price
        print(f"\n💹 Fetching NIFTY spot price...")
        spot = adapter.get_spot_price()
        print(f"   Spot: ₹{spot:,.2f}")

        # Fetch CE LTP
        print(f"\n📊 CE Option (Strike: {strike}):")
        print(f"   Symbol: {ce_contract.get('symbol')}")
        ce_ltp = adapter.get_ltp('NIFTY', 'CE', strike, expiry)

        if ce_ltp:
            print(f"   ✅ LTP: ₹{ce_ltp:,.2f}")

            # Fetch full quote
            print(f"\n   📈 Fetching full CE quote...")
            ce_quote = adapter.get_quote('NIFTY', 'CE', strike, expiry)

            if ce_quote:
                print(f"   ✅ Full Quote:")
                print(f"      LTP:     ₹{ce_quote.ltp:,.2f}")
                print(f"      Open:    ₹{ce_quote.open:,.2f}")
                print(f"      High:    ₹{ce_quote.high:,.2f}")
                print(f"      Low:     ₹{ce_quote.low:,.2f}")
                print(f"      Close:   ₹{ce_quote.close:,.2f}")
                print(f"      Volume:  {ce_quote.volume:,}")
                print(f"      OI:      {ce_quote.oi:,}")
                print(f"      Bid:     ₹{ce_quote.bid:,.2f}")
                print(f"      Ask:     ₹{ce_quote.ask:,.2f}")
        else:
            print(f"   ❌ Failed to fetch CE LTP")

        # Fetch PE LTP
        print(f"\n📊 PE Option (Strike: {strike}):")
        print(f"   Symbol: {pe_contract.get('symbol')}")
        pe_ltp = adapter.get_ltp('NIFTY', 'PE', strike, expiry)

        if pe_ltp:
            print(f"   ✅ LTP: ₹{pe_ltp:,.2f}")

            # Fetch full quote
            print(f"\n   📉 Fetching full PE quote...")
            pe_quote = adapter.get_quote('NIFTY', 'PE', strike, expiry)

            if pe_quote:
                print(f"   ✅ Full Quote:")
                print(f"      LTP:     ₹{pe_quote.ltp:,.2f}")
                print(f"      Open:    ₹{pe_quote.open:,.2f}")
                print(f"      High:    ₹{pe_quote.high:,.2f}")
                print(f"      Low:     ₹{pe_quote.low:,.2f}")
                print(f"      Volume:  {pe_quote.volume:,}")
                print(f"      OI:      {pe_quote.oi:,}")
        else:
            print(f"   ❌ Failed to fetch PE LTP")

        # Summary
        print(f"\n✅ Quick Check Complete!")
        print(f"   Broker:     {broker_name.upper()}")
        print(f"   Strike:     {strike}")
        print(f"   CE LTP:     ₹{ce_ltp:,.2f}" if ce_ltp else "   CE LTP:     Failed")
        print(f"   PE LTP:     ₹{pe_ltp:,.2f}" if pe_ltp else "   PE LTP:     Failed")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        adapter.disconnect()
        print(f"\n🔌 Disconnected")


def main():
    parser = argparse.ArgumentParser(description='Quick LTP check')
    parser.add_argument('--broker', required=True, choices=['zerodha', 'angelone'])
    parser.add_argument('--strike', type=int, required=True, help='Strike price')
    parser.add_argument('--expiry', default='current_week',
                       choices=['current_week', 'next_week', 'current_month', 'next_month'])

    args = parser.parse_args()
    quick_check(args.broker, args.strike, args.expiry)


if __name__ == '__main__':
    main()
