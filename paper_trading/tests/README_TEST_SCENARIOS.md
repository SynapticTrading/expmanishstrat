# Trade Flow Scenarios Test

## Overview

This comprehensive test (`test_trade_flow_scenarios.py`) simulates all key scenarios in the paper trading system to validate behavior from trade entry to exit, including the 1-trade-per-day limit enforcement.

## Test Scenarios

### Scenario 1: Trade Entry - OI Unwinding + Price Above VWAP

**What happens:**
1. Market opens at 9:15 AM - Direction is determined (CALL or PUT based on OI buildup)
2. First candle at 9:20 AM - VWAP tracking is initialized
3. Entry signal at 9:25 AM - OI unwinding detected + Price above VWAP
4. Trade is executed

**Expected logs:**
```
[2026-01-05 09:25:00] 🎯 ENTRY SIGNAL: PUT 24450 - Price: 64.00, VWAP: 61.00, OI Change: -300,000 (-10.00%)
[2026-01-05 09:25:00] 📈 PLACING BUY ORDER: size=1, expected_price=64.00
[2026-01-05 09:25:00] ✓ BUY ORDER EXECUTED
[2026-01-05 09:25:00] 🔵 BUY OPTION EXECUTED: PUT 24450 @ ₹64.00 (Expiry: 2026-01-09, 1 lot = 75 qty)
```

**What you'll see in logs:**
- Trade history: 0 → 1
- Open positions: 0 → 1
- Cash: ₹100,000 → ₹95,200 (₹4,800 cost for 75 qty @ ₹64)
- Daily trade taken: False → True

---

### Scenario 2: Trade Exit - Stop Loss Hit

**What happens:**
1. Next candle at 9:30 AM - Price drops significantly
2. Stop loss (25%) is triggered
3. Position is closed

**Expected logs:**
```
[2026-01-05 09:30:00] 📊 LTP CHECK: 24450 PUT
    Current LTP: ₹36.00 | Entry: ₹64.00 | P&L: -43.75%
    Initial Stop: ₹48.00 (distance: -25.00%)
[2026-01-05 09:30:00] EXIT SIGNAL: Stop Loss (25%)
[2026-01-05 09:30:00] ✓ SELL ORDER EXECUTED
```

**What you'll see in logs:**
- Trade history: 1 (with closed trade details)
- Open positions: 1 → 0
- Cash: ₹95,200 → ₹97,900 (recovered ₹2,700 from sale at ₹36/qty)
- P&L: -₹2,100 (-43.75%)
- Daily trade taken: True (remains True)

---

### Scenario 3: Closed Position + Next Candle

**What happens:**
1. Next candle at 9:35 AM
2. System is in "MONITORING MODE" - no new entries allowed
3. System continues checking entry conditions but will NOT enter

**Expected logs:**
```
[2026-01-05 09:35:00] Checking entry: PUT 24450, Expiry=2026-01-09
[2026-01-05 09:35:00] PUT 24450: OI=2,460,000, Change=-540,000 (-18.00%) - UNWINDING ✓
[2026-01-05 09:35:00] PUT 24450: Price=₹40.00, VWAP=₹45.00 - BELOW ✗
```

**What you'll see:**
- No entry attempt (because price is below VWAP in this case)
- System continues monitoring
- Daily trade taken: True (prevents new entries)

---

### Scenario 4: New Entry Signal After Closed Trade - Should Be Blocked

**What happens:**
1. Perfect entry signal at 10:00 AM (OI unwinding + Price above VWAP)
2. Entry conditions are MET but system BLOCKS the entry
3. Reason: Daily trade limit reached (1 trade/day)

**Expected logs:**
```
[2026-01-05 10:05:00] 🎯 ENTRY SIGNAL: PUT 24500 - Price: 80.00, VWAP: 77.87, OI Change: -60,000 (-2.86%)
[2026-01-05 10:05:00] ⛔ Entry blocked: Daily trade limit reached (1 trade/day)
```

**What you'll see:**
- Entry signal detected ✓
- Entry conditions met ✓
- But entry BLOCKED due to daily trade limit
- Open positions: 0 (no new entry)
- Cash: Unchanged (no deduction)

---

### Scenario 5: Blocked Trade + Next Candle

**What happens:**
1. Next candle at 10:05 AM
2. System continues monitoring
3. No new entries allowed

**Expected logs:**
- Similar to Scenario 4
- System logs entry checks but does NOT execute

---

## Log Files Generated

After running the test, check these files:

### 1. Daily Trade Log
**Location:** `paper_trading/logs/trades_YYYYMMDD_HHMMSS.csv`

**Contents:**
```csv
entry_time,exit_time,strike,option_type,expiry,entry_price,exit_price,size,pnl,pnl_pct,vwap_at_entry,vwap_at_exit,oi_at_entry,oi_change_at_entry,oi_at_exit,exit_reason
2026-01-05 16:12:31,2026-01-05 16:12:31,24450,PUT,2026-01-09,64.0,36.0,75,-2100.0,-43.75,61.0,50.29,2700000.0,-10.0,2520000.0,Stop Loss (25%)
```

**What you see:**
- Complete trade details
- Entry/exit times
- P&L information
- VWAP at entry and exit
- OI data
- Exit reason

### 2. Cumulative Trade Log
**Location:** `paper_trading/logs/trades_cumulative.csv`

**Contents:**
- Same format as daily log
- Accumulates ALL trades across ALL test runs
- Useful for historical analysis

### 3. State File
**Location:** `paper_trading/tests/test_state/trading_state_YYYYMMDD.json`

**Contents:**
```json
{
  "timestamp": "2026-01-05T16:12:31.208912+05:30",
  "active_positions": {},
  "closed_positions": [
    {
      "order_id": "PAPER_20260105_001",
      "strike": 24450,
      "option_type": "PUT",
      "pnl": -2100.0,
      "pnl_pct": -43.75,
      "exit_reason": "Stop Loss (25%)"
    }
  ],
  "strategy_state": {
    "current_spot": 24550,
    "trading_strike": 24500,
    "direction": "PUT",
    "vwap_tracking": {...}
  },
  "daily_stats": {
    "trades_today": 1,
    "max_trades_allowed": 1,
    "total_pnl_today": -2100.0,
    "win_rate": 0.0
  },
  "portfolio": {
    "initial_capital": 100000,
    "current_cash": 97900.0,
    "total_value": 97900.0,
    "total_return_pct": -2.10
  }
}
```

**What you see:**
- Active positions (empty after exit)
- Closed positions with full details
- Strategy state (direction, strike, VWAP tracking)
- Daily statistics
- Portfolio value

---

## How to Run the Test

```bash
python paper_trading/tests/test_trade_flow_scenarios.py
```

---

## Key Behaviors to Observe

### 1. Trade Entry
- ✓ Direction is determined at market open (9:15 AM)
- ✓ VWAP tracking is initialized on first candle
- ✓ Entry requires BOTH: OI unwinding AND price above VWAP
- ✓ Trade is executed with proper position tracking

### 2. Trade Exit
- ✓ LTP (Last Traded Price) is checked every candle
- ✓ Stop loss triggers at 25% loss
- ✓ Position is closed and moved to trade history
- ✓ Cash is updated with sale proceeds

### 3. Closed Position + Next Candle
- ✓ System continues monitoring
- ✓ Entry conditions are still checked
- ✓ But NO new entries are made (due to daily_trade_taken flag)

### 4. New Signal After Closed Trade
- ✓ Entry signal is detected
- ✓ Entry conditions are validated
- ✓ But entry is BLOCKED with message: "⛔ Entry blocked: Daily trade limit reached"
- ✓ Cash remains unchanged

### 5. Blocked Trade + Next Candle
- ✓ System continues normal operation
- ✓ Monitoring continues
- ✓ No new entries allowed

---

## Understanding the Logs

### Entry Logs
Look for:
- `🎯 ENTRY SIGNAL` - Entry conditions met
- `📈 PLACING BUY ORDER` - Order being placed
- `✓ BUY ORDER EXECUTED` - Order executed
- `🔵 BUY OPTION EXECUTED` - Position opened

### Exit Logs
Look for:
- `📊 LTP CHECK` - Price monitoring
- `EXIT SIGNAL` - Exit condition triggered
- `✓ SELL ORDER EXECUTED` - Order executed

### Blocking Logs
Look for:
- `⛔ Entry blocked: Daily trade limit reached` - Entry blocked

### Monitoring Logs
Look for:
- `Checking entry:` - Entry conditions being evaluated
- `UNWINDING ✓` or `BUILDING` - OI status
- `ABOVE ✓` or `BELOW ✗` - Price vs VWAP status

---

## Test Success Criteria

The test is successful if:
1. ✓ Trade entry executes when conditions are met
2. ✓ Trade exit executes on stop loss
3. ✓ System continues monitoring after close
4. ✓ New entry signals are BLOCKED after 1 trade
5. ✓ Cash flow is correct (deducted on entry, credited on exit)
6. ✓ All logs are generated correctly
7. ✓ State file reflects accurate system state

---

## Next Steps

After running this test, you can:
1. Verify the CSV log files have correct data
2. Check the state JSON file for accurate tracking
3. Modify test parameters to test different scenarios
4. Add more scenarios (e.g., trailing stop, VWAP stop, OI increase stop)
5. Test with multiple trades per day (when limit is increased)

---

## Troubleshooting

**If entry doesn't execute:**
- Check if OI is actually unwinding (negative change)
- Check if price is above VWAP
- Check if daily_trade_taken is False

**If exit doesn't execute:**
- Check if stop loss threshold is correct (25% = price <= 75% of entry)
- Check if position exists in broker.positions

**If blocking doesn't work:**
- Check daily_trade_taken flag
- Check broker.trade_history length

---

## Customization

You can modify the test by changing:
- `spot_price` - Initial spot price
- `strike` - Strike price
- `option_price` - Option premium
- `oi` - Open Interest values
- `volume` - Trading volume
- Entry/exit times
- Stop loss percentages (in MockConfig)
