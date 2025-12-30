# Issue #6: Python Output Buffering - Logs Not Showing in Real-Time

**Date:** 2025-12-29
**Severity:** Medium
**Status:** ✅ Resolved

---

## Problem

When running the paper trading system, logs were not showing up in real-time:

```bash
$ python3 paper_trading/runner.py --broker zerodha 2>&1 | tee log.txt

/path/to/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports...
  warnings.warn(

# ← NOTHING AFTER THIS! System appears frozen
```

The system was running but no output was visible until it was killed.

---

## Root Cause

**Python buffers stdout by default when piping to another process** (like `tee`).

### Buffering Modes

Python has different output buffering modes:

1. **Line-buffered (default for terminal):**
   - Output appears after each newline (`\n`)
   - Works when running directly: `python3 script.py`

2. **Block-buffered (default when piping):**
   - Output appears only when buffer is full (~4KB)
   - Happens with: `python3 script.py | tee log.txt`
   - Result: No output until buffer fills or program exits

3. **Unbuffered (forced with `-u`):**
   - Output appears immediately
   - Works everywhere

### Why This Happened

```bash
# Direct execution - Works fine (line-buffered)
python3 paper_trading/runner.py --broker zerodha

# Piped to tee - No output (block-buffered)
python3 paper_trading/runner.py --broker zerodha 2>&1 | tee log.txt

# Script using tee - No output (block-buffered)
./start_paper_trading.sh
```

---

## Solution

Add the `-u` flag to make Python unbuffered:

### start_paper_trading.sh (Before)

```bash
#!/bin/bash

LOG_FILE="reports/paper_trading_log_$(date +%Y%m%d_%H%M%S).txt"

# Start paper trading with logging
python3 paper_trading/runner.py --broker zerodha 2>&1 | tee "$LOG_FILE"
```

### start_paper_trading.sh (After)

```bash
#!/bin/bash

LOG_FILE="reports/paper_trading_log_$(date +%Y%m%d_%H%M%S).txt"

# Start paper trading with logging
# The -u flag makes Python unbuffered (shows output immediately)
python3 -u paper_trading/runner.py --broker zerodha 2>&1 | tee "$LOG_FILE"
```

---

## Alternative Solutions

### 1. Set Environment Variable

```bash
PYTHONUNBUFFERED=1 python3 paper_trading/runner.py --broker zerodha 2>&1 | tee log.txt
```

### 2. Flush Manually in Code

```python
import sys

print("Some output")
sys.stdout.flush()  # Force output immediately
```

### 3. Use stdbuf (Linux only)

```bash
stdbuf -oL python3 paper_trading/runner.py --broker zerodha 2>&1 | tee log.txt
```

**We chose the `-u` flag** because it's:
- Simple (one character)
- Cross-platform (works on Mac/Linux/Windows)
- Permanent (fixed in the script)
- No code changes needed

---

## Testing

### Before Fix

```bash
$ ./start_paper_trading.sh

==================================
   PAPER TRADING LAUNCHER
==================================

Starting paper trading...
Broker: Zerodha
Log file: reports/paper_trading_log_20251229_141139.txt

Press Ctrl+C to stop
==================================

/path/to/urllib3/__init__.py:35: NotOpenSSLWarning...
  warnings.warn(

# ← Nothing appears, even though system is running!
```

### After Fix

```bash
$ ./start_paper_trading.sh

==================================
   PAPER TRADING LAUNCHER
==================================

Starting paper trading...
Broker: Zerodha
Log file: reports/paper_trading_log_20251229_141139.txt

Press Ctrl+C to stop
==================================

================================================================================
UNIVERSAL PAPER TRADING SYSTEM
================================================================================

Loading configuration...
Loading credentials from: paper_trading/config/credentials_zerodha.txt
Creating broker instance...
✓ Broker: Zerodha

[2025-12-29 14:12:00] Checking for previous session...
[2025-12-29 14:12:00] No previous state found - starting fresh

[2025-12-29 14:12:00] Connecting to Zerodha...
[2025-12-29 14:12:00] Generated TOTP: 123456
[2025-12-29 14:12:01] ✓ Connection successful!
...
```

Output now appears **immediately as it happens!** ✅

---

## Files Changed

- `start_paper_trading.sh` (line 31)

---

## Impact

- ✅ Real-time log visibility
- ✅ Can monitor system startup
- ✅ Can see connection status immediately
- ✅ Better debugging experience
- ✅ Logs still saved to .txt file

---

## Python Buffering Reference

| Command | Buffering Mode | Output Timing |
|---------|---------------|---------------|
| `python3 script.py` | Line-buffered | After each `\n` |
| `python3 script.py \| tee log` | Block-buffered | After ~4KB |
| `python3 -u script.py \| tee log` | Unbuffered | Immediate |
| `PYTHONUNBUFFERED=1 python3 ...` | Unbuffered | Immediate |
