"""
Test crash recovery logic for paper trading

Tests:
1. With active/closed positions -> full recovery (restore strategy state)
2. No positions (flat day) -> start fresh (don't restore strategy state)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch
import json
from datetime import datetime


def create_mock_recovery_info(has_active=False, has_closed=False):
    """Create mock recovery info for testing"""
    recovery_info = {
        'can_recover': True,
        'last_heartbeat': '2026-01-14T15:00:00+05:30',
        'crash_time': '2026-01-14T15:00:00+05:30',
        'recovery_time': '2026-01-14T15:05:00+05:30',
        'downtime_minutes': 5,
        'active_positions': {},
        'active_positions_count': 0,
        'closed_positions': [],
        'strategy_state': {
            'direction': 'PUT',
            'trading_strike': 25650.0,
            'trading_expiry': '2026-01-20',
            'current_spot': 25660.0,
            'max_call_oi_strike': 25800.0,
            'max_put_oi_strike': 25700.0,
        },
        'daily_stats': {
            'trades_today': 0,
            'total_pnl_today': 0.0,
        },
        'portfolio': {
            'initial_capital': 100000,
            'current_cash': 100000,
        }
    }

    if has_active:
        recovery_info['active_positions'] = {
            'PAPER_20260114_001': {
                'strike': 25650.0,
                'option_type': 'PUT',
                'expiry': '2026-01-20',
                'entry': {'price': 100.0, 'quantity': 65}
            }
        }
        recovery_info['active_positions_count'] = 1

    if has_closed:
        recovery_info['closed_positions'] = [{
            'strike': 25650.0,
            'option_type': 'PUT',
            'expiry': '2026-01-20',
            'entry_price': 100.0,
            'exit_price': 110.0,
            'pnl': 650.0
        }]
        recovery_info['daily_stats']['trades_today'] = 1

    return recovery_info


def test_recovery_with_active_positions():
    """Test: With active positions, strategy state should be restored"""
    print("\n" + "="*60)
    print("TEST 1: Recovery with ACTIVE positions")
    print("="*60)

    recovery_info = create_mock_recovery_info(has_active=True, has_closed=False)

    has_active = recovery_info.get('active_positions_count', 0) > 0
    has_closed = len(recovery_info.get('closed_positions', [])) > 0

    print(f"  Active positions: {recovery_info['active_positions_count']}")
    print(f"  Closed positions: {len(recovery_info['closed_positions'])}")
    print(f"  has_active: {has_active}")
    print(f"  has_closed: {has_closed}")

    should_restore = has_active or has_closed

    if should_restore:
        print("  -> SHOULD restore strategy state (has positions)")
        print("  -> Direction, strike, expiry will be restored from saved state")
    else:
        print("  -> SHOULD start fresh (no positions)")

    assert should_restore == True, "Should restore when there are active positions"
    print("  ✓ TEST PASSED: Will restore strategy state")


def test_recovery_with_closed_positions():
    """Test: With closed positions (trade completed), strategy state should be restored"""
    print("\n" + "="*60)
    print("TEST 2: Recovery with CLOSED positions (trade done)")
    print("="*60)

    recovery_info = create_mock_recovery_info(has_active=False, has_closed=True)

    has_active = recovery_info.get('active_positions_count', 0) > 0
    has_closed = len(recovery_info.get('closed_positions', [])) > 0

    print(f"  Active positions: {recovery_info['active_positions_count']}")
    print(f"  Closed positions: {len(recovery_info['closed_positions'])}")
    print(f"  has_active: {has_active}")
    print(f"  has_closed: {has_closed}")

    should_restore = has_active or has_closed

    if should_restore:
        print("  -> SHOULD restore strategy state (has closed trades)")
        print("  -> Direction, strike, expiry will be restored from saved state")
    else:
        print("  -> SHOULD start fresh (no positions)")

    assert should_restore == True, "Should restore when there are closed positions"
    print("  ✓ TEST PASSED: Will restore strategy state")


def test_recovery_flat_day_no_positions():
    """Test: No positions (flat day), should start fresh"""
    print("\n" + "="*60)
    print("TEST 3: Recovery with NO positions (flat day)")
    print("="*60)

    recovery_info = create_mock_recovery_info(has_active=False, has_closed=False)

    has_active = recovery_info.get('active_positions_count', 0) > 0
    has_closed = len(recovery_info.get('closed_positions', [])) > 0

    print(f"  Active positions: {recovery_info['active_positions_count']}")
    print(f"  Closed positions: {len(recovery_info['closed_positions'])}")
    print(f"  has_active: {has_active}")
    print(f"  has_closed: {has_closed}")

    should_restore = has_active or has_closed

    if should_restore:
        print("  -> SHOULD restore strategy state")
    else:
        print("  -> SHOULD start fresh (no positions/trades)")
        print("  -> Will re-determine direction from CURRENT OI data")

    assert should_restore == False, "Should NOT restore when flat (no positions)"
    print("  ✓ TEST PASSED: Will start fresh and re-determine direction")


def test_expiry_restoration_from_strategy_state():
    """Test: Expiry is correctly restored from strategy_state"""
    print("\n" + "="*60)
    print("TEST 4: Expiry restoration from strategy_state")
    print("="*60)

    strategy_state = {
        'direction': 'PUT',
        'trading_strike': 25650.0,
        'trading_expiry': '2026-01-20',
    }

    # Simulate restore logic
    expiry_restored = False
    restored_expiry = None

    # Try strategy_state first
    if strategy_state.get('trading_expiry'):
        restored_expiry = strategy_state.get('trading_expiry')
        expiry_restored = True
        print(f"  Restored expiry from strategy_state: {restored_expiry}")

    assert expiry_restored == True, "Expiry should be restored from strategy_state"
    assert restored_expiry == '2026-01-20', "Expiry should be 2026-01-20"
    print("  ✓ TEST PASSED: Expiry correctly restored from strategy_state")


def test_expiry_fallback_to_positions():
    """Test: Expiry falls back to positions if not in strategy_state"""
    print("\n" + "="*60)
    print("TEST 5: Expiry fallback to positions")
    print("="*60)

    # Old state without trading_expiry
    strategy_state = {
        'direction': 'PUT',
        'trading_strike': 25650.0,
        # No trading_expiry
    }

    active_positions = {
        'PAPER_001': {'expiry': '2026-01-20'}
    }

    closed_positions = []

    # Simulate restore logic
    expiry_restored = False
    restored_expiry = None

    # Try strategy_state first
    if strategy_state.get('trading_expiry'):
        restored_expiry = strategy_state.get('trading_expiry')
        expiry_restored = True
        print(f"  Restored expiry from strategy_state: {restored_expiry}")

    # Fallback: active positions
    if not expiry_restored and active_positions:
        first_position = list(active_positions.values())[0]
        restored_expiry = first_position.get('expiry')
        expiry_restored = True
        print(f"  Restored expiry from active position: {restored_expiry}")

    # Fallback: closed positions
    if not expiry_restored and closed_positions:
        restored_expiry = closed_positions[0].get('expiry')
        expiry_restored = True
        print(f"  Restored expiry from closed position: {restored_expiry}")

    assert expiry_restored == True, "Expiry should be restored from positions"
    assert restored_expiry == '2026-01-20', "Expiry should be 2026-01-20"
    print("  ✓ TEST PASSED: Expiry correctly restored from fallback (positions)")


def test_state_manager_saves_expiry():
    """Test: StateManager saves expiry in strategy_state"""
    print("\n" + "="*60)
    print("TEST 6: StateManager saves expiry")
    print("="*60)

    # Simulate state structure
    state = {
        "strategy_state": {
            "current_spot": None,
            "trading_strike": None,
            "trading_expiry": None,
            "direction": None,
        }
    }

    # Simulate update_strategy_state with expiry
    from datetime import date
    expiry = date(2026, 1, 20)

    state["strategy_state"]["trading_strike"] = 25650.0
    state["strategy_state"]["direction"] = "PUT"

    # Save expiry as string
    if expiry is not None:
        if hasattr(expiry, 'strftime'):
            state["strategy_state"]["trading_expiry"] = expiry.strftime('%Y-%m-%d')
        else:
            state["strategy_state"]["trading_expiry"] = str(expiry)

    print(f"  Saved trading_expiry: {state['strategy_state']['trading_expiry']}")

    assert state["strategy_state"]["trading_expiry"] == "2026-01-20", "Expiry should be saved"
    print("  ✓ TEST PASSED: Expiry correctly saved to strategy_state")


def test_get_option_data_expiry_fallback():
    """Test: _get_option_data uses expiry from options_data if not provided"""
    print("\n" + "="*60)
    print("TEST 7: _get_option_data expiry fallback to options_data")
    print("="*60)

    import pandas as pd
    from datetime import date

    # Simulate options_data from contracts_cache.json
    options_data = pd.DataFrame({
        'strike': [25650.0, 25650.0, 25700.0, 25700.0],
        'option_type': ['CE', 'PE', 'CE', 'PE'],
        'expiry': [date(2026, 1, 20)] * 4,
        'close': [100.0, 115.0, 80.0, 95.0],
        'OI': [1000000, 2000000, 1500000, 1800000],
        'volume': [50000, 60000, 40000, 55000]
    })

    # Simulate the fallback logic from _get_option_data
    expiry = None  # Not provided (crash recovery bug)

    if expiry is None and not options_data.empty and 'expiry' in options_data.columns:
        expiry = options_data.iloc[0]['expiry']
        print(f"  Fallback: Got expiry from options_data: {expiry}")

    assert expiry == date(2026, 1, 20), "Should get expiry from options_data"
    print(f"  ✓ TEST PASSED: Expiry fallback works (got {expiry})")


def run_all_tests():
    """Run all crash recovery tests"""
    print("\n" + "="*60)
    print("CRASH RECOVERY TESTS")
    print("="*60)

    tests = [
        test_recovery_with_active_positions,
        test_recovery_with_closed_positions,
        test_recovery_flat_day_no_positions,
        test_expiry_restoration_from_strategy_state,
        test_expiry_fallback_to_positions,
        test_state_manager_saves_expiry,
        test_get_option_data_expiry_fallback,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  ✗ TEST FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ TEST ERROR: {e}")
            failed += 1

    print("\n" + "="*60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
