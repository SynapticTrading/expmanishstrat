# Issue #7: Why Mapping Was Correct But Data Was Still Stale

**Date:** 2025-12-29
**Related to:** Issue #4
**Status:** ✅ Explained & Resolved

---

## The Question

**User asked:** "Earlier why was it using stale results if the mapping was right?"

This is a great question because the code already had the correct PUT → PE mapping at `strategy.py:476-482`:

```python
# Map CALL/PUT to CE/PE (to match data format from broker)
if option_type == 'CALL':
    option_type_filter = 'CE'
elif option_type == 'PUT':
    option_type_filter = 'PE'
else:
    option_type_filter = option_type  # Already CE/PE
```

So why was the LTP stuck at ₹30.00 for multiple minutes?

---

## The Answer: Shared Variable vs Fresh API Call

The mapping was correct, but **the data source was wrong**.

### Data Flow Before Fix

```
Strategy Loop (every 5 min):
  └─> Fetches fresh options data
      └─> Stores in self.current_options_data  ← Shared variable
          └─> This data sits there for 5 minutes

Exit Monitor (every 1 min):
  └─> Reads self.current_options_data  ← Reading shared variable
      └─> Gets the SAME data for 5 minutes
          └─> option_data['close'] = 5-min candle close
              └─> Same ₹30.00 for 5 minutes!
```

### Code Before Fix (runner.py:334-346)

```python
# Get current options data for exit checks
with self.exit_monitor_lock:
    spot_price = self.current_spot_price        # ❌ Shared variable (5-min old)
    options_data = self.current_options_data    # ❌ Shared variable (5-min old)

if spot_price is None or options_data is None or options_data.empty:
    time_module.sleep(60)
    continue

# Check exits using strategy logic
print(f"[{current_time}] 🔍 Exit Monitor: Checking {len(positions)} position(s)...")
self.strategy._check_exits(current_time, options_data)  # ❌ Using 5-min old data!
```

**Problem:** Even though `strategy._check_exits()` correctly mapped PUT → PE, the `options_data` DataFrame itself was 5 minutes old!

---

## The Fix: Fetch Fresh Data Every Minute

### Data Flow After Fix

```
Exit Monitor (every 1 min):
  └─> Calls broker_api.get_spot_price()  ← Fresh API call
      └─> Calls _get_options_data()  ← Fresh API call
          └─> Calls broker_api.get_options_chain()  ← Fresh API call
              └─> Gets real-time quotes from Zerodha
                  └─> option_data['close'] = CURRENT LTP
                      └─> Different value every minute!
```

### Code After Fix (runner.py:334-350)

```python
# Fetch FRESH real-time LTP data (not 5-min cached data)
spot_price = self.broker_api.get_spot_price()  # ✅ Fresh API call
if not spot_price:
    print(f"[{current_time}] ⚠️ Exit Monitor: Could not get spot price, skipping...")
    time_module.sleep(60)
    continue

# Fetch fresh options chain with real-time LTP
print(f"[{current_time}] 🔍 Exit Monitor: Fetching real-time LTP for {len(positions)} position(s)...")
options_data = self._get_options_data(current_time, spot_price)  # ✅ Fresh API call
if options_data is None or options_data.empty:
    print(f"[{current_time}] ⚠️ Exit Monitor: Could not get options data, skipping...")
    time_module.sleep(60)
    continue

# Check exits using strategy logic with REAL-TIME LTP
self.strategy._check_exits(current_time, options_data)  # ✅ Fresh data with real-time LTP!
```

**Solution:** Now the exit monitor makes its own API call every minute, getting completely fresh data.

---

## Analogy

Think of it like this:

### Before Fix (Shared Variable)
```
Strategy Loop: "Let me check the newspaper and put it on the table"
               [Puts 5-minute-old newspaper on table at 14:30]

Exit Monitor at 14:31: "What's the current price?"
                       [Reads newspaper from table]
                       [Sees ₹30.00 from 14:30 data]

Exit Monitor at 14:32: "What's the current price?"
                       [Reads SAME newspaper from table]
                       [Sees ₹30.00 from 14:30 data]  ← Still stale!

Exit Monitor at 14:33: "What's the current price?"
                       [Reads SAME newspaper from table]
                       [Sees ₹30.00 from 14:30 data]  ← Still stale!

Exit Monitor at 14:34: "What's the current price?"
                       [Reads SAME newspaper from table]
                       [Sees ₹30.00 from 14:30 data]  ← Still stale!

Strategy Loop at 14:35: "Let me check the newspaper and update the table"
                        [Puts NEW newspaper on table]
                        [Now shows ₹30.50]

Exit Monitor at 14:36: "What's the current price?"
                       [Reads newspaper from table]
                       [Sees ₹30.50 from 14:35 data]  ← Finally updated!
```

### After Fix (Fresh API Call)
```
Exit Monitor at 14:31: "What's the current price?"
                       [Calls Zerodha API directly]
                       [Gets ₹30.15 - LIVE!]

Exit Monitor at 14:32: "What's the current price?"
                       [Calls Zerodha API directly]
                       [Gets ₹30.25 - LIVE!]

Exit Monitor at 14:33: "What's the current price?"
                       [Calls Zerodha API directly]
                       [Gets ₹29.95 - LIVE!]

Exit Monitor at 14:34: "What's the current price?"
                       [Calls Zerodha API directly]
                       [Gets ₹30.35 - LIVE!]
```

---

## Why The Mapping Didn't Matter

The mapping (PUT → PE) was always correct, so:

```python
# This part always worked:
option_type_filter = 'PE'  # ✅ Correct mapping

# This part worked too:
option_data = options_data[options_data['option_type'] == 'PE']  # ✅ Found the option

# But the DATA ITSELF was old:
ltp = option_data['close']  # ❌ This was the 5-min candle close, not real-time!
```

It's like having the correct address (PE) but looking at an old photograph of the house instead of seeing it in real-time.

---

## Test Results Proving The Fix

### Before Fix (Stuck at Same Value)
```
[14:45:29] LTP: ₹30.00 | P&L: +0.00%
[14:46:29] LTP: ₹30.00 | P&L: +0.00%  ← Exactly the same!
[14:47:29] LTP: ₹30.00 | P&L: +0.00%  ← Exactly the same!
```

### After Fix (Changing Every Minute)
```
[15:22:53] LTP: ₹43.95 | OI: 9,494,250
[15:23:53] LTP: ₹44.45 | OI: 9,494,250  ← Changed by +₹0.50!
[15:24:53] LTP: ₹42.85 | OI: 9,026,100  ← Changed by -₹1.60!
```

---

## Summary

| Component | Before Fix | After Fix |
|-----------|------------|-----------|
| **Mapping** | ✅ Correct (PUT → PE) | ✅ Correct (PUT → PE) |
| **Data Source** | ❌ Shared variable (5-min old) | ✅ Fresh API call (real-time) |
| **LTP Update Frequency** | ❌ Every 5 minutes | ✅ Every 1 minute |
| **Result** | ❌ Stuck at same value | ✅ Changes every minute |

**The mapping was never the problem - the data source was!**

---

## Files Changed

- `paper_trading/runner.py` (lines 334-350)
  - Changed from reading `self.current_options_data` to calling `self._get_options_data()`

---

## Related Issues

- [Issue #4: Exit Monitor Using Stale Data](04_exit_monitor_using_stale_data.md)
- [Issue #1: Exit Monitor Not Implemented](01_exit_monitor_not_implemented.md)

---

**Lesson:** Having the correct logic doesn't help if you're reading from stale data. Always verify your data source, not just your data processing.
