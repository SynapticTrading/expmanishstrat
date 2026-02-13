"""
Standalone VWAP calculator — mirrors live trading logic in strategy._calculate_vwap()

Key rules (same as live):
  - price  = option close (LTP) at end of each 5-min candle
  - volume = CUMULATIVE volume reported by broker (from market open)
  - TPV    = Σ (price × incremental_volume)
  - VWAP   = TPV / total_incremental_volume
  - Resets every trading day at 9:15 AM
"""

from datetime import datetime, date, time, timedelta

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────
STRIKE      = 23000
OPTION_TYPE = "CALL"
EXPIRY      = "2025-02-27"
INTERVAL    = 5          # minutes per candle
MARKET_OPEN = time(9, 15)
MARKET_CLOSE= time(15, 30)

# ──────────────────────────────────────────────
# Simulated 5-min candle data
# Each row: (cumulative_volume_from_broker, close_price)
# Volume is CUMULATIVE — same format as live broker feed
# ──────────────────────────────────────────────
SIMULATED_CANDLES = [
    # (cumul_vol, close_price)
    (120,   185.50),   # 09:15
    (280,   187.20),   # 09:20
    (410,   186.00),   # 09:25
    (590,   189.75),   # 09:30
    (740,   191.00),   # 09:35
    (860,   190.50),   # 09:40
    (1050,  192.30),   # 09:45
    (1200,  193.80),   # 09:50
    (1340,  193.00),   # 09:55
    (1480,  194.50),   # 10:00
    (1600,  195.20),   # 10:05
    (1750,  194.00),   # 10:10
    (1870,  193.50),   # 10:15
    (2000,  192.80),   # 10:20
    (2120,  191.60),   # 10:25
]


# ──────────────────────────────────────────────
# VWAP State  (mirrors self.vwap_running_totals)
# ──────────────────────────────────────────────
vwap_state = {}


def calculate_vwap(strike, option_type, expiry, price, cumul_volume):
    """
    Exact copy of strategy._calculate_vwap() logic.
    Uses cumulative broker volume → computes incremental delta.
    """
    key = (strike, option_type, expiry)

    # First time seeing this option — initialise state
    if key not in vwap_state:
        vwap_state[key] = {
            'tpv':                    0.0,
            'volume':                 0.0,
            'prev_cumulative_volume': 0.0,
        }

    prev_cumul   = vwap_state[key]['prev_cumulative_volume']
    incr_volume  = cumul_volume - prev_cumul          # delta since last candle

    # Running totals
    vwap_state[key]['tpv']    += price * incr_volume
    vwap_state[key]['volume'] += incr_volume
    vwap_state[key]['prev_cumulative_volume'] = cumul_volume

    total_vol = vwap_state[key]['volume']
    if total_vol > 0:
        return vwap_state[key]['tpv'] / total_vol
    else:
        return price   # fallback


# ──────────────────────────────────────────────
# Run simulation with detailed logs
# ──────────────────────────────────────────────
def run():
    print("=" * 70)
    print(f"  STANDALONE VWAP TEST — {OPTION_TYPE} {STRIKE} exp:{EXPIRY}")
    print(f"  Logic: mirrors live strategy._calculate_vwap()")
    print(f"  Candle interval: {INTERVAL} min  |  Volume: CUMULATIVE (broker)")
    print("=" * 70)
    print()

    header = f"{'Time':<8} {'CumulVol':>10} {'IncrVol':>10} {'Price':>8} {'TPV_added':>12} {'RunTPV':>12} {'RunVol':>10} {'VWAP':>8}"
    print(header)
    print("-" * len(header))

    # Generate timestamps starting at 09:15
    base_dt = datetime.combine(date.today(), MARKET_OPEN)

    for i, (cumul_vol, price) in enumerate(SIMULATED_CANDLES):
        candle_time = base_dt + timedelta(minutes=i * INTERVAL)
        ts          = candle_time.strftime("%H:%M")

        key = (STRIKE, OPTION_TYPE, EXPIRY)

        # Snapshot state BEFORE update (for logging the delta clearly)
        prev_cumul  = vwap_state.get(key, {}).get('prev_cumulative_volume', 0.0)
        prev_tpv    = vwap_state.get(key, {}).get('tpv', 0.0)
        prev_vol    = vwap_state.get(key, {}).get('volume', 0.0)

        incr_vol    = cumul_vol - prev_cumul
        tpv_added   = price * incr_vol

        vwap = calculate_vwap(STRIKE, OPTION_TYPE, EXPIRY, price, cumul_vol)

        run_tpv = vwap_state[key]['tpv']
        run_vol = vwap_state[key]['volume']

        print(
            f"{ts:<8} {cumul_vol:>10,} {incr_vol:>10,} "
            f"{price:>8.2f} {tpv_added:>12,.2f} "
            f"{run_tpv:>12,.2f} {run_vol:>10,.0f} {vwap:>8.2f}"
        )

    # ── Final summary ──────────────────────────────────────────────────────
    key      = (STRIKE, OPTION_TYPE, EXPIRY)
    state    = vwap_state[key]
    final_vwap = state['tpv'] / state['volume']

    print()
    print("=" * 70)
    print("  FINAL STATE")
    print("=" * 70)
    print(f"  Total Incremental Volume : {state['volume']:,.0f}")
    print(f"  Total TPV                : {state['tpv']:,.2f}")
    print(f"  Final VWAP               : {final_vwap:.4f}")
    print()
    print("  FORMULA USED:")
    print("    incremental_volume = cumul_vol(t) - cumul_vol(t-1)")
    print("    TPV               += price × incremental_volume")
    print("    VWAP               = Σ TPV / Σ incremental_volume")
    print()
    print("  NOTE: price = LTP/close only (no H/L — live feed has no candle OHLC)")
    print("        This differs from backtest VWAP which uses (H+L+C)/3")
    print("=" * 70)


if __name__ == "__main__":
    run()
