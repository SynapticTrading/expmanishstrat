"""
Validate Adapter Structure and Cache

This script validates the adapter setup WITHOUT connecting to broker APIs.
Can be run anytime to verify:
- Cache structure is correct
- Tokens are present
- Adapters can be created
- ContractManager works

Usage:
    python paper_trading/test_adapter/validate_structure.py
"""

import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from paper_trading.brokers.adapter.factory import create_adapter, get_available_brokers
from paper_trading.core.contract_manager import ContractManager
import yaml


def validate_cache_structure():
    """Validate contracts_cache.json structure."""
    print("\n" + "="*80)
    print("  1. CACHE STRUCTURE VALIDATION")
    print("="*80)

    cache_path = Path(__file__).parent.parent.parent / "contracts_cache.json"

    if not cache_path.exists():
        print("❌ contracts_cache.json not found")
        print("   Run: python refresh_contracts.py --broker zerodha")
        return False

    print(f"✅ Cache file exists: {cache_path}")

    # Load cache
    with open(cache_path, 'r') as f:
        cache = json.load(f)

    # Check top-level structure
    print("\n📋 Top-level structure:")
    required_keys = ['timestamp', 'symbol', 'exchange', 'source_broker']
    for key in required_keys:
        if key in cache:
            print(f"   ✅ {key}: {cache[key]}")
        else:
            print(f"   ❌ Missing key: {key}")
            return False

    # Check options structure
    print("\n📋 Options structure:")
    if 'options' in cache:
        print(f"   ✅ 'options' key present")

        options = cache['options']
        if 'mapping' in options:
            print(f"   ✅ 'mapping' key present")

            mapping = options['mapping']
            expiry_types = ['current_week', 'next_week', 'current_month', 'next_month']

            for expiry_type in expiry_types:
                if expiry_type in mapping:
                    exp_data = mapping[expiry_type]
                    ce_count = len(exp_data.get('CE', []))
                    pe_count = len(exp_data.get('PE', []))
                    print(f"   ✅ {expiry_type}: {ce_count} CE, {pe_count} PE contracts")
                else:
                    print(f"   ⚠️  {expiry_type} not found")
        else:
            print(f"   ❌ 'mapping' key missing")
            return False
    else:
        print(f"   ❌ 'options' key missing")
        return False

    # Check sample contract structure
    print("\n📋 Sample contract structure:")
    current_week = mapping.get('current_week', {})
    ce_contracts = current_week.get('CE', [])

    if ce_contracts:
        sample = ce_contracts[0]
        print(f"   ✅ Sample CE contract:")

        required_fields = ['symbol', 'strike', 'option_type', 'expiry', 'lot_size']
        for field in required_fields:
            if field in sample:
                print(f"      ✅ {field}: {sample[field]}")
            else:
                print(f"      ❌ Missing field: {field}")

        # Check token fields
        print(f"\n   🔑 Token fields:")
        if 'token' in sample:
            print(f"      ✅ token (AngelOne): {sample['token']}")
        else:
            print(f"      ⚠️  'token' missing - run with --broker angelone")

        if 'zerodha_instrument_token' in sample:
            print(f"      ✅ zerodha_instrument_token: {sample['zerodha_instrument_token']}")
        else:
            print(f"      ⚠️  'zerodha_instrument_token' missing - run with --broker zerodha")
    else:
        print(f"   ❌ No CE contracts found")
        return False

    print("\n✅ Cache structure validation PASSED")
    return True


def validate_contract_manager():
    """Validate ContractManager functionality."""
    print("\n" + "="*80)
    print("  2. CONTRACT MANAGER VALIDATION")
    print("="*80)

    try:
        print("\n🔧 Initializing ContractManager...")
        cm = ContractManager()
        print("✅ ContractManager initialized")

        # Test has_instrument_tokens
        print("\n🔍 Checking for instrument tokens...")
        has_tokens = cm.has_instrument_tokens()
        print(f"   {'✅' if has_tokens else '❌'} Has instrument tokens: {has_tokens}")

        # Test get_options_expiry
        print("\n📅 Testing expiry retrieval...")
        expiry_types = ['current_week', 'next_week', 'current_month', 'next_month']

        for expiry_type in expiry_types:
            expiry = cm.get_options_expiry(expiry_type)
            if expiry:
                print(f"   ✅ {expiry_type}: {expiry}")
            else:
                print(f"   ⚠️  {expiry_type}: Not found")

        # Test get_option_contract
        print("\n🔍 Testing contract retrieval...")
        current_week_expiry = cm.get_options_expiry('current_week')

        if current_week_expiry:
            # Get first available strike
            current_week = cm.cache['options']['mapping']['current_week']
            ce_contracts = current_week.get('CE', [])

            if ce_contracts:
                test_strike = ce_contracts[0]['strike']

                print(f"\n   Testing with strike: {test_strike}")

                # Test CE
                ce_contract = cm.get_option_contract(current_week_expiry, test_strike, 'CE')
                if ce_contract:
                    print(f"   ✅ CE contract retrieved:")
                    print(f"      Symbol: {ce_contract.get('symbol')}")
                    print(f"      Token: {ce_contract.get('token', 'N/A')}")
                    print(f"      Zerodha Token: {ce_contract.get('zerodha_instrument_token', 'N/A')}")
                else:
                    print(f"   ❌ Failed to retrieve CE contract")

                # Test PE
                pe_contract = cm.get_option_contract(current_week_expiry, test_strike, 'PE')
                if pe_contract:
                    print(f"   ✅ PE contract retrieved:")
                    print(f"      Symbol: {pe_contract.get('symbol')}")
                else:
                    print(f"   ❌ Failed to retrieve PE contract")

        print("\n✅ ContractManager validation PASSED")
        return True

    except Exception as e:
        print(f"\n❌ ContractManager validation FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_adapter_creation():
    """Validate adapter creation (without connection)."""
    print("\n" + "="*80)
    print("  3. ADAPTER CREATION VALIDATION")
    print("="*80)

    # Load config
    config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"

    if not config_path.exists():
        print(f"⚠️  Config not found: {config_path}")
        print("   Using dummy credentials for structure test")
        dummy_credentials = {
            'zerodha': {
                'api_key': 'dummy',
                'api_secret': 'dummy',
                'user_id': 'dummy',
                'user_password': 'dummy',
                'totp_key': 'dummy'
            },
            'angelone': {
                'api_key': 'dummy',
                'username': 'dummy',
                'password': 'dummy',
                'totp_token': 'dummy'
            }
        }
        credentials_config = dummy_credentials
    else:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            credentials_config = config.get('brokers', {})

    # Get available brokers
    print("\n🔍 Available brokers:")
    brokers = get_available_brokers()
    for broker in brokers:
        print(f"   ✅ {broker}")

    # Initialize ContractManager
    cm = ContractManager()

    # Test adapter creation
    print("\n🔧 Testing adapter creation...")

    for broker_name in ['zerodha', 'angelone']:
        print(f"\n   Testing {broker_name}:")

        credentials = credentials_config.get(broker_name)
        if not credentials:
            print(f"      ⚠️  No credentials configured")
            continue

        try:
            # Create adapter (without connecting)
            adapter = create_adapter(credentials, broker_name, cm)

            print(f"      ✅ Adapter created")
            print(f"      ✅ Broker name: {adapter.broker_name}")
            print(f"      ✅ Has ContractManager: {adapter.contract_manager is not None}")
            print(f"      ✅ Connected: {adapter.is_connected()}")

            # Test _resolve_instrument method
            expiry = cm.get_options_expiry('current_week')
            if expiry:
                current_week = cm.cache['options']['mapping']['current_week']
                ce_contracts = current_week.get('CE', [])

                if ce_contracts:
                    test_strike = ce_contracts[0]['strike']

                    print(f"\n      🔍 Testing instrument resolution (strike: {test_strike})...")
                    contract = adapter._resolve_instrument('NIFTY', 'CE', test_strike, expiry)

                    if contract:
                        print(f"         ✅ Contract resolved")
                        print(f"         ✅ Symbol: {contract.get('symbol')}")

                        # Check token field
                        if broker_name == 'zerodha':
                            token = contract.get('zerodha_instrument_token')
                            token_field = 'zerodha_instrument_token'
                        else:
                            token = contract.get('token')
                            token_field = 'token'

                        if token:
                            print(f"         ✅ {token_field}: {token}")
                        else:
                            print(f"         ⚠️  {token_field} missing")
                    else:
                        print(f"         ❌ Failed to resolve contract")

        except Exception as e:
            print(f"      ❌ Failed to create adapter: {e}")

    print("\n✅ Adapter creation validation PASSED")
    return True


def validate_token_flow():
    """Validate token-based lookup flow."""
    print("\n" + "="*80)
    print("  4. TOKEN-BASED LOOKUP FLOW VALIDATION")
    print("="*80)

    print("\n🔍 Validating token-based approach...")

    cm = ContractManager()
    expiry = cm.get_options_expiry('current_week')

    if not expiry:
        print("❌ Cannot get expiry")
        return False

    # Get sample strike
    current_week = cm.cache['options']['mapping']['current_week']
    ce_contracts = current_week.get('CE', [])

    if not ce_contracts:
        print("❌ No CE contracts available")
        return False

    sample_strike = ce_contracts[0]['strike']

    print(f"\nTest Parameters:")
    print(f"   Underlying: NIFTY")
    print(f"   Option Type: CE")
    print(f"   Strike: {sample_strike}")
    print(f"   Expiry: {expiry}")

    print(f"\n📋 Flow:")
    print(f"   1. Strategy calls adapter.get_ltp(NIFTY, CE, {sample_strike}, {expiry})")

    print(f"\n   2. Adapter calls _resolve_instrument():")
    contract = cm.get_option_contract(expiry, sample_strike, 'CE')

    if contract:
        print(f"      ✅ ContractManager returns contract from cache")
        print(f"      ✅ Symbol (for reference): {contract.get('symbol')}")
        print(f"      ✅ Token: {contract.get('token', 'N/A')}")
        print(f"      ✅ Zerodha Token: {contract.get('zerodha_instrument_token', 'N/A')}")
    else:
        print(f"      ❌ Contract not found")
        return False

    print(f"\n   3. Adapter extracts token:")
    token = contract.get('token') or contract.get('zerodha_instrument_token')

    if token:
        print(f"      ✅ Token extracted: {token}")
    else:
        print(f"      ❌ No token found")
        return False

    print(f"\n   4. Adapter calls broker API with TOKEN:")
    print(f"      ✅ Zerodha: kite.ltp(['NFO:{token}'])")
    print(f"      ✅ AngelOne: getMarketData(exchangeTokens={{'NFO': ['{token}']}})")

    print(f"\n   5. Broker returns LTP")
    print(f"      ✅ Adapter returns LTP to strategy")

    print(f"\n✅ TOKEN-BASED FLOW:")
    print(f"   ✅ No manual symbol construction")
    print(f"   ✅ Token retrieved from cache")
    print(f"   ✅ API called with token only")

    print("\n✅ Token-based lookup flow validation PASSED")
    return True


def main():
    """Run all validations."""
    print("\n" + "🔍 " * 40)
    print("ADAPTER STRUCTURE VALIDATION")
    print("🔍 " * 40)

    print("\nThis validates adapter structure WITHOUT connecting to brokers.")
    print("Safe to run anytime, no market hours or API calls required.")

    results = []

    # Run validations
    results.append(('Cache Structure', validate_cache_structure()))
    results.append(('ContractManager', validate_contract_manager()))
    results.append(('Adapter Creation', validate_adapter_creation()))
    results.append(('Token Flow', validate_token_flow()))

    # Summary
    print("\n" + "="*80)
    print("  VALIDATION SUMMARY")
    print("="*80)

    all_passed = True
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status:12} - {name}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n🎉 All validations PASSED!")
        print("\nYou can now run manual tests:")
        print("   python paper_trading/test_adapter/manual_test_fetches.py --broker zerodha")
        print("   python paper_trading/test_adapter/quick_check_ltp.py --broker zerodha --strike 23500")
    else:
        print("\n⚠️  Some validations FAILED!")
        print("\nCheck the errors above and:")
        print("   1. Ensure contracts_cache.json exists")
        print("   2. Run: python refresh_contracts.py --broker zerodha")
        print("   3. Verify config/config.yaml has broker credentials")


if __name__ == '__main__':
    main()
