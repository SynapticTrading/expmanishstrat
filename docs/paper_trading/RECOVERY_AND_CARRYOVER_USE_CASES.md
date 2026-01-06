# Recovery and Carryover Use Cases

This document explains how the paper trading system handles various scenarios including crashes, restarts, and the 1-trade-per-day limit.

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
11:30 - Restart → Choose "y" (recovery)
```

**System Behavior:**
```
Restoring 1 position(s)...
  ✓ Restored: CALL 26050.0 @ ₹107.40
  Peak: ₹176.95, Trailing: True

Restored daily_trade_taken: True (has open positions)

→ Continues monitoring position
→ Blocks new entries
→ After exit: Auto-shutdown
```

---

## ✅ Use Case 3: Crash Recovery with Closed Trade

**Scenario:**
```
10:00 - Trade taken
10:30 - Trade exits
11:00 - System crashes (no positions)
11:30 - Restart → Choose "y" (recovery)
```

**System Behavior:**
```
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

## ⚠️ Use Case 4: Fresh Start (Same Day) - Portfolio Only

**Scenario:**
```
10:00 - Trade taken, P&L = +₹6,420
10:30 - Trade exits
11:00 - System crashes
11:30 - Restart → Choose "n" (fresh start)
```

**System Behavior:**
```
📊 PORTFOLIO CARRYOVER
  Starting Capital: ₹106,547.50 ← Cash preserved!
  Previous P&L: ₹+6,420.00

→ daily_trade_taken = False (reset)
→ closed_positions = [] (cleared)
→ CAN take another trade! ⚠️
```

**Why This is OK:**
- You chose fresh start, not recovery
- Portfolio (cash) is preserved
- Trade history cleared by choice
- Expected behavior

---

## 🔑 Summary Table

| Scenario | Portfolio Preserved? | Trade History? | daily_trade_taken? | Continues Monitoring? | Shutdown Time |
|----------|---------------------|----------------|-------------------|-----------------------|---------------|
| Runtime (no crash) | ✅ Yes | ✅ Yes | ✅ Stays True | ✅ Yes (until EOD) | EOD / Market Close |
| Recovery (open pos) | ✅ Yes | ✅ Yes | ✅ True | ✅ Yes (until EOD) | EOD / Market Close |
| Recovery (closed) | ✅ Yes | ✅ Yes | ✅ True | ✅ Yes (until EOD) | EOD / Market Close |
| Fresh start (same day) | ✅ Yes | ❌ No | ❌ False | ✅ Yes (until EOD) | EOD / Market Close |
| Fresh start (next day) | ✅ Yes | ❌ No | ❌ False | ✅ Yes (until EOD) | EOD / Market Close |

---

## 📋 Testing Checklist

- [ ] Take trade → Exit → Verify system continues monitoring (no auto-shutdown)
- [ ] Trade complete → Check for entry signal → Verify entry blocked with log message
- [ ] Crash with position → Recover → Verify position restored
- [ ] Crash after exit → Recover → Verify P&L correct + continues monitoring
- [ ] Fresh start same day → Verify portfolio preserved, can retrade
- [ ] EOD exit → Verify shutdown at 15:00 / 3:00 PM (only EOD shutdown)
- [ ] Verify monitoring mode logs appear when trade limit reached
