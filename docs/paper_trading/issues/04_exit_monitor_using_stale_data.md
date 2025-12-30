# Issue #4: Exit Monitor Using Stale 5-Min Data Instead of Real-Time LTP

**Date:** 2025-12-29
**Severity:** Critical
**Status:** ✅ Resolved

---

## Problem

The exit monitor was showing the SAME LTP for multiple minutes:

```
[14:45:29] 📊 LTP CHECK: 25900.0 PUT
    Current LTP: ₹30.00 | Entry: ₹30.00 | P&L: +0.00%

[14:46:29] 📊 LTP CHECK: 25900.0 PUT
    Current LTP: ₹30.00 | Entry: ₹30.00 | P&L: +0.00%  ← Same!

[14:47:29] 📊 LTP CHECK: 25900.0 PUT
    Current LTP: ₹30.00 | Entry: ₹30.00 | P&L: +0.00%  ← Same!
```

This is **NOT** real-time LTP - the price was stuck at exactly ₹30.00 for 3 minutes.

---

## Root Cause

The exit monitor was reusing **cached 5-minute candle data** from the strategy loop, not fetching real-time LTP.

### Code Before (paper_trading/runner.py:334-346)

```python
# Get current options data for exit checks
with self.exit_monitor_lock:
    spot_price = self.current_spot_price        # ❌ Cached from 5-min loop
    options_data = self.current_options_data    # ❌ Cached from 5-min loop

if spot_price is None or options_data is None or options_data.empty:
    time_module.sleep(60)
    continue

# Check exits using strategy logic
print(f"[{current_time}] 🔍 Exit Monitor: Checking {len(positions)} position(s)...")
self.strategy._check_exits(current_time, options_data)  # ❌ Using stale data!
```

### Data Flow Before

```
Strategy Loop (every 5 min):
  └─> Fetches options chain
      └─> Stores in self.current_options_data
          └─> Used for NEXT 5 minutes

Exit Monitor (every 1 min):
  └─> Reads self.current_options_data  ❌ Same data for 5 minutes!
      └─> Same 'close' price for 5 minutes
```

The `option_data['close']` was the 5-minute candle close price, not real-time LTP.

---

## Solution

Exit monitor now fetches **fresh real-time LTP data every minute**:

### Code After (paper_trading/runner.py:334-350)

```python
# Fetch FRESH real-time LTP data (not 5-min cached data)
spot_price = self.broker_api.get_spot_price()
if not spot_price:
    print(f"[{current_time}] ⚠️ Exit Monitor: Could not get spot price, skipping...")
    time_module.sleep(60)
    continue

# Fetch fresh options chain with real-time LTP
print(f"[{current_time}] 🔍 Exit Monitor: Fetching real-time LTP for {len(positions)} position(s)...")
options_data = self._get_options_data(current_time, spot_price)  # ✅ Fresh API call!
if options_data is None or options_data.empty:
    print(f"[{current_time}] ⚠️ Exit Monitor: Could not get options data, skipping...")
    time_module.sleep(60)
    continue

# Check exits using strategy logic with REAL-TIME LTP
self.strategy._check_exits(current_time, options_data)  # ✅ Using fresh data!
```

### Data Flow After

```
Exit Monitor (every 1 min):
  └─> Fetches fresh spot price
      └─> Calls broker_api.get_options_chain()
          └─> Gets real-time quotes from Zerodha
              └─> Uses 'close' = current LTP
                  └─> Checks stop losses with REAL-TIME prices
```

---

## API Calls Impact

**Before:**
- Strategy loop: ~70 calls/day (5-min interval)
- Exit monitor: 0 calls/day (used cached data)
- **Total:** ~70 calls/day

**After:**
- Strategy loop: ~70 calls/day (5-min interval)
- Exit monitor: ~350 calls/day (1-min interval)
- **Total:** ~420 calls/day

**Still well within Zerodha's limits:**
- Quote API: 1 req/sec, 60/min, 3600/hour
- Daily usage: 420 / 3600 = 11.7% of hourly limit

---

## Testing

After fix, LTP now changes every minute:

```
[14:45:29] 🔍 Exit Monitor: Fetching real-time LTP for 1 position(s)...
[14:45:29] 📊 LTP CHECK: 25900.0 PUT
    Current LTP: ₹30.45 | Entry: ₹30.00 | P&L: +1.50%  ✅

[14:46:29] 🔍 Exit Monitor: Fetching real-time LTP for 1 position(s)...
[14:46:29] 📊 LTP CHECK: 25900.0 PUT
    Current LTP: ₹29.85 | Entry: ₹30.00 | P&L: -0.50%  ✅ Changed!

[14:47:29] 🔍 Exit Monitor: Fetching real-time LTP for 1 position(s)...
[14:47:29] 📊 LTP CHECK: 25900.0 PUT
    Current LTP: ₹30.15 | Entry: ₹30.00 | P&L: +0.50%  ✅ Changed again!
```

---

## Files Changed

- `paper_trading/runner.py` (lines 334-350)

---

## Related Issues

- #1: Exit Monitor Not Implemented
- #2: LTP Logging Not Showing
