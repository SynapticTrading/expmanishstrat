#!/bin/bash

# Detect Python command (prefer venv python over python3)
if command -v python &> /dev/null && python -c "import sys; sys.exit(0 if sys.prefix != sys.base_prefix else 1)" 2>/dev/null; then
    PYTHON_CMD=python
elif command -v python3 &> /dev/null; then
    PYTHON_CMD=python3
else
    echo "Error: Python not found. Please activate your virtual environment or install Python."
    exit 1
fi

echo "Using Python: $PYTHON_CMD ($(which $PYTHON_CMD))"
echo ""

# Create reports directory
mkdir -p reports

# Generate timestamp for this run
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="reports/backtest_log_${TIMESTAMP}.txt"

echo "================================================================================================"
echo "Starting Backtest at $(date)"
echo "Log file: $LOG_FILE"
echo "Trades will be saved to: reports/trades_${TIMESTAMP}.csv"
echo "================================================================================================"
echo ""

# Run backtest with unbuffered output and capture ALL to log file (and still show on terminal)
$PYTHON_CMD -u backtest_runner.py 2>&1 | tee "$LOG_FILE"

echo ""
echo "================================================================================================"
echo "Backtest completed at $(date)"
echo "Log saved to: $LOG_FILE"
echo "Check reports/ folder for all timestamped output files"
echo "================================================================================================"
