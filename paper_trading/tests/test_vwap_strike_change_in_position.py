"""
Test: VWAP state preserved when strike changes while in position

Scenario:
  1. Strategy enters a position at 25300 PE with VWAP built up over several candles
  2. Spot price is artificially raised by 50 to force a new ATM strike (25350)
  3. on_candle() is called — STEP 2 should be SKIPPED (open position exists)
     → no daily_strike update, no VWAP reset, no double-count
  4. VWAP is updated only once via _update_vwap_for_positions (exit monitor path)
  5. Position is closed
  6. on_candle() is called again — normal behavior resumes
     → strike updates to new ATM, cleanup of old strike, VWAP re-initialized
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from datetime import datetime
from unittest.mock import MagicMock, patch
import pandas as pd
import yaml

from paper_trading.core.strategy import IntradayMomentumOIPaper
from paper_trading.core.broker import PaperBroker
from src.oi_analyzer import OIAnalyzer


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def make_strategy():
    config_path = Path(__file__).parent.parent.parent / 'config' / 'strategy_config.yaml'
    with open(config_path) as f:
        config = yaml.safe_load(f)

    broker = PaperBroker(initial_capital=500000, broker_name='test')
    dummy_df = pd.DataFrame({
        'strike': [25250, 25300, 25350],
        'option_type': ['PE', 'PE', 'PE'],
        'OI': [1000000, 2000000, 1500000]
    })
    oi_analyzer = OIAnalyzer(dummy_df)
    strategy = IntradayMomentumOIPaper(config, broker, oi_analyzer)

    # Set up daily state as if on_new_day already ran
    strategy.daily_direction   = 'PE'
    strategy.daily_strike      = 25300
    strategy.daily_expiry      = '2026-03-06'
    strategy.daily_trade_taken = False
    strategy.vwap_initialized  = False
    strategy.current_date      = datetime(2026, 3, 2).date()  # prevent on_new_day trigger

    return strategy, broker


def build_vwap_state(strategy, strike, n_candles=5):
    """Simulate n_candles of VWAP accumulation for a strike using _calculate_vwap_ohlc."""
    key = (strike, 'PE', '2026-03-06')
    strategy.vwap_running_totals[key] = {
        'tpv': 0.0,
        'volume': 0.0,
        'prev_cumulative_volume': 0.0,
        'is_interval_volume': True
    }

    base_close  = 80.0
    base_volume = 500_000

    for i in range(n_candles):
        close  = base_close + i * 2
        volume = base_volume + i * 50_000
        ohlc   = {'open': close - 1, 'high': close + 2, 'low': close - 2, 'close': close}
        strategy._calculate_vwap_ohlc(strike, 'PE', '2026-03-06', ohlc, volume)

    totals = strategy.vwap_running_totals[key]
    vwap   = totals['tpv'] / totals['volume']
    print(f"  Built VWAP state: tpv={totals['tpv']:,.0f}, volume={totals['volume']:,.0f}, vwap={vwap:.4f}")
    return vwap


def make_options_data(spot, strikes=(25250, 25300, 25350)):
    """Minimal options DataFrame for on_candle."""
    rows = []
    for s in strikes:
        rows.append({'strike': s, 'option_type': 'PE', 'OI': 1_500_000,
                     'LTP': 80.0, 'expiry': '2026-03-06'})
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────
# Test
# ─────────────────────────────────────────────

def test_vwap_preserved_during_strike_change_in_position():
    print("\n" + "="*80)
    print("TEST: VWAP state preserved when strike changes while in position")
    print("="*80)

    strategy, broker = make_strategy()
    expiry  = '2026-03-06'
    strike  = 25300
    key     = (strike, 'PE', expiry)

    # ── Phase 1: build up VWAP over 5 candles ──────────────────────────────
    print("\n[Phase 1] Building VWAP state for 25300 PE over 5 candles...")
    vwap_before = build_vwap_state(strategy, strike, n_candles=5)

    tpv_before    = strategy.vwap_running_totals[key]['tpv']
    volume_before = strategy.vwap_running_totals[key]['volume']
    print(f"  VWAP before position: {vwap_before:.4f}")

    # ── Phase 2: enter position ─────────────────────────────────────────────
    print(f"\n[Phase 2] Entering position at 25300 PE @ ₹{vwap_before:.2f}")
    position = broker.buy(
        strike=strike, option_type='PE', expiry=expiry,
        price=vwap_before, size=50, vwap=vwap_before, oi=1_500_000, oi_change=0.05
    )
    assert position is not None, "Buy failed"
    assert len(broker.get_open_positions()) == 1
    print(f"  Position open: {broker.get_open_positions()[0].strike} PE ✅")

    # ── Phase 3: spot +50 → new ATM = 25350, call on_candle ────────────────
    real_spot  = 25300.0
    fake_spot  = real_spot + 50      # forces new ATM to 25350
    current_time = datetime(2026, 3, 2, 10, 0, 0)
    options_data = make_options_data(fake_spot)

    print(f"\n[Phase 3] Calling on_candle with spot={fake_spot} (+50 forced)")
    print(f"  Expected: STEP 2 skipped entirely (open position), daily_strike stays 25300")
    print(f"  Expected: VWAP state for 25300 PE unchanged")

    # Patch adapter and internal candle fetch so on_candle doesn't hit network
    strategy.adapter = None   # adapter=None causes STEP 2 historical fetch to be skipped anyway
    with patch.object(strategy, '_fetch_current_strike_candle', return_value=None), \
         patch.object(strategy, 'oi_analyzer') as mock_oi:

        # Make oi_analyzer return 25350 as new ATM (spot+50 scenario)
        mock_oi.get_nearest_strike.return_value = 25350

        strategy.on_candle(current_time, fake_spot, options_data)

    # ── Assertions after on_candle with open position ───────────────────────
    print("\n[Assertions — in position]")

    # daily_strike must NOT have changed
    assert strategy.daily_strike == 25300, \
        f"daily_strike changed to {strategy.daily_strike} — STEP 2 was NOT skipped!"
    print(f"  ✅ daily_strike unchanged: {strategy.daily_strike}")

    # VWAP key must still exist
    assert key in strategy.vwap_running_totals, \
        "VWAP key was deleted — state was reset!"
    print(f"  ✅ VWAP key exists for 25300 PE")

    # tpv and volume must be identical (no double-count, no reset)
    tpv_after    = strategy.vwap_running_totals[key]['tpv']
    volume_after = strategy.vwap_running_totals[key]['volume']
    assert tpv_after == tpv_before, \
        f"TPV changed: {tpv_before} → {tpv_after} (double-count or reset!)"
    assert volume_after == volume_before, \
        f"Volume changed: {volume_before} → {volume_after} (double-count or reset!)"
    print(f"  ✅ No double-count: tpv={tpv_after:,.0f}, volume={volume_after:,.0f}")

    # ── Phase 4: simulate exit monitor updating VWAP (once) ─────────────────
    print(f"\n[Phase 4] Simulating exit monitor: _update_vwap_for_positions (once at 5-min boundary)")
    new_candle_ohlc = {'open': 89.0, 'high': 93.0, 'low': 87.0, 'close': 91.0}
    new_volume      = 600_000

    with patch.object(strategy, '_fetch_current_strike_candle',
                      return_value={**new_candle_ohlc, 'volume': new_volume, 'oi': 1_600_000}):
        strategy._update_vwap_for_positions(current_time)

    tpv_after_update    = strategy.vwap_running_totals[key]['tpv']
    volume_after_update = strategy.vwap_running_totals[key]['volume']
    vwap_after_update   = tpv_after_update / volume_after_update

    assert volume_after_update == volume_before + new_volume, \
        f"Volume should be +{new_volume}, got {volume_after_update - volume_before}"
    print(f"  ✅ VWAP updated once: {vwap_before:.4f} → {vwap_after_update:.4f}")
    print(f"     tpv={tpv_after_update:,.0f}, volume={volume_after_update:,.0f}")

    # ── Phase 5: close position ──────────────────────────────────────────────
    print(f"\n[Phase 5] Closing position (trailing stop hit)")
    broker.sell(position, price=95.0, vwap=vwap_after_update, oi=1_600_000, reason="Trailing Stop")
    assert len(broker.get_open_positions()) == 0
    print(f"  ✅ Position closed, open_positions = []")

    # ── Phase 6: next on_candle — normal behavior resumes ───────────────────
    print(f"\n[Phase 6] Calling on_candle after exit (spot still {fake_spot})")
    print(f"  Expected: STEP 2 runs — daily_strike updates 25300 → 25350, cleanup 25300")

    current_time2 = datetime(2026, 3, 2, 10, 5, 0)

    with patch.object(strategy, '_fetch_current_strike_candle',
                      return_value={'open':91,'high':95,'low':89,'close':93,'volume':500000,'oi':1700000}), \
         patch.object(strategy, 'oi_analyzer') as mock_oi2, \
         patch.object(strategy, '_initialize_vwap_with_history', return_value=True) as mock_init, \
         patch.object(strategy, '_store_historical_candles_bulk'):

        mock_oi2.get_nearest_strike.return_value = 25350

        # Patch adapter so historical fetch block is skipped (adapter=None check in code)
        strategy.adapter = None

        strategy.on_candle(current_time2, fake_spot, options_data)

    print("\n[Assertions — post exit]")

    # daily_strike should now be 25350
    assert strategy.daily_strike == 25350, \
        f"daily_strike should be 25350 after exit, got {strategy.daily_strike}"
    print(f"  ✅ daily_strike updated to: {strategy.daily_strike}")

    # old key (25300) should be cleaned up
    assert key not in strategy.vwap_running_totals, \
        f"25300 PE VWAP key still exists after exit — cleanup did not run!"
    print(f"  ✅ 25300 PE VWAP state cleaned up")

    print("\n" + "="*80)
    print("ALL ASSERTIONS PASSED ✅")
    print("="*80)


if __name__ == '__main__':
    test_vwap_preserved_during_strike_change_in_position()
