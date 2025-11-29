# Trade Logging Fix Summary

## Problem
The backtest was executing trades but:
1. Multiple buy orders were being placed for the same position
2. Trades were not being saved to `trades.csv`
3. Debug messages cluttered the output
4. No trade summary was generated on forceful exit (Ctrl+C)

## Solution

### 1. Fixed Multiple Entry Orders
**Problem**: Strategy was placing multiple buy orders before the first one executed.

**Fix**: Added `pending_entry` flag
- Set to `True` when buy order is placed
- Reset to `False` when buy order executes
- Check both `position.size` and `pending_entry` before allowing new entries

**Files Modified**: `strategies/intraday_momentum_oi.py:50, 94, 269-274, 431, 460`

### 2. Immediate Trade Logging to CSV
**Problem**: Trades were stored in memory but not written to file until backtest ended.

**Fix**: Implemented immediate write-to-file on every trade
- CSV file created with headers in `__init__()`
- Each trade appended to CSV immediately after execution in `notify_order()`
- File path: `reports/trades.csv`

**Files Modified**: `strategies/intraday_momentum_oi.py:61-75, 162-169`

### 3. Summary Files on Any Exit
**Problem**: Summary was only printed to console, not saved to file.

**Fix**: Created `save_summary_to_file()` method
- Saves trade summary to `reports/trade_summary.txt` (human-readable)
- Saves trade summary to `reports/trade_summary.json` (machine-readable)
- Called automatically in `stop()` method
- Called on forceful exit (Ctrl+C) via signal handler

**Files Modified**: `strategies/intraday_momentum_oi.py:482-557`

### 4. Signal Handlers for Graceful Shutdown
**Problem**: Ctrl+C or kill would lose all trade data.

**Fix**: Added signal handlers for SIGINT and SIGTERM
- Catches Ctrl+C and kill signals
- Saves summary before exiting
- Ensures no data loss

**Files Modified**: `strategies/intraday_momentum_oi.py:77-85`

### 5. Removed Debug Messages
**Problem**: Output was cluttered with debug messages.

**Fix**: Removed:
- "Is trading time?" messages (every 30 min)
- "DEBUG: next() called" messages (every 5 min)

**Files Modified**: `strategies/intraday_momentum_oi.py:416-420, 453-460`

## Files Generated

The strategy now generates the following files in `reports/`:

1. **`trades.csv`** - All completed trades with columns:
   - entry_time
   - exit_time
   - strike
   - option_type
   - expiry
   - entry_price
   - exit_price
   - size
   - pnl
   - pnl_pct

2. **`trade_summary.txt`** - Human-readable summary:
   - Final Portfolio Value
   - Total Trades
   - Winning/Losing Trades
   - Win Rate
   - Total PnL
   - Average PnL
   - Best/Worst Trade

3. **`trade_summary.json`** - Machine-readable summary (same data as .txt)

4. **`backtest_metrics.json`** - Full backtest metrics (from Reporter)

## Key Features

✅ **Immediate Write**: Trades written to CSV as they complete (no memory-only storage)
✅ **No Data Loss**: Files saved even on forceful exit (Ctrl+C)
✅ **Clean Output**: Removed debug spam, only important logs shown
✅ **Multiple Formats**: Both human-readable (.txt) and machine-readable (.json) summaries
✅ **No Duplicate Entries**: Fixed multiple buy orders for same position

## Testing

To test the changes:

```bash
# Run normal backtest
python backtest_runner.py

# Files will be in reports/:
# - reports/trades.csv
# - reports/trade_summary.txt
# - reports/trade_summary.json

# Test forceful exit:
# 1. Start backtest: python backtest_runner.py
# 2. Press Ctrl+C after a few trades
# 3. Check that files are saved with trades up to that point
```

## Trade Flow

1. **Entry**: Buy order placed → `pending_entry = True`
2. **Execution**: Order fills → Trade info stored → `pending_entry = False`
3. **Exit**: Sell order placed → `pending_exit = True`
4. **Completion**: Exit fills → Calculate P&L → **Write to CSV immediately** → `pending_exit = False`
5. **Backtest End**: Call `stop()` → Save summary files

## Notes

- Trades are logged **immediately** after exit, not at end of backtest
- CSV file is created with headers at strategy initialization
- Signal handlers ensure graceful shutdown on Ctrl+C
- All file I/O happens in strategy, not in Reporter (for immediate writes)
