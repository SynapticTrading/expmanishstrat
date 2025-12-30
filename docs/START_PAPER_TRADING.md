# How to Start Paper Trading and View Logs

## 🚀 Quick Start

### 1. Start Paper Trading

```bash
cd /Users/Algo_Trading/manishsir_options
python3 paper_trading/runner.py --broker zerodha
```

**Or run in background:**
```bash
# Start in background
nohup python3 paper_trading/runner.py --broker zerodha > paper_trading/logs/paper_trading.log 2>&1 &

# Save the process ID
echo $! > paper_trading/paper_trading.pid
```

### 2. View Logs in Real-Time

**Console Output (if running in foreground):**
```bash
python3 paper_trading/runner.py --broker zerodha
```

**If running in background:**
```bash
# View live updates
tail -f paper_trading/logs/paper_trading.log

# Or for trades only
tail -f paper_trading/logs/trades_*.csv
```

---

## 📁 Log Files Location

### Trade Logs (CSV)
**File:** `paper_trading/logs/trades_YYYYMMDD_HHMMSS.csv`

**Contains:**
- Order ID
- Symbol
- Strike, Type, Expiry
- Entry Price, Time
- Exit Price, Time
- P&L, P&L %
- Exit Reason
- Entry OI, VWAP
- Duration

**Example:**
```csv
order_id,symbol,strike,option_type,expiry,entry_price,entry_time,exit_price,exit_time,pnl,pnl_pct,exit_reason,entry_oi,entry_vwap,duration_minutes
PAPER_20251229_001,NIFTY25DEC26000CE,26000,CALL,2025-12-30,150.0,2025-12-29 09:35:00,159.5,2025-12-29 09:47:00,712.5,6.33,trailing_stop,31813050,148.0,12
```

### State File (JSON)
**File:** `paper_trading/state/trading_state_YYYYMMDD.json`

**Contains:**
- All active positions
- Closed positions
- Daily P&L
- VWAP tracking
- Strategy state
- System health

**View:**
```bash
cat paper_trading/state/trading_state_*.json | jq .
```

---

## 📊 Current vs Backtest Logs

### Backtest Log Format:
```
[2024-01-01 09:45:00] 🎯 ENTRY SIGNAL: CE 21750 - Price: 118.70, VWAP: 110.58, OI Change: -21450 (-0.54%)
[2024-01-01 09:50:00] 🔵 BUY OPTION EXECUTED: CE 21750 @ ₹118.70
[2024-01-01 10:20:00] 📊 VWAP STOP HIT: Current: ₹101.00, Stop: ₹108.68
[2024-01-01 10:25:00] 🔴 SELL OPTION EXECUTED: CE 21750 @ ₹108.68 | P&L: ₹-751.30 (-8.44%)
```

### Current Paper Trading Output:
```
[2025-12-29 11:35:00+05:30] STRATEGY LOOP - Processing 5-min candle...
[2025-12-29 11:35:00+05:30] Nifty Spot: 25973.50
[2025-12-29 11:35:00+05:30] Got 10 options in options chain
[11:35:05] Waiting 295s for next candle at 11:40:00
```

---

## 🔧 Enable Detailed Logging

The strategy already has detailed logging built-in! Just need to ensure it's outputting to file.

### Option 1: Redirect Console to File (Simplest)

```bash
python3 paper_trading/runner.py --broker zerodha 2>&1 | tee paper_trading/logs/paper_$(date +%Y%m%d_%H%M%S).log
```

This will:
- Show output in console (like backtest)
- Save to log file simultaneously
- Include all emoji indicators (🎯, 🔵, 🔴, etc.)

### Option 2: Background with Logging

```bash
python3 paper_trading/runner.py --broker zerodha > paper_trading/logs/paper_$(date +%Y%m%d_%H%M%S).log 2>&1 &
```

Then view:
```bash
tail -f paper_trading/logs/paper_*.log
```

---

## 📈 What You'll See

### On Market Open (9:15 AM):
```
[2025-12-29 09:15:00+05:30] STRATEGY LOOP - Processing 5-min candle...
[2025-12-29 09:15:00+05:30] Nifty Spot: 25973.50
[2025-12-29 09:15:00+05:30] NEW TRADING DAY: 2025-12-29
[2025-12-29 09:15:00+05:30] Determining daily direction...
[2025-12-29 09:15:00+05:30] Max Call OI: 26000, Max Put OI: 25900
[2025-12-29 09:15:00+05:30] Direction: CALL (Call dist: 26.50, Put dist: 73.50)
[2025-12-29 09:15:00+05:30] Daily Analysis Complete: Direction=CALL, Strike=26000
```

### On Entry Signal (e.g., 9:35 AM):
```
[2025-12-29 09:35:00+05:30] Entry Check:
[2025-12-29 09:35:00+05:30]   Strike: 26000 CALL
[2025-12-29 09:35:00+05:30]   Price: ₹150.00, VWAP: ₹148.00
[2025-12-29 09:35:00+05:30]   OI: 31,813,050, Change: -5.2%
[2025-12-29 09:35:00+05:30]   Unwinding: True, Price>VWAP: True
[2025-12-29 09:35:00+05:30] ✓ ENTRY CONDITIONS MET!
[2025-12-29 09:35:00] Paper Broker: BUY 26000 CALL @ ₹150.00
```

### On Exit (e.g., 9:47 AM):
```
[2025-12-29 09:47:00] Exit Monitor: Checking position PAPER_20251229_001
[2025-12-29 09:47:00]   Current LTP: ₹159.50
[2025-12-29 09:47:00]   Peak: ₹165.00
[2025-12-29 09:47:00]   Trailing Stop: ₹160.20 (10% below peak)
[2025-12-29 09:47:00] ✓ TRAILING STOP HIT!
[2025-12-29 09:47:00] Paper Broker: SELL 26000 CALL @ ₹159.50
[2025-12-29 09:47:00]   Entry: ₹150.00
[2025-12-29 09:47:00]   P&L: ₹712.50 (+6.33%)
[2025-12-29 09:47:00]   Duration: 12 minutes
```

---

## 🎯 Complete Example: Running a Session

```bash
# Terminal 1: Start paper trading
cd /Users/Algo_Trading/manishsir_options
python3 paper_trading/runner.py --broker zerodha 2>&1 | tee paper_trading/logs/session_$(date +%Y%m%d).log

# Terminal 2: Watch trades in real-time
watch -n 1 "tail -20 paper_trading/logs/trades_*.csv"

# Terminal 3: Monitor state
watch -n 5 "cat paper_trading/state/trading_state_*.json | jq '{date, daily_direction, open_positions, total_pnl_today}'"
```

---

## 📋 Stop Paper Trading

### If running in foreground:
Press `Ctrl+C`

### If running in background:
```bash
# Find process ID
cat paper_trading/paper_trading.pid

# Or search
ps aux | grep "paper_trading/runner.py"

# Kill gracefully
kill $(cat paper_trading/paper_trading.pid)

# Or force kill if needed
kill -9 $(cat paper_trading/paper_trading.pid)
```

---

## 🔍 Analyze Logs After Trading

### View all trades:
```bash
cat paper_trading/logs/trades_*.csv | column -t -s,
```

### Count winning vs losing trades:
```bash
# Winning trades
awk -F',' '$10 > 0 {count++} END {print "Wins:", count}' paper_trading/logs/trades_*.csv

# Losing trades
awk -F',' '$10 < 0 {count++} END {print "Losses:", count}' paper_trading/logs/trades_*.csv

# Total P&L
awk -F',' 'NR>1 {sum+=$10} END {print "Total P&L: ₹" sum}' paper_trading/logs/trades_*.csv
```

### View final state:
```bash
cat paper_trading/state/trading_state_*.json | jq '{
  total_pnl_today: .daily_stats.total_pnl_today,
  win_rate: .daily_stats.win_rate,
  trades_today: .daily_stats.trades_today,
  portfolio_value: .portfolio.total_value
}'
```

---

## 📊 Compare with Backtest

**Backtest:**
```bash
python3 backtest_runner.py > reports/backtest_$(date +%Y%m%d).txt
```

**Paper Trading:**
```bash
python3 paper_trading/runner.py --broker zerodha 2>&1 | tee paper_trading/logs/paper_$(date +%Y%m%d).log
```

**Both produce similar detailed logs with:**
- ✅ Entry/Exit signals
- ✅ VWAP calculations
- ✅ OI changes
- ✅ Trailing stop activation
- ✅ P&L tracking
- ✅ Timestamped events

---

## 🎉 Ready to Start!

**Your command:**
```bash
python3 paper_trading/runner.py --broker zerodha 2>&1 | tee paper_trading/logs/paper_$(date +%Y%m%d_%H%M%S).log
```

**What happens:**
1. Connects to Zerodha (~0.3s)
2. Loads 47K instruments (~1.3s)
3. Starts dual loops:
   - Strategy: Every 5 minutes
   - Exit monitor: Every 1 minute
4. Logs everything to console AND file
5. Saves trades to CSV
6. Saves state to JSON

**Press Ctrl+C when done to exit gracefully.**
