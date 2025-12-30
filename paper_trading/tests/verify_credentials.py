"""
Verify Credentials Files - Quick test before Monday trading
Tests that both Zerodha and AngelOne credentials can be loaded correctly
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))


def load_credentials_from_file(filepath):
    """
    Load credentials from file (copied from zerodha_connection.py to avoid import issues)

    Format: key = value (one per line)
    """
    credentials = {}

    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue

                # Parse key = value
                if '=' in line:
                    key, value = line.split('=', 1)
                    credentials[key.strip()] = value.strip()

        return credentials
    except Exception as e:
        print(f"Error loading credentials: {e}")
        return None


def test_zerodha_credentials():
    """Test Zerodha credentials file"""
    print("\n" + "="*80)
    print("TESTING ZERODHA CREDENTIALS")
    print("="*80)

    creds_path = "paper_trading/config/credentials_zerodha.txt"

    if not Path(creds_path).exists():
        print(f"✗ FAIL: Credentials file not found: {creds_path}")
        return False

    print(f"[1/4] Loading credentials from: {creds_path}")
    creds = load_credentials_from_file(creds_path)

    if not creds:
        print(f"✗ FAIL: Could not load credentials")
        return False

    print(f"✓ Credentials loaded successfully")

    # Verify required keys
    print(f"\n[2/4] Verifying required keys...")
    required_keys = ['api_key', 'api_secret', 'user_id', 'user_password', 'totp_key']
    missing_keys = [key for key in required_keys if key not in creds]

    if missing_keys:
        print(f"✗ FAIL: Missing keys: {missing_keys}")
        return False

    print(f"✓ All required keys present: {required_keys}")

    # Verify values are not empty
    print(f"\n[3/4] Verifying credential values...")
    empty_keys = [key for key, value in creds.items() if not value or value.strip() == ""]

    if empty_keys:
        print(f"✗ FAIL: Empty values for keys: {empty_keys}")
        return False

    print(f"✓ All credentials have values")

    # Print masked values
    print(f"\n[4/4] Credential values (masked):")
    print(f"  api_key: {creds['api_key'][:4]}...{creds['api_key'][-4:]}")
    print(f"  api_secret: {creds['api_secret'][:4]}...{creds['api_secret'][-4:]}")
    print(f"  user_id: {creds['user_id']}")
    print(f"  user_password: {'*' * len(creds['user_password'])}")
    print(f"  totp_key: {creds['totp_key'][:4]}...{creds['totp_key'][-4:]}")

    print(f"\n✓ ZERODHA CREDENTIALS: READY")
    return True


def test_angelone_credentials():
    """Test AngelOne credentials file"""
    print("\n" + "="*80)
    print("TESTING ANGELONE CREDENTIALS")
    print("="*80)

    creds_path = "paper_trading/config/credentials_angelone.txt"

    if not Path(creds_path).exists():
        print(f"✗ FAIL: Credentials file not found: {creds_path}")
        return False

    print(f"[1/4] Loading credentials from: {creds_path}")
    creds = load_credentials_from_file(creds_path)

    if not creds:
        print(f"✗ FAIL: Could not load credentials")
        return False

    print(f"✓ Credentials loaded successfully")

    # Verify required keys
    print(f"\n[2/4] Verifying required keys...")
    required_keys = ['api_key', 'username', 'password', 'totp_token']
    missing_keys = [key for key in required_keys if key not in creds]

    if missing_keys:
        print(f"✗ FAIL: Missing keys: {missing_keys}")
        return False

    print(f"✓ All required keys present: {required_keys}")

    # Verify values are not empty
    print(f"\n[3/4] Verifying credential values...")
    empty_keys = [key for key, value in creds.items() if not value or value.strip() == ""]

    if empty_keys:
        print(f"✗ FAIL: Empty values for keys: {empty_keys}")
        return False

    print(f"✓ All credentials have values")

    # Print masked values
    print(f"\n[4/4] Credential values (masked):")
    print(f"  api_key: {creds['api_key'][:4]}...{creds['api_key'][-4:]}")
    print(f"  username: {creds['username']}")
    print(f"  password: {'*' * len(creds['password'])}")
    print(f"  totp_token: {creds['totp_token'][:4]}...{creds['totp_token'][-4:]}")

    print(f"\n✓ ANGELONE CREDENTIALS: READY")
    return True


def detect_broker_type(credentials):
    """
    Auto-detect broker type from credentials (copied from factory.py)
    """
    # Zerodha has: api_secret and user_id
    # AngelOne has: username (not user_id)
    has_api_secret = 'api_secret' in credentials
    has_username = 'username' in credentials
    has_user_id = 'user_id' in credentials

    if has_api_secret and has_user_id:
        return 'zerodha'
    elif has_username:
        return 'angelone'
    else:
        return 'unknown'


def test_broker_detection():
    """Test broker auto-detection"""
    print("\n" + "="*80)
    print("TESTING BROKER AUTO-DETECTION")
    print("="*80)

    # Test Zerodha detection
    print(f"\n[Zerodha] Loading credentials...")
    zerodha_creds = load_credentials_from_file("paper_trading/config/credentials_zerodha.txt")

    if zerodha_creds:
        detected_type = detect_broker_type(zerodha_creds)
        print(f"  Detected broker type: {detected_type}")

        if detected_type == 'zerodha':
            print(f"  ✓ Correctly detected as Zerodha")
        else:
            print(f"  ✗ FAIL: Expected 'zerodha', got '{detected_type}'")
            return False

    # Test AngelOne detection
    print(f"\n[AngelOne] Loading credentials...")
    angelone_creds = load_credentials_from_file("paper_trading/config/credentials_angelone.txt")

    if angelone_creds:
        detected_type = detect_broker_type(angelone_creds)
        print(f"  Detected broker type: {detected_type}")

        if detected_type == 'angelone':
            print(f"  ✓ Correctly detected as AngelOne")
        else:
            print(f"  ✗ FAIL: Expected 'angelone', got '{detected_type}'")
            return False

    print(f"\n✓ BROKER AUTO-DETECTION: WORKING")
    return True


def main():
    """Run all credential verification tests"""
    print("\n" + "#"*80)
    print("#" + " "*78 + "#")
    print("#" + " "*20 + "CREDENTIALS VERIFICATION - MONDAY READY CHECK" + " "*13 + "#")
    print("#" + " "*78 + "#")
    print("#"*80)

    # Test 1: Zerodha credentials
    zerodha_ok = test_zerodha_credentials()

    # Test 2: AngelOne credentials
    angelone_ok = test_angelone_credentials()

    # Test 3: Broker auto-detection
    detection_ok = test_broker_detection()

    # Final summary
    print("\n" + "="*80)
    print("MONDAY READINESS SUMMARY")
    print("="*80)
    print(f"Zerodha Credentials:     {'✓ READY' if zerodha_ok else '✗ NOT READY'}")
    print(f"AngelOne Credentials:    {'✓ READY' if angelone_ok else '✗ NOT READY'}")
    print(f"Broker Auto-Detection:   {'✓ WORKING' if detection_ok else '✗ NOT WORKING'}")
    print("="*80)

    all_ok = zerodha_ok and angelone_ok and detection_ok

    if all_ok:
        print("\n" + "🎉"*20)
        print("\n✓ ALL SYSTEMS READY FOR MONDAY TRADING!")
        print("\nYou can start paper trading with:")
        print("  1. Zerodha:  python runner.py --broker zerodha")
        print("  2. AngelOne: python runner.py --broker angelone")
        print("  3. Auto:     python runner.py  (auto-detects from credentials)")
        print("\n" + "🎉"*20)
    else:
        print("\n⚠️  SOME ISSUES DETECTED - Please fix before Monday")
        print("\nCheck the errors above and correct the credentials files.")

    print("\n" + "#"*80)

    return all_ok


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
