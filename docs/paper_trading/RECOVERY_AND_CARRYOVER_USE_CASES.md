# Recovery and Carryover Use Cases

This document explains how the paper trading system handles various scenarios including crashes, restarts, and the 1-trade-per-day limit.

## 🚀 AUTOMATIC CRASH RECOVERY

**IMPORTANT: The system now AUTOMATICALLY recovers from crashes without any user input.**

- ✅ No prompts asking "Resume from crash? (y/n)"
- ✅ Always resumes from previous session when crash detected
- ✅ Preserves all positions, trade history, and portfolio
- ✅ Works for both open positions and closed trades
- ✅ Zero manual intervention required

---

## ✅ Continuous Monitoring Feature

**The system continues running and monitoring even after the daily trade limit is reached:**

- ✅ Continues fetching option chains every 5 minutes
- ✅ Continues running 5-min strategy loop
- ✅ Blocks new entries when daily trade limit reached (1 trade/day)
- ✅ Continues monitoring for exits on open positions
- ✅ Logs "MONITORING MODE" when trade limit reached but no positions
- ✅ Clear signal that no new trades will be taken

**Shutdown Conditions (only when these occur):**
1. Past EOD exit time (15:00 / 3:00 PM)
2. Market closed

**Note:** The system does NOT auto-shutdown when trade is completed. It continues monitoring until EOD or market close.

---

## ✅ Use Case 1: Normal Runtime - Trade Complete Continuous Monitoring

**Scenario:**
```
09:30 - System starts
10:00 - Entry signal → Trade taken (daily_trade_taken = True)
10:30 - Stop loss hit → Trade exits
10:35 - Next 5-min candle → System detects trade done, no positions
       → CONTINUES MONITORING (no shutdown)
11:00 - Another signal appears → Entry blocked (daily limit reached)
11:05 - System continues checking every 5 min until EOD
14:50 - Force exit triggered (2:50 PM)
15:00 - Past EOD exit time (3:00 PM) → System stops
```

**Output:**
```
[10:30:XX] ✓ SELL ORDER EXECUTED
  P&L: ₹-2,000.00
  Exit Reason: Stop Loss

[10:35:XX] 📊 MONITORING MODE: Daily trade limit reached (1/1 trades taken)
[10:35:XX] System will continue monitoring but will NOT enter new trades

[11:00:XX] Checking entry: CALL 26050.0
[11:00:XX] ⛔ Entry blocked: Daily trade limit reached (1 trade/day)

[11:05:XX] 📊 MONITORING MODE: Daily trade limit reached (1/1 trades taken)
...continues until EOD...

[15:00:XX] Past EOD exit time (3:00 PM), stopping...

Final Statistics:
  Total Trades: 1
  Total P&L: ₹-2,000.00
```

**Why it works:**
- `daily_trade_taken` stays True after exit (never resets during day)
- System continues running, fetching data, but blocks new entries
- Logs clearly show monitoring mode active
- Only stops at EOD or market close

---

## ✅ Use Case 2: Crash Recovery with Open Position

**Scenario:**
```
10:00 - Trade taken
11:00 - System crashes (position still open)
11:30 - Restart → AUTOMATIC RECOVERY (no user input)
```

**System Behavior:**
```
⚠️  CRITICAL: 1 open position(s) detected!
Cannot start fresh session with active positions.
Automatically resuming from crash...

Restoring 1 position(s)...
  ✓ Restored: CALL 26050.0 @ ₹107.40
  Peak: ₹176.95, Trailing: True

Restored daily_trade_taken: True (has open positions)

→ Continues monitoring position
→ Blocks new entries
→ After exit: Continues monitoring until EOD
```

---

## ✅ Use Case 3: Crash Recovery with Closed Trade

**Scenario:**
```
10:00 - Trade taken
10:30 - Trade exits
11:00 - System crashes (no positions)
11:30 - Restart → AUTOMATIC RECOVERY (no user input)
```

**System Behavior:**
```
✓ AUTOMATIC RECOVERY: Previous session detected
Automatically resuming from crash...

Restoring 1 closed trade(s)...
  ✓ Restored trade: CALL 26050.0 | P&L: ₹+6,420.00

Restored daily_trade_taken: True (has closed trades, trades_today=1)

[11:30:XX] 📊 MONITORING MODE: Daily trade limit reached (1/1 trades taken)
[11:30:XX] System will continue monitoring but will NOT enter new trades

[11:35:XX] Checking entry: CALL 26100.0
[11:35:XX] ⛔ Entry blocked: Daily trade limit reached (1 trade/day)

...continues until EOD...

[15:00:XX] Past EOD exit time (3:00 PM), stopping...

Final Statistics:
  Total Trades: 1
  Total P&L: ₹6,420.00 ← Correct!
```

**→ Continues monitoring until EOD (no auto-shutdown)**

---

## ⚠️ Use Case 4: Next Day Start - Portfolio Carryover

**Scenario:**
```
Day 1:
  10:00 - Trade taken, P&L = +₹6,420
  10:30 - Trade exits
  15:00 - System stops (EOD)

Day 2:
  09:30 - System starts (new day)
```

**System Behavior:**
```
📊 PORTFOLIO CARRYOVER
  Previous Date: 2025-01-10
  Starting Capital: ₹106,547.50 ← Cash preserved!
  Previous P&L: ₹+6,420.00
  Previous Trades: 1
  Previous Win Rate: 100.0%

→ daily_trade_taken = False (new day)
→ closed_positions = [] (new day)
→ CAN take trade today! ✓
```

**Why This Works:**
- New trading day detected
- Portfolio (cash) carried forward
- Trade history starts fresh for new day
- Expected behavior

---

## 🔑 Summary Table

| Scenario | Portfolio Preserved? | Trade History? | daily_trade_taken? | Continues Monitoring? | Shutdown Time | User Input? |
|----------|---------------------|----------------|-------------------|-----------------------|---------------|-------------|
| Runtime (no crash) | ✅ Yes | ✅ Yes | ✅ Stays True | ✅ Yes (until EOD) | EOD / Market Close | N/A |
| Auto-Recovery (open pos) | ✅ Yes | ✅ Yes | ✅ True | ✅ Yes (until EOD) | EOD / Market Close | ❌ No - Automatic |
| Auto-Recovery (closed) | ✅ Yes | ✅ Yes | ✅ True | ✅ Yes (until EOD) | EOD / Market Close | ❌ No - Automatic |
| Next day start | ✅ Yes | ❌ No (new day) | ❌ False (new day) | ✅ Yes (until EOD) | EOD / Market Close | N/A |

---

## 📋 Testing Checklist

- [ ] Take trade → Exit → Verify system continues monitoring (no auto-shutdown)
- [ ] Trade complete → Check for entry signal → Verify entry blocked with log message
- [ ] Crash with position → Restart → Verify AUTOMATIC recovery (no prompt) + position restored
- [ ] Crash after exit → Restart → Verify AUTOMATIC recovery (no prompt) + P&L correct + continues monitoring
- [ ] Verify NO user input prompt appears during crash recovery
- [ ] EOD exit → Verify shutdown at 15:00 / 3:00 PM (only EOD shutdown)
- [ ] Verify monitoring mode logs appear when trade limit reached
- [ ] Next day start → Verify portfolio carryover but fresh trade history
