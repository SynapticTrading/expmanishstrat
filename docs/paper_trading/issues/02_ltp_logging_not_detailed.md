# Issue #2: LTP Logging Not Detailed Enough

**Date:** 2025-12-29
**Severity:** Medium
**Status:** ✅ Resolved

---

## Problem

The exit monitor was running but not logging:
- Current LTP values
- Stop loss levels
- Distance to each stop loss
- Trailing stop status
- VWAP stop levels
- OI change thresholds

This made it impossible to verify if the monitoring was working correctly.

### Log Output Before

```
[14:45:29] 🔍 Exit Monitor: Checking 1 position(s)...
```

That's it. No details about what was being checked.

---

## Solution

Added comprehensive logging in `strategy._check_exits()` to show:
- Current LTP
- Entry price and P&L
- All stop loss levels
- Distance to each stop
- Trailing stop status and peak price

### Code Added (paper_trading/core/strategy.py:386-407)

```python
# Calculate all stop loss levels
stop_loss_price = position.entry_price * (1 - self.initial_stop_loss_pct)

# Log current status
print(f"[{current_time}] 📊 LTP CHECK: {position.strike} {position.option_type}")
print(f"    Current LTP: ₹{current_price:.2f} | Entry: ₹{position.entry_price:.2f} | P&L: {pnl_pct*100:+.2f}%")
print(f"    Initial Stop: ₹{stop_loss_price:.2f} (distance: {((current_price/stop_loss_price - 1)*100):.2f}%)")

# VWAP stop info (only in loss)
if pnl_pct < 0 and vwap:
    vwap_stop_price = vwap * (1 - self.vwap_stop_pct)
    print(f"    VWAP Stop: ₹{vwap_stop_price:.2f} | Current VWAP: ₹{vwap:.2f}")

# OI change info (only in loss)
if pnl_pct < 0:
    oi_change_pct = (current_oi / position.oi_at_entry - 1)
    print(f"    OI Change: {oi_change_pct*100:+.2f}% (Threshold: {self.oi_increase_stop_pct*100:.0f}%)")

# Trailing stop info (if active)
if position.trailing_stop_active:
    trailing_stop_price = position.peak_price * (1 - self.trailing_stop_pct)
    print(f"    🎯 Trailing: Active | Peak: ₹{position.peak_price:.2f} | Stop: ₹{trailing_stop_price:.2f}")
```

---

## Log Output After

```
[14:45:29] 🔍 Exit Monitor: Fetching real-time LTP for 1 position(s)...
[14:45:29] 📊 LTP CHECK: 25900.0 PUT
    Current LTP: ₹30.45 | Entry: ₹30.00 | P&L: +1.50%
    Initial Stop: ₹22.50 (distance: 35.33%)

[14:46:29] 🔍 Exit Monitor: Fetching real-time LTP for 1 position(s)...
[14:46:29] 📊 LTP CHECK: 25900.0 PUT
    Current LTP: ₹29.85 | Entry: ₹30.00 | P&L: -0.50%
    Initial Stop: ₹22.50 (distance: 32.67%)
    VWAP Stop: ₹32.38 | Current VWAP: ₹34.08
    OI Change: +0.50% (Threshold: 10%)

[14:47:29] 🔍 Exit Monitor: Fetching real-time LTP for 1 position(s)...
[14:47:29] 📊 LTP CHECK: 25900.0 PUT
    Current LTP: ₹33.50 | Entry: ₹30.00 | P&L: +11.67%
    Initial Stop: ₹22.50 (distance: 48.89%)
    🎯 Trailing: Active | Peak: ₹33.50 | Stop: ₹30.15
```

---

## Files Changed

- `paper_trading/core/strategy.py` (lines 386-407)

---

## Benefits

- ✅ Can verify LTP is updating every minute
- ✅ Can see exact stop loss levels
- ✅ Can monitor trailing stop activation
- ✅ Can debug exit logic issues
- ✅ Provides transparency for trading decisions
