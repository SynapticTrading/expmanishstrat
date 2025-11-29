# How to Run the Backtest

## Quick Start

### Option 1: Run with Automatic Logging (Recommended)
```bash
./run_backtest.sh
```

This will:
- ✅ Create a fresh `reports/trades.csv`
- ✅ Save ALL terminal output to `reports/backtest_log_YYYYMMDD_HHMMSS.txt`
- ✅ Show output on screen AND save to file simultaneously
- ✅ Generate summary files when complete

### Option 2: Run Directly (Manual)
```bash
python backtest_runner.py
```

This will:
- ✅ Create `reports/trades.csv` with immediate trade logging
- ✅ Show output on terminal only (not saved to file)
- ✅ Generate summary files when complete

### Option 3: Run and Save Output Manually
```bash
python backtest_runner.py 2>&1 | tee reports/backtest_log.txt
```

## Files Generated

After running the backtest, you'll find these files in `reports/`:

### 1. `trades.csv` - All Completed Trades
```csv
entry_time,exit_time,strike,option_type,expiry,entry_price,exit_price,size,pnl,pnl_pct
2025-01-01 09:37:00,2025-01-01 14:51:00,23600,PE,2025-01-02,103.4,238.8,1,135.4,130.89
...
```

**Key Feature**: Trades are written IMMEDIATELY after each exit - no data loss!

### 2. `trade_summary.txt` - Human-Readable Summary
```
================================================================================
TRADE SUMMARY
================================================================================
Final Portfolio Value: ₹100,452.30
Total Trades: 15
Winning Trades: 9
Losing Trades: 6
Win Rate: 60.00%
Total PnL: ₹452.30
Average PnL: ₹30.15
Average PnL %: 12.45%
Best Trade: ₹416.50
Worst Trade: ₹-42.90
================================================================================
```

### 3. `trade_summary.json` - Machine-Readable Summary
```json
{
  "final_portfolio_value": 100452.30,
  "total_trades": 15,
  "winning_trades": 9,
  "losing_trades": 6,
  "win_rate": 60.0,
  "total_pnl": 452.30,
  "average_pnl": 30.15,
  "average_pnl_pct": 12.45,
  "best_trade": 416.50,
  "worst_trade": -42.90
}
```

### 4. `backtest_log_YYYYMMDD_HHMMSS.txt` - Complete Terminal Output
Contains everything shown on terminal during the backtest run.

### 5. `backtest_metrics.json` - Detailed Metrics from Reporter
Full backtest analytics including Sharpe ratio, drawdown, etc.

## Data Safety Features

### ✅ Immediate Write
Every trade is written to `trades.csv` as soon as it completes. No waiting for backtest to finish!

### ✅ Ctrl+C Safe
Press Ctrl+C at any time:
- All completed trades are already in `trades.csv`
- Summary files are generated before exit
- Zero data loss!

### ✅ Fresh Start Every Run
When using `run_backtest.sh`:
- Old `trades.csv` is deleted
- New timestamped log file is created
- No confusion between different runs

## Configuration

Edit `config/strategy_config.yaml` to change:
- Date range for backtest
- Entry/exit times
- Stop loss and profit targets
- Position sizing
- Risk management rules

## Viewing Results

```bash
# View all trades
cat reports/trades.csv | column -t -s,

# View summary
cat reports/trade_summary.txt

# View latest log
ls -t reports/backtest_log_*.txt | head -1 | xargs cat

# Count total trades
wc -l reports/trades.csv
# (Subtract 1 for header line)
```

## Troubleshooting

### No trades in trades.csv?
Check:
1. Backtest is still running (it takes time)
2. Date range in config has market data
3. Entry conditions are being met (check log file)

### Log file too large?
The log contains every bar's analysis. This is normal for 1-minute data over a month.

### Want to stop and restart?
Press Ctrl+C - all completed trades are already saved!
Then run `./run_backtest.sh` again for a fresh start.
