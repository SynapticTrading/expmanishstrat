# Intraday Momentum OI Unwinding Strategy - Backtest System

<div align="center">

**A Professional Options Trading Strategy Backtesting Framework for Nifty Weekly Options**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: Private](https://img.shields.io/badge/license-Private-red.svg)](LICENSE)

</div>

---

## Table of Contents
- [Overview](#overview)
- [Key Features](#key-features)
- [Project Structure](#project-structure)
- [First-Time Setup](#first-time-setup)
- [Installation](#installation)
- [Configuration](#configuration)
- [Execution Modes: STRICT vs NORMAL](#execution-modes-strict-vs-normal)
- [Running Backtests](#running-backtests)
- [Understanding the Output](#understanding-the-output)
- [Strategy Logic](#strategy-logic)
- [Customization](#customization)
- [Troubleshooting](#troubleshooting)
- [Documentation](#documentation)
- [Performance Optimization](#performance-optimization)

---

## Overview

This is a comprehensive backtesting system for the **Intraday Momentum OI Unwinding Strategy** designed for **Nifty weekly options**. The strategy identifies and trades based on **Open Interest (OI) unwinding patterns** (short covering/long unwinding) combined with **VWAP confirmations**.

### What This Strategy Does

The strategy analyzes options Open Interest (OI) patterns to detect:
- **Short Covering**: Calls with decreasing OI (bullish)
- **Long Unwinding**: Puts with decreasing OI (bearish)

When combined with VWAP confirmation, these signals generate high-probability intraday option buying opportunities.

### Core Trading Concept

1. **Daily Market Analysis**: Identify direction based on maximum Call/Put OI buildup near spot price
2. **Entry Signal**: OI unwinding (decrease) at selected strike + Option price above VWAP
3. **Exit Management**: Multiple stop losses (Initial 25%, VWAP-based 5%, OI-based 10%, Trailing 10%)
4. **Risk Control**: Time-based EOD exit + configurable position sizing

---

## Key Features

### Backtesting Engine
- ✅ **High-Resolution Data**: 5-minute candle backtesting (configurable to 1-min, 3-min, etc.)
- ✅ **IST Timezone Handling**: Proper Indian market hours (09:15 - 15:30)
- ✅ **Weekly Expiry Options**: Supports Nifty weekly options analysis
- ✅ **OI Change Tracking**: Real-time OI monitoring for unwinding detection
- ✅ **VWAP Indicator**: Market-open anchored VWAP for entry/exit signals

### Risk Management
- ✅ **Multiple Stop Losses**: Initial (25%), VWAP (5%), OI (10%), Trailing (10%)
- ✅ **Strict Execution Mode**: Exit at EXACT threshold prices (no slippage)
- ✅ **Position Sizing**: Configurable capital allocation and lot sizing
- ✅ **Time-based Exits**: Automatic position closure before market close
- ✅ **Max Concurrent Positions**: Limit number of simultaneous trades

### Reporting & Analytics
- ✅ **Comprehensive Trade Logs**: Timestamped CSV files with all trade details
- ✅ **Performance Metrics**: Sharpe ratio, max drawdown, win rate, profit factor
- ✅ **Visual Reports**: Equity curve, trade analysis, monthly statistics
- ✅ **Terminal Output Logging**: Complete backtest logs saved automatically
- ✅ **JSON Export**: Machine-readable metrics for further analysis

### Configuration
- ✅ **YAML-based Config**: Easy-to-edit strategy parameters
- ✅ **Date Range Selection**: Backtest any historical period
- ✅ **Flexible Timeframes**: 1-min, 3-min, 5-min, 15-min candles
- ✅ **Toggle Execution Modes**: Switch between STRICT and NORMAL with one command

---

## Project Structure

```
manishsir_options/
│
├── README.md                          # This file - comprehensive guide
├── requirements.txt                   # Python dependencies
├── backtest_runner.py                 # Main backtest execution script
│
├── config/                            # Configuration files
│   └── strategy_config.yaml           # Strategy parameters (EDIT THIS!)
│
├── src/                               # Core source code modules
│   ├── __init__.py                    # Package initialization
│   ├── config_loader.py               # Configuration loader utility
│   ├── data_loader.py                 # Data loading & preprocessing
│   ├── oi_analyzer.py                 # Open Interest analysis logic
│   ├── indicators.py                  # Custom indicators (VWAP, etc.)
│   └── reporter.py                    # Performance reporting & metrics
│
├── strategies/                        # Strategy implementations
│   ├── __init__.py                    # Package initialization
│   └── intraday_momentum_oi.py        # Main strategy logic (750+ lines)
│
├── DataDump/                          # Input data files
│   ├── nifty_5min_2024.csv            # Spot price data (5-min OHLCV)
│   └── combined_options_5min_2024_with_delta.csv  # Options data with OI
│
├── reports/                           # Generated output (DO NOT EDIT)
│   ├── trades.csv                     # Latest trade log
│   ├── trades_YYYYMMDD_HHMMSS.csv     # Archived timestamped trades
│   ├── trade_summary.txt              # Human-readable summary
│   ├── trade_summary.json             # JSON metrics export
│   ├── backtest_metrics.json          # Detailed analytics
│   ├── backtest_log_YYYYMMDD_HHMMSS.txt  # Full terminal output logs
│   ├── equity_curve.png               # Portfolio value chart
│   └── trade_analysis.png             # Trade distribution chart
│
├── logs/                              # Application logs
│   └── backtest.log                   # Detailed debug logs
│
├── scripts/                           # Utility scripts
│   └── toggle_strict_execution.py     # Switch STRICT ↔ NORMAL mode
│
├── docs/                              # Documentation (READ THESE!)
│   ├── HOW_TO_RUN.md                  # Quick start guide
│   ├── QUICKSTART.md                  # Ultra-fast setup guide
│   ├── STRATEGY_DETAILS.md            # Strategy logic deep-dive
│   ├── STRICT_VS_NORMAL_COMPARISON.md # Execution mode comparison
│   ├── STRICT_EXECUTION_CHANGES.py    # Technical docs for strict mode
│   ├── LOGGING_FIX_SUMMARY.md         # Logging implementation details
│   ├── QUICK_REFERENCE.txt            # Cheat sheet for commands
│   ├── ISSUES_AND_FIXES.md            # Common problems & solutions
│   ├── REALISTIC_EXECUTION_ANALYSIS.md    # Execution realism analysis
│   ├── REALISTIC_EXECUTION_EXPLAINED.md   # Execution model explanation
│   └── SWITCHING_THEORETICAL_REALISTIC_MODES.md  # Mode switching guide
│
├── utils/                             # Utility modules (if any)
└── data/                              # Additional data files (if any)
```

### Key Files to Know

| File/Directory | Purpose | When to Edit |
|----------------|---------|--------------|
| `config/strategy_config.yaml` | Strategy parameters | Always - customize your strategy |
| `backtest_runner.py` | Main execution script | Rarely - only for advanced features |
| `strategies/intraday_momentum_oi.py` | Strategy logic | Advanced users only |
| `scripts/toggle_strict_execution.py` | Switch execution modes | Run as-is, don't edit |
| `reports/` | Output files | Never - auto-generated |
| `DataDump/` | Input CSV files | Replace with your data |
| `docs/` | Documentation | Read for reference |

---

## First-Time Setup

### Prerequisites

Before starting, ensure you have:

1. **Python 3.8 or higher** installed
   ```bash
   python --version  # Should show 3.8.x or higher
   ```

2. **pip** package manager installed
   ```bash
   pip --version
   ```

3. **Git** (optional, for version control)
   ```bash
   git --version
   ```

4. **At least 8GB RAM** (for processing large options data)
5. **2GB free disk space** (for data files and reports)

### Quick Setup (5 Minutes)

```bash
# 1. Navigate to project directory
cd /Users/Algo_Trading/manishsir_options

# 2. Install dependencies
pip install -r requirements.txt

# 3. Verify data files exist
ls -lh DataDump/
# Should show:
#   nifty_5min_2024.csv
#   combined_options_5min_2024_with_delta.csv

# 4. Check current execution mode
python scripts/toggle_strict_execution.py --check

# 5. Run your first backtest!
python backtest_runner.py

# 6. View results
cat reports/trade_summary.txt
```

That's it! You're ready to backtest.

---

## Installation

### Step 1: Install Python Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `backtrader==1.9.78.123` - Backtesting framework
- `pandas==2.0.3` - Data manipulation
- `numpy==1.24.3` - Numerical computing
- `matplotlib==3.7.2` - Charting
- `PyYAML==6.0.1` - Configuration parsing
- `pytz==2023.3` - Timezone handling

### Step 2: Verify Installation

```bash
python -c "import backtrader as bt; print(f'Backtrader {bt.__version__} installed successfully!')"
```

Expected output: `Backtrader 1.9.78.123 installed successfully!`

### Step 3: Prepare Data Files

Ensure your data files are in the correct format:

#### Spot Price CSV Format (`DataDump/nifty_5min_2024.csv`)
```csv
date,open,high,low,close,volume
2024-01-01 09:15:00+05:30,23637.65,23681.7,23633.35,23649.55,0
2024-01-01 09:20:00+05:30,23649.55,23670.20,23645.10,23658.30,0
```

**Requirements:**
- Timestamp with IST timezone (`+05:30`)
- 5-minute intervals (or your configured timeframe)
- OHLCV columns

#### Options CSV Format (`DataDump/combined_options_5min_2024_with_delta.csv`)
```csv
timestamp,strike,expiry,option_type,open,high,low,close,volume,underlying_price,futures_price,IV,time_to_expiry,delta,OI
2024-01-01 09:15:00+05:30,22000,2024-01-02,CE,1421.75,1427.15,1421.75,1427.15,975,23649.55,23651.94,0.759,0.0016,0.976,12255300
```

**Requirements:**
- Timestamp with IST timezone
- Columns: `timestamp`, `strike`, `expiry`, `option_type`, `open`, `high`, `low`, `close`, `volume`, `OI`
- Option types: `CE` (Call) or `PE` (Put)
- Open Interest (`OI`) column is critical

---

## Configuration

All strategy parameters are controlled via `config/strategy_config.yaml`.

### Key Configuration Sections

#### 1. Data Settings

```yaml
data:
  spot_price_file: "DataDump/nifty_5min_2024.csv"
  options_file: "DataDump/combined_options_5min_2024_with_delta.csv"
  timeframe: 5          # Candle size in minutes (1, 3, 5, 15, etc.)
  start_date: "2024-01-01"
  end_date: "2024-12-31"
  timezone: "Asia/Kolkata"
```

**Tip:** For faster backtests, use `timeframe: 5` instead of `timeframe: 1`.

#### 2. Market Settings

```yaml
market:
  instrument: "NIFTY"
  expiry_type: "weekly"
  option_lot_size: 75   # Standard NIFTY lot size (verify with current NSE specs)
```

#### 3. Entry Configuration

```yaml
entry:
  start_time: "09:30"   # First entry allowed at 9:30 AM IST
  end_time: "14:30"     # Last entry allowed at 2:30 PM IST
  strikes_above_spot: 5 # Analyze 5 strikes above current spot
  strikes_below_spot: 5 # Analyze 5 strikes below current spot
```

**Explanation:**
- `start_time`: Wait for market to stabilize before entering
- `end_time`: Don't enter too close to market close
- `strikes_above/below_spot`: Defines OI analysis range

#### 4. Exit Configuration (CRITICAL!)

```yaml
exit:
  exit_start_time: "14:50"      # Start closing positions at 2:50 PM
  exit_end_time: "15:00"        # Force close all by 3:00 PM
  initial_stop_loss_pct: 0.25   # 25% stop loss (exit at 75% of entry price)
  profit_threshold: 1.10        # Activate trailing stop at 10% profit
  trailing_stop_pct: 0.10       # Trail by 10% from highest price
  vwap_stop_pct: 0.05           # Exit if price drops >5% below VWAP (loss trades only)
  oi_increase_stop_pct: 0.10    # Exit if OI increases >10% from entry (loss trades only)
```

**Stop Loss Hierarchy:**
1. **Initial SL (25%)**: First line of defense
2. **VWAP Stop (5%)**: Exit if price significantly below VWAP
3. **OI Stop (10%)**: Exit if OI reversal detected
4. **Trailing Stop (10%)**: Protect profits after 10% gain
5. **EOD Exit**: Close all positions before 3:00 PM

#### 5. Position Sizing

```yaml
position_sizing:
  initial_capital: 100000      # Starting capital: ₹1,00,000
  risk_per_trade_pct: 0.01     # Risk 1% per trade
  position_size: 1             # 1 lot per trade in Backtrader (represents 75 units for NIFTY)
```

**Example Calculation:**
- Capital: ₹1,00,000
- Risk per trade: 1% = ₹1,000
- Entry price: ₹100
- Stop loss: 25% = ₹75
- Risk per unit: ₹25
- Position size: ₹1,000 / ₹25 = 40 units (rounded)

#### 6. Risk Management

```yaml
risk_management:
  max_positions: 2              # Maximum 2 simultaneous trades
  avoid_monday_tuesday: false   # Set true to skip Mon/Tue (near expiry)
```

**Tip:** Set `max_positions: 1` if you want only one trade at a time.

#### 7. Backtesting Parameters

```yaml
backtest:
  commission: 0.0005   # 0.05% commission per trade (₹50 per ₹1L)
  slippage: 0.0        # 0% slippage (use STRICT mode instead)
```

**Note:** Slippage is controlled via execution mode (STRICT/NORMAL), not this parameter.

---

## Execution Modes: STRICT vs NORMAL

This is a **UNIQUE FEATURE** of this backtesting system!

### What's the Difference?

| Aspect | NORMAL Mode | STRICT Mode |
|--------|-------------|-------------|
| **Stop Loss Exit** | Exit at current market price when threshold crossed | Exit at EXACT threshold price |
| **Example** | SL at -25%, but exits at -33% | SL at -25%, exits at exactly -25% |
| **Slippage** | 3-4% average excess loss | 0% excess loss |
| **Live Trading** | Pessimistic (assumes worst case) | Realistic (matches limit orders) |
| **Backtest Results** | More conservative | More accurate |
| **Use Case** | Research, worst-case analysis | Live trading simulation |

### Visual Example

**Scenario:** 25% stop loss on ₹100 entry (stop at ₹75)

**NORMAL Mode:**
```
Time    Price   Status
09:35   ₹100    Entry
10:15   ₹80     Still OK (above SL ₹75)
10:20   ₹70     🛑 SL TRIGGERED! Exit at ₹70 (-30%)
```
Result: -30% loss (5% slippage beyond configured -25%)

**STRICT Mode:**
```
Time    Price   Status
09:35   ₹100    Entry
10:15   ₹80     Still OK (above SL ₹75)
10:20   ₹70     🛑 SL TRIGGERED! Exit at ₹75 (-25%) STRICT
```
Result: -25% loss (exactly as configured, 0% slippage)

### How to Toggle Modes

#### Check Current Mode
```bash
python scripts/toggle_strict_execution.py --check
```

Output:
```
Current execution mode: STRICT
  ✅ Stops exit at EXACT threshold prices (5%, 10%, 25%)
  ✅ Best for live trading with precise risk control
```

#### Switch to STRICT Mode (Recommended)
```bash
python scripts/toggle_strict_execution.py --mode strict
```

Output:
```
✅ Successfully enabled STRICT mode!
   All stops will now exit at EXACT THRESHOLD PRICES (5%, 10%, 25%).
```

#### Switch to NORMAL Mode
```bash
python scripts/toggle_strict_execution.py --mode normal
```

Output:
```
✅ Successfully reverted to NORMAL mode!
   All stops will now exit at CURRENT MARKET PRICE when thresholds are crossed.
```

### When to Use Each Mode

**Use STRICT Mode (Recommended):**
- ✅ Simulating live trading with limit orders
- ✅ Precise risk management requirements
- ✅ Professional trading setups
- ✅ Consistent, predictable results

**Use NORMAL Mode:**
- ⚠️ Conservative backtesting (worst-case scenarios)
- ⚠️ Academic research on slippage effects
- ⚠️ Testing strategy robustness with realistic market friction

**Default:** The system is currently in **STRICT mode** for optimal performance.

---

## Running Backtests

### Basic Usage

```bash
# Run backtest with default configuration
python backtest_runner.py
```

### Advanced Usage

```bash
# Use custom configuration file
python backtest_runner.py --config config/my_custom_config.yaml

# Run with verbose logging
python -u backtest_runner.py 2>&1 | tee reports/my_backtest_log.txt
```

### What Happens During a Backtest

1. **Initialization** (5-30 seconds)
   - Load configuration
   - Load spot price data
   - Load options data (large file, be patient!)
   - Initialize Backtrader cerebro engine

2. **Execution** (1-5 minutes depending on date range)
   - Process each candle sequentially
   - Analyze OI patterns daily
   - Generate entry/exit signals
   - Execute trades
   - Update positions

3. **Reporting** (2-3 seconds)
   - Calculate performance metrics
   - Generate trade logs
   - Create visualizations
   - Save summary files

### Monitoring Progress

You'll see real-time output like:

```
================================================================================
Starting Backtest: 2024-01-01 to 2024-12-31
================================================================================

[2024-01-01 09:15:00] Starting daily analysis - Spot: ₹23,649.55
[2024-01-01 09:15:00] Direction determined: PUT (Max OI buildup at 23600 PE)
[2024-01-01 09:36:00] 🎯 ENTRY SIGNAL: PE 23600 @ ₹103.50 (above VWAP ₹97.47)
[2024-01-01 09:37:00] 🔵 BUY OPTION EXECUTED: PE 23600 @ ₹103.40 (1 lot)

...

[2024-01-01 14:51:00] 🔴 SELL OPTION EXECUTED: PE 23600 @ ₹238.80
[2024-01-01 14:51:00] 💰 Trade Closed: P&L = +₹135.40 (+130.89%)

...

================================================================================
                          BACKTEST RESULTS
================================================================================
Final Portfolio Value:  ₹170,300.00
Total Return:           ₹70,300.00 (+70.30%)
Total Trades:           194
Win Rate:               27.84%
Sharpe Ratio:           2.27
Max Drawdown:           -13.83%
================================================================================
```

### Stopping a Backtest

- **Ctrl+C**: Safe interrupt - summary files will be generated before exit
- All completed trades are saved immediately (no data loss)

---

## Understanding the Output

### Generated Files

After a backtest run, you'll find these files in `reports/`:

#### 1. Trade Log - `trades.csv`
**Format:**
```csv
entry_time,exit_time,strike,option_type,expiry,entry_price,exit_price,size,pnl,pnl_pct,exit_reason
2024-01-01 09:37:00,2024-01-01 14:51:00,23600,PE,2024-01-02,103.4,238.8,1,135.4,130.89,EOD
```

**Columns:**
- `entry_time`: Trade entry timestamp (IST)
- `exit_time`: Trade exit timestamp (IST)
- `strike`: Strike price
- `option_type`: CE (Call) or PE (Put)
- `expiry`: Option expiry date
- `entry_price`: Buy price (₹)
- `exit_price`: Sell price (₹)
- `size`: Position size (lots)
- `pnl`: Profit/Loss in rupees
- `pnl_pct`: Profit/Loss percentage
- `exit_reason`: Why trade closed (EOD, SL, VWAP_STOP, OI_STOP, TRAILING)

#### 2. Trade Summary - `trade_summary.txt`
Human-readable performance summary:

```
================================================================================
TRADE SUMMARY
================================================================================
Final Portfolio Value: ₹170,300.00
Total Return:          ₹70,300.00 (+70.30%)

Trade Statistics:
  Total Trades:        194
  Winning Trades:      54
  Losing Trades:       140
  Win Rate:            27.84%

Profitability:
  Total P&L:           ₹70,300.00
  Average P&L:         ₹362.37
  Best Trade:          ₹8,450.00 (+245.6%)
  Worst Trade:         ₹-1,250.00 (-25.0%)
  Profit Factor:       2.67

Risk Metrics:
  Sharpe Ratio:        2.27
  Max Drawdown:        ₹-13,830.00 (-13.83%)
  Max Drawdown Date:   2024-06-15
================================================================================
```

#### 3. JSON Metrics - `trade_summary.json`
Machine-readable format for further analysis:

```json
{
  "final_value": 170300.00,
  "total_return": 70300.00,
  "total_return_pct": 70.30,
  "total_trades": 194,
  "win_rate": 27.84,
  "sharpe_ratio": 2.27,
  "max_drawdown": -13.83,
  "profit_factor": 2.67
}
```

#### 4. Backtest Log - `backtest_log_YYYYMMDD_HHMMSS.txt`
Complete terminal output with all entry/exit signals:

```
[2024-01-01 09:15:00] Starting daily analysis
[2024-01-01 09:15:00] Analyzing 10 strikes (5 above, 5 below spot)
[2024-01-01 09:15:00] Max Call OI: 23650 (1,234,500 contracts)
[2024-01-01 09:15:00] Max Put OI: 23600 (1,567,800 contracts)
[2024-01-01 09:15:00] Direction: PUT (23600 closer to spot 23649.55)
...
```

**Tip:** Use this for detailed debugging and understanding why trades were taken.

#### 5. Charts - `equity_curve.png` and `trade_analysis.png`
Visual representations of:
- Portfolio value over time
- Trade distribution (wins vs losses)
- Monthly returns
- Drawdown periods

### Interpreting Results

#### Key Metrics Explained

**1. Total Return %**
- **What:** Overall profit/loss percentage
- **Good:** >20% annually
- **Excellent:** >50% annually
- **Your target:** Depends on risk appetite

**2. Win Rate**
- **What:** Percentage of winning trades
- **Normal:** 30-40% (due to tight stops)
- **Don't worry:** Low win rate is OK if profit factor is high

**3. Profit Factor**
- **What:** Total wins ÷ Total losses
- **Minimum:** >1.5 (profitable)
- **Good:** >2.0
- **Excellent:** >3.0

**4. Sharpe Ratio**
- **What:** Risk-adjusted return
- **Good:** >1.0
- **Excellent:** >2.0
- **Interpretation:** Higher = better risk/reward

**5. Max Drawdown**
- **What:** Largest peak-to-trough decline
- **Acceptable:** <20%
- **Warning:** >30% (too risky)
- **Critical:** >50% (strategy needs revision)

**6. Average P&L**
- **What:** Average profit/loss per trade
- **Important:** Should be positive
- **Ideal:** >₹500 per trade for ₹1L capital

---

## Strategy Logic

### How the Strategy Works (Step-by-Step)

#### Phase 1: Daily Market Analysis (09:15 AM)

**Step 1:** Identify current spot price
```
Spot Price: ₹23,649.55
```

**Step 2:** Analyze OI buildup in 10 strikes (5 above, 5 below)
```
Strikes: 23550, 23600, 23650, 23700, 23750 (5 below)
         23750, 23800, 23850, 23900, 23950 (5 above)
```

**Step 3:** Find maximum Call OI and Put OI
```
Max Call OI: 23800 CE (1,456,000 contracts) - Distance from spot: 150 points
Max Put OI:  23600 PE (1,897,000 contracts) - Distance from spot: 49 points
```

**Step 4:** Determine direction (choose closer to spot)
```
Decision: TRADE PUT OPTIONS (23600 PE closer to spot)
Reasoning: Strong Put OI buildup near spot = potential Put unwinding (bullish Put premium)
```

**Step 5:** Select strike to trade
```
For PUT direction: Choose nearest strike BELOW spot
Selected Strike: 23600 PE
```

#### Phase 2: Entry Signal Detection (09:30 - 14:30)

**Monitor every 5 minutes:**

**Entry Condition 1:** OI is DECREASING (unwinding)
```
Previous OI: 1,897,000
Current OI:  1,856,000
Change:      -41,000 (-2.16%) ✅ UNWINDING DETECTED
```

**Entry Condition 2:** Option price is ABOVE VWAP
```
Current Price: ₹103.50
VWAP:          ₹97.47
Difference:    +6.2% ✅ PRICE ABOVE VWAP
```

**Entry Condition 3:** Within entry time window
```
Current Time: 09:36 AM ✅ (between 09:30 - 14:30)
```

**🎯 ALL CONDITIONS MET → ENTER TRADE**
```
🔵 BUY OPTION: PE 23600 @ ₹103.40 (1 lot = 75 units)
```

#### Phase 3: Position Management (During Trade)

**Every 5 minutes, check 4 stops in this order:**

**1. Initial Stop Loss (25%)**
```
Entry Price:  ₹103.40
Stop Price:   ₹77.55 (25% below entry)
Current Price: ₹95.20
Status: ✅ OK (above stop)
```

**2. VWAP Stop (5% below VWAP, only if trade in loss)**
```
Current VWAP: ₹98.50
VWAP Threshold: ₹93.58 (5% below)
Current Price: ₹95.20
Trade P&L: -7.9% (in loss)
Status: ✅ OK (above VWAP threshold)
```

**3. OI Increase Stop (10%, only if trade in loss)**
```
Entry OI:     1,856,000
Current OI:   1,798,000
Change:       -3.1% (still unwinding)
Status: ✅ OK (OI not increasing)
```

**4. Trailing Stop (10% from peak, only after 10% profit)**
```
Highest Price: ₹238.80 (profit = +130.9%)
Trailing Stop: ₹214.92 (10% below peak)
Current Price: ₹238.80
Status: ✅ OK (trailing stop active, protecting profit)
```

#### Phase 4: Exit Signal

**Exit can happen for 5 reasons:**

**Reason 1: Time-based (EOD)**
```
Time: 14:51 PM ✅ Force close all positions
Exit Price: ₹238.80
P&L: +₹135.40 (+130.89%) 💰
```

**Reason 2: Initial Stop Loss Hit**
```
Current Price: ₹75.00 (crossed ₹77.55 SL)
Exit Price: ₹77.55 (STRICT mode) or ₹75.00 (NORMAL mode)
P&L: -25.0% (STRICT) or -27.4% (NORMAL)
```

**Reason 3: VWAP Stop Hit**
```
Current Price: ₹90.00 (>5% below VWAP)
Exit Price: ₹93.58 (STRICT mode) or ₹90.00 (NORMAL mode)
P&L: -9.5% (STRICT) or -13.0% (NORMAL)
```

**Reason 4: OI Increase Stop Hit**
```
OI increased +12% from entry (reversal signal)
Exit at proportional price for +10% OI (STRICT) or current price (NORMAL)
```

**Reason 5: Trailing Stop Hit**
```
Price dropped 10% from peak ₹250.00 to ₹225.00
Exit Price: ₹225.00 (10% trail from peak)
P&L: +117.6% (protecting profits)
```

### Strategy Edge

**Why This Strategy Works:**

1. **OI Unwinding = Real Money Flow**: Institutional positions closing = strong price movement
2. **VWAP Confirmation**: Filters false signals by requiring price strength
3. **Multiple Timeframe Analysis**: Daily analysis + intraday execution
4. **Asymmetric Risk/Reward**: Small losses (25% max), big wins (often >100%)
5. **Strict Risk Management**: 4 layers of protection prevent catastrophic losses

---

## Customization

### Common Modifications

#### 1. Change Backtest Period

Edit `config/strategy_config.yaml`:
```yaml
data:
  start_date: "2024-06-01"  # Start from June
  end_date: "2024-12-31"    # End at December
```

#### 2. Adjust Stop Losses

```yaml
exit:
  initial_stop_loss_pct: 0.20    # Wider stop: 20% instead of 25%
  trailing_stop_pct: 0.15        # Wider trail: 15% instead of 10%
  vwap_stop_pct: 0.08            # More lenient: 8% instead of 5%
```

**Effect:** Fewer stop-outs, but larger losses when stops hit.

#### 3. Increase Position Size

```yaml
position_sizing:
  initial_capital: 200000   # Double capital to ₹2L
  position_size: 2          # Trade 2 lots instead of 1
```

**Warning:** Higher returns but also higher risk!

#### 4. Limit to One Trade Per Day

Edit `strategies/intraday_momentum_oi.py` (line ~400):
```python
# Add flag in __init__
self.traded_today = False

# In check_entry_conditions():
if self.traded_today:
    return  # Skip if already traded today

# In notify_order() after entry:
self.traded_today = True

# In next() at daily reset:
if self.current_date != datetime.now().date():
    self.traded_today = False
```

#### 5. Skip Expiry Days (Monday/Tuesday)

```yaml
risk_management:
  avoid_monday_tuesday: true  # Don't trade near weekly expiry
```

**Reasoning:** Theta decay and volatility spikes near expiry.

#### 6. Change Candle Timeframe

```yaml
data:
  timeframe: 3  # Use 3-minute candles instead of 5-minute
```

**Note:** Requires 3-minute data in `DataDump/` files.

---

## Troubleshooting

### Common Issues & Solutions

#### Issue 1: "Memory Error" when loading data

**Symptoms:**
```
MemoryError: Unable to allocate array with shape...
```

**Cause:** Options CSV file is very large (2GB+)

**Solutions:**
1. **Increase system RAM** (minimum 8GB recommended)
2. **Reduce date range** in config:
   ```yaml
   data:
     start_date: "2024-11-01"  # Only test 2 months
     end_date: "2024-12-31"
   ```
3. **Filter data file** to only relevant strikes:
   ```bash
   # Keep only strikes within ±500 points of spot
   python scripts/filter_options_data.py
   ```

#### Issue 2: "No trades generated"

**Symptoms:**
```
Total Trades: 0
Final Value: ₹100,000.00 (unchanged)
```

**Possible Causes:**

**A. No OI data in date range**
```bash
# Check if OI column has values
head -20 DataDump/combined_options_5min_2024_with_delta.csv
# Look for non-zero OI values
```

**B. Entry conditions too restrictive**
- Temporarily relax conditions to test:
```yaml
entry:
  start_time: "09:15"  # Earlier entry (was 09:30)
  end_time: "15:00"    # Later entry (was 14:30)
```

**C. Wrong timezone in data**
```bash
# Verify timestamps have +05:30 suffix
head DataDump/nifty_5min_2024.csv
```

#### Issue 3: "Timezone errors"

**Symptoms:**
```
ValueError: Timestamp has no timezone info
```

**Solution:**
Ensure all timestamps in CSV files include timezone:
```bash
# Fix missing timezone
sed 's/\([0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\} [0-9]\{2\}:[0-9]\{2\}:[0-9]\{2\}\)$/\1+05:30/g' \
  DataDump/nifty_5min_2024.csv > DataDump/nifty_5min_2024_fixed.csv
```

#### Issue 4: "Import errors"

**Symptoms:**
```
ModuleNotFoundError: No module named 'backtrader'
```

**Solution:**
```bash
# Reinstall all dependencies
pip install -r requirements.txt --upgrade --force-reinstall

# Verify installation
python -c "import backtrader, pandas, numpy, yaml; print('All modules OK')"
```

#### Issue 5: "Permission denied" on toggle script

**Symptoms:**
```
Permission denied: scripts/toggle_strict_execution.py
```

**Solution:**
```bash
# Make script executable
chmod +x scripts/toggle_strict_execution.py

# Run with python explicitly
python scripts/toggle_strict_execution.py --check
```

#### Issue 6: Results differ from previous runs

**Symptoms:**
```
Previous run: +70.3% return
Current run:  +42.1% return
```

**Possible Causes:**

**A. Execution mode changed**
```bash
# Check if STRICT ↔ NORMAL mode was toggled
python scripts/toggle_strict_execution.py --check
```

**B. Configuration modified**
```bash
# Check what changed
git diff config/strategy_config.yaml
```

**C. Data files updated**
```bash
# Check file modification dates
ls -lht DataDump/
```

### Getting Help

If issues persist:

1. **Check logs:**
   ```bash
   cat reports/backtest_log_*.txt | tail -100
   ```

2. **Enable debug mode:**
   ```python
   # In backtest_runner.py, add:
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

3. **Review documentation:**
   ```bash
   cat docs/ISSUES_AND_FIXES.md
   ```

4. **Contact support:** [Your support channel here]

---

## Documentation

### Quick Reference

| Document | Purpose | When to Read |
|----------|---------|--------------|
| `README.md` (this file) | Comprehensive guide | First-time setup, reference |
| `docs/QUICKSTART.md` | Ultra-fast 2-minute setup | Experienced users |
| `docs/HOW_TO_RUN.md` | Detailed run instructions | Before first run |
| `docs/STRATEGY_DETAILS.md` | Strategy logic deep-dive | Understanding the algorithm |
| `docs/STRICT_VS_NORMAL_COMPARISON.md` | Execution mode comparison | Choosing STRICT vs NORMAL |
| `docs/STRICT_EXECUTION_CHANGES.py` | Technical implementation | Developers, advanced users |
| `docs/LOGGING_FIX_SUMMARY.md` | Logging system details | Understanding output files |
| `docs/QUICK_REFERENCE.txt` | Command cheat sheet | Daily usage |
| `docs/ISSUES_AND_FIXES.md` | Troubleshooting guide | When problems arise |
| `docs/REALISTIC_EXECUTION_EXPLAINED.md` | Execution model explanation | Understanding trade fills |

### Learning Path

**Beginner (Day 1):**
1. Read this README (you're here!) ✓
2. Run first backtest: `python backtest_runner.py`
3. Review `reports/trade_summary.txt`
4. Check `docs/QUICKSTART.md`

**Intermediate (Day 2-3):**
1. Understand strategy: `docs/STRATEGY_DETAILS.md`
2. Customize config: `config/strategy_config.yaml`
3. Compare modes: `docs/STRICT_VS_NORMAL_COMPARISON.md`
4. Toggle and test both modes

**Advanced (Day 4+):**
1. Modify strategy code: `strategies/intraday_momentum_oi.py`
2. Add custom indicators: `src/indicators.py`
3. Build analysis scripts: Python + pandas
4. Optimize parameters: Grid search on config values

---

## Performance Optimization

### For Faster Backtests

#### 1. Use Larger Timeframes
```yaml
data:
  timeframe: 5  # 5-min is 5x faster than 1-min
```

**Speed impact:** 1-min (slowest) → 3-min (fast) → 5-min (fastest)

#### 2. Reduce Date Range
```yaml
data:
  start_date: "2024-10-01"  # Test 3 months instead of 1 year
  end_date: "2024-12-31"
```

**Speed impact:** 1 year (slow) → 6 months (fast) → 3 months (fastest)

#### 3. Filter Options Data

Create `scripts/filter_options_data.py`:
```python
import pandas as pd

# Load full data
df = pd.read_csv('DataDump/combined_options_5min_2024_with_delta.csv')

# Keep only strikes within ±10% of spot (reduces size by 80%)
spot_mean = df['underlying_price'].mean()
df_filtered = df[
    (df['strike'] >= spot_mean * 0.90) &
    (df['strike'] <= spot_mean * 1.10)
]

# Save filtered version
df_filtered.to_csv('DataDump/combined_options_5min_2024_filtered.csv', index=False)
print(f"Reduced from {len(df):,} to {len(df_filtered):,} rows")
```

Then update config:
```yaml
data:
  options_file: "DataDump/combined_options_5min_2024_filtered.csv"
```

#### 4. Use SSD Storage
- Store `DataDump/` on SSD for 3-5x faster loading
- Move project to SSD if on HDD

#### 5. Disable Plotting (for bulk runs)
```yaml
reporting:
  generate_plots: false  # Saves 2-3 seconds per run
```

#### 6. Run in Background
```bash
# Run backtest and free up terminal
nohup python backtest_runner.py > reports/backtest.out 2>&1 &

# Check progress
tail -f reports/backtest.out
```

### For Better Performance

#### 1. Optimize Parameters
Use grid search to find best configuration:

```python
# Create scripts/optimize.py
import yaml
from itertools import product

# Parameters to test
stop_losses = [0.20, 0.25, 0.30]
trailing_stops = [0.08, 0.10, 0.12]

results = []
for sl, ts in product(stop_losses, trailing_stops):
    # Update config
    config = yaml.safe_load(open('config/strategy_config.yaml'))
    config['exit']['initial_stop_loss_pct'] = sl
    config['exit']['trailing_stop_pct'] = ts

    # Save temp config
    with open('config/temp_config.yaml', 'w') as f:
        yaml.dump(config, f)

    # Run backtest
    os.system('python backtest_runner.py --config config/temp_config.yaml')

    # Parse results
    summary = json.load(open('reports/trade_summary.json'))
    results.append({
        'sl': sl,
        'ts': ts,
        'return': summary['total_return_pct'],
        'sharpe': summary['sharpe_ratio']
    })

# Find best parameters
best = max(results, key=lambda x: x['sharpe'])
print(f"Best config: SL={best['sl']}, TS={best['ts']}, Sharpe={best['sharpe']}")
```

#### 2. Analyze Trade Patterns
```bash
# Extract winning trades
awk -F',' '$9 > 0' reports/trades.csv > reports/winners.csv

# Extract losing trades
awk -F',' '$9 < 0' reports/trades.csv > reports/losers.csv

# Find patterns (e.g., time of day, strike levels, etc.)
```

#### 3. Backtest Multiple Years
```bash
# Test 2022, 2023, 2024 separately
for year in 2022 2023 2024; do
  # Update config for each year
  sed -i "s/start_date: \"[0-9]*-01-01\"/start_date: \"$year-01-01\"/" config/strategy_config.yaml
  sed -i "s/end_date: \"[0-9]*-12-31\"/end_date: \"$year-12-31\"/" config/strategy_config.yaml

  # Run backtest
  python backtest_runner.py

  # Archive results
  cp reports/trade_summary.txt reports/summary_$year.txt
done
```

---

## Advanced Topics

### Walk-Forward Analysis

Test strategy on rolling windows:

```python
# scripts/walk_forward.py
import pandas as pd
from dateutil.relativedelta import relativedelta

start = pd.Timestamp('2024-01-01')
end = pd.Timestamp('2024-12-31')

# 3-month train, 1-month test windows
train_months = 3
test_months = 1

current = start
while current + relativedelta(months=train_months + test_months) <= end:
    train_start = current
    train_end = current + relativedelta(months=train_months)
    test_start = train_end
    test_end = test_start + relativedelta(months=test_months)

    print(f"Train: {train_start:%Y-%m-%d} to {train_end:%Y-%m-%d}")
    print(f"Test:  {test_start:%Y-%m-%d} to {test_end:%Y-%m-%d}")

    # 1. Optimize on train period
    # 2. Test on test period
    # 3. Record results

    current = test_start
```

### Monte Carlo Simulation

Assess strategy robustness:

```python
# scripts/monte_carlo.py
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Load trades
trades = pd.read_csv('reports/trades.csv')
returns = trades['pnl'].values

# Run 10,000 simulations
n_sims = 10000
n_trades = len(returns)
final_values = []

for _ in range(n_sims):
    # Resample trades with replacement
    sim_returns = np.random.choice(returns, size=n_trades, replace=True)
    final_value = 100000 + sim_returns.sum()
    final_values.append(final_value)

# Plot distribution
plt.hist(final_values, bins=50)
plt.xlabel('Final Portfolio Value (₹)')
plt.ylabel('Frequency')
plt.title('Monte Carlo Simulation (10,000 runs)')
plt.savefig('reports/monte_carlo.png')

# Statistics
print(f"Mean: ₹{np.mean(final_values):,.0f}")
print(f"Median: ₹{np.median(final_values):,.0f}")
print(f"5th Percentile: ₹{np.percentile(final_values, 5):,.0f}")
print(f"95th Percentile: ₹{np.percentile(final_values, 95):,.0f}")
```

---

## FAQs

**Q: How accurate is this backtest compared to live trading?**
A: With STRICT mode, very accurate (assumes limit orders at exact prices). NORMAL mode is conservative (assumes market orders with slippage).

**Q: Can I use this for Sensex or Bank Nifty?**
A: Yes! Just replace data files and update `option_lot_size` in config (15 for Bank Nifty, 10 for Sensex).

**Q: What capital do I need to trade this live?**
A: Minimum ₹50,000. Recommended ₹1,00,000+ for proper risk management.

**Q: How often should I update the strategy?**
A: Review monthly. Adjust parameters if market regime changes significantly.

**Q: Can I run this on a Raspberry Pi?**
A: No, requires too much RAM. Use a laptop/desktop with 8GB+ RAM.

**Q: Is this strategy profitable in all market conditions?**
A: No strategy works in all conditions. This works best in trending markets with clear OI patterns. Sideways/choppy markets may underperform.

**Q: How do I connect this to a broker for live trading?**
A: This is a backtesting system only. For live trading, you need to integrate with broker APIs (e.g., Zerodha Kite, IBKR API). That's beyond the scope of this system.

**Q: Can I share this strategy with others?**
A: This is a private strategy implementation. Check with the owner before sharing.

---

## Contributing

This is a private strategy implementation. Modifications should be tracked via git:

```bash
# Track changes
git add .
git commit -m "Modified stop loss parameters"

# View history
git log --oneline

# Revert if needed
git checkout HEAD~1 -- config/strategy_config.yaml
```

---

## License

**Private use only.** Not for distribution.

---

## References

- **Strategy Document:** `Trading Strategy _ Intraday_Momentum_OIUnwinding.pdf`
- **Backtrader Documentation:** https://www.backtrader.com/docu/
- **NSE Options Data:** https://www.nseindia.com/
- **NIFTY Specifications:** https://www.nseindia.com/products-services/indices-nifty50

---

## Contact & Support

For questions about this implementation:
- **Email:** [Your email]
- **GitHub Issues:** [If applicable]
- **Documentation:** Check `docs/` folder first

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2024-01-27 | Initial release |
| 1.1.0 | 2024-12-03 | Added STRICT/NORMAL execution modes |
| 1.2.0 | 2024-12-09 | Enhanced logging and reporting |
| 1.3.0 | 2024-12-11 | Comprehensive README and documentation |

---

## Acknowledgments

- Strategy concept: Manish Sir
- Implementation: Development Team
- Backtrader framework: Daniel Rodriguez (https://github.com/mementum/backtrader)

---

<div align="center">

**Ready to start backtesting?**

```bash
python backtest_runner.py
```

**Need help?** Read `docs/QUICKSTART.md` for a 2-minute setup guide.

**Good luck with your backtesting!** 🚀

</div>
