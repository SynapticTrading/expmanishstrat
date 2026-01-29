# 1 Trade/Day Limit - How It Works

## Overview

The system enforces **1 trade per day GLOBALLY** across:
- ✅ All brokers (Zerodha, AngelOne, etc.)
- ✅ All modes (Paper and Live)

This means:
- If you take a **paper** trade, you **cannot** take a **live** trade the same day
- If you take a **live** trade, you **cannot** take a **paper** trade the same day

---

## How It's Checked

### 🔍 Check Locations

The check happens in **2 places**:

1. **At System Startup** (recovery) - `runner.py`
2. **At Market Open** (daily reset) - `strategy.py`
3. **Before Entry** (trade execution) - `strategy.py`

---

## 1️⃣ At System Startup (Recovery Check)

**File:** `paper_trading/runner.py`
**Method:** `initialize()` → calls `_check_global_trades_today()`

```python
def _check_global_trades_today(self):
    """
    Check cumulative CSV for any trades today (from ANY broker).
    Returns: int - Number of trades today across all brokers
    """
    cumulative_csv = Path(__file__).parent / "logs" / "trades_cumulative.csv"

    # Read CSV and count trades from today
    df = pd.read_csv(cumulative_csv)
    today = self._get_ist_now().date()
    df['entry_date'] = pd.to_datetime(df['entry_time']).dt.date
    trades_today = len(df[df['entry_date'] == today])

    return trades_today
```

**⚠️ ISSUE FOUND:** This only checks `trades_cumulative.csv` (paper trades)
**Missing:** `live_trades_cumulative.csv` (live trades)

### What Happens on Startup

```python
# In initialize() after recovery
global_trades_today = self._check_global_trades_today()

if global_trades_today > 0:
    self.strategy.daily_trade_taken = True  # Block new trades
    print(f"📊 GLOBAL TRADE LIMIT: {global_trades_today} trade(s) already taken today")
```

**If recovering from crash:**
```python
# In initialize() during recovery
has_open_positions = recovery_info.get('active_positions_count', 0) > 0
has_closed_trades = len(recovery_info.get('closed_positions', [])) > 0
trades_today = recovery_info.get('daily_stats', {}).get('trades_today', 0)
global_trades_today = self._check_global_trades_today()

if has_open_positions or has_closed_trades or trades_today > 0 or global_trades_today > 0:
    self.strategy.daily_trade_taken = True
```

---

## 2️⃣ At Market Open (Daily Reset)

**File:** `paper_trading/core/strategy.py`
**Method:** `on_new_day()`

```python
def _check_global_trades_today(self, current_time):
    """
    Check cumulative CSV for any trades today (from ANY broker AND any mode).
    This ensures 1 trade/day limit works globally across:
    - All brokers (Zerodha, AngelOne, etc.)
    - All modes (paper and live)

    Returns: int - Number of trades today across all brokers and modes
    """
    logs_dir = Path(__file__).parent.parent / "logs"
    today = current_time.date()
    total_trades_today = 0

    # Check BOTH paper and live cumulative CSVs
    csv_files = [
        logs_dir / "trades_cumulative.csv",        # Paper trades ✅
        logs_dir / "live_trades_cumulative.csv"    # Live trades ✅
    ]

    for cumulative_csv in csv_files:
        if not cumulative_csv.exists():
            continue

        df = pd.read_csv(cumulative_csv)
        df['entry_date'] = pd.to_datetime(df['entry_time']).dt.date
        trades = len(df[df['entry_date'] == today])
        total_trades_today += trades

        if trades > 0:
            mode = "live" if "live_trades" in str(cumulative_csv) else "paper"
            print(f"📊 Found {trades} {mode} trade(s) today")

    return total_trades_today
```

### Daily Reset Logic

```python
def on_new_day(self, current_time, spot_price, options_data):
    """Called at market open to determine daily direction"""

    # Check for ANY trades today
    has_open_positions = len(self.broker.get_open_positions()) > 0
    has_closed_trades = len(self.broker.trade_history) > 0
    global_trades_today = self._check_global_trades_today(current_time)

    if has_open_positions:
        # Has open position → keep blocked
        print(f"⚠️  Open positions detected - keeping daily_trade_taken = True")
    elif has_closed_trades:
        # Has closed trade in memory → keep blocked
        self.daily_trade_taken = True
        print(f"⚠️  Closed trades detected - setting daily_trade_taken = True")
    elif global_trades_today > 0:
        # Found trade in CSV (paper OR live) → block
        self.daily_trade_taken = True
        print(f"⚠️  Global trades detected ({global_trades_today} trade(s) today) - setting daily_trade_taken = True")
    else:
        # No trades anywhere → allow
        self.daily_trade_taken = False
```

---

## 3️⃣ Before Entry (Trade Execution Block)

**File:** `paper_trading/core/strategy.py`
**Method:** `on_data_update()` → before calling `broker.buy()`

```python
def on_data_update(self, current_time, spot_price, options_data):
    """Process options data and check for entry conditions"""

    # ... entry signal detected ...

    # Check if already took trade today
    if self.daily_trade_taken:
        print(f"⛔ Entry blocked: Daily trade limit reached (1 trade/day)")
        return  # BLOCKED - cannot enter

    # Execute trade
    position = self.broker.buy(...)

    if position:
        self.daily_trade_taken = True  # Set flag immediately
```

---

## 📊 Flow Diagram

### Scenario 1: Paper Trade Taken, Try Live Trade

```
Morning:
  [09:15] System starts in PAPER mode
  [09:15] Check trades_cumulative.csv → 0 trades
  [09:15] daily_trade_taken = False
  [10:00] Paper entry signal → Execute trade
  [10:00] daily_trade_taken = True
  [10:00] Write to trades_cumulative.csv

Later:
  [11:00] System RESTARTS in LIVE mode
  [11:00] Check trades_cumulative.csv → 1 paper trade ❌ BUG!
  [11:00] ⚠️  Should check live_trades_cumulative.csv too
  [11:00] daily_trade_taken = True (if bug is fixed)
  [11:30] Live entry signal → ⛔ BLOCKED (correct behavior)
```

### Scenario 2: Live Trade Taken, Try Paper Trade

```
Morning:
  [09:15] System starts in LIVE mode
  [09:15] Check live_trades_cumulative.csv → 0 trades
  [09:15] daily_trade_taken = False
  [10:00] Live entry signal → Execute trade
  [10:00] daily_trade_taken = True
  [10:00] Write to live_trades_cumulative.csv

Later:
  [11:00] System RESTARTS in PAPER mode
  [11:00] Check trades_cumulative.csv → 0 trades ✅
  [11:00] on_new_day() checks BOTH CSVs → 1 live trade found ✅
  [11:00] daily_trade_taken = True (correct)
  [11:30] Paper entry signal → ⛔ BLOCKED (correct behavior)
```

---

## 🐛 BUG FOUND

### Issue: Incomplete Check in `runner._check_global_trades_today()`

**Current Code (runner.py):**
```python
def _check_global_trades_today(self):
    # ❌ Only checks paper trades
    cumulative_csv = Path(__file__).parent / "logs" / "trades_cumulative.csv"
```

**Should Be:**
```python
def _check_global_trades_today(self):
    # ✅ Check BOTH paper and live trades
    csv_files = [
        logs_dir / "trades_cumulative.csv",        # Paper
        logs_dir / "live_trades_cumulative.csv"    # Live
    ]
```

### Impact

**Broken Scenario:**
1. Take **live** trade in morning → `live_trades_cumulative.csv` has 1 trade
2. Restart system in **paper** mode
3. Startup check: `runner._check_global_trades_today()` checks `trades_cumulative.csv` → 0 trades ❌
4. Startup sets: `daily_trade_taken = False` ❌ WRONG!
5. Market open: `strategy.on_new_day()` checks BOTH CSVs → 1 trade found ✅
6. Sets: `daily_trade_taken = True` ✅ FIXED by strategy

**Result:** Window of vulnerability between startup and market open where flag is wrong.

---

## ✅ How It SHOULD Work (After Fix)

### All 3 Check Points Should Check BOTH CSVs

| Check Location | Current Status | Should Check |
|---------------|----------------|--------------|
| `runner._check_global_trades_today()` | ❌ Paper only | ✅ Paper + Live |
| `strategy._check_global_trades_today()` | ✅ Paper + Live | ✅ Paper + Live |
| `strategy.on_data_update()` | ✅ Uses flag | ✅ Uses flag |

---

## 📝 Current vs Desired Behavior

### Current Behavior

✅ **Works Correctly:**
- Take paper trade → `daily_trade_taken = True`
- Same session → Cannot take another paper trade ✅

✅ **Works Correctly (after market open):**
- Take live trade → restart in paper mode
- At market open → `on_new_day()` checks both CSVs → blocks ✅

❌ **Bug (between startup and market open):**
- Take live trade → restart in paper mode
- Startup check misses live trade → `daily_trade_taken = False` ❌
- Market open fixes it → `daily_trade_taken = True` ✅

### Desired Behavior

✅ **After Fix:**
- Take live trade → restart in paper mode
- Startup check finds live trade → `daily_trade_taken = True` ✅
- Market open confirms → `daily_trade_taken = True` ✅
- No window of vulnerability

---

## 🔧 Fix Required

Update `runner._check_global_trades_today()` to match `strategy._check_global_trades_today()`:

```python
# runner.py
def _check_global_trades_today(self):
    """
    Check cumulative CSV for any trades today (from ANY broker AND mode).
    """
    try:
        logs_dir = Path(__file__).parent / "logs"
        today = self._get_ist_now().date()
        total_trades_today = 0

        # Check BOTH paper and live cumulative CSVs ← FIX
        csv_files = [
            logs_dir / "trades_cumulative.csv",        # Paper
            logs_dir / "live_trades_cumulative.csv"    # Live
        ]

        for cumulative_csv in csv_files:
            if not cumulative_csv.exists():
                continue

            df = pd.read_csv(cumulative_csv)
            if df.empty:
                continue

            df['entry_date'] = pd.to_datetime(df['entry_time']).dt.date
            trades = len(df[df['entry_date'] == today])
            total_trades_today += trades

            if trades > 0:
                mode = "live" if "live_trades" in str(cumulative_csv) else "paper"
                print(f"📊 Found {trades} {mode} trade(s) today")

        return total_trades_today
    except Exception as e:
        print(f"⚠️  Error checking global trades: {e}")
        return 0
```

---

## 🎯 Summary

### How 1 Trade/Day Works

1. **Startup Check** (runner.py)
   - ❌ Currently: Only checks paper CSV
   - ✅ Should: Check BOTH paper and live CSVs

2. **Market Open Check** (strategy.py)
   - ✅ Already: Checks BOTH paper and live CSVs

3. **Entry Check** (strategy.py)
   - ✅ Already: Uses `daily_trade_taken` flag

### What Needs Fixing

Fix `runner._check_global_trades_today()` to check BOTH:
- `logs/trades_cumulative.csv` (paper trades)
- `logs/live_trades_cumulative.csv` (live trades)

This ensures the limit works **globally across all modes** from the moment the system starts, not just after market open.
