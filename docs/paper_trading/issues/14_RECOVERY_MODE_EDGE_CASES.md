# Issue 14: Recovery Mode Edge Cases

**Date:** 2025-12-30
**Severity:** MEDIUM (Data Loss Risk)
**Status:** ✅ FIXED

---

## Problem

When system crashes mid-day with open positions, if user **declines recovery**, the open position value is **lost** from the portfolio.

## Scenarios Analysis

### Scenario 1: Normal Daily Restart ✅ WORKS
```
Yesterday: ₹127,000
Today: No state file
Result: Carries forward ₹127,000 from yesterday ✓
```

### Scenario 2: Crash WITH Open Position ⚠️ HAS BUG
```
Before Crash:
  Portfolio: ₹127,000
  Cash: ₹125,000
  Position: ₹2,000 (active)

System Crashed → Restart

Option A: User Says YES to Recovery
  → Restores position ✓
  → Portfolio = ₹125,000 + ₹2,000 = ₹127,000 ✓

Option B: User Says NO to Recovery
  → Position abandoned ✗
  → Portfolio = ₹125,000 only
  → Lost ₹2,000! ✗
```

### Scenario 3: Crash WITHOUT Open Position ✅ WORKS
```
Before Crash:
  Portfolio: ₹127,500 (all cash, no positions)

System Crashed → Restart

User Says YES or NO:
  → Both result in ₹127,500 ✓
  → No position to lose ✓
```

## Root Cause

**File:** `paper_trading/runner.py:127-137`

```python
# Ask user if they want to recover
response = input("Resume from crash? (y/n): ").strip().lower()

if response == 'y':
    self.recovery_mode = True
    self.state_manager.resume_session()
    return True
else:
    # ❌ BUG: Allows declining even with open positions!
    print(f"Starting fresh session...")
    return False  # Abandons open positions
```

Then in `initialize()`:
```python
if not self.recovery_mode:
    # Gets latest portfolio
    previous_portfolio = self.state_manager.get_latest_portfolio()
    # ❌ This finds TODAY's state with cash only (excludes position value)
```

## Proposed Solution

### Option 1: Force Recovery When Positions Exist (Recommended)

```python
def try_recover_state(self):
    # ... existing code ...

    # Check if there are open positions
    has_open_positions = bool(self.recovery_info.get('active_positions_count', 0) > 0)

    if has_open_positions:
        # FORCE recovery if there are open positions
        print(f"⚠️  CRITICAL: Open positions detected - MUST recover!")
        print(f"Cannot start fresh session with active positions.")
        print(f"Forcing recovery mode...")

        self.recovery_mode = True
        self.state_manager.resume_session()
        return True
    else:
        # No positions - safe to ask user
        response = input("Resume from crash? (y/n): ").strip().lower()

        if response == 'y':
            self.recovery_mode = True
            self.state_manager.resume_session()
            return True
        else:
            print(f"Starting fresh session...")
            return False
```

### Option 2: Better Portfolio Handling on Decline

When user declines, use **yesterday's portfolio** instead of today's:

```python
def try_recover_state(self):
    # ... existing code ...

    if response != 'y':
        if self.recovery_info.get('active_positions_count', 0) > 0:
            print(f"⚠️  WARNING: Abandoning {self.recovery_info['active_positions_count']} open position(s)")
            print(f"This will result in portfolio discrepancy!")
            confirm = input("Are you sure? (yes/no): ").strip().lower()
            if confirm != 'yes':
                print("Forcing recovery mode...")
                self.recovery_mode = True
                self.state_manager.resume_session()
                return True

        # Mark today's state as invalid if positions were abandoned
        if self.recovery_info.get('active_positions_count', 0) > 0:
            # TODO: Delete or mark today's state file as corrupted
            pass

        return False
```

### Option 3: Auto-Close Positions at Market Price

```python
def try_recover_state(self):
    # ... existing code ...

    if response != 'y' and has_open_positions:
        print(f"⚠️  Auto-closing {self.recovery_info['active_positions_count']} position(s) at current market price...")

        # Connect to broker
        # Fetch current prices
        # Close positions
        # Update portfolio
        # Save state

        # Then start fresh with correct portfolio
```

## Recommended Implementation

**Use Option 1** - Force recovery when positions exist.

**Reasoning:**
1. **Safest** - No data loss
2. **Simplest** - No complex logic needed
3. **Correct** - You MUST handle open positions
4. **User-friendly** - Clear messaging

**Implementation:**

```python
def try_recover_state(self):
    """
    Try to recover from previous session

    Returns:
        bool: True if recovery successful
    """
    print(f"\n[{self._get_ist_now()}] Checking for previous session...")

    # Try to load today's state
    loaded_state = self.state_manager.load()

    if not loaded_state:
        print(f"[{self._get_ist_now()}] No previous state found - starting fresh")
        return False

    # Check if can recover
    if not self.state_manager.can_recover():
        print(f"[{self._get_ist_now()}] Previous state found but nothing to recover - starting fresh")
        return False

    # Get recovery info
    self.recovery_info = self.state_manager.get_recovery_info()

    print(f"\n{'='*80}")
    print(f"CRASH RECOVERY DETECTED")
    print(f"{'='*80}")
    print(f"Last Activity: {self.recovery_info['crash_time']}")
    print(f"Downtime: ~{self.recovery_info['downtime_minutes']} minutes")
    print(f"Active Positions: {self.recovery_info['active_positions_count']}")
    print(f"Daily P&L: ₹{self.recovery_info['daily_stats'].get('total_pnl_today', 0):,.2f}")
    print(f"{'='*80}\n")

    # Check for open positions
    has_open_positions = self.recovery_info.get('active_positions_count', 0) > 0

    if has_open_positions:
        # FORCE recovery - cannot abandon positions
        print(f"⚠️  CRITICAL: {self.recovery_info['active_positions_count']} open position(s) detected!")
        print(f"Cannot start fresh session with active positions.")
        print(f"Automatically resuming from crash...\n")

        self.recovery_mode = True
        self.state_manager.resume_session()
        return True
    else:
        # No positions - safe to ask user
        response = input("Resume from crash? (y/n): ").strip().lower()

        if response == 'y':
            print(f"\n[{self._get_ist_now()}] Resuming session...")
            self.recovery_mode = True
            self.state_manager.resume_session()
            return True
        else:
            print(f"\n[{self._get_ist_now()}] Starting fresh session...")
            return False
```

## Impact of Fix

### Before Fix:
- ❌ Can lose position value if user declines recovery
- ❌ Portfolio becomes inconsistent
- ❌ No way to recover lost value

### After Fix:
- ✅ Positions always restored if they exist
- ✅ Portfolio always consistent
- ✅ Clear messaging to user
- ✅ No data loss possible

## Testing Scenarios

### Test 1: Crash with Open Position
```
1. Start trading, enter position
2. Kill process (simulate crash)
3. Restart
4. Verify: Auto-resumes (doesn't ask), position restored ✓
```

### Test 2: Crash without Position
```
1. Start trading, enter and exit position
2. Kill process
3. Restart
4. Verify: Asks user, can decline safely ✓
```

### Test 3: Normal Daily Restart
```
1. End yesterday with ₹127,000
2. Start today fresh
3. Verify: No recovery prompt, carries forward ₹127,000 ✓
```

## Files to Modify

1. `paper_trading/runner.py:94-137` - Update try_recover_state()

## Related Issues

- Issue 11: Portfolio Carryover (related logic)
- Issue 09: Portfolio State Updates (related tracking)

## Status

✅ **FIXED** - Implementation complete (2025-12-30)

## Implementation

**File Modified:** `paper_trading/runner.py:94-150`

The fix has been implemented as recommended (Option 1):
- When crash recovery detects open positions, it **forces** recovery mode
- User is NOT given option to decline (would cause data loss)
- Clear messaging explains why auto-recovery is happening
- If no positions exist, user can still choose to decline safely

## Priority

**MEDIUM** - Implemented before production deployment ✓
- Prevents data loss in crash scenarios
- Ensures portfolio consistency
- Production-ready
