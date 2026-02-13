"""
Live VWAP Calculator — Zerodha (READ-ONLY, NO TRADES)

Connects to Zerodha, fetches real option quotes every 5 minutes,
and calculates VWAP using the exact same logic as strategy._calculate_vwap().

Usage:
    python paper_trading/tests/vwap_live_zerodha.py
    python paper_trading/tests/vwap_live_zerodha.py --strike 23000 --type CE
    python paper_trading/tests/vwap_live_zerodha.py --strike 23000 --type CE --expiry 2026-02-17

NO ORDERS ARE PLACED. This is purely a data fetch + calculation script.
"""

import sys
import os
import json
import time
import argparse
from datetime import datetime, date, timedelta

# ── Add project root to path ──────────────────────────────────────────────────
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)

from paper_trading.legacy.zerodha_connection import ZerodhaConnection, load_credentials_from_file

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────────────────────
CREDS_FILE     = os.path.join(ROOT, 'paper_trading', 'config', 'credentials_zerodha.txt')
CACHE_FILE     = os.path.join(ROOT, 'contracts_cache.json')
INTERVAL_MIN   = 5          # fetch every 5 minutes
NIFTY_TOKEN    = "NSE:NIFTY 50"


# ──────────────────────────────────────────────────────────────────────────────
# VWAP STATE  (mirrors strategy.vwap_running_totals)
# ──────────────────────────────────────────────────────────────────────────────
vwap_state = {}


def calculate_vwap(strike, option_type, expiry, price, cumul_volume):
    """
    Exact copy of strategy._calculate_vwap().
    Uses incremental delta of cumulative broker volume.
    """
    key = (strike, option_type, expiry)

    if key not in vwap_state:
        vwap_state[key] = {
            'tpv':                    0.0,
            'volume':                 0.0,
            'prev_cumulative_volume': 0.0,
        }

    prev_cumul  = vwap_state[key]['prev_cumulative_volume']
    incr_volume = cumul_volume - prev_cumul

    vwap_state[key]['tpv']    += price * incr_volume
    vwap_state[key]['volume'] += incr_volume
    vwap_state[key]['prev_cumulative_volume'] = cumul_volume

    total_vol = vwap_state[key]['volume']
    if total_vol > 0:
        return vwap_state[key]['tpv'] / total_vol
    else:
        return price


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def load_contracts_cache():
    """Load contracts_cache.json"""
    try:
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Could not load contracts cache: {e}")
        return None


def get_instrument_token(cache, expiry, strike, option_type):
    """
    Look up Zerodha instrument token from contracts_cache.json.
    Returns integer token or None.
    """
    try:
        instruments = cache['options']['instruments']
        expiry_data  = instruments.get(expiry, {})
        strike_data  = expiry_data.get(str(int(strike)), {})
        contract     = strike_data.get(option_type.upper(), {})
        token_str    = contract.get('token')
        if token_str:
            return int(token_str)
        return None
    except Exception as e:
        print(f"[ERROR] Token lookup failed: {e}")
        return None


def get_current_week_expiry(cache):
    """Get the nearest upcoming expiry from cache."""
    today = date.today()
    expiry_dates = cache['options'].get('expiry_dates', [])
    for exp in sorted(expiry_dates):
        exp_date = datetime.strptime(exp, '%Y-%m-%d').date()
        if exp_date >= today:
            return exp
    return None


def get_nifty_spot(kite):
    """Fetch NIFTY spot price."""
    try:
        data = kite.ltp([NIFTY_TOKEN])
        return data[NIFTY_TOKEN]['last_price']
    except Exception as e:
        print(f"[ERROR] Could not fetch NIFTY spot: {e}")
        return None


def get_atm_strike(spot, step=50):
    """Round spot to nearest step for ATM strike."""
    return round(spot / step) * step


def fetch_quote(kite, instrument_token):
    """
    Fetch full quote for an option using its Zerodha instrument token.
    Returns (ltp, cumulative_volume, oi) or (None, None, None) on error.
    """
    try:
        data     = kite.quote([instrument_token])
        token_key = str(instrument_token)
        if token_key not in data:
            print(f"[WARN] Token {token_key} not in response. Keys: {list(data.keys())}")
            return None, None, None
        q        = data[token_key]
        ltp      = q.get('last_price', 0)
        volume   = q.get('volume', 0)   # cumulative from broker
        oi       = q.get('oi', 0)
        return ltp, volume, oi
    except Exception as e:
        print(f"[ERROR] Quote fetch failed: {e}")
        return None, None, None


def seconds_until_next_candle(interval_min=5):
    """Seconds remaining until the next 5-min candle boundary."""
    now              = datetime.now()
    minutes_past     = now.minute % interval_min
    seconds_past     = minutes_past * 60 + now.second
    seconds_in_block = interval_min * 60
    wait             = seconds_in_block - seconds_past
    return wait if wait > 0 else seconds_in_block


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Live VWAP Calculator (Zerodha) — NO TRADES')
    parser.add_argument('--strike', type=int,   default=None, help='Strike price (default: ATM)')
    parser.add_argument('--type',   type=str,   default='CE', help='CE or PE (default: CE)')
    parser.add_argument('--expiry', type=str,   default=None, help='Expiry YYYY-MM-DD (default: current week)')
    args = parser.parse_args()

    print("=" * 65)
    print("  LIVE VWAP CALCULATOR — ZERODHA  (READ-ONLY, NO TRADES)")
    print("=" * 65)

    # ── 1. Load credentials ────────────────────────────────────────────────
    print(f"\n[1/4] Loading credentials from {CREDS_FILE}")
    creds = load_credentials_from_file(CREDS_FILE)
    if not creds:
        print("[ERROR] Could not load credentials. Check path.")
        sys.exit(1)
    print(f"      User: {creds.get('user_id')}  API key: {creds.get('api_key', '')[:10]}...")

    # ── 2. Connect to Zerodha ─────────────────────────────────────────────
    print(f"\n[2/4] Connecting to Zerodha (TOTP auto-login)...")
    connection = ZerodhaConnection(
        api_key       = creds['api_key'],
        api_secret    = creds['api_secret'],
        user_id       = creds['user_id'],
        user_password = creds['user_password'],
        totp_key      = creds['totp_key']
    )
    kite = connection.connect()
    if not kite:
        print("[ERROR] Zerodha connection failed.")
        sys.exit(1)
    print("      Connected successfully.")

    # ── 3. Resolve strike / expiry / token ────────────────────────────────
    print(f"\n[3/4] Resolving instrument...")
    cache = load_contracts_cache()
    if not cache:
        sys.exit(1)

    expiry = args.expiry or get_current_week_expiry(cache)
    if not expiry:
        print("[ERROR] Could not determine expiry from cache.")
        sys.exit(1)

    option_type = args.type.upper()

    if args.strike:
        strike = args.strike
    else:
        spot = get_nifty_spot(kite)
        if not spot:
            print("[ERROR] Could not fetch NIFTY spot price.")
            sys.exit(1)
        strike = get_atm_strike(spot)
        print(f"      NIFTY Spot = {spot:.2f}  →  ATM Strike = {strike}")

    token = get_instrument_token(cache, expiry, strike, option_type)
    if not token:
        print(f"[ERROR] No token found for {option_type} {strike} exp:{expiry}")
        print(f"        Run:  python refresh_contracts.py --broker zerodha")
        sys.exit(1)

    print(f"      Instrument : {option_type} {strike}  exp:{expiry}")
    print(f"      Token      : {token}")

    # ── 4. Start VWAP fetch loop ──────────────────────────────────────────
    print(f"\n[4/4] Starting VWAP loop (every {INTERVAL_MIN} min, Ctrl+C to stop)...")
    print()

    header = (
        f"{'Time':<8} {'LTP':>8} {'CumulVol':>10} {'IncrVol':>10} "
        f"{'TPV_added':>12} {'RunVol':>10} {'VWAP':>8}"
    )
    print(header)
    print("-" * len(header))

    candle_count = 0

    try:
        while True:
            now = datetime.now()

            # Reset VWAP at market open (9:15)
            if now.hour == 9 and now.minute == 15 and now.second < 30:
                key = (strike, option_type, expiry)
                if key in vwap_state:
                    vwap_state[key] = {
                        'tpv': 0.0, 'volume': 0.0, 'prev_cumulative_volume': 0.0
                    }
                    print(f"\n[{now.strftime('%H:%M:%S')}] Day reset — VWAP state cleared.\n")
                    print(header)
                    print("-" * len(header))

            # Fetch quote
            ltp, cumul_vol, oi = fetch_quote(kite, token)

            if ltp is None:
                print(f"[{now.strftime('%H:%M:%S')}] Quote fetch failed — retrying next cycle.")
            else:
                candle_count += 1

                # Snapshot pre-update state for logging
                key        = (strike, option_type, expiry)
                prev_cumul = vwap_state.get(key, {}).get('prev_cumulative_volume', 0.0)
                incr_vol   = cumul_vol - prev_cumul
                tpv_added  = ltp * incr_vol

                # Calculate VWAP (same logic as strategy)
                vwap = calculate_vwap(strike, option_type, expiry, ltp, cumul_vol)

                run_vol = vwap_state[key]['volume']

                ts = now.strftime('%H:%M:%S')
                print(
                    f"{ts:<8} {ltp:>8.2f} {cumul_vol:>10,} {incr_vol:>10,.0f} "
                    f"{tpv_added:>12,.2f} {run_vol:>10,.0f} {vwap:>8.2f}"
                )

                # Extra detail every 6 candles (~30 min)
                if candle_count % 6 == 0:
                    state = vwap_state[key]
                    print(f"\n  --- 30-min snapshot ---")
                    print(f"  RunTPV    : {state['tpv']:,.2f}")
                    print(f"  RunVol    : {state['volume']:,.0f}")
                    print(f"  VWAP      : {vwap:.4f}")
                    print(f"  OI        : {oi:,.0f}")
                    print(f"  Candles   : {candle_count}")
                    print()
                    print(header)
                    print("-" * len(header))

            # Wait until next 5-min candle boundary
            wait = seconds_until_next_candle(INTERVAL_MIN)
            print(f"  [next fetch in {wait:.0f}s at {(now + timedelta(seconds=wait)).strftime('%H:%M:%S')}]")
            time.sleep(wait)

    except KeyboardInterrupt:
        print("\n\nStopped by user.")

    finally:
        # Print final VWAP state
        key = (strike, option_type, expiry)
        if key in vwap_state and vwap_state[key]['volume'] > 0:
            state = vwap_state[key]
            final_vwap = state['tpv'] / state['volume']
            print("\n" + "=" * 65)
            print("  FINAL VWAP STATE")
            print("=" * 65)
            print(f"  Instrument       : {option_type} {strike} exp:{expiry}")
            print(f"  Total Candles    : {candle_count}")
            print(f"  Total IncrVol    : {state['volume']:,.0f}")
            print(f"  Total TPV        : {state['tpv']:,.2f}")
            print(f"  Final VWAP       : {final_vwap:.4f}")
            print("=" * 65)

        connection.logout()


if __name__ == "__main__":
    main()
