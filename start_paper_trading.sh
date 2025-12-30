#!/bin/bash

# Paper Trading Launcher
# Starts paper trading with proper logging

echo "=================================="
echo "   PAPER TRADING LAUNCHER"
echo "=================================="
echo ""

# Create necessary directories
mkdir -p paper_trading/logs
mkdir -p paper_trading/state

# Generate log filename with timestamp (matching backtest format)
LOG_FILE="paper_trading/logs/session_log_$(date +%Y%m%d_%H%M%S).txt"

echo "Starting paper trading..."
echo "Broker: Zerodha"
echo "Log file: $LOG_FILE"
echo ""
echo "Press Ctrl+C to stop"
echo "=================================="
echo ""

# Start paper trading with logging
# The -u flag makes Python unbuffered (shows output immediately)
# The 2>&1 redirects stderr to stdout
# tee shows output AND saves to file
python3 -u paper_trading/runner.py --broker zerodha 2>&1 | tee "$LOG_FILE"

echo ""
echo "=================================="
echo "Paper trading stopped"
echo ""
echo "Session log: $LOG_FILE"
echo ""
echo "View files:"
echo "  Session log:  cat $LOG_FILE"
echo "  Trade log:    cat paper_trading/logs/trades_*.csv"
echo "  State (JSON): cat paper_trading/state/trading_state_*.json | jq ."
echo ""
echo "All paper trading files are in: paper_trading/"
echo "  - paper_trading/logs/       (session logs & trade CSVs)"
echo "  - paper_trading/state/      (state JSON files)"
echo "=================================="
