# Issue 10: Strategy State Not Saving to JSON

**Date:** 2025-12-30
**Severity:** MEDIUM
**Status:** ✅ FIXED

---

## Problem

Strategy state remained empty in JSON file even after direction determination:

```json
"strategy_state": {
  "current_spot": null,          ✗ Should have spot price
  "trading_strike": null,        ✗ Should have strike
  "direction": null,             ✗ Should have CALL/PUT
  "max_call_oi_strike": null,    ✗ Should have max OI strike
  "max_put_oi_strike": null,     ✗ Should have max OI strike
  "last_oi_check": null,         ✗ Should have timestamp
  "vwap_tracking": {}            ✗ Should have VWAP data
}
```

Logs showed strategy was working:
```
Direction determined: PUT @ 25900
Max Call OI: 36,595,925 @ 26000
Max Put OI: 38,819,025 @ 25900
```

But state file never updated!

## Root Cause

**Missing connection between Strategy and StateManager:**

### Issue 1: StateManager Not Passed to Strategy
**File:** `paper_trading/runner.py:187` (original)

```python
self.strategy = IntradayMomentumOIPaper(
    config=self.config,
    broker=self.paper_broker,
    oi_analyzer=self.oi_analyzer
    # ❌ Missing: state_manager parameter
)
```

### Issue 2: Strategy Never Called update_strategy_state()
Even if it had state_manager, it never called the update method.

## Solution

### 1. Pass StateManager to Strategy
**File:** `paper_trading/runner.py:187-191`

```python
self.strategy = IntradayMomentumOIPaper(
    config=self.config,
    broker=self.paper_broker,
    oi_analyzer=self.oi_analyzer,
    state_manager=self.state_manager  # ✅ NEW
)
```

### 2. Accept StateManager in Strategy Init
**File:** `paper_trading/core/strategy.py:23-36`

```python
def __init__(self, config, broker: PaperBroker, oi_analyzer: OIAnalyzer, state_manager=None):
    """
    Initialize strategy

    Args:
        config: Strategy configuration dict
        broker: PaperBroker instance
        oi_analyzer: OIAnalyzer instance
        state_manager: StateManager instance (optional)  # ✅ NEW
    """
    self.config = config
    self.broker = broker
    self.oi_analyzer = oi_analyzer
    self.state_manager = state_manager  # ✅ NEW
```

### 3. Add Instance Variables for Tracking
**File:** `paper_trading/core/strategy.py:69-70`

```python
# Daily state
self.current_date = None
self.daily_direction = None
self.daily_strike = None
self.daily_expiry = None
self.daily_trade_taken = False
self.max_call_oi_strike = None  # ✅ NEW - For state tracking
self.max_put_oi_strike = None   # ✅ NEW - For state tracking
```

### 4. Store Max OI Strikes When Calculated
**File:** `paper_trading/core/strategy.py:123-125`

```python
# Calculate max OI buildup from current options data
max_call_strike, max_put_strike, call_distance, put_distance = \
    self.oi_analyzer.calculate_max_oi_buildup(options_data, spot_price)

# ✅ NEW: Store for state tracking
self.max_call_oi_strike = max_call_strike
self.max_put_oi_strike = max_put_strike
```

### 5. Update State After Direction Determination
**File:** `paper_trading/core/strategy.py:162-171`

```python
print(f"[{current_time}] ✓ Daily Analysis Complete: Direction={self.daily_direction}, Strike={self.daily_strike}, Expiry={self.daily_expiry}, Spot={spot_price:.2f}")

# ✅ NEW: Update strategy state
if self.state_manager:
    self.state_manager.update_strategy_state(
        spot=spot_price,
        strike=self.daily_strike,
        direction=self.daily_direction,
        call_strike=max_call_strike,
        put_strike=max_put_strike,
        vwap_tracking=self.vwap_running_totals
    )
    self.state_manager.save()
```

### 6. Update State After Every Candle
**File:** `paper_trading/core/strategy.py:221-231`

```python
# Force exit at EOD
if self.exit_start_time <= current_time_only <= self.exit_end_time:
    self._force_eod_exit(current_time, options_data)

# ✅ NEW: Update strategy state (periodic update with current data)
if self.state_manager and self.daily_direction:
    self.state_manager.update_strategy_state(
        spot=spot_price,
        strike=self.daily_strike,
        direction=self.daily_direction,
        call_strike=self.max_call_oi_strike,
        put_strike=self.max_put_oi_strike,
        vwap_tracking=self.vwap_running_totals
    )
    self.state_manager.save()
```

## Example Results

### After Fix - State File:
```json
"strategy_state": {
  "current_spot": 25942.35,          ✓ Updated every candle
  "trading_strike": 25900.0,         ✓ Daily strike
  "direction": "PUT",                ✓ Direction determined
  "max_call_oi_strike": 26000.0,     ✓ Max Call OI location
  "max_put_oi_strike": 25900.0,      ✓ Max Put OI location
  "last_oi_check": "2025-12-30...",  ✓ Last update time
  "vwap_tracking": {
    "25900.0PUT": {
      "sum_typical_price_volume": 350773.29,
      "sum_volume": 64727425.0,
      "current_vwap": 5.42,
      "last_update": "2025-12-30T14:26:51..."
    }
  }
}
```

## Verification

**Logs Confirm Strategy is Working:**
```
Direction determined: PUT (Call dist: 71.75, Put dist: 28.25)
✓ Daily Analysis Complete: Direction=PUT, Strike=25900.0, Spot=25928.25
```

**State File Now Shows:**
```json
"direction": "PUT",
"trading_strike": 25900.0,
"current_spot": 25928.25
```

✅ Perfect sync between logs and state!

## Impact

- ✅ Full visibility into strategy decisions
- ✅ Can debug direction/strike selection
- ✅ VWAP tracking preserved across restarts
- ✅ OI analysis data available for review
- ✅ State recovery includes strategy context

## Related Issues

- **Prerequisite:** Issue 08 (JSON serialization fix)
- **Complementary:** Issue 09 (Portfolio state update)

## Files Modified

1. `paper_trading/runner.py:191` - Pass state_manager to strategy
2. `paper_trading/core/strategy.py:23-36` - Accept state_manager param
3. `paper_trading/core/strategy.py:69-70` - Add tracking variables
4. `paper_trading/core/strategy.py:123-125` - Store max OI strikes
5. `paper_trading/core/strategy.py:162-171` - Update state on new day
6. `paper_trading/core/strategy.py:221-231` - Update state every candle
