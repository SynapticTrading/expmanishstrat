# Issue #5: State Persistence Broken - Positions Not Saved

**Date:** 2025-12-29
**Severity:** Critical
**Status:** ✅ Resolved

---

## Problem

When the system was killed with an open position, restarting showed:
```
[14:52:00] Checking for previous session...
[14:52:00] ✓ State loaded from paper_trading/state/trading_state_20251229.json
[14:52:00] Previous state found but no active positions - starting fresh
```

But the user HAD an active position before killing the process!

### State File Contents

```json
{
  "active_positions": {},  ← Empty!
  "closed_positions": [],
  "daily_stats": {
    "current_positions": 0,  ← Should be 1!
    "total_pnl_today": 0.0
  }
}
```

**Positions were not being saved to the state file.**

---

## Root Cause

The `PaperBroker` and `StateManager` were **completely disconnected**.

### Architecture Before

```
runner.py:
  ├─> self.state_manager = StateManager()
  └─> self.paper_broker = PaperBroker(initial_capital)  ❌ No connection!

PaperBroker.buy():
  └─> Creates position
      └─> Adds to self.positions
          └─> ❌ Never calls state_manager!

StateManager:
  └─> Has methods: update_position_entry(), update_position_exit()
      └─> ❌ Never called by PaperBroker!
```

The state manager had all the right methods, but **PaperBroker never called them**.

---

## Solution

Connected `PaperBroker` to `StateManager`:

### 1. Pass StateManager to PaperBroker

**File:** `paper_trading/runner.py:173`

```python
# Before
self.paper_broker = PaperBroker(initial_capital)

# After
self.paper_broker = PaperBroker(initial_capital, state_manager=self.state_manager)
```

### 2. Store StateManager in PaperBroker

**File:** `paper_trading/core/broker.py:41-46`

```python
class PaperBroker:
    def __init__(self, initial_capital=100000, state_manager=None):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions = []
        self.trade_history = []
        self.state_manager = state_manager  # ✅ Store reference
```

### 3. Save Position on Entry

**File:** `paper_trading/core/broker.py:94-97`

```python
# Update cash
self.cash -= cost
self.positions.append(position)

# Save to state
if self.state_manager:
    order_id = self.state_manager.update_position_entry(position)
    position.order_id = order_id  # Store order_id in position
```

### 4. Save Position on Exit

**File:** `paper_trading/core/broker.py:141-143`

```python
# Log to file
self._log_trade(position, vwap, oi)

# Update state
if self.state_manager and hasattr(position, 'order_id'):
    self.state_manager.update_position_exit(position.order_id, position)
```

---

## Data Flow After Fix

```
PaperBroker.buy():
  └─> Creates position
      └─> state_manager.update_position_entry(position)
          └─> Saves to state['active_positions']
              └─> Calls state.save()
                  └─> Writes to JSON file

PaperBroker.sell():
  └─> Closes position
      └─> state_manager.update_position_exit(order_id, position)
          └─> Moves to state['closed_positions']
              └─> Updates daily stats
                  └─> Calls state.save()
                      └─> Writes to JSON file
```

---

## State File After Fix

```json
{
  "active_positions": {
    "PAPER_20251229_001": {
      "order_id": "PAPER_20251229_001",
      "symbol": "NIFTY25DEC25900PUT",
      "strike": 25900.0,
      "option_type": "PUT",
      "expiry": "2025-12-30",
      "entry": {
        "price": 30.0,
        "time": "2025-12-29T14:40:00+05:30",
        "quantity": 75
      },
      "stop_losses": {
        "initial_stop": 22.5,
        "trailing_stop": null,
        "trailing_active": false
      },
      "status": "OPEN"
    }
  },
  "daily_stats": {
    "current_positions": 1,
    "total_pnl_today": 0.0
  }
}
```

---

## Testing Crash Recovery

### Before Fix

```bash
# 1. Start system, take trade
./start_paper_trading.sh
# [Trade entered at ₹30.00]

# 2. Kill process
Ctrl+C

# 3. Restart
./start_paper_trading.sh
# ❌ Previous state found but no active positions - starting fresh
```

### After Fix

```bash
# 1. Start system, take trade
./start_paper_trading.sh
# [Trade entered at ₹30.00]

# 2. Kill process
Ctrl+C

# 3. Restart
./start_paper_trading.sh
# ✅ CRASH RECOVERY DETECTED
# Last Activity: 2025-12-29T14:45:00+05:30
# Active Positions: 1
# Daily P&L: ₹0.00
# Resume from crash? (y/n): y
# ✅ Resuming session...
# ✅ Position recovered: PUT 25900.0 @ ₹30.00
```

---

## Files Changed

- `paper_trading/core/broker.py` (lines 41-46, 94-97, 141-143)
- `paper_trading/runner.py` (line 173)

---

## Benefits

- ✅ Positions survive system crashes
- ✅ Can restart without losing trades
- ✅ Full state recovery (VWAP tracking, daily stats, etc.)
- ✅ Audit trail in JSON format
- ✅ Can resume monitoring from where it left off
