"""
Simulation test: trailing stop activation and behaviour when PnL goes negative.

Scenarios covered:
  A - Price rises 10%+, trailing activates, then gaps below entry (negative PnL)
  B - Price rises 10%+, trailing activates, then slowly bleeds negative via VWAP stop
  C - Price rises 10%+, trailing activates, stays positive but dips — trailing fires
  D - Price never reaches 10%, VWAP stop fires in loss (normal path, no trailing)
  E - Gap-down candle: price crosses trailing AND VWAP stop simultaneously — least-loss wins
"""

from dataclasses import dataclass, field
from typing import Optional, List, Tuple
try:
    from tabulate import tabulate
except ImportError:
    def tabulate(rows, headers, tablefmt=None):
        col_w = [max(len(str(headers[i])), max(len(str(r[i])) for r in rows)) for i in range(len(headers))]
        sep = "+-" + "-+-".join("-"*w for w in col_w) + "-+"
        fmt = "| " + " | ".join(f"{{:<{w}}}" for w in col_w) + " |"
        lines = [sep, fmt.format(*headers), sep]
        for r in rows:
            lines.append(fmt.format(*[str(x) for x in r]))
        lines.append(sep)
        return "\n".join(lines)

# ── config (mirrors paper_trading defaults) ──────────────────────────────────
INITIAL_STOP_LOSS_PCT  = 0.25   # 25% hard stop
PROFIT_THRESHOLD       = 1.10   # 10% profit activates trailing
TRAILING_STOP_PCT      = 0.10   # 10% below peak
VWAP_STOP_PCT          = 0.05   # 5% below VWAP
OI_INCREASE_STOP_PCT   = 0.10   # 10% OI increase


# ── minimal position ──────────────────────────────────────────────────────────
@dataclass
class MockPosition:
    strike: int
    option_type: str
    entry_price: float
    oi_at_entry: float
    peak_price: float = field(init=False)
    trailing_stop_active: bool = field(init=False, default=False)

    def __post_init__(self):
        self.peak_price = self.entry_price


# ── the exact exit decision logic (copy of strategy._check_exit_conditions) ──
def decide_exit(position: MockPosition,
                current_price: float,
                vwap: Optional[float],
                current_oi: float) -> Optional[str]:
    """Returns exit reason string or None."""
    pnl_pct = (current_price / position.entry_price) - 1
    stop_loss_price = position.entry_price * (1 - INITIAL_STOP_LOSS_PCT)

    # ── update peak ──────────────────────────────────────────────────────────
    if current_price > position.peak_price:
        position.peak_price = current_price

    # ── activate trailing ────────────────────────────────────────────────────
    if current_price >= position.entry_price * PROFIT_THRESHOLD:
        if not position.trailing_stop_active:
            position.trailing_stop_active = True

    # ── exit decision ────────────────────────────────────────────────────────
    exit_reason = None

    if position.trailing_stop_active:
        trailing_stop_price = position.peak_price * (1 - TRAILING_STOP_PCT)

        if pnl_pct >= 0:
            # In profit: only trailing stop
            if current_price <= trailing_stop_price:
                exit_reason = f"Trailing Stop (peak={position.peak_price:.1f}, ts={trailing_stop_price:.1f})"
        else:
            # In loss: pick highest triggered stop price = least loss
            triggered: List[Tuple[float, str]] = []

            if current_price <= trailing_stop_price:
                triggered.append((trailing_stop_price,
                                   f"Trailing Stop (ts={trailing_stop_price:.1f})"))

            if current_price <= stop_loss_price:
                triggered.append((stop_loss_price,
                                   f"Hard Stop (sl={stop_loss_price:.1f})"))

            if vwap is not None:
                vwap_stop_price = vwap * (1 - VWAP_STOP_PCT)
                if current_price <= vwap_stop_price:
                    triggered.append((vwap_stop_price,
                                       f"VWAP Stop (vs={vwap_stop_price:.1f})"))

            if triggered:
                exit_reason = max(triggered, key=lambda x: x[0])[1]
            else:
                oi_change_pct = (current_oi / position.oi_at_entry) - 1
                if oi_change_pct > OI_INCREASE_STOP_PCT:
                    exit_reason = (f"OI Stop (oi_chg={oi_change_pct*100:+.1f}%)")
    else:
        # Trailing not active — normal priority
        if current_price <= stop_loss_price:
            exit_reason = f"Hard Stop (sl={stop_loss_price:.1f})"
        elif pnl_pct < 0 and vwap is not None:
            vwap_stop_price = vwap * (1 - VWAP_STOP_PCT)
            if current_price <= vwap_stop_price:
                exit_reason = f"VWAP Stop (vs={vwap_stop_price:.1f})"
        elif pnl_pct < 0:
            oi_change_pct = (current_oi / position.oi_at_entry) - 1
            if oi_change_pct > OI_INCREASE_STOP_PCT:
                exit_reason = f"OI Stop (oi_chg={oi_change_pct*100:+.1f}%)"

    return exit_reason


# ── candle runner ─────────────────────────────────────────────────────────────
def run_scenario(name: str,
                 candles: List[dict],   # each: {price, vwap, oi}
                 entry_price: float,
                 oi_at_entry: float,
                 description: str):

    print(f"\n{'='*72}")
    print(f"SCENARIO {name}: {description}")
    print(f"  Entry={entry_price}  Hard-stop={entry_price*(1-INITIAL_STOP_LOSS_PCT):.1f}"
          f"  Trail-activates-at={entry_price*PROFIT_THRESHOLD:.1f}")
    print('='*72)

    pos = MockPosition(strike=20000, option_type="CE",
                       entry_price=entry_price, oi_at_entry=oi_at_entry)

    rows = []
    for i, c in enumerate(candles, 1):
        price   = c['price']
        vwap    = c.get('vwap')
        oi      = c.get('oi', oi_at_entry)
        pnl_pct = (price / entry_price - 1) * 100

        # snapshot BEFORE deciding (so we can show pre-candle state)
        trailing_was = pos.trailing_stop_active
        peak_before  = pos.peak_price
        ts_level     = peak_before * (1 - TRAILING_STOP_PCT) if trailing_was else None

        reason = decide_exit(pos, price, vwap, oi)

        rows.append([
            i,
            f"{price:.1f}",
            f"{pnl_pct:+.1f}%",
            f"{vwap:.1f}" if vwap else "—",
            "YES" if trailing_was else "no",
            f"{ts_level:.1f}" if ts_level else "—",
            reason if reason else "—",
        ])

        if reason:
            break

    headers = ["Candle", "Price", "PnL%", "VWAP", "Trail?", "TS-Level", "Exit Reason"]
    print(tabulate(rows, headers=headers, tablefmt="rounded_outline"))

    if not reason:
        print("  ⚠  Position still open after all candles — no stop triggered.")


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIOS
# ─────────────────────────────────────────────────────────────────────────────

ENTRY  = 100.0
OI_BASE = 500_000

# ── A: Rises >10%, trailing activates, then gaps BELOW entry → trailing fires
run_scenario(
    name="A",
    description="Rise 10%+ → trailing activates → gaps below entry (negative PnL)",
    entry_price=ENTRY,
    oi_at_entry=OI_BASE,
    candles=[
        {"price": 102.0, "vwap": 101.0, "oi": OI_BASE},
        {"price": 107.0, "vwap": 104.0, "oi": OI_BASE},
        {"price": 112.0, "vwap": 107.0, "oi": OI_BASE},   # trailing activates (>110)
        {"price": 115.0, "vwap": 109.0, "oi": OI_BASE},   # peak moves up
        {"price": 108.0, "vwap": 107.0, "oi": OI_BASE},   # TS = 115*0.9=103.5, price above
        {"price": 97.0,  "vwap": 102.0, "oi": OI_BASE},   # PnL negative, TS=103.5 → fires
    ]
)

# ── B: Rises >10%, trailing activates, bleeds slowly — VWAP also in play
#      In-loss: trailing stop (103.5) > VWAP stop (~97) → trailing wins as "least loss"
run_scenario(
    name="B",
    description="Rise 10%+ → trailing on → slow bleed: trailing vs VWAP stop (least-loss picks trailing)",
    entry_price=ENTRY,
    oi_at_entry=OI_BASE,
    candles=[
        {"price": 105.0, "vwap": 102.0, "oi": OI_BASE},
        {"price": 112.0, "vwap": 106.0, "oi": OI_BASE},   # trailing activates, peak=112
        {"price": 108.0, "vwap": 107.0, "oi": OI_BASE},   # TS=100.8, price above
        {"price": 101.5, "vwap": 105.0, "oi": OI_BASE},   # TS=100.8, price above, PnL+
        {"price":  99.5, "vwap":  99.0, "oi": OI_BASE},   # PnL neg, TS=100.8 fires (> VWAP stop ~94)
    ]
)

# ── C: Rises, trailing on, stays positive but dips to trailing level → trailing fires
run_scenario(
    name="C",
    description="Rise 10%+ → trailing on → dips to trailing level while still in profit",
    entry_price=ENTRY,
    oi_at_entry=OI_BASE,
    candles=[
        {"price": 108.0, "vwap": 104.0, "oi": OI_BASE},
        {"price": 118.0, "vwap": 109.0, "oi": OI_BASE},   # trailing activates, peak=118
        {"price": 120.0, "vwap": 111.0, "oi": OI_BASE},   # new peak=120, TS=108
        {"price": 115.0, "vwap": 112.0, "oi": OI_BASE},   # TS=108, price above
        {"price": 106.0, "vwap": 110.0, "oi": OI_BASE},   # PnL+, TS=108, price(106) <= 108 → fires
    ]
)

# ── D: Normal path — trailing never activates, VWAP stop fires in loss
run_scenario(
    name="D",
    description="No trailing (price never hits 10% profit) → VWAP stop fires in loss",
    entry_price=ENTRY,
    oi_at_entry=OI_BASE,
    candles=[
        {"price": 103.0, "vwap": 101.0, "oi": OI_BASE},
        {"price": 100.5, "vwap": 100.5, "oi": OI_BASE},
        {"price":  96.0, "vwap": 100.0, "oi": OI_BASE},   # VWAP stop=95, price above
        {"price":  93.0, "vwap":  99.0, "oi": OI_BASE},   # VWAP stop=94.05, price(93) fires
    ]
)

# ── E: Gap-down candle — trailing AND VWAP stop both triggered simultaneously
#      Trailing stop (103.5) > VWAP stop (96.1) → trailing wins = least loss
run_scenario(
    name="E",
    description="Gap-down candle: trailing + VWAP both triggered → highest stop (least loss) wins",
    entry_price=ENTRY,
    oi_at_entry=OI_BASE,
    candles=[
        {"price": 112.0, "vwap": 106.0, "oi": OI_BASE},   # trailing activates, peak=112, TS=100.8
        {"price": 115.0, "vwap": 108.0, "oi": OI_BASE},   # peak=115, TS=103.5
        {"price":  94.0, "vwap": 101.0, "oi": OI_BASE},   # gap! PnL neg, TS=103.5 fires (vs VWAP stop~95.9)
    ]
)

print("\n")
print("Legend:")
print("  Trail?    = was trailing stop already active BEFORE this candle")
print("  TS-Level  = trailing stop trigger price (peak × 0.90)")
print("  Least-loss = when PnL<0 and trailing active, highest triggered stop price wins")
