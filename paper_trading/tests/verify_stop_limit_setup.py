"""
Verification Script for Stop Limit Order Test

Checks if all prerequisites are met before running the stop limit test.

Usage:
    python paper_trading/tests/verify_stop_limit_setup.py
"""

import sys
from pathlib import Path
import json

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

def print_header(title):
    """Print section header."""
    print("\n" + "="*80)
    print(f"{title}")
    print("="*80)

def check_credentials():
    """Check if AngelOne credentials file exists."""
    print_header("1. CHECKING CREDENTIALS FILE")

    creds_file = Path(__file__).parent.parent / "config" / "credentials_angelone.txt"

    if not creds_file.exists():
        print(f"✗ Credentials file not found: {creds_file}")
        print("\nCreate it using:")
        print(f"  cp {creds_file.parent}/credentials_angelone.template.txt {creds_file}")
        return False

    print(f"✓ Credentials file exists: {creds_file}")

    # Try to load credentials
    credentials = {}
    try:
        with open(creds_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    credentials[key.strip()] = value.strip()

        required_keys = ['api_key', 'client_code', 'mpin', 'totp_secret']
        missing_keys = [key for key in required_keys if key not in credentials]

        if missing_keys:
            print(f"✗ Missing required keys: {', '.join(missing_keys)}")
            return False

        print("✓ All required credentials found")
        print(f"  - api_key: {credentials['api_key'][:10]}...")
        print(f"  - client_code: {credentials['client_code']}")
        print(f"  - mpin: {'*' * len(credentials['mpin'])}")
        print(f"  - totp_secret: {credentials['totp_secret'][:10]}...")

        return True

    except Exception as e:
        print(f"✗ Error reading credentials: {e}")
        return False

def check_contracts_cache():
    """Check if contracts cache exists and is valid."""
    print_header("2. CHECKING CONTRACTS CACHE")

    cache_file = Path(__file__).parent.parent.parent / "contracts_cache.json"

    if not cache_file.exists():
        print(f"✗ Contracts cache not found: {cache_file}")
        print("\nRefresh contracts using:")
        print("  python refresh_contracts.py --broker angelone")
        return False

    print(f"✓ Contracts cache exists: {cache_file}")

    # Try to load and validate cache
    try:
        with open(cache_file, 'r') as f:
            cache = json.load(f)

        # Check structure
        if 'options' not in cache:
            print("✗ Invalid cache structure: missing 'options' key")
            return False

        if 'instruments' not in cache['options']:
            print("✗ Invalid cache structure: missing 'options.instruments' key")
            return False

        # Check if we have any instruments
        instruments = cache['options']['instruments']
        if not instruments:
            print("✗ Cache is empty")
            return False

        # Get first expiry
        first_expiry = list(instruments.keys())[0] if instruments else None
        if not first_expiry:
            print("✗ No expiry dates found in cache")
            return False

        # Count total instruments
        total_instruments = sum(
            len(strikes) for expiry_instruments in instruments.values()
            for strikes in expiry_instruments.values()
        )

        print("✓ Contracts cache is valid")
        print(f"  - Source broker: {cache.get('source_broker', 'N/A')}")
        print(f"  - Last updated: {cache.get('timestamp', 'N/A')}")
        print(f"  - Total expiries: {len(instruments)}")
        print(f"  - Next expiry: {first_expiry}")
        print(f"  - Total instruments: {total_instruments}")

        # Check mapping
        if 'mapping' in cache['options']:
            mapping = cache['options']['mapping']
            print(f"  - Current week: {mapping.get('current_week', 'N/A')}")
            print(f"  - Next week: {mapping.get('next_week', 'N/A')}")

        return True

    except json.JSONDecodeError as e:
        print(f"✗ Invalid JSON in cache file: {e}")
        return False
    except Exception as e:
        print(f"✗ Error reading cache: {e}")
        return False

def check_adapter_methods():
    """Check if AngelOne adapter has required methods."""
    print_header("3. CHECKING ANGELONE ADAPTER")

    try:
        from paper_trading.brokers.adapter.plugins.angelone import AngelOneAdapter
        from paper_trading.brokers.adapter.types import OrderType

        print("✓ AngelOne adapter imported successfully")

        # Check required methods
        required_methods = [
            'place_order',
            'modify_order',
            'cancel_order',
            'get_ltp',
            'get_quote',
            'get_spot_price',
            'get_order',
            'connect',
            'disconnect'
        ]

        missing_methods = [
            method for method in required_methods
            if not hasattr(AngelOneAdapter, method)
        ]

        if missing_methods:
            print(f"✗ Missing methods: {', '.join(missing_methods)}")
            return False

        print("✓ All required methods exist")
        for method in required_methods:
            print(f"  - {method}")

        # Check OrderType.SL exists
        if not hasattr(OrderType, 'SL'):
            print("✗ OrderType.SL not found (required for stop limit orders)")
            return False

        print("✓ OrderType.SL exists (stop limit order support)")

        return True

    except ImportError as e:
        print(f"✗ Failed to import AngelOne adapter: {e}")
        return False
    except Exception as e:
        print(f"✗ Error checking adapter: {e}")
        return False

def check_contract_manager():
    """Check if ContractManager works correctly."""
    print_header("4. CHECKING CONTRACT MANAGER")

    try:
        from paper_trading.core.contract_manager import ContractManager

        print("✓ ContractManager imported successfully")

        # Initialize
        manager = ContractManager()
        print("✓ ContractManager initialized")

        # Check if contracts loaded
        if not manager.options_instruments:
            print("✗ No instruments loaded")
            return False

        print("✓ Instruments loaded")

        # Get current week expiry
        current_week = manager.get_options_expiry('current_week')
        if not current_week:
            print("✗ Could not get current week expiry")
            return False

        print(f"✓ Current week expiry: {current_week}")

        # Try to get a sample contract
        expiries = list(manager.options_instruments.keys())
        if not expiries:
            print("✗ No expiries available")
            return False

        sample_expiry = expiries[0]
        strikes = list(manager.options_instruments[sample_expiry].keys())

        if not strikes:
            print("✗ No strikes available")
            return False

        sample_strike = int(strikes[0])
        sample_contract = manager.get_option_contract(sample_expiry, sample_strike, 'CE')

        if not sample_contract:
            print("✗ Could not get sample contract")
            return False

        if 'token' not in sample_contract:
            print("✗ Sample contract missing token")
            return False

        print("✓ Sample contract retrieved successfully")
        print(f"  - Expiry: {sample_expiry}")
        print(f"  - Strike: {sample_strike}")
        print(f"  - Token: {sample_contract['token']}")

        return True

    except ImportError as e:
        print(f"✗ Failed to import ContractManager: {e}")
        return False
    except Exception as e:
        print(f"✗ Error checking ContractManager: {e}")
        return False

def check_logs_directory():
    """Check if logs directory exists."""
    print_header("5. CHECKING LOGS DIRECTORY")

    log_dir = Path(__file__).parent / "logs"

    if not log_dir.exists():
        print(f"Creating logs directory: {log_dir}")
        log_dir.mkdir(parents=True, exist_ok=True)
        print("✓ Logs directory created")
    else:
        print(f"✓ Logs directory exists: {log_dir}")

    # Check write permissions
    try:
        test_file = log_dir / "test_write.tmp"
        test_file.write_text("test")
        test_file.unlink()
        print("✓ Logs directory is writable")
        return True
    except Exception as e:
        print(f"✗ Logs directory is not writable: {e}")
        return False

def check_test_file():
    """Check if test file exists."""
    print_header("6. CHECKING TEST FILE")

    test_file = Path(__file__).parent / "test_stop_limit_modify.py"

    if not test_file.exists():
        print(f"✗ Test file not found: {test_file}")
        return False

    print(f"✓ Test file exists: {test_file}")
    print(f"  Size: {test_file.stat().st_size} bytes")

    return True

def main():
    """Run all checks."""
    print("\n" + "#"*80)
    print("#" + " "*78 + "#")
    print("#" + " "*20 + "STOP LIMIT ORDER TEST - VERIFICATION" + " "*22 + "#")
    print("#" + " "*78 + "#")
    print("#"*80)

    checks = [
        ("Credentials", check_credentials),
        ("Contracts Cache", check_contracts_cache),
        ("AngelOne Adapter", check_adapter_methods),
        ("Contract Manager", check_contract_manager),
        ("Logs Directory", check_logs_directory),
        ("Test File", check_test_file)
    ]

    results = {}

    for check_name, check_func in checks:
        try:
            results[check_name] = check_func()
        except Exception as e:
            print(f"\n✗ Unexpected error in {check_name}: {e}")
            results[check_name] = False

    # Print summary
    print_header("VERIFICATION SUMMARY")

    all_passed = True
    for check_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status:>10}  {check_name}")
        if not passed:
            all_passed = False

    print("\n" + "="*80)

    if all_passed:
        print("\n🎉 ALL CHECKS PASSED!")
        print("\nYou can now run the test:")
        print("  python -m pytest paper_trading/tests/test_stop_limit_modify.py -v -s")
    else:
        print("\n⚠️  SOME CHECKS FAILED")
        print("\nPlease fix the issues above before running the test.")
        print("\nQuick fixes:")
        print("  1. Create credentials file:")
        print("     cp paper_trading/config/credentials_angelone.template.txt \\")
        print("        paper_trading/config/credentials_angelone.txt")
        print("\n  2. Refresh contracts:")
        print("     python refresh_contracts.py --broker angelone")

    print("\n" + "="*80 + "\n")

    return 0 if all_passed else 1

if __name__ == '__main__':
    sys.exit(main())
