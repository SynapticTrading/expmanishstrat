# Optimized Fetch Fixes - Summary

## Issues Found and Fixed

### 🐛 Issue #1: `entry_oi` Not Reset on Strike Update (CRITICAL - Original Bug)

**Problem:**
- Strike update logic existed in TWO places: `runner.py` (lines 900-903) and `strategy.py` (lines 335-344)
- When optimized fetch was active, `runner.py` updated the strike BEFORE calling strategy
- Then `strategy.py` checked if strike changed, but it was already changed by runner
- The condition `new_strike != self.daily_strike` was always False
- Result: `entry_oi` and `vwap_initialized` reset code NEVER executed
- This caused OI change to use the old strike's baseline, showing incorrect percentages like +89.53%

**Execution Flow (OLD - BUGGY):**
```
1. runner.py line 900: Detects strike change 25750 → 25700
2. runner.py line 902: Updates self.strategy.daily_strike = 25700
3. runner.py line 903: Logs "📍 STRIKE UPDATED"
4. strategy.py line 335: Calculates new_strike = 25700
5. strategy.py line 335: Checks new_strike != self.daily_strike (25700 != 25700 = False)
6. strategy.py lines 340-344: Reset code NEVER RUNS ❌
7. strategy.py line 399: entry_oi still exists with OLD strike's baseline
8. Result: OI change shows +89.53% instead of 0%
```

**Fix:**
- Removed strike update logic from `runner.py` (single source of truth)
- Runner now only calculates the strike and fetches data for it
- Strategy receives available strikes via DataFrame metadata
- Strategy updates its own strike and properly resets all state variables

**Execution Flow (NEW - FIXED):**
```
1. runner.py: Calculates current_strike = 25700
2. runner.py: Fetches data for strike 25700
3. runner.py: Adds available_strikes to DataFrame metadata
4. strategy.py line 327: Uses available_strikes from metadata
5. strategy.py line 335: Calculates new_strike = 25700
6. strategy.py line 341: Checks new_strike != self.daily_strike (25700 != 25750 = True) ✓
7. strategy.py line 343: Updates self.daily_strike = 25700 ✓
8. strategy.py lines 346-348: Resets entry_oi ✓
9. strategy.py lines 351-353: Resets vwap_initialized ✓
10. strategy.py lines 356-363: Cleans up old VWAP data ✓
11. Result: OI change correctly shows 0% for new strike ✓
```

---

### 🐛 Issue #2: Redundant Strike Calculation with Limited Data

**Problem:**
- With optimized fetch, `options_data` contains only 1 strike (the current one)
- Strategy tried to recalculate strike using `options_data['strike'].unique()`
- This returned only [current_strike], making the calculation meaningless
- Strike would always be "recalculated" as the same value

**Fix:**
- Runner passes `available_strikes` list (11 strikes: ±5 from ATM) in DataFrame metadata
- Strategy checks for metadata and uses the fuller strike range if available
- Falls back to `options_data['strike'].unique()` for backward compatibility with full fetch

**Code Changes (strategy.py lines 326-334):**
```python
# Use available_strikes from metadata if provided (optimized fetch path),
# otherwise use strikes from options_data (full fetch path)
if hasattr(options_data, 'attrs') and 'available_strikes' in options_data.attrs:
    strikes = options_data.attrs['available_strikes']
else:
    strikes = options_data['strike'].unique()
```

---

### 🐛 Issue #3: VWAP Memory Bloat

**Problem:**
- When strike changed, old strike's VWAP data remained in `vwap_running_totals` dict
- Each strike update left orphaned data: `{(old_strike, option_type, expiry): {...}}`
- Over a trading day with multiple strike updates, memory would accumulate unused data

**Fix:**
- Added cleanup code to remove old strike's VWAP data when strike changes
- Logs cleanup action for visibility

**Code Changes (strategy.py lines 356-363):**
```python
# Clean up old strike's VWAP data to prevent memory bloat
keys_to_remove = [
    key for key in self.vwap_running_totals.keys()
    if key[0] == old_strike  # key format: (strike, option_type, expiry)
]
for key in keys_to_remove:
    del self.vwap_running_totals[key]

if keys_to_remove:
    print(f"[{current_time}] 🧹 Cleaned up VWAP data for old strike {old_strike}")
```

---

### 🐛 Issue #4: Duplicate Strike Update Logic (Design Issue)

**Problem:**
- Strike update logic existed in two places creating confusion and bugs
- Violated single responsibility principle
- Made code harder to maintain and debug

**Fix:**
- **Removed** strike update from `runner.py` (data fetching layer)
- **Kept** strike update in `strategy.py` (business logic layer)
- Clear separation of concerns:
  - Runner: Calculate strikes, fetch data, pass metadata
  - Strategy: Receive data, make decisions, update state

---

## Files Modified

### 1. `paper_trading/runner.py` (lines 878-918)
**Changes:**
- Removed direct update of `self.strategy.daily_strike`
- Removed duplicate "📍 STRIKE UPDATED" log message
- Added `available_strikes` to DataFrame metadata
- Runner now fetches data for calculated strike without updating strategy state

### 2. `paper_trading/core/strategy.py` (lines 326-363)
**Changes:**
- Added metadata check to use `available_strikes` from optimized fetch
- Enhanced strike update block with proper state resets
- Added VWAP cleanup when strike changes
- Added cleanup log message for visibility

---

## Expected Behavior After Fix

### Strike Update Logs (Correct):
```
[2026-02-03 09:45:00] 📍 STRIKE UPDATED: 25750 → 25700 (Spot: 25727.30)
[2026-02-03 09:45:00] 🧹 Cleaned up VWAP data for old strike 25750
[2026-02-03 09:45:00] 🎯 Initialized VWAP for PUT 25700: 14 bars from 9:15 AM
[2026-02-03 09:45:00] PUT 25700: OI=8,714,420, Change=0 (+0.00%) - BUILDING ✓
```

Key differences from the buggy logs:
1. Only ONE "📍 STRIKE UPDATED" message (from strategy, not runner)
2. OI Change shows 0% (not +89.53%)
3. VWAP cleanup message appears
4. VWAP initialized for NEW strike

---

## Test Files Affected

The following test files need updating to reflect new behavior:

### ⚠️ Needs Update:
1. `paper_trading/tests/test_runner_strike_update.py` - Tests runner strike updates (now done by strategy)
2. `paper_trading/tests/test_runner_strike_direct.py` - Direct runner tests (now invalid)

These tests expect `runner._get_options_for_entry()` to update `self.strategy.daily_strike`,
but with the fix, the strike update happens in `strategy._check_entry()` instead.

**Recommended Action:**
- Run manual testing first to verify the fix works in production
- Then update/rewrite tests to reflect new architecture
- Consider adding integration tests that test the full runner → strategy flow

---

## Verification Steps

### Manual Testing:
1. Start paper trading with optimized fetch enabled
2. Monitor logs when strike updates occur
3. Verify:
   - ✅ Only ONE "📍 STRIKE UPDATED" message per update
   - ✅ OI Change shows 0% immediately after strike update
   - ✅ VWAP shows "Initialized VWAP" for new strike
   - ✅ No duplicate or stale data in VWAP calculations
   - ✅ Cleanup message appears: "🧹 Cleaned up VWAP data for old strike"

### Log Pattern to Look For:
```
[TIME] 📍 STRIKE UPDATED: X → Y
[TIME] 🧹 Cleaned up VWAP data for old strike X
[TIME] 🎯 Initialized VWAP for [CALL/PUT] Y: N bars from 9:15 AM
[TIME] [CALL/PUT] Y: OI=..., Change=0 (+0.00%) - BUILDING
```

---

## Architecture Changes Summary

### Before (Buggy):
```
Runner (Data Layer)          Strategy (Logic Layer)
  │                                │
  ├─ Calculate strike              ├─ Calculate strike (redundant)
  ├─ Update strategy.daily_strike  ├─ Check if changed (always False!)
  ├─ Log "STRIKE UPDATED"          ├─ Reset state (NEVER RUNS!)
  └─ Fetch data                    └─ Use stale entry_oi ❌
```

### After (Fixed):
```
Runner (Data Layer)               Strategy (Logic Layer)
  │                                     │
  ├─ Calculate strike                   ├─ Receive data + metadata
  ├─ Fetch data for strike              ├─ Check if strike changed
  ├─ Add available_strikes metadata     ├─ Update self.daily_strike
  └─ Return DataFrame                   ├─ Reset entry_oi ✓
                                        ├─ Reset vwap_initialized ✓
                                        ├─ Cleanup old VWAP data ✓
                                        └─ Continue with fresh state ✓
```

---

## Additional Notes

### Why Metadata Instead of Fetching Multiple Strikes?
- Optimized fetch's purpose is to fetch only 1 strike (fast, 1 API call)
- We need strike range for the `get_nearest_strike()` calculation
- Solution: Pass calculated strike range as metadata (no extra API calls)
- Maintains optimization while providing necessary data

### Why Not Just Use options_data['strike'].unique()?
- With optimized fetch, this returns only [current_strike]
- Not enough data to detect if spot moved enough to warrant strike change
- Runner has already calculated the full range, so we pass it along

### Thread Safety Note:
- The exit monitor thread also calls strategy methods
- No changes needed there - it doesn't update strikes
- Exit logic tracks existing position strikes (immutable after entry)
