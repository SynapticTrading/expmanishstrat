# Issue #3: Entry Time Window Bug (Seconds Comparison)

**Date:** 2025-12-29
**Severity:** High
**Status:** ✅ Identified (Later Reverted per User Request)

---

## Problem

Entry checks were not running at 14:30 PM despite being within the configured entry window.

### Root Cause

The time comparison was including seconds:

```python
current_time_only = current_time.time()  # e.g., time(14, 30, 25)
entry_end_time = time(14, 30)            # Defaults to time(14, 30, 0)

if self.entry_start_time <= current_time_only <= self.entry_end_time:
    self._check_entry(...)
```

**Result:**
`time(14, 30, 25) > time(14, 30, 0)` → Entry check skipped!

### Observed Behavior

```
[14:25:00] STRATEGY LOOP - Processing 5-min candle...
[14:25:00] Checking entry: PUT 25950.0, Expiry=2025-12-30
[14:25:00] PUT 25950.0: Price=₹42.95, VWAP=₹42.95 - BELOW ✗
STATUS UPDATE

[14:30:00] STRATEGY LOOP - Processing 5-min candle...
[14:30:25] ✓ Retrieved 22 option quotes
[14:30:25] Waiting 275s for next candle at 14:35:00  ← NO ENTRY CHECK!
```

By the time data was fetched (14:30:25), it was past 14:30:00, so entry was skipped.

---

## Solution (Initially Implemented)

Created a time comparison that ignores seconds:

```python
current_time_only = current_time.time()
# For time window comparisons, ignore seconds (only compare HH:MM)
current_time_hhmm = time(current_time_only.hour, current_time_only.minute)

# Check entry conditions (only during entry window)
# Use HH:MM comparison to allow entry during the entire end minute (e.g., 14:30:00-14:30:59)
if self.entry_start_time <= current_time_hhmm <= self.entry_end_time:
    self._check_entry(current_time, spot_price, options_data)
```

This allowed entries anytime during 14:30:00 - 14:30:59.

---

## Revert

**User requested to revert this change** to maintain strict time boundaries.

The original behavior was restored:
- Entry window: 09:30:00 to 14:30:00 (strict)
- If data fetching takes time and it's past 14:30:00, entry is skipped

### Rationale

User prefers precise time boundaries matching backtest behavior, even if occasional delays cause missed entries at the boundary.

---

## Current Status

The code uses strict time comparison with seconds. If you want entries to work during the entire 14:30 minute, the fix is available in git history.

---

## Files Changed (Then Reverted)

- `paper_trading/core/strategy.py` (lines 176, 194, 198)

---

## Workaround

To ensure entries at 14:30, either:
1. Extend `end_time` to `14:31` in config
2. Use the HH:MM comparison fix from git history
3. Accept that 14:30 entries may occasionally be skipped due to API latency
