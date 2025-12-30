# Issue 09: Portfolio State Not Updating After Trades

**Date:** 2025-12-30
**Severity:** HIGH
**Status:** ✅ FIXED

---

## Problem

After successful trades, the portfolio state in JSON showed stale values:

```json
"daily_stats": {
  "total_pnl_today": 127.5    ✓ Correct
},
"portfolio": {
  "initial_capital": 100000,
  "current_cash": 100000,      ✗ WRONG - Should be 100,127.50
  "total_value": 0.0,          ✗ WRONG - Should be 100,127.50
  "total_return_pct": 0.0      ✗ WRONG - Should be 0.1275%
}
```

## Root Cause

`PaperBroker` was updating its **internal cash balance** correctly but **never syncing** to `StateManager`:

```python
# In paper_trading/core/broker.py

def buy(...):
    self.cash -= cost              # ✓ Updated internally
    self.positions.append(position)
    # ❌ Missing: state_manager.update_portfolio()

def sell(...):
    self.cash += proceeds          # ✓ Updated internally
    # ❌ Missing: state_manager.update_portfolio()
```

### What Was Happening:
1. Trade executed → Broker updates `self.cash`
2. State saved → Portfolio values NOT updated
3. JSON shows stale portfolio data
4. Next day → Can't carry forward correct portfolio

## Solution

### 1. Update Portfolio After BUY
**File:** `paper_trading/core/broker.py:99-102`

```python
# Save to state
if self.state_manager:
    order_id = self.state_manager.update_position_entry(position)
    position.order_id = order_id

    # ✅ NEW: Update portfolio state
    positions_value = sum(p.entry_price * p.size for p in self.positions)
    self.state_manager.update_portfolio(self.initial_capital, self.cash, positions_value)
    self.state_manager.save()
```

### 2. Update Portfolio After SELL
**File:** `paper_trading/core/broker.py:150-153`

```python
# Update state
if self.state_manager and hasattr(position, 'order_id'):
    self.state_manager.update_position_exit(position.order_id, position)

    # ✅ NEW: Update portfolio state
    positions_value = sum(p.entry_price * p.size for p in self.positions)
    self.state_manager.update_portfolio(self.initial_capital, self.cash, positions_value)
    self.state_manager.save()
```

## Example Fix in Action

### Before Fix:
```json
{
  "portfolio": {
    "initial_capital": 100000,
    "current_cash": 100000,      // Broker internal: 100,127.50
    "positions_value": 0.0,
    "total_value": 0.0           // Should be 100,127.50
  }
}
```

### After Fix:
```json
{
  "portfolio": {
    "initial_capital": 100000,
    "current_cash": 100127.5,    // ✅ Synced from broker
    "positions_value": 0.0,
    "total_value": 100127.5,     // ✅ Calculated correctly
    "total_return_pct": 0.1275   // ✅ ROI correct
  }
}
```

## Verification

**Tested with Trade:**
- Entry: ₹5.00 @ 25900 PUT
- Exit: ₹6.70 (profit ₹127.50)

**State File After:**
```json
"portfolio": {
  "current_cash": 100127.5,    ✓ Correct
  "total_value": 100127.5,     ✓ Correct
  "total_return_pct": 0.1275   ✓ Correct
}
```

## Impact

- ✅ Portfolio values now track correctly
- ✅ Real-time cash balance reflected in state
- ✅ Open positions value calculated
- ✅ Total value and ROI accurate
- ✅ Portfolio carryover now possible (Issue 11)

## Related Issues

- **Prerequisite:** Issue 08 (JSON serialization fix)
- **Enables:** Issue 11 (Portfolio carryover)

## Files Modified

1. `paper_trading/core/broker.py:99-102` - Portfolio update after BUY
2. `paper_trading/core/broker.py:150-153` - Portfolio update after SELL
