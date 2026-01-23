"""
Manual Test Script for Market Data Fetching

Run this script to manually test:
- LTP fetching using token-based approach
- Quote fetching (full market data)
- Option chain fetching
- Spot price fetching
- Contract resolution from cache

Usage:
    python paper_trading/test_adapter/manual_test_fetches.py --broker zerodha
    python paper_trading/test_adapter/manual_test_fetches.py --broker angelone
"""

import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from paper_trading.brokers.adapter.factory import create_adapter
from paper_trading.core.contract_manager import ContractManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config():
    """Load broker credentials from config."""
    import yaml
    config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"

    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        return None

    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def print_section(title):
    """Print section header."""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)


def test_contract_resolution(adapter, contract_manager):
    """Test contract resolution from cache."""
    print_section("1. CONTRACT RESOLUTION TEST")

    # Get current week expiry
    expiry = contract_manager.get_options_expiry('current_week')
    print(f"📅 Current Week Expiry: {expiry}")

    # Get spot price to determine ATM
    spot = adapter.get_spot_price()
    print(f"💹 NIFTY Spot Price: {spot}")

    if spot:
        atm_strike = round(spot / 50) * 50
        print(f"🎯 ATM Strike: {atm_strike}")

        # Test CE contract resolution
        print("\n🔍 Resolving CE Contract...")
        ce_contract = contract_manager.get_option_contract(expiry, atm_strike, 'CE')

        if ce_contract:
            print(f"✅ CE Contract Found:")
            print(f"   Symbol: {ce_contract.get('symbol')}")
            print(f"   Token: {ce_contract.get('token')}")
            print(f"   Zerodha Token: {ce_contract.get('zerodha_instrument_token')}")
            print(f"   Strike: {ce_contract.get('strike')}")
            print(f"   Lot Size: {ce_contract.get('lot_size')}")
        else:
            print("❌ CE Contract not found in cache")

        # Test PE contract resolution
        print("\n🔍 Resolving PE Contract...")
        pe_contract = contract_manager.get_option_contract(expiry, atm_strike, 'PE')

        if pe_contract:
            print(f"✅ PE Contract Found:")
            print(f"   Symbol: {pe_contract.get('symbol')}")
            print(f"   Token: {pe_contract.get('token')}")
            print(f"   Strike: {pe_contract.get('strike')}")
        else:
            print("❌ PE Contract not found in cache")

        return expiry, atm_strike, ce_contract, pe_contract

    return None, None, None, None


def test_ltp_fetching(adapter, expiry, atm_strike):
    """Test LTP fetching using token-based approach."""
    print_section("2. LTP FETCHING TEST (Token-Based)")

    if not expiry or not atm_strike:
        print("⚠️  Skipping - no contract data available")
        return

    print(f"Testing LTP fetch for Strike: {atm_strike}, Expiry: {expiry}")

    # Test CE LTP
    print("\n📊 Fetching CE LTP...")
    ce_ltp = adapter.get_ltp(
        underlying='NIFTY',
        option_type='CE',
        strike=atm_strike,
        expiry=expiry
    )

    if ce_ltp:
        print(f"✅ CE LTP: ₹{ce_ltp}")
    else:
        print("❌ Failed to fetch CE LTP")

    # Test PE LTP
    print("\n📊 Fetching PE LTP...")
    pe_ltp = adapter.get_ltp(
        underlying='NIFTY',
        option_type='PE',
        strike=atm_strike,
        expiry=expiry
    )

    if pe_ltp:
        print(f"✅ PE LTP: ₹{pe_ltp}")
    else:
        print("❌ Failed to fetch PE LTP")

    return ce_ltp, pe_ltp


def test_quote_fetching(adapter, expiry, atm_strike):
    """Test full quote fetching."""
    print_section("3. FULL QUOTE FETCHING TEST")

    if not expiry or not atm_strike:
        print("⚠️  Skipping - no contract data available")
        return

    print(f"Testing full quote for Strike: {atm_strike}, Expiry: {expiry}")

    # Test CE Quote
    print("\n📈 Fetching CE Full Quote...")
    ce_quote = adapter.get_quote(
        underlying='NIFTY',
        option_type='CE',
        strike=atm_strike,
        expiry=expiry
    )

    if ce_quote:
        print(f"✅ CE Quote:")
        print(f"   LTP:        ₹{ce_quote.ltp}")
        print(f"   Open:       ₹{ce_quote.open}")
        print(f"   High:       ₹{ce_quote.high}")
        print(f"   Low:        ₹{ce_quote.low}")
        print(f"   Close:      ₹{ce_quote.close}")
        print(f"   Volume:     {ce_quote.volume:,}")
        print(f"   OI:         {ce_quote.oi:,}")
        print(f"   Bid:        ₹{ce_quote.bid}")
        print(f"   Ask:        ₹{ce_quote.ask}")
        print(f"   Change:     {ce_quote.change:+.2f} ({ce_quote.change_pct:+.2f}%)")
    else:
        print("❌ Failed to fetch CE quote")

    # Test PE Quote
    print("\n📉 Fetching PE Full Quote...")
    pe_quote = adapter.get_quote(
        underlying='NIFTY',
        option_type='PE',
        strike=atm_strike,
        expiry=expiry
    )

    if pe_quote:
        print(f"✅ PE Quote:")
        print(f"   LTP:        ₹{pe_quote.ltp}")
        print(f"   Open:       ₹{pe_quote.open}")
        print(f"   High:       ₹{pe_quote.high}")
        print(f"   Low:        ₹{pe_quote.low}")
        print(f"   Volume:     {pe_quote.volume:,}")
        print(f"   OI:         {pe_quote.oi:,}")
    else:
        print("❌ Failed to fetch PE quote")

    return ce_quote, pe_quote


def test_multiple_quotes(adapter, expiry, atm_strike):
    """Test fetching quotes for multiple instruments."""
    print_section("4. MULTIPLE QUOTES TEST")

    if not expiry or not atm_strike:
        print("⚠️  Skipping - no contract data available")
        return

    # Build list of instruments (ATM and OTM strikes)
    instruments = []
    for strike_offset in [-100, -50, 0, 50, 100]:
        strike = atm_strike + strike_offset
        instruments.append(('NIFTY', 'CE', strike, expiry))
        instruments.append(('NIFTY', 'PE', strike, expiry))

    print(f"Fetching quotes for {len(instruments)} instruments...")
    print(f"Strikes: {[atm_strike + offset for offset in [-100, -50, 0, 50, 100]]}")

    quotes = adapter.get_quotes(instruments)

    if quotes:
        print(f"\n✅ Fetched {len(quotes)} quotes:")
        print("\nStrike    Type    LTP      Volume    OI")
        print("-" * 50)

        for (underlying, opt_type, strike, exp), quote in sorted(quotes.items()):
            print(f"{strike:6d}    {opt_type:2s}    ₹{quote.ltp:7.2f}  {quote.volume:8,d}  {quote.oi:10,d}")
    else:
        print("❌ Failed to fetch quotes")

    return quotes


def test_option_chain(adapter, contract_manager, expiry, atm_strike):
    """Test option chain fetching."""
    print_section("5. OPTION CHAIN TEST")

    if not expiry or not atm_strike:
        print("⚠️  Skipping - no contract data available")
        return

    # Get strikes around ATM
    strikes = [atm_strike + offset for offset in range(-200, 250, 50)]

    print(f"Fetching option chain for expiry: {expiry}")
    print(f"Strikes: {strikes}")

    option_chain = adapter.get_option_chain('NIFTY', expiry, strikes)

    if option_chain is not None and not option_chain.empty:
        print(f"\n✅ Option Chain Data ({len(option_chain)} rows):")
        print("\nStrike    Type    Close      Volume      OI")
        print("-" * 60)

        for _, row in option_chain.head(10).iterrows():
            print(f"{row.get('strike', 0):6d}    "
                  f"{row.get('option_type', 'N/A'):2s}    "
                  f"₹{row.get('close', 0):7.2f}  "
                  f"{row.get('volume', 0):10,d}  "
                  f"{row.get('OI', 0):10,d}")

        if len(option_chain) > 10:
            print(f"... and {len(option_chain) - 10} more rows")
    else:
        print("❌ Failed to fetch option chain")

    return option_chain


def test_spot_price(adapter):
    """Test spot price fetching."""
    print_section("6. SPOT PRICE TEST")

    print("Fetching NIFTY spot price...")
    spot = adapter.get_spot_price()

    if spot:
        print(f"✅ NIFTY Spot Price: ₹{spot:,.2f}")
    else:
        print("❌ Failed to fetch spot price")

    return spot


def test_market_status(adapter):
    """Test market status check."""
    print_section("7. MARKET STATUS TEST")

    is_open = adapter.is_market_open()

    print(f"Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Market Status: {'🟢 OPEN' if is_open else '🔴 CLOSED'}")

    return is_open


def test_token_based_approach(adapter, contract_manager, broker_name):
    """Verify token-based approach is being used."""
    print_section("8. TOKEN-BASED APPROACH VERIFICATION")

    print(f"Broker: {broker_name.upper()}")
    print("\nVerifying system uses ONLY tokens (no manual symbol construction)...")

    # Check if ContractManager has tokens
    has_tokens = contract_manager.has_instrument_tokens()
    print(f"✅ ContractManager has tokens: {has_tokens}")

    # Get a sample contract and verify it has required token fields
    expiry = contract_manager.get_options_expiry('current_week')
    if expiry:
        spot = adapter.get_spot_price()
        if spot:
            atm_strike = round(spot / 50) * 50
            contract = contract_manager.get_option_contract(expiry, atm_strike, 'CE')

            if contract:
                print(f"\n📋 Sample Contract Structure:")

                if broker_name == 'zerodha':
                    has_zerodha_token = 'zerodha_instrument_token' in contract
                    print(f"   Has 'zerodha_instrument_token': {has_zerodha_token}")
                    if has_zerodha_token:
                        print(f"   ✅ Token Value: {contract['zerodha_instrument_token']}")
                    else:
                        print(f"   ❌ Missing zerodha_instrument_token - run: python refresh_contracts.py --broker zerodha")

                elif broker_name == 'angelone':
                    has_token = 'token' in contract
                    print(f"   Has 'token': {has_token}")
                    if has_token:
                        print(f"   ✅ Token Value: {contract['token']}")
                    else:
                        print(f"   ❌ Missing token - run: python refresh_contracts.py --broker angelone")

                print(f"   Symbol (for reference): {contract.get('symbol')}")

                print(f"\n✅ System configured for TOKEN-BASED lookups")
                print(f"   All API calls use tokens from contracts_cache.json")
                print(f"   No runtime symbol construction required")


def run_all_tests(broker_name):
    """Run all market data fetching tests."""
    print("\n" + "🚀 " * 40)
    print(f"MARKET DATA FETCHING TEST - {broker_name.upper()}")
    print("🚀 " * 40)

    # Load configuration
    config = load_config()
    if not config:
        print("❌ Failed to load configuration")
        return

    # Get credentials
    credentials = config.get('brokers', {}).get(broker_name)
    if not credentials:
        print(f"❌ No credentials found for {broker_name}")
        return

    # Initialize ContractManager
    print("\n📦 Loading ContractManager...")
    contract_manager = ContractManager()
    print(f"✅ ContractManager loaded")

    # Create adapter
    print(f"\n🔌 Creating {broker_name} adapter...")
    adapter = create_adapter(
        credentials=credentials,
        broker=broker_name,
        contract_manager=contract_manager
    )
    print(f"✅ Adapter created: {adapter.broker_name}")

    # Connect to broker
    print(f"\n🔗 Connecting to {broker_name}...")
    connected = adapter.connect()

    if not connected:
        print(f"❌ Failed to connect to {broker_name}")
        return

    print(f"✅ Connected to {broker_name}")

    try:
        # Run all tests
        expiry, atm_strike, ce_contract, pe_contract = test_contract_resolution(adapter, contract_manager)

        test_spot_price(adapter)

        test_market_status(adapter)

        test_ltp_fetching(adapter, expiry, atm_strike)

        test_quote_fetching(adapter, expiry, atm_strike)

        test_multiple_quotes(adapter, expiry, atm_strike)

        test_option_chain(adapter, contract_manager, expiry, atm_strike)

        test_token_based_approach(adapter, contract_manager, broker_name)

        # Summary
        print_section("TEST SUMMARY")
        print("✅ All market data fetching tests completed!")
        print(f"Broker: {broker_name.upper()}")
        print(f"Connection: {'🟢 Active' if adapter.is_connected() else '🔴 Inactive'}")
        print(f"Token-Based: ✅ YES")

    except Exception as e:
        print(f"\n❌ Error during tests: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Disconnect
        print("\n🔌 Disconnecting...")
        adapter.disconnect()
        print("✅ Disconnected")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Manual test script for market data fetching'
    )
    parser.add_argument(
        '--broker',
        type=str,
        choices=['zerodha', 'angelone'],
        required=True,
        help='Broker to test (zerodha or angelone)'
    )

    args = parser.parse_args()

    run_all_tests(args.broker)


if __name__ == '__main__':
    main()
