#!/bin/bash

# Create reports directory
mkdir -p reports

# Generate timestamp for this run
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="reports/backtest_log_${TIMESTAMP}.txt"

# Clear old CSV to start fresh
rm -f reports/trades.csv reports/trade_summary.txt reports/trade_summary.json

echo "================================================================================================"
echo "Starting Backtest at $(date)"
echo "Log file: $LOG_FILE"
echo "================================================================================================"
echo ""

# Run backtest with unbuffered output and capture ALL to log file (and still show on terminal)
python -u backtest_runner.py 2>&1 | tee "$LOG_FILE"

echo ""
echo "================================================================================================"
echo "Backtest completed at $(date)"
echo "Log saved to: $LOG_FILE"
echo "Trades saved to: reports/trades.csv"
echo "Summary saved to: reports/trade_summary.txt"
echo "================================================================================================"
