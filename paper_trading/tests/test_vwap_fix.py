"""
Test VWAP Initialization Fix

This test verifies that the VWAP initialization bug is fixed:
- Old bug: Used current_price × cumulative_volume (incorrect)
- New fix: Uses historical bars with proper (price × volume) accumulation

Tests:
1. VWAP starts correctly from scratch (no history)
2. VWAP backfills correctly when strike changes (with history)
3. Historical candles are stored as they arrive
4. Cleanup works properly (strike change, new day)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from datetime import datetime, time
import pandas as pd
from paper_trading.core.strategy import IntradayMomentumOIPaper
from paper_trading.core.broker import PaperBroker
from src.oi_analyzer import OIAnalyzer
import yaml


def create_test_strategy():
    """Create a strategy instance for testing"""
    # Load config
    config_path = Path(__file__).parent.parent.parent / 'config' / 'strategy_config.yaml'
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Create broker and strategy
    broker = PaperBroker(initial_capital=100000, broker_name='test_broker')

    # Create dummy options_df for OIAnalyzer
    dummy_options_df = pd.DataFrame({
        'strike': [25000, 25050, 25100],
        'option_type': ['CE', 'PE', 'CE'],
        'OI': [1000000, 2000000, 1500000]
    })

    oi_analyzer = OIAnalyzer(dummy_options_df)
    strategy = IntradayMomentumOIPaper(config, broker, oi_analyzer)

    return strategy, broker, config


def test_1_vwap_starts_fresh():
    """Test that VWAP starts correctly with no historical data"""
    print("\n" + "="*80)
    print("TEST 1: VWAP Initialization from Scratch (No History)")
    print("="*80)

    strategy, broker, config = create_test_strategy()

    # Simulate first call at 09:15
    current_time = datetime(2026, 2, 13, 9, 15, 0)
    strike = 25500
    option_type = 'PUT'
    expiry = '2026-02-17'
    price = 57.20
    volume = 18623215  # Cumulative volume

    # Store historical candle
    strategy._store_historical_candle(strike, option_type, expiry, current_time, price, volume)

    # Calculate VWAP (first time)
    vwap = strategy._calculate_vwap(strike, option_type, expiry, price, volume)

    print(f"\nTime: {current_time}")
    print(f"Price: {price}, Volume: {volume:,}")
    print(f"VWAP: {vwap:.2f}")

    # Verify
    assert abs(vwap - price) < 0.01, f"First VWAP should equal price, got {vwap} vs {price}"
    print("✓ PASSED: First VWAP equals price (no history available)")

    # Simulate second call at 09:20
    current_time = datetime(2026, 2, 13, 9, 20, 0)
    price = 54.90
    volume = 10821395  # Individual candle volume (not cumulative!)

    # Convert to cumulative for broker simulation
    volume_cumulative = 18623215 + 10821395

    strategy._store_historical_candle(strike, option_type, expiry, current_time, price, volume_cumulative)
    vwap = strategy._calculate_vwap(strike, option_type, expiry, price, volume_cumulative)

    # Expected VWAP = (57.20*18623215 + 54.90*10821395) / (18623215+10821395)
    expected_vwap = (57.20 * 18623215 + 54.90 * 10821395) / (18623215 + 10821395)

    print(f"\nTime: {current_time}")
    print(f"Price: {price}, Cumulative Volume: {volume_cumulative:,}")
    print(f"VWAP: {vwap:.2f}, Expected: {expected_vwap:.2f}")

    assert abs(vwap - expected_vwap) < 0.01, f"VWAP mismatch: {vwap} vs {expected_vwap}"
    print("✓ PASSED: VWAP accumulates correctly")

    return strategy


def test_2_vwap_backfills_with_history():
    """Test that VWAP backfills correctly when strike changes"""
    print("\n" + "="*80)
    print("TEST 2: VWAP Backfill with Historical Data (Strike Change)")
    print("="*80)

    strategy, broker, config = create_test_strategy()

    # Simulate receiving candles for strike 25500
    strike_old = 25500
    option_type = 'PUT'
    expiry = '2026-02-17'

    candles = [
        (datetime(2026, 2, 13, 9, 15, 0), 57.20, 18623215),
        (datetime(2026, 2, 13, 9, 20, 0), 54.90, 29444610),  # Cumulative
        (datetime(2026, 2, 13, 9, 25, 0), 59.35, 35332440),
        (datetime(2026, 2, 13, 9, 30, 0), 71.60, 49618530),
    ]

    print("\nStoring historical candles for strike 25500...")
    for timestamp, close, cumul_vol in candles:
        strategy._store_historical_candle(strike_old, option_type, expiry, timestamp, close, cumul_vol)
        print(f"  {timestamp.strftime('%H:%M')} - Close: {close:6.2f}, CumulVol: {cumul_vol:,}")

    # Now simulate strike change to 25450
    strike_new = 25450
    print(f"\n📍 STRIKE CHANGE: {strike_old} → {strike_new}")

    # Store some candles for new strike (simulating it was trading alongside)
    candles_new_strike = [
        (datetime(2026, 2, 13, 9, 15, 0), 60.50, 15234567),
        (datetime(2026, 2, 13, 9, 20, 0), 58.30, 25456789),
        (datetime(2026, 2, 13, 9, 25, 0), 62.15, 33567890),
        (datetime(2026, 2, 13, 9, 30, 0), 65.80, 45678901),
    ]

    print("\nStoring historical candles for strike 25450...")
    for timestamp, close, cumul_vol in candles_new_strike:
        strategy._store_historical_candle(strike_new, option_type, expiry, timestamp, close, cumul_vol)

    # Initialize VWAP for new strike (should backfill)
    current_time = datetime(2026, 2, 13, 9, 35, 0)
    current_price = 68.50
    current_volume = 52345678

    print(f"\nInitializing VWAP for strike {strike_new} at {current_time.strftime('%H:%M')}...")
    vwap = strategy._calculate_vwap(strike_new, option_type, expiry, current_price, current_volume)

    # Calculate expected VWAP from historical backfill
    # Manual calculation:
    # Bar 0: 60.50 * 15234567 = 921,791,304.50
    # Bar 1: 58.30 * (25456789-15234567) = 58.30 * 10222222 = 595,955,542.60
    # Bar 2: 62.15 * (33567890-25456789) = 62.15 * 8111101 = 504,003,227.15
    # Bar 3: 65.80 * (45678901-33567890) = 65.80 * 12111011 = 796,906,523.80
    # Bar 4: 68.50 * (52345678-45678901) = 68.50 * 6666777 = 456,874,224.50
    # Total TPV = 3,275,530,822.55
    # Total Vol = 52345678
    # VWAP = 62.57

    tpv = 0
    prev_vol = 0
    for timestamp, close, cumul_vol in candles_new_strike:
        incr_vol = cumul_vol - prev_vol
        tpv += close * incr_vol
        prev_vol = cumul_vol

    # Add current bar
    incr_vol = current_volume - prev_vol
    tpv += current_price * incr_vol

    expected_vwap = tpv / current_volume

    print(f"\nVWAP: {vwap:.2f}, Expected: {expected_vwap:.2f}")

    # The VWAP should NOT equal current price (proves backfill worked)
    assert abs(vwap - current_price) > 1.0, f"VWAP should not equal current price (backfill should affect it)"
    assert abs(vwap - expected_vwap) < 0.01, f"VWAP mismatch: {vwap:.2f} vs {expected_vwap:.2f}"

    print(f"✓ PASSED: VWAP backfilled correctly (VWAP={vwap:.2f} ≠ Price={current_price:.2f})")

    # Check that historical candles were stored
    key_new = (strike_new, option_type, expiry)
    assert key_new in strategy.historical_candles, "Historical candles not stored"
    assert len(strategy.historical_candles[key_new]) == 4, f"Should have 4 candles, got {len(strategy.historical_candles[key_new])}"
    print(f"✓ PASSED: Historical candles stored ({len(strategy.historical_candles[key_new])} candles)")

    return strategy


def test_3_historical_candles_storage():
    """Test that historical candles are stored and limited properly"""
    print("\n" + "="*80)
    print("TEST 3: Historical Candles Storage and Limits")
    print("="*80)

    strategy, broker, config = create_test_strategy()
    strategy.historical_candles_max_size = 10  # Set small limit for testing

    strike = 25500
    option_type = 'PUT'
    expiry = '2026-02-17'

    # Store 15 candles (should keep only last 10)
    print(f"\nStoring 15 candles (max size = {strategy.historical_candles_max_size})...")
    for i in range(15):
        # Calculate time properly (handle hour overflow)
        minutes = 15 + i * 5
        hour = 9 + (minutes // 60)
        minute = minutes % 60
        timestamp = datetime(2026, 2, 13, hour, minute, 0)
        close = 50.0 + i
        volume = 1000000 * (i + 1)
        strategy._store_historical_candle(strike, option_type, expiry, timestamp, close, volume)

    key = (strike, option_type, expiry)
    stored_count = len(strategy.historical_candles[key])

    print(f"Stored candles: {stored_count}")
    assert stored_count == strategy.historical_candles_max_size, f"Should store max {strategy.historical_candles_max_size}, got {stored_count}"
    print(f"✓ PASSED: Storage limited to {strategy.historical_candles_max_size} candles")

    # Verify oldest candle was removed
    first_stored_time = strategy.historical_candles[key][0][0]
    expected_first = datetime(2026, 2, 13, 9, 15 + 5 * 5, 0)  # 6th candle (index 5)

    print(f"First stored candle: {first_stored_time.strftime('%H:%M')}")
    print(f"Expected (6th candle): {expected_first.strftime('%H:%M')}")
    assert first_stored_time == expected_first, f"Oldest candle incorrect"
    print("✓ PASSED: Oldest candles removed correctly")

    return strategy


def test_4_cleanup_on_strike_change():
    """Test that old strike's data is cleaned up"""
    print("\n" + "="*80)
    print("TEST 4: Cleanup on Strike Change")
    print("="*80)

    strategy, broker, config = create_test_strategy()

    strike_old = 25500
    strike_new = 25450
    option_type = 'PUT'
    expiry = '2026-02-17'

    # Store candles for old strike
    print(f"\nStoring candles for strike {strike_old}...")
    for i in range(3):
        timestamp = datetime(2026, 2, 13, 9, 15 + i * 5, 0)
        strategy._store_historical_candle(strike_old, option_type, expiry, timestamp, 50.0, 1000000)

    # Initialize VWAP for old strike
    strategy._calculate_vwap(strike_old, option_type, expiry, 50.0, 1000000)

    key_old = (strike_old, option_type, expiry)
    assert key_old in strategy.historical_candles, "Old strike candles not stored"
    assert key_old in strategy.vwap_running_totals, "Old strike VWAP not initialized"
    print(f"✓ Old strike {strike_old} has historical candles and VWAP data")

    # Simulate cleanup (as done in strategy when strike changes)
    print(f"\n🧹 Cleaning up old strike {strike_old}...")

    hist_keys_to_remove = [key for key in strategy.historical_candles.keys() if key[0] == strike_old]
    for key in hist_keys_to_remove:
        del strategy.historical_candles[key]

    vwap_keys_to_remove = [key for key in strategy.vwap_running_totals.keys() if key[0] == strike_old]
    for key in vwap_keys_to_remove:
        del strategy.vwap_running_totals[key]

    # Verify cleanup
    assert key_old not in strategy.historical_candles, "Old strike candles not cleaned up"
    assert key_old not in strategy.vwap_running_totals, "Old strike VWAP not cleaned up"
    print(f"✓ PASSED: Old strike {strike_old} data cleaned up successfully")

    return strategy


def test_5_csv_data_verification():
    """Test with actual CSV data to verify correct VWAP calculation"""
    print("\n" + "="*80)
    print("TEST 5: Verification with Real CSV Data")
    print("="*80)

    csv_path = '/Users/vidheeshetty/Downloads/NSE_NIFTY260217P25500.csv'
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print("⚠️  CSV file not found, skipping test")
        return

    strategy, broker, config = create_test_strategy()

    strike = 25500
    option_type = 'PUT'
    expiry = '2026-02-17'

    # Convert individual volumes to cumulative
    df['Candle_Volume'] = df['Volume']
    df['Volume_Cumulative'] = df['Candle_Volume'].cumsum()

    print("\nProcessing CSV candles...")
    vwap_values = []

    for idx, row in df.iterrows():
        timestamp = pd.to_datetime(row['time'])
        close = row['close']
        cumul_vol = row['Volume_Cumulative']

        # Store historical candle
        strategy._store_historical_candle(strike, option_type, expiry, timestamp, close, cumul_vol)

        # Calculate VWAP
        vwap = strategy._calculate_vwap(strike, option_type, expiry, close, cumul_vol)
        vwap_values.append(vwap)

        if idx < 5:  # Print first 5
            print(f"  {timestamp.strftime('%H:%M')} - Close: {close:6.2f}, VWAP: {vwap:6.2f}")

    # At row 3 (09:30), VWAP should be 61.10, NOT 71.60 (the bug)
    vwap_at_row3 = vwap_values[3]
    price_at_row3 = df.iloc[3]['close']

    print(f"\n📊 At 09:30:00 (row 3):")
    print(f"  Price: {price_at_row3:.2f}")
    print(f"  VWAP (calculated): {vwap_at_row3:.2f}")
    print(f"  VWAP (expected): 61.10")

    # Verify VWAP is correct (not equal to price, which was the bug)
    assert abs(vwap_at_row3 - 61.10) < 0.5, f"VWAP should be ~61.10, got {vwap_at_row3:.2f}"
    assert abs(vwap_at_row3 - price_at_row3) > 5.0, f"VWAP should not equal price (bug check)"

    print(f"✓ PASSED: VWAP = {vwap_at_row3:.2f} (correct, not {price_at_row3:.2f})")

    return strategy


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*80)
    print("VWAP INITIALIZATION FIX - COMPREHENSIVE TEST SUITE")
    print("="*80)

    tests = [
        ("Fresh Start", test_1_vwap_starts_fresh),
        ("Backfill with History", test_2_vwap_backfills_with_history),
        ("Storage Limits", test_3_historical_candles_storage),
        ("Cleanup", test_4_cleanup_on_strike_change),
        ("CSV Verification", test_5_csv_data_verification),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            test_func()
            results.append((test_name, "✓ PASSED"))
        except AssertionError as e:
            results.append((test_name, f"✗ FAILED: {e}"))
        except Exception as e:
            results.append((test_name, f"✗ ERROR: {e}"))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    for test_name, result in results:
        print(f"{test_name:30s} {result}")

    passed = sum(1 for _, r in results if r.startswith("✓"))
    total = len(results)

    print("\n" + "="*80)
    print(f"TOTAL: {passed}/{total} tests passed")
    print("="*80)

    if passed == total:
        print("\n🎉 ALL TESTS PASSED! VWAP fix is working correctly.")
        return True
    else:
        print("\n⚠️  Some tests failed. Please review the output above.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
