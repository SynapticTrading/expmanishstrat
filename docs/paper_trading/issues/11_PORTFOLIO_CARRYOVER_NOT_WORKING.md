# Issue 11: Portfolio Not Carrying Forward Across Days

**Date:** 2025-12-30
**Severity:** CRITICAL
**Status:** ✅ FIXED

---

## Problem

When restarting paper trading on a new day, portfolio always started at ₹100,000 instead of carrying forward previous day's balance:

**Dec 29 End of Day:**
```json
"portfolio": {
  "current_cash": 100352.5  // ₹352.50 profit
}
```

**Dec 30 Startup:**
```
Paper Broker initialized with capital: ₹100,000.00  // ❌ Reset to default!
```

**Expected Behavior:**
```
📊 PORTFOLIO CARRYOVER
  Previous Date: 2025-12-29
  Starting Capital: ₹100,352.50  // ← Should carry forward!
```

## Root Cause

**Wrong order of operations in initialization:**

**File:** `paper_trading/runner.py:148-154` (original)

```python
def initialize(self):
    if not self.recovery_mode:
        print("Initializing new session...")
        self.state_manager.initialize_session(mode="paper")  # ❌ Creates TODAY's file FIRST!

        # Check for previous portfolio
        previous_portfolio = self.state_manager.get_latest_portfolio()  # ❌ Finds TODAY's empty file!
```

### What Happened:
1. `initialize_session()` creates `trading_state_20251230.json` (empty)
2. `get_latest_portfolio()` sorts files by date, finds newest
3. Newest = `trading_state_20251230.json` (just created, empty!)
4. Returns `current_cash: 0` or defaults to ₹100,000

### The Deadly Sequence:
```
Step 1: initialize_session() creates trading_state_20251230.json
        {
          "portfolio": {
            "current_cash": 100000  // Default value
          }
        }

Step 2: get_latest_portfolio() finds files
        - trading_state_20251229.json  (has ₹100,352.50)
        - trading_state_20251230.json  (just created, ₹100,000)

Step 3: Sorts by date, picks newest = 20251230.json
        Returns: current_cash = 100,000  // ❌ Wrong file!

Step 4: Initializes broker with ₹100,000
        // Lost ₹352.50 profit from yesterday!
```

## Solution

**Reverse the order - Check BEFORE creating new state:**

**File:** `paper_trading/runner.py:148-173`

```python
def initialize(self):
    """Initialize components"""

    # Initialize or resume state
    if not self.recovery_mode:
        print(f"\n[{self._get_ist_now()}] Initializing new session...")

        # ✅ CRITICAL: Check for previous portfolio BEFORE creating today's state file
        previous_portfolio = self.state_manager.get_latest_portfolio()

        if previous_portfolio:
            # Carry forward portfolio from previous day
            initial_capital = previous_portfolio['current_cash']
            print(f"[{self._get_ist_now()}] 📊 PORTFOLIO CARRYOVER")
            print(f"  Previous Date: {previous_portfolio['previous_date']}")
            print(f"  Starting Capital: ₹{initial_capital:,.2f}")
            print(f"  Previous P&L: ₹{previous_portfolio['total_pnl']:+,.2f}")
            print(f"  Previous Trades: {previous_portfolio['trades_count']}")
            print(f"  Previous Win Rate: {previous_portfolio['win_rate']:.1f}%")
        else:
            # First time running - use config
            initial_capital = self.config['position_sizing']['initial_capital']
            print(f"[{self._get_ist_now()}] 🆕 First session - Starting with ₹{initial_capital:,.2f}")

        # ✅ NOW create today's state file (after reading yesterday's)
        self.state_manager.initialize_session(mode="paper")
```

### Correct Sequence:
```
Step 1: get_latest_portfolio() finds files
        - trading_state_20251229.json  (has ₹100,352.50)
        (No 20251230.json yet!)

Step 2: Returns Dec 29's portfolio
        current_cash = 100,352.50  ✓ Correct!

Step 3: initialize_session() creates trading_state_20251230.json
        With initial_capital = 100,352.50  ✓ Carried forward!

Step 4: Initializes broker with ₹100,352.50
        ✓ Portfolio continues from yesterday!
```

## Supporting Method

**File:** `paper_trading/core/state_manager.py:428-466`

Created `get_latest_portfolio()` method to safely retrieve previous day's portfolio:

```python
def get_latest_portfolio(self):
    """
    Get portfolio value from the most recent state file
    Used for carrying forward portfolio across trading days

    Returns:
        dict: Portfolio info with initial_capital, current_cash, total_pnl
              or None if no previous state found
    """
    # Get all state files sorted by date (newest first)
    state_files = sorted(self.state_dir.glob("trading_state_*.json"), reverse=True)

    if not state_files:
        return None

    # Try to load the most recent state file
    for state_file in state_files:
        try:
            with open(state_file, 'r') as f:
                state = json.load(f)

            portfolio = state.get('portfolio', {})
            daily_stats = state.get('daily_stats', {})

            # Return portfolio info
            return {
                'previous_date': state.get('date'),
                'initial_capital': portfolio.get('initial_capital', 100000),
                'current_cash': portfolio.get('current_cash', 100000),
                'total_value': portfolio.get('total_value', 100000),
                'total_pnl': daily_stats.get('total_pnl_today', 0),
                'trades_count': daily_stats.get('trades_today', 0),
                'win_rate': daily_stats.get('win_rate', 0)
            }
        except Exception as e:
            print(f"Could not read {state_file}: {e}")
            continue

    return None
```

## Example Results

### Day 1 (Dec 29) End:
```json
{
  "date": "2025-12-29",
  "portfolio": {
    "initial_capital": 100000,
    "current_cash": 100352.5,
    "total_value": 100352.5
  },
  "daily_stats": {
    "total_pnl_today": 352.5,
    "trades_today": 1,
    "win_rate": 100.0
  }
}
```

### Day 2 (Dec 30) Start:
```
📊 PORTFOLIO CARRYOVER
  Previous Date: 2025-12-29
  Starting Capital: ₹100,352.50    ✓ Carried forward!
  Previous P&L: ₹+352.50
  Previous Trades: 1
  Previous Win Rate: 100.0%

Paper Broker initialized with capital: ₹100,352.50  ✓ Correct!
```

### Day 2 (Dec 30) State:
```json
{
  "date": "2025-12-30",
  "portfolio": {
    "initial_capital": 100352.5,   ✓ Started from yesterday
    "current_cash": 100352.5,      ✓ Fresh day, no trades yet
    "total_value": 100352.5
  }
}
```

## Verification

**Test Scenario:**
1. Day 1: Start with ₹100,000, make ₹352.50 profit → End with ₹100,352.50
2. Restart service (simulating daily cron job)
3. Day 2: Should start with ₹100,352.50 ✓

**Confirmed working with:**
- Dec 29 → Dec 30 carryover
- Multiple session restarts
- Profit and loss scenarios

## Impact

- ✅ Portfolio compounds over time (like real account)
- ✅ Proper ROI tracking across days
- ✅ Server restart safe (daily cron compatible)
- ✅ Historical portfolio growth preserved
- ✅ Multi-day performance analysis possible

## Related Issues

- **Prerequisite:** Issue 09 (Portfolio state must update correctly)
- **Enables:** Long-term paper trading with cumulative P&L

## Files Modified

1. `paper_trading/runner.py:148-173` - Reordered initialization logic
2. `paper_trading/core/state_manager.py:428-466` - Added get_latest_portfolio()

## Production Deployment Notes

Perfect for **daily cron job** on server:
```bash
# Daily cron at 9:00 AM IST
0 9 * * 1-5 /path/to/start_paper_trading.sh
```

System will automatically:
1. Check previous day's portfolio
2. Carry forward balance
3. Start fresh daily state
4. Trade with compounded capital
