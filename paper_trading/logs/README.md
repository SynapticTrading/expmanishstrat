# Paper Trading Logs

This folder contains all paper trading logs and reports.

---

## File Types

### 1. Session Logs (`session_log_*.txt`)
Complete session output including:
- Connection status
- Strategy decisions
- Entry/exit signals
- LTP monitoring
- System health

**Example:** `session_log_20251229_143000.txt`

**View:**
```bash
cat paper_trading/logs/session_log_20251229_143000.txt
```

---

### 2. Trade Logs (`trades_*.csv`)
CSV file with all executed trades containing:
- Entry/exit times
- Strike & option type
- Entry/exit prices
- P&L
- Exit reason
- VWAP & OI data

**Example:** `trades_20251229_143000.csv`

**View:**
```bash
cat paper_trading/logs/trades_20251229_143000.csv
column -t -s, paper_trading/logs/trades_20251229_143000.csv  # Pretty format
```

---

## Folder Structure

```
paper_trading/
├── logs/                          ← All logs here
│   ├── session_log_*.txt         ← Session output logs
│   ├── trades_*.csv              ← Trade CSV files
│   └── README.md                 ← This file
├── state/                        ← State persistence
│   └── trading_state_*.json     ← State snapshots
└── config/                       ← Configuration
    ├── config.yaml              ← Strategy config
    └── credentials_zerodha.txt  ← API credentials
```

---

## Log Rotation

Logs are **NOT** automatically deleted. Each session creates a new timestamped file.

**Cleanup old logs:**
```bash
# Delete logs older than 7 days
find paper_trading/logs -name "*.txt" -mtime +7 -delete
find paper_trading/logs -name "*.csv" -mtime +7 -delete
```

**Archive logs:**
```bash
# Archive logs by month
mkdir -p paper_trading/logs/archive/2025-12
mv paper_trading/logs/*20251229*.* paper_trading/logs/archive/2025-12/
```

---

## Quick Commands

**View latest session log:**
```bash
ls -t paper_trading/logs/session_log_*.txt | head -1 | xargs cat
```

**View latest trades:**
```bash
ls -t paper_trading/logs/trades_*.csv | head -1 | xargs cat
```

**Count total trades today:**
```bash
grep -v "entry_time" paper_trading/logs/trades_$(date +%Y%m%d)_*.csv 2>/dev/null | wc -l
```

**Show all P&L today:**
```bash
awk -F',' 'NR>1 {sum+=$9} END {print "Total P&L: ₹"sum}' paper_trading/logs/trades_$(date +%Y%m%d)_*.csv 2>/dev/null
```

---

**Last Updated:** 2025-12-29
