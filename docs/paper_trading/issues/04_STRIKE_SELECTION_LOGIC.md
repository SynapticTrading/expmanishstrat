# Issue 4: Strike Selection Logic Clarification

**Date**: December 29, 2025
**Status**: ✅ CLARIFIED (Not a bug - working as designed)
**Priority**: Medium

## Problem

User questioned the strike selection logic:

**User**: "if spot was 25946 it shouldve taken 25950 strike right?"

**Context**:
- Spot price: 25946.95
- Direction: PUT
- Selected strike: 25900
- Expected strike (user): 25950

**Why the confusion?**
User expected "nearest strike to spot" but system selects "nearest OTM strike" based on direction.

## Root Cause

### Misunderstanding of OTM Logic

The strategy is designed to trade **Out-of-The-Money (OTM)** options, not At-The-Money (ATM) options:

**OTM Options Benefits**:
1. Lower premium cost
2. Less capital at risk
3. Better risk-reward for momentum plays
4. Institutional unwinding typically affects OTM strikes

**Strike Selection Rules**:
- **PUT direction**: Select nearest strike **BELOW** spot (OTM for puts)
- **CALL direction**: Select nearest strike **ABOVE** spot (OTM for calls)

### Example Breakdown

**Spot**: 25946.95

**Available strikes** (50-point intervals):
```
... 25850, 25900, 25950, 26000, 26050 ...
                  ↑ SPOT
```

**For PUT direction**:
- OTM strikes (below spot): 25900, 25850, 25800...
- **Selected**: 25900 (nearest OTM)
- ❌ NOT 25950 (that's above spot, would be ITM for puts)

**For CALL direction**:
- OTM strikes (above spot): 25950, 26000, 26050...
- **Selected**: 25950 (nearest OTM)
- ❌ NOT 25900 (that's below spot, would be ITM for calls)

## Implementation

### Strike Selection Code

**File**: `src/oi_analyzer.py:134-151`

```python
def get_nearest_strike(self, spot_price, option_type, available_strikes):
    """
    Get nearest strike to spot price
    For CALL: nearest strike on upper side (>= spot)
    For PUT: nearest strike on lower side (< spot)

    Args:
        spot_price: Current spot price
        option_type: 'CALL' or 'PUT'
        available_strikes: List of available strikes

    Returns:
        Nearest OTM strike
    """
    if option_type == 'CALL':
        # Nearest strike >= spot (OTM for calls)
        upper_strikes = [s for s in available_strikes if s >= spot_price]
        if upper_strikes:
            return min(upper_strikes)
    else:  # PUT
        # Nearest strike < spot (OTM for puts)
        lower_strikes = [s for s in available_strikes if s < spot_price]
        if lower_strikes:
            return max(lower_strikes)

    return None
```

### Why OTM Instead of ATM?

#### 1. Strategy Design
The strategy trades **directional momentum** based on OI unwinding:
- When calls unwind → Bearish → Buy PUTs (OTM)
- When puts unwind → Bullish → Buy CALLs (OTM)

#### 2. Cost Efficiency
**Example** (Spot: 25946):

| Strike | Type | Moneyness | Premium | Capital |
|--------|------|-----------|---------|---------|
| 25950  | PUT  | ATM       | ₹80.00  | ₹6,000  |
| 25900  | PUT  | OTM       | ₹36.80  | ₹2,760  |

- **OTM saves 54% in premium** (₹36.80 vs ₹80.00)
- Lower capital at risk per lot
- Can take larger positions with same capital

#### 3. Risk Management
- Max loss = Premium paid (lower for OTM)
- Stop losses are percentage-based
- Lower premium = lower absolute loss in rupees

#### 4. Institutional Behavior
When institutions unwind positions, they typically affect OTM strikes first:
- Retail traders prefer ATM (higher liquidity)
- Institutions hedge with OTM (cost effective)
- OI changes more visible in OTM strikes

## Real-World Examples

### Example 1: PUT Direction (Actual trade)

**Time**: 1:42 PM, Dec 29, 2025
**Spot**: 25946.95

```
Strategy Analysis:
├─ 9:15 AM Direction: PUT (calls had higher OI)
├─ Current OI Status: Unwinding at 25900
├─ Strike Selection:
│  ├─ Available: [25800, 25850, 25900, 25950, 26000]
│  ├─ Spot: 25946.95
│  ├─ Direction: PUT
│  └─ Selected: 25900 (nearest strike < 25946)
└─ Entry: PUT 25900 @ ₹36.80
```

**Why 25900, not 25950?**
- PUT direction requires strike BELOW spot
- 25900 < 25946 ✓ (OTM for puts)
- 25950 > 25946 ✗ (would be ITM for puts)

### Example 2: CALL Direction (Hypothetical)

**Spot**: 25946.95
**Direction**: CALL

```
Strike Selection:
├─ Available: [25800, 25850, 25900, 25950, 26000]
├─ Spot: 25946.95
├─ Direction: CALL
└─ Selected: 25950 (nearest strike >= 25946)

Entry: CALL 25950 @ ₹XX.XX
```

**Why 25950, not 25900?**
- CALL direction requires strike ABOVE spot
- 25950 > 25946 ✓ (OTM for calls)
- 25900 < 25946 ✗ (would be ITM for calls)

## Visual Guide

### PUT Direction Strike Selection

```
Spot = 25946

        ITM (In-The-Money)         |  OTM (Out-Of-Money)
              ↓                     |        ↓
    [26000] [25950] [25900] [25850] [25800]
                     ↑ SPOT

For PUT options:
✗ 25950, 26000 = ITM (strike > spot)
✓ 25900, 25850 = OTM (strike < spot)

Selected: 25900 (nearest OTM)
```

### CALL Direction Strike Selection

```
Spot = 25946

  OTM (Out-Of-Money)         |  ITM (In-The-Money)
        ↓                     |        ↓
    [25800] [25850] [25900] [25950] [26000]
                     ↑ SPOT

For CALL options:
✗ 25900, 25850 = ITM (strike < spot)
✓ 25950, 26000 = OTM (strike > spot)

Selected: 25950 (nearest OTM)
```

## Dynamic Strike Updates

The system updates strikes dynamically as spot moves:

**File**: `paper_trading/core/strategy.py:216-231`

```python
# Check if strike needs updating based on spot price
strikes = options_data['strike'].unique()
new_strike = self.oi_analyzer.get_nearest_strike(
    spot_price, self.daily_direction, strikes
)

if new_strike != self.daily_strike and new_strike is not None:
    old_strike = self.daily_strike
    self.daily_strike = new_strike
    print(f"[{current_time}] 📍 STRIKE UPDATED: {old_strike} → {new_strike} (Spot: {spot_price:.2f})")
```

### Example Strike Update Scenario

**PUT Direction**:

| Time | Spot | Old Strike | New Strike | Reason |
|------|------|------------|------------|--------|
| 1:30 | 25846 | 25850 | 25800 | Spot moved below 25850 |
| 1:35 | 25896 | 25800 | 25850 | Spot moved above 25850 |
| 1:40 | 25946 | 25850 | 25900 | Spot moved above 25900 |

Each time, the system selects nearest strike **below** current spot (for PUT direction).

## Testing and Verification

### Production Logs (Dec 29, 2025)

**File**: `reports/paper_trading_log_20251229_135313.txt`

```
[13:42:17] Checking entry: PUT 25900, Expiry=2025-12-30
[13:42:17] Spot: 25946.95
[13:42:17] PUT 25900: OI=34,765,425, Change=-267,500 (-0.76%) - UNWINDING ✓
[13:42:17] PUT 25900: Price=₹36.80, VWAP=₹36.21 - ABOVE ✓
[13:42:17] ✅ ENTRY: Bought 1 lot of PUT 25900 @ ₹36.80
```

✅ Correct: 25900 selected for PUT (below spot 25946)
✅ OTM premium: ₹36.80 (lower cost)
✅ System working as designed

## Comparison with Backtest

The backtest uses **identical logic**:

**File**: `src/backtest_strategy.py` (same OI analyzer)

```python
# Same strike selection logic
strike = self.oi_analyzer.get_nearest_strike(
    spot_price,
    self.daily_direction,
    available_strikes
)
```

✅ Paper trading matches backtest behavior
✅ Historical results validated with OTM approach
✅ No changes needed - working correctly

## Common Questions

### Q1: Why not just trade ATM always?
**A**: ATM costs more premium. Strategy is designed for OTM momentum trades where OI unwinding creates price movement. Lower cost = better risk-reward.

### Q2: What if spot moves past strike after entry?
**A**: Strike gets updated on next 5-min candle. If already in position, stops monitor the existing position. New entries use updated strike.

### Q3: How far OTM is acceptable?
**A**: System selects **nearest** OTM, typically 0-50 points away. Not deep OTM. Strike interval is 50 points for Nifty.

### Q4: Do we ever trade ITM?
**A**: No. System always selects OTM by design. ITM would mean:
- Higher premium cost
- Less leverage
- Doesn't align with institutional unwinding behavior

## Related Issues

- [OI Logging Improvements](./02_OI_LOGGING_IMPROVEMENTS.md) - Explains max OI vs trading strike difference
