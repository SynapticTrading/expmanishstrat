# Recovery & Portfolio Carryover - All Use Cases

**Purpose:** Complete reference for all crash recovery and portfolio carryover scenarios

**Date:** 2025-12-30

---

## Table of Contents

1. [Normal Day-to-Day Operation](#normal-day-to-day-operation)
2. [Crash Recovery - With Open Positions](#crash-recovery---with-open-positions)
3. [Crash Recovery - Without Open Positions](#crash-recovery---without-open-positions)
4. [Edge Cases & Known Issues](#edge-cases--known-issues)
5. [CSV Logging Behavior](#csv-logging-behavior)
6. [Quick Reference Table](#quick-reference-table)

---

## Normal Day-to-Day Operation

### Case 1A: First Day Ever (Fresh Installation)

**Scenario:**
```
- No previous state files exist
- Fresh installation of paper trading system
```

**Execution Flow:**
```python
1. try_recover_state()
   → load() searches for: trading_state_20251229.json
   → File not found
   → Returns False

2. initialize()
   → get_latest_portfolio()
      → Searches: paper_trading/state/*.json
      → No files found
      → Returns None
   → initial_capital = config['position_sizing']['initial_capital']
   → initial_capital = ₹100,000
   → initialize_session() creates: trading_state_20251229.json

3. CSV Logging
   → Daily CSV: trades_20251229_093000.csv (created fresh)
   → Cumulative CSV: trades_cumulative.csv (created with header)
```

**Result:**
```
✅ Portfolio: ₹100,000
✅ Message: "🆕 First session - Starting with ₹100,000.00"
✅ No recovery prompt
✅ State file: trading_state_20251229.json created
```

---

### Case 1B: Second Day Onwards (Normal Daily Start)

**Scenario:**
```
Day 1 (Dec 29): Ended with ₹100,352.50 (after 1 trade)
Day 2 (Dec 30): Normal restart at 9:15 AM
```

**Yesterday's State (trading_state_20251229.json):**
```json
{
  "date": "2025-12-29",
  "portfolio": {
    "initial_capital": 100000,
    "current_cash": 100352.5,
    "total_value": 100352.5
  },
  "daily_stats": {
    "trades_today": 1,
    "total_pnl_today": 352.5
  }
}
```

**Execution Flow:**
```python
1. try_recover_state()
   → load() searches for: trading_state_20251230.json
   → File not found (today's file doesn't exist yet)
   → Returns False

2. initialize()
   → get_latest_portfolio()
      → Searches: paper_trading/state/*.json (sorted by date, newest first)
      → Finds: trading_state_20251229.json
      → Reads portfolio: current_cash = ₹100,352.50
      → Returns {
           'previous_date': '2025-12-29',
           'current_cash': 100352.5,
           'total_pnl': 352.5,
           'trades_count': 1
         }
   → initial_capital = ₹100,352.50 (from yesterday's current_cash)
   → initialize_session() creates: trading_state_20251230.json
      → Sets initial_capital = ₹100,352.50
      → Sets current_cash = ₹100,352.50

3. CSV Logging
   → Daily CSV: trades_20251230_091500.csv (NEW file for today)
   → Cumulative CSV: trades_cumulative.csv (APPEND to existing file)
```

**Result:**
```
✅ Portfolio: ₹100,352.50 (carried forward from Dec 29)
✅ Message:
    "📊 PORTFOLIO CARRYOVER
     Previous Date: 2025-12-29
     Starting Capital: ₹100,352.50
     Previous P&L: +₹352.50
     Previous Trades: 1
     Previous Win Rate: 100.0%"
✅ No recovery prompt
✅ State file: trading_state_20251230.json created
✅ Daily stats: Reset to 0 trades, ₹0 P&L (new day)
```

**CSV Files After Day 2 Trade:**
```
paper_trading/logs/
├── trades_20251229_093000.csv      # Day 1: 1 trade
├── trades_20251230_091500.csv      # Day 2: 1 trade
└── trades_cumulative.csv           # Total: 2 trades
```

---

## Crash Recovery - With Open Positions

### Case 2A: Mid-Trade Crash (Position Open)

**Scenario:**
```
Time: 2:25 PM (same day)
Portfolio before crash:
  Initial: ₹100,352.50
  Entry: Bought 75 lots @ ₹5.00 = ₹375
  Cash: ₹99,977.50
  Position value: ₹375
  Total: ₹100,352.50

CRASH at 2:30 PM
RESTART at 2:45 PM
```

**State File (trading_state_20251230.json) at Crash Time:**
```json
{
  "date": "2025-12-30",
  "active_positions": {
    "PAPER_20251230_001": {
      "strike": 25900,
      "option_type": "PUT",
      "entry_price": 5.0,
      "size": 75,
      "entry_time": "2025-12-30 14:25:19"
    }
  },
  "strategy_state": {
    "trading_strike": 25900,
    "direction": "CALL",
    "vwap_tracking": {...}
  },
  "portfolio": {
    "initial_capital": 100352.5,
    "current_cash": 99977.5,
    "positions_value": 375.0,
    "total_value": 100352.5
  },
  "daily_stats": {
    "trades_today": 0,
    "total_pnl_today": 0
  }
}
```

**Execution Flow:**
```python
1. try_recover_state()
   → load() finds: trading_state_20251230.json ✓
   → can_recover() checks:
      → active_positions = {"PAPER_20251230_001": {...}} → TRUE ✓
   → get_recovery_info()
      → active_positions_count = 1

   → Displays:
      "CRASH RECOVERY DETECTED
       Last Activity: 2025-12-30 14:30:00
       Downtime: ~15 minutes
       Active Positions: 1
       Daily P&L: ₹0.00"

   → has_open_positions = True
   → FORCE RECOVERY (Issue 14 fix):
      → Print: "⚠️  CRITICAL: 1 open position(s) detected!"
      → Print: "Cannot start fresh session with active positions."
      → Print: "Automatically resuming from crash..."
      → NO USER PROMPT
      → recovery_mode = True
      → resume_session()

2. initialize()
   → recovery_mode = True (skip portfolio carryover logic)
   → initial_capital = ₹99,977.50 (from crashed state)

3. Strategy & Broker
   → Restores position: 75 lots @ ₹5.00
   → Restores strategy state: CALL 25900, VWAP tracking
   → Continue monitoring exits with real-time LTP
```

**Result:**
```
✅ Auto-resumes (NO user choice)
✅ Position restored: 75 lots @ ₹5.00
✅ Cash: ₹99,977.50
✅ Portfolio: ₹100,352.50
✅ Strategy: CALL @ 25900 (preserved)
✅ VWAP tracking: Restored
✅ Exit monitoring: Continues normally
```

---

## Crash Recovery - Without Open Positions

### Case 3A: Crash After Direction Determined (Before Entry)

**Scenario:**
```
Time: 11:00 AM
- Daily analysis completed
- Direction: CALL @ 25900
- VWAP initialized
- Max OI strikes stored
- Waiting for entry conditions
- NO TRADE ENTERED YET

CRASH at 11:30 AM
RESTART at 11:45 AM
```

**State File (trading_state_20251230.json):**
```json
{
  "date": "2025-12-30",
  "active_positions": {},  // EMPTY - no open positions
  "strategy_state": {
    "trading_strike": 25900,
    "direction": "CALL",
    "max_call_oi_strike": 26000,
    "max_put_oi_strike": 25800,
    "vwap_tracking": {
      "sum_price_volume": 1234567.5,
      "sum_volume": 50000
    }
  },
  "portfolio": {
    "initial_capital": 100352.5,
    "current_cash": 100352.5,
    "positions_value": 0,
    "total_value": 100352.5
  },
  "daily_stats": {
    "trades_today": 0,
    "total_pnl_today": 0
  }
}
```

**Execution Flow:**
```python
1. try_recover_state()
   → load() finds: trading_state_20251230.json ✓
   → can_recover() checks:
      → active_positions? Empty
      → trading_strike exists? YES (25900) → TRUE ✓

   → get_recovery_info()
      → active_positions_count = 0

   → Displays recovery info
   → has_open_positions = False
   → ASK USER:
      Input: "Resume from crash? (y/n): "
```

**User Choice: YES**
```python
   → recovery_mode = True
   → resume_session()

2. initialize()
   → recovery_mode = True
   → initial_capital = ₹100,352.50 (from crashed state)

3. Strategy
   → Restores: direction = CALL, strike = 25900
   → Restores: VWAP tracking
   → Restores: Max OI strikes
   → Continues: Checking entry conditions
```

**Result if YES:**
```
✅ Strategy state: CALL @ 25900 (preserved)
✅ VWAP tracking: Restored
✅ Max OI strikes: Restored
✅ Portfolio: ₹100,352.50
✅ Continues checking entry conditions
```

**User Choice: NO**
```python
   → recovery_mode = False
   → Returns False

2. initialize()
   → recovery_mode = False
   → get_latest_portfolio()
      → Finds: trading_state_20251230.json (TODAY's crashed file)
      → Returns current_cash = ₹100,352.50
   → initial_capital = ₹100,352.50
   → initialize_session() creates: trading_state_20251230.json
      → OVERWRITES crashed file with fresh state
      → daily_stats: Reset to 0
      → strategy_state: Empty
      → closed_positions: []

3. Strategy
   → RE-ANALYZES market (could determine DIFFERENT direction!)
   → VWAP tracking: Starts fresh
   → Max OI strikes: Re-calculates
```

**Result if NO:**
```
⚠️  Strategy state: LOST (will re-analyze)
⚠️  VWAP tracking: RESET
⚠️  Direction: Could be DIFFERENT now (PUT instead of CALL)
✅ Portfolio: ₹100,352.50 (preserved from crashed state)
⚠️  Might pick different strike/direction mid-day!
```

---

### Case 3B: Crash After Trade Closed (Has Daily P&L)

**Scenario:**
```
Time: 2:00 PM
- Entered and exited 1 trade
- Profit: +₹127.50
- Portfolio: ₹100,480.00
- All cash (no positions)

CRASH at 2:30 PM
RESTART at 2:45 PM
```

**State File (trading_state_20251230.json):**
```json
{
  "date": "2025-12-30",
  "active_positions": {},  // No open positions
  "closed_positions": [
    {
      "order_id": "PAPER_20251230_001",
      "strike": 25900,
      "entry_price": 5.0,
      "exit_price": 6.7,
      "size": 75,
      "pnl": 127.5,
      "exit_reason": "trailing_stop"
    }
  ],
  "strategy_state": {
    "trading_strike": 25900,
    "direction": "CALL"
  },
  "portfolio": {
    "initial_capital": 100352.5,
    "current_cash": 100480.0,
    "total_value": 100480.0
  },
  "daily_stats": {
    "trades_today": 1,
    "total_pnl_today": 127.5,
    "win_count": 1,
    "win_rate": 100.0
  }
}
```

**Execution Flow:**
```python
1. try_recover_state()
   → load() finds: trading_state_20251230.json ✓
   → can_recover() → trading_strike exists → TRUE ✓
   → active_positions_count = 0
   → has_open_positions = False
   → ASK USER: "Resume from crash? (y/n): "
```

**User Choice: YES**
```python
   → recovery_mode = True
   → resume_session()
   → Preserves ALL state data
```

**Result if YES:**
```
✅ Portfolio: ₹100,480.00
✅ Daily stats: 1 trade, ₹127.50 profit (preserved)
✅ Closed positions: Trade history preserved
✅ Strategy state: CALL @ 25900 (preserved)
✅ Trade limit: Already used 1 of 1 trades (enforced)
✅ Won't enter new trades (limit reached)
```

**User Choice: NO**
```python
   → recovery_mode = False

2. initialize()
   → get_latest_portfolio()
      → Finds: trading_state_20251230.json (today)
      → Returns current_cash = ₹100,480.00
   → initialize_session()
      → OVERWRITES: trading_state_20251230.json
      → Creates fresh state with empty daily_stats
```

**Result if NO:**
```
✅ Portfolio: ₹100,480.00 (value preserved)
❌ Daily stats: 0 trades, ₹0 P&L (LOST!)
❌ Closed positions: [] (LOST!)
❌ Trade limit: Shows 0 trades, will allow new trade (WRONG!)
✅ CSV log: Still has trade (permanent record)
⚠️  State shows 0 trades, CSV shows 1 trade (MISMATCH!)
```

---

### Case 3C: Crash Before Strategy Initialization

**Scenario:**
```
Time: 9:20 AM
- System just started
- Broker connected
- Before daily analysis completed
- No direction determined yet

CRASH immediately
RESTART at 9:25 AM
```

**State File (trading_state_20251230.json):**
```json
{
  "date": "2025-12-30",
  "active_positions": {},
  "strategy_state": {
    "trading_strike": null,  // Not set yet
    "direction": null
  },
  "portfolio": {
    "initial_capital": 100480.0,
    "current_cash": 100480.0
  },
  "daily_stats": {
    "trades_today": 0
  }
}
```

**Execution Flow:**
```python
1. try_recover_state()
   → load() finds: trading_state_20251230.json ✓
   → can_recover() checks:
      → active_positions? Empty
      → trading_strike? null → FALSE ✗
   → Returns False (nothing to recover)

2. initialize()
   → get_latest_portfolio()
      → Finds: trading_state_20251230.json (today)
      → Returns current_cash = ₹100,480.00
   → initialize_session()
      → Overwrites with fresh state
```

**Result:**
```
✅ Portfolio: ₹100,480.00
✅ No recovery prompt (nothing to recover)
✅ Starts fresh
✅ Will perform daily analysis normally
```

---

## Edge Cases & Known Issues

### Case 4A: Same-Day Multiple Crashes

**Scenario:**
```
10:00 AM: Trade 1 → +₹500 profit → Portfolio: ₹100,852.50
11:00 AM: CRASH 1
11:15 AM: RESTART → User declines recovery
          → Overwrites state, loses Trade 1 from state
          → Portfolio value: ✅ ₹100,852.50 (correct)
          → Daily stats: ❌ 0 trades (wrong)

12:00 PM: Trade 2 → +₹300 profit → Portfolio: ₹101,152.50
1:00 PM:  CRASH 2
1:15 PM:  RESTART → User declines recovery
          → Overwrites state again, loses Trade 2 from state
          → Portfolio value: ✅ ₹101,152.50 (correct)
          → Daily stats: ❌ 0 trades (wrong)
```

**Issue:**
```
✅ Portfolio value: Always correct (uses latest state's current_cash)
❌ State shows: 0 trades, ₹0 P&L
✅ CSV shows: 2 trades, ₹800 total profit
⚠️  Trade limit: Would allow 3rd trade (sees 0 in state)
```

**Impact:**
- State vs CSV divergence
- Could violate "1 trade per day" limit
- Win rate calculations wrong

---

### Case 4B: Market Close with Open Position

**Scenario:**
```
3:00 PM: Open position
         Entry: ₹5.00
         Current LTP: ₹6.50
         Cash: ₹99,977.50
         Position value: ₹487.50
         Total: ₹100,465.00

3:10 PM: CRASH (system dies)

3:30 PM: Market closes
         Exchange auto-squares position at ₹6.50
         P&L: +₹112.50
         Final cash should be: ₹100,090.00

Next Day 9:15 AM: RESTART
```

**Yesterday's State (trading_state_20251230.json):**
```json
{
  "date": "2025-12-30",
  "active_positions": {
    "PAPER_001": {...}  // Still shows as open!
  },
  "portfolio": {
    "current_cash": 99977.5,  // Pre-square-off
    "positions_value": 487.5
  }
}
```

**Execution Flow:**
```python
1. try_recover_state()
   → load() searches: trading_state_20251231.json
   → Not found (new day)
   → Returns False

2. initialize()
   → get_latest_portfolio()
      → Finds: trading_state_20251230.json (yesterday)
      → Returns current_cash = ₹99,977.50 ❌ WRONG!
   → Starts with WRONG portfolio value
```

**Issue:**
```
❌ Missing: +₹112.50 from auto-square-off
❌ Portfolio: ₹99,977.50 (should be ₹100,090.00)
❌ Lost: ₹112.50 forever (no way to recover)
```

**Root Cause:**
- Paper trading doesn't track exchange operations
- No EOD reconciliation
- System crashed before position could be manually squared

**Workaround:**
- Always square positions before 3:15 PM
- Strategy should have EOD exit logic

---

## CSV Logging Behavior

### Daily CSV Creation

**File Naming:**
```
trades_{YYYYMMDD}_{HHMMSS}.csv
```

**When Created:**
```python
# In PaperBroker.__init__()
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
self.daily_trade_log = Path('paper_trading/logs') / f'trades_{timestamp}.csv'
```

**Behavior:**
- **New session** → New daily CSV file
- **Crash recovery (accept)** → Still creates new daily CSV (doesn't append to crashed session's file)
- **Crash recovery (decline)** → Creates new daily CSV

**Example:**
```
Session 1 (9:15 AM): trades_20251230_091500.csv
CRASH (2:30 PM)
Session 2 (2:45 PM): trades_20251230_144500.csv  (NEW FILE!)

Result: 2 daily CSV files for same day
```

---

### Cumulative CSV Appending

**File:** `trades_cumulative.csv`

**Behavior:**
```python
# First time
if not self.cumulative_trade_log.exists():
    # Create with header
    writer.writeheader()

# Every trade (all sessions)
writer.writerow(trade_data)  # APPEND
```

**Properties:**
- Single file for entire trading history
- Never reset or recreated
- Survives all crashes and recoveries
- Permanent record of all trades

**Example:**
```csv
entry_time,exit_time,strike,pnl,...
2025-12-29 10:45:00,2025-12-29 14:25:30,23900.0,352.5,...
2025-12-30 14:25:19,2025-12-30 14:26:51,25900.0,127.5,...
2025-12-31 11:15:00,2025-12-31 14:30:00,24500.0,250.0,...
```

---

## Quick Reference Table

### Recovery Decision Matrix

| Scenario | Today's State File | Active Positions? | Strategy State? | can_recover()? | User Prompted? | Auto-Resume? |
|----------|-------------------|-------------------|-----------------|----------------|----------------|--------------|
| **First day ever** | ❌ Not exists | N/A | N/A | N/A | ❌ No | ❌ No |
| **Normal new day** | ❌ Not exists | N/A | N/A | N/A | ❌ No | ❌ No |
| **Crash with position** | ✅ Exists | ✅ Yes | ✅ Yes | ✅ TRUE | ❌ No | ✅ YES (forced) |
| **Crash after direction** | ✅ Exists | ❌ No | ✅ Yes | ✅ TRUE | ✅ Yes | ❌ Only if accepts |
| **Crash after trade** | ✅ Exists | ❌ No | ✅ Yes | ✅ TRUE | ✅ Yes | ❌ Only if accepts |
| **Crash before init** | ✅ Exists | ❌ No | ❌ No | ❌ FALSE | ❌ No | ❌ No |

---

### Portfolio Source Matrix

| Scenario | Portfolio Source | Which File? | Value Correct? |
|----------|-----------------|-------------|----------------|
| **First day** | Config | N/A | ✅ ₹100,000 |
| **Normal new day** | Yesterday's state | trading_state_20251229.json | ✅ Yes |
| **Accept recovery** | Crashed state | trading_state_20251230.json | ✅ Yes |
| **Decline recovery (same day)** | Crashed state → overwritten | trading_state_20251230.json | ✅ Yes (value), ❌ No (stats) |
| **Market close crash** | Yesterday's state (pre-square-off) | trading_state_20251230.json | ❌ Wrong (missing P&L) |

---

### Data Preservation Matrix

| Data Type | Accept Recovery | Decline Recovery (same day) | Decline Recovery (new day) | CSV Log |
|-----------|----------------|----------------------------|---------------------------|---------|
| **Portfolio Value** | ✅ Preserved | ✅ Preserved | ✅ Preserved | N/A |
| **Active Positions** | ✅ Restored | ❌ Lost | N/A | N/A |
| **Daily Stats** | ✅ Preserved | ❌ Lost | N/A | N/A |
| **Closed Positions** | ✅ Preserved | ❌ Lost | N/A | ✅ Always preserved |
| **Strategy State** | ✅ Preserved | ❌ Lost | N/A | N/A |
| **VWAP Tracking** | ✅ Preserved | ❌ Lost | N/A | N/A |
| **Trade History** | ✅ Preserved | ❌ Lost from state | N/A | ✅ Always preserved |

---

## Key Takeaways

### ✅ What Works Perfectly

1. **Day-to-day carryover**: Portfolio carries forward correctly
2. **Forced recovery with positions**: Prevents data loss (Issue 14 fix)
3. **CSV logging**: Permanent, never lost
4. **Portfolio value**: Always preserved (even when declining recovery)

### ⚠️ Known Limitations

1. **Same-day decline loses stats**: Daily P&L, trade count lost from state (but preserved in CSV)
2. **Strategy state can be lost**: Re-analysis might pick different direction
3. **Market close edge case**: Auto-square-offs not tracked
4. **Multiple crashes**: Cumulative state loss if keep declining

### 💡 Best Practices

1. **Always accept recovery when prompted** (unless you know what you're doing)
2. **Square positions before 3:15 PM** (avoid market close edge case)
3. **Check CSV logs for accurate history** (state can lose data on declines)
4. **Monitor portfolio carryover messages** (verify correct starting capital)
5. **Avoid crashes during active trading** (obvious, but important!)

---

**Last Updated:** 2025-12-30
