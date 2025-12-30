# Dual-Loop Architecture Explained

## The Problem with Single-Loop Implementation

### ❌ What Was Wrong (Original Implementation)

**File**: `zerodha_paper_runner.py`

```python
# WRONG: Single 5-min loop checking both entry AND exit
while running:
    # Every 5 minutes:
    spot_price = get_spot_price()
    options_data = get_options_chain()  # 5-min candle data

    strategy.on_candle()  # Checks BOTH entry and exit

    wait_for_next_candle()  # Sleep for 5 minutes
```

**Issues**:
1. ⚠️ **Exit delays up to 5 minutes** - Stop loss won't trigger immediately
2. ⚠️ **Missed trailing stop updates** - Peak price only updates every 5 min
3. ⚠️ **Poor execution** - Exit at stale 5-min candle price, not real-time LTP
4. ⚠️ **Overstated losses** - May exit at worse price than necessary

**Example Problem**:
```
9:30:00 - Entry at ₹150
9:31:30 - Price drops to ₹110 (below 25% SL of ₹112.50)
9:35:00 - Exit at ₹108 (waited for 5-min candle!)

Should have exited: ₹110 at 9:31:30
Actually exited: ₹108 at 9:35:00
Extra loss: ₹2 per share × 75 = ₹150
```

---

## ✅ Correct Implementation: Dual-Loop Architecture

### File**: `dual_loop_runner.py`

### Loop 1: Strategy Loop (5-min Candles)

**Purpose**: Entry decisions and direction determination

```python
def _strategy_loop(self):
    """Runs every 5 minutes"""
    while running:
        # Get 5-min aggregated candle data
        spot_price = get_spot_price()
        options_data = get_options_chain()  # OHLCV candles

        # Calculate VWAP (needs candle data)
        # Check OI changes (needs historical OI)
        # Make ENTRY decisions

        # Update shared data for exit monitor
        current_options_data = options_data

        wait_for_next_candle()  # Sleep ~5 minutes
```

**Checks**:
- ✓ Daily direction (9:15 AM)
- ✓ Entry signals (OI unwinding + VWAP)
- ✓ VWAP calculation
- ✓ Updates shared market data

### Loop 2: Exit Monitor Loop (1-Minute LTP)

**Purpose**: Exit monitoring with 1-minute LTP checks

```python
def _exit_monitor_loop(self):
    """Runs every 1 minute"""
    while running:
        positions = get_open_positions()

        if not positions:
            sleep(60)  # No positions, sleep 1 minute
            continue

        # We have positions - check LTP
        for position in positions:
            # Get LTP (every 1 minute)
            ltp = get_option_ltp(position)

            # Check ALL stop losses
            if ltp <= stop_loss_price:
                EXIT NOW

            if ltp <= trailing_stop_price:
                EXIT NOW

            # Update peak price
            if ltp > position.peak_price:
                position.peak_price = ltp

        sleep(60)  # Check again in 1 minute
```

**Checks** (every 1 minute):
- ✓ Real-time LTP
- ✓ 25% stop loss
- ✓ VWAP stop
- ✓ OI stop
- ✓ Trailing stop
- ✓ EOD exit

---

## Why Two Loops?

| Aspect | Strategy Loop (5-min) | Exit Monitor (1-min) |
|--------|----------------------|---------------------|
| **Purpose** | Entry decisions | Exit decisions |
| **Data** | 5-min OHLCV candles | 1-min LTP |
| **Frequency** | Every 5 minutes | Every 1 minute |
| **What it checks** | OI unwinding, VWAP | Stop losses, trailing |
| **Why this data?** | VWAP needs candles | Exits need granularity |

### Entry Needs Candles (5-min)

```
Entry Signal = OI Unwinding + Price > VWAP

VWAP = Cumulative (Typical Price × Volume) / Cumulative Volume
      ↑ Requires OHLCV candle data
```

Can't use LTP for entry because:
- LTP has no volume data
- VWAP calculation needs historical candles
- OI comparison needs previous candle's OI

### Exit Needs LTP (Real-time)

```
Stop Loss Check = Current Price <= Entry × 0.75

Current Price = Real-time LTP (updated every second)
                ↑ Not 5-min delayed candle close
```

Must use LTP for exit because:
- Immediate execution prevents larger losses
- Trailing stop needs continuous price updates
- 5-min delay = unacceptable slippage

---

## Real Trading Day Example

### 9:30:00 - Entry Signal

**Strategy Loop (5-min candle)**:
```
✓ 23000 CALL
✓ OI unwinding (-5.2%)
✓ Price ₹150 > VWAP ₹148
→ ENTER at ₹150
```

**Exit Monitor**: Now monitoring every 1 minute (LTP checks)

---

### 9:31:00 - Price Climbing (1-min LTP check)

**Exit Monitor (LTP - checked every 1 min)**:
```
LTP = ₹155
Stop Loss = ₹112.50 ✓ Safe
Trailing = Not active yet
→ Continue monitoring
```

**Strategy Loop**: Sleeping (next check at 9:35:00)

---

### 9:34:00 - 10% Profit Reached (1-min LTP check)

**Exit Monitor (LTP - checked every 1 min)**:
```
LTP = ₹165
Profit = (165-150)/150 = 10% → Activate trailing!
Peak = ₹165
Trailing Stop = 165 × 0.90 = ₹148.50
→ Trailing stop now active
```

**Strategy Loop**: Still sleeping

---

### 9:36:00 - New Peak (1-min LTP check)

**Exit Monitor (LTP - checked every 1 min)**:
```
LTP = ₹172 (new high!)
Peak = ₹172 (updated)
Trailing Stop = 172 × 0.90 = ₹154.80 (updated)
→ Continue monitoring
```

---

### 9:38:00 - Trailing Stop Hit (1-min LTP check)

**Exit Monitor (LTP - checked every 1 min)**:
```
LTP = ₹154.00 (dropped!)
Trailing Stop = ₹154.80
₹154.00 < ₹154.80 → EXIT!

→ EXIT at ₹154.00 (exit within 1 min)
P&L = (154 - 150) × 75 = ₹300
```

**Strategy Loop**: Still sleeping (next check at 9:40:00, but position already closed!)

---

## Performance Comparison

### Scenario: Stop Loss Hit

| Event | Single Loop | Dual Loop |
|-------|------------|-----------|
| Entry | 9:30:00 @ ₹150 | 9:30:00 @ ₹150 |
| SL Triggered | 9:31:30 @ ₹110 | 9:31:30 @ ₹110 |
| Exit Time | 9:35:00 | 9:31:31 |
| Exit Price | ₹108 | ₹110 |
| P&L per share | -₹42 | -₹40 |
| Total P&L | -₹3,150 | -₹3,000 |
| **Difference** | **-₹150 worse** | **Better by ₹150** |

### Scenario: Trailing Stop

| Event | Single Loop | Dual Loop |
|-------|------------|-----------|
| Entry | 9:30:00 @ ₹150 | 9:30:00 @ ₹150 |
| Peak Reached | 9:36:20 @ ₹175 | 9:36:20 @ ₹175 |
| Peak Detected | 9:40:00 (delayed!) | 9:36:20 (real-time) |
| Price Drops | 9:37:45 @ ₹155 | 9:37:45 @ ₹155 |
| Trailing Hit | 9:40:00 | 9:37:46 |
| Exit Price | ₹152 | ₹157 |
| P&L per share | +₹2 | +₹7 |
| Total P&L | +₹150 | +₹525 |
| **Difference** | **-₹375 worse** | **Better by ₹375** |

---

## Threading Implementation

### Main Thread: Strategy Loop

```python
def run(self):
    # Start exit monitor in separate thread
    exit_thread = Thread(target=_exit_monitor_loop)
    exit_thread.start()

    # Run strategy loop in main thread
    _strategy_loop()
```

### Background Thread: Exit Monitor

```python
def _exit_monitor_loop(self):
    while running:
        # Only run when positions exist
        if no_positions:
            sleep(5)
            continue

        # Monitor aggressively
        for position in positions:
            ltp = get_realtime_ltp()
            check_all_stops()

        sleep(1)  # Check every second
```

### Thread Safety

```python
# Shared data protected by lock
exit_monitor_lock = threading.Lock()

# Strategy loop updates shared data
with exit_monitor_lock:
    current_options_data = new_data

# Exit monitor reads shared data
with exit_monitor_lock:
    data = current_options_data
```

---

## How to Use

### Run Dual-Loop System

```bash
python dual_loop_runner.py
```

### Console Output

```
DUAL-LOOP PAPER TRADING
  Loop 1: Strategy (5-min candles) - Entry decisions
  Loop 2: Exit Monitor (1-min LTP) - Exit decisions

✓ Exit monitor loop started (continuous LTP)
✓ Strategy loop started

[9:30:00] STRATEGY LOOP - Entry signal detected
[9:30:00] ✓ BUY ORDER EXECUTED

[9:33:45] EXIT MONITOR: Trailing stop activated (10% profit)
[9:37:46] EXIT MONITOR: Trailing Stop (10%)
[9:37:46] ✓ SELL ORDER EXECUTED
```

---

## Summary

### ❌ Single Loop (Wrong)
- Entry + Exit both every 5 min
- Delayed exits
- Stale prices
- Poor execution

### ✅ Dual Loop (Correct)
- Entry: 5-min candles
- Exit: 1-min LTP checks
- Exit within 1 minute
- Better P&L

**Use**: `dual_loop_runner.py` for proper implementation!
