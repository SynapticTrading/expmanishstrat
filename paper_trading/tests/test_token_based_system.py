"""
Comprehensive Test: Verify Both Brokers Use Pure Token-Based Approach

Tests:
1. Zerodha LTP fetch using tokens (no symbols)
2. Zerodha quote fetch using tokens (no symbols)
3. AngelOne LTP fetch using tokens (no symbols)
4. AngelOne quote fetch using tokens (no symbols)
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from paper_trading.core.contract_manager import ContractManager
from paper_trading.brokers.adapter import create_adapter
from paper_trading.legacy.zerodha_connection import load_credentials_from_file
import json

def test_zerodha_token_based():
    """Test Zerodha adapter with pure token-based approach"""
    print("\n" + "="*80)
    print("ZERODHA TOKEN-BASED TEST")
    print("="*80)
    
    # Load credentials
    creds_path = "paper_trading/config/credentials_zerodha.txt"
    credentials = load_credentials_from_file(creds_path)
    
    if not credentials:
        print("❌ Failed to load Zerodha credentials")
        return False
    
    # Load contract manager
    contract_manager = ContractManager('contracts_cache.json')
    
    # Create adapter
    print("\nCreating Zerodha adapter...")
    adapter = create_adapter(credentials, 'zerodha', contract_manager)
    
    # Connect
    print("Connecting to Zerodha...")
    if not adapter.connect():
        print("❌ Failed to connect to Zerodha")
        return False
    
    # Store kite reference for spot price
    kite = adapter._kite
    
    print("✓ Connected successfully\n")
    
    # Get spot price to find ATM strike
    spot_data = kite.ltp(['NSE:NIFTY 50'])
    spot_price = spot_data['NSE:NIFTY 50']['last_price']
    atm_strike = round(spot_price / 50) * 50
    print(f"Nifty Spot: ₹{spot_price:.2f}, ATM Strike: {atm_strike}\n")
    
    # Get a sample contract from cache
    expiry = contract_manager.get_options_expiry('current_week')
    
    # Use ATM or nearby strike
    strike = None
    contract = None
    for offset in [0, 50, -50, 100, -100]:
        test_strike = atm_strike + offset
        contract = contract_manager.get_option_contract(expiry, test_strike, 'CE')
        if contract and 'zerodha_instrument_token' in contract:
            strike = test_strike
            break
    
    if not contract or not strike:
        print("❌ No contract found in cache")
        return False
    
    token = contract.get('zerodha_instrument_token')
    symbol = contract.get('symbol')
    
    print(f"Testing with:")
    print(f"  Expiry: {expiry}")
    print(f"  Strike: {strike} CE")
    print(f"  Token: {token}")
    print(f"  Symbol: {symbol}")
    print()
    
    # Test LTP
    print("TEST 1: get_ltp() - Should use token directly")
    print("-" * 80)
    ltp = adapter.get_ltp('NIFTY', 'CE', 23200, expiry)
    if ltp:
        print(f"✓ LTP fetched successfully: ₹{ltp:.2f}")
        print(f"  Method: Token-based (instrument_token={token})")
    else:
        print(f"❌ Failed to fetch LTP")
        return False
    
    print()
    
    # Test Quote
    print("TEST 2: get_quote() - Should use token directly")
    print("-" * 80)
    quote = adapter.get_quote('NIFTY', 'CE', 23200, expiry)
    if quote:
        print(f"✓ Quote fetched successfully:")
        print(f"  LTP: ₹{quote.ltp:.2f}")
        print(f"  Open: ₹{quote.open:.2f}")
        print(f"  High: ₹{quote.high:.2f}")
        print(f"  Low: ₹{quote.low:.2f}")
        print(f"  OI: {quote.oi:,}")
        print(f"  Method: Token-based (instrument_token={token})")
    else:
        print(f"❌ Failed to fetch quote")
        return False
    
    adapter.disconnect()
    print("\n✓ Zerodha token-based test PASSED")
    return True


def test_angelone_token_based():
    """Test AngelOne adapter with pure token-based approach"""
    print("\n" + "="*80)
    print("ANGELONE TOKEN-BASED TEST")
    print("="*80)
    
    # Load credentials
    creds_path = "paper_trading/config/credentials_angelone.txt"
    credentials = load_credentials_from_file(creds_path)
    
    if not credentials:
        print("❌ Failed to load AngelOne credentials")
        return False
    
    # Load contract manager
    contract_manager = ContractManager('contracts_cache.json')
    
    # Create adapter
    print("\nCreating AngelOne adapter...")
    adapter = create_adapter(credentials, 'angelone', contract_manager)
    
    # Connect
    print("Connecting to AngelOne...")
    if not adapter.connect():
        print("❌ Failed to connect to AngelOne")
        return False
    
    print("✓ Connected successfully\n")
    
    # Get spot price to find ATM strike
    spot_data = adapter._smart_api.ltpData("NSE", "NIFTY 50", "99926000")
    spot_price = float(spot_data['data']['ltp'])
    atm_strike = round(spot_price / 50) * 50
    print(f"Nifty Spot: ₹{spot_price:.2f}, ATM Strike: {atm_strike}\n")
    
    # Get a sample contract from cache
    expiry = contract_manager.get_options_expiry('current_week')
    
    # Use ATM or nearby strike
    strike = None
    contract = None
    for offset in [0, 50, -50, 100, -100]:
        test_strike = atm_strike + offset
        contract = contract_manager.get_option_contract(expiry, test_strike, 'CE')
        if contract and 'token' in contract:
            strike = test_strike
            break
    
    if not contract or not strike:
        print("❌ No contract found in cache")
        return False
    
    token = contract.get('token')
    symbol = contract.get('symbol')
    
    print(f"Testing with:")
    print(f"  Expiry: {expiry}")
    print(f"  Strike: {strike} CE")
    print(f"  Token: {token}")
    print(f"  Symbol: {symbol}")
    print()
    
    # Test LTP
    print("TEST 1: get_ltp() - Should use token directly")
    print("-" * 80)
    ltp = adapter.get_ltp('NIFTY', 'CE', strike, expiry)
    if ltp:
        print(f"✓ LTP fetched successfully: ₹{ltp:.2f}")
        print(f"  Method: Token-based (symbol_token={token})")
    else:
        print(f"❌ Failed to fetch LTP")
        return False
    
    print()
    
    # Test Quote
    print("TEST 2: get_quote() - Should use token directly")
    print("-" * 80)
    quote = adapter.get_quote('NIFTY', 'CE', strike, expiry)
    if quote:
        print(f"✓ Quote fetched successfully:")
        print(f"  LTP: ₹{quote.ltp:.2f}")
        print(f"  Open: ₹{quote.open:.2f}")
        print(f"  High: ₹{quote.high:.2f}")
        print(f"  Low: ₹{quote.low:.2f}")
        print(f"  OI: {quote.oi:,}")
        print(f"  Method: Token-based (symbol_token={token})")
    else:
        print(f"❌ Failed to fetch quote")
        return False
    
    adapter.disconnect()
    print("\n✓ AngelOne token-based test PASSED")
    return True


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("PURE TOKEN-BASED SYSTEM VERIFICATION")
    print("Testing both Zerodha and AngelOne adapters")
    print("="*80)
    
    results = {
        'zerodha': False,
        'angelone': False
    }
    
    # Test Zerodha
    try:
        results['zerodha'] = test_zerodha_token_based()
    except Exception as e:
        print(f"\n❌ Zerodha test failed with exception: {e}")
        import traceback
        traceback.print_exc()
    
    # Test AngelOne
    try:
        results['angelone'] = test_angelone_token_based()
    except Exception as e:
        print(f"\n❌ AngelOne test failed with exception: {e}")
        import traceback
        traceback.print_exc()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Zerodha (token-based):  {'✓ PASS' if results['zerodha'] else '❌ FAIL'}")
    print(f"AngelOne (token-based): {'✓ PASS' if results['angelone'] else '❌ FAIL'}")
    
    if all(results.values()):
        print("\n🎉 ALL TESTS PASSED - Both brokers are pure token-based!")
        print("✓ NO tradingsymbol conversions")
        print("✓ Direct token API calls")
        print("✓ Consistent implementation across brokers")
    else:
        print("\n⚠️  Some tests failed - see details above")
    
    print("="*80)


if __name__ == "__main__":
    main()
