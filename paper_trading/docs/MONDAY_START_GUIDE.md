# Monday Trading - Quick Start Guide

**Date**: Monday, December 30, 2025 (or next trading day)
**Status**: ✅ ALL CREDENTIALS VERIFIED AND READY

---

## Pre-Flight Checklist

✅ **Zerodha Credentials**: Configured and verified
✅ **AngelOne Credentials**: Configured and verified
✅ **Broker Auto-Detection**: Working
✅ **System Architecture**: Clean and organized
✅ **State Persistence**: Implemented
✅ **Crash Recovery**: Implemented

---

## Morning Routine (Before 9:15 AM)

### 1. Navigate to Project Directory
```bash
cd /Users/Algo_Trading/manishsir_options
```

### 2. Activate Virtual Environment (if using one)
```bash
# If you have a venv
source venv/bin/activate
```

### 3. Verify Credentials (Optional but Recommended)
```bash
python paper_trading/tests/verify_credentials.py
```

**Expected Output:**
```
✓ ALL SYSTEMS READY FOR MONDAY TRADING!
```

---

## Starting Paper Trading

### Option 1: Auto-Detect Broker (Recommended)
```bash
python paper_trading/runner.py
```

System will automatically:
1. Look for credentials files
2. Detect which broker (Zerodha found first, then AngelOne)
3. Connect and start trading

### Option 2: Explicitly Choose Zerodha
```bash
python paper_trading/runner.py --broker zerodha
```

### Option 3: Explicitly Choose AngelOne
```bash
python paper_trading/runner.py --broker angelone
```

---

## What to Expect on Startup

### Successful Startup

```
================================================================================
UNIVERSAL PAPER TRADING SYSTEM
================================================================================

Loading configuration...
Loading credentials from: paper_trading/config/credentials_zerodha.txt
Creating broker instance...
✓ Broker: Zerodha

[2025-12-30 09:00:00+05:30] Checking for previous session...
[2025-12-30 09:00:00+05:30] No previous state found - starting fresh

[2025-12-30 09:00:01+05:30] Connecting to Zerodha...
[2025-12-30 09:00:02+05:30] ✓ Connected to Zerodha

[2025-12-30 09:00:03+05:30] Initializing new session...
[2025-12-30 09:00:03+05:30] Session initialized: SESSION_20251230_0900

================================================================================
[2025-12-30 09:00:05+05:30] Starting DUAL-LOOP paper trading...
  Broker: Zerodha
  Loop 1: Strategy Loop - Every 5 minutes (Entry decisions)
  Loop 2: Exit Monitor Loop - Every 1 minute (LTP-based exits)
================================================================================
```

### If Market is Closed

```
[2025-12-30 08:00:00+05:30] Market closed, waiting...
```

System will wait and automatically start when market opens at 9:15 AM.

---

## Trading Day Timeline

### 9:15 AM - Market Opens
- System starts dual-loop trading
- Strategy loop checks 5-min candles
- Exit monitor checks LTP every 1 minute

### 9:20 AM - First Strategy Check
- Fetches 5-min candle (9:15-9:20)
- Analyzes OI + VWAP
- Makes entry decision if conditions met

### Throughout the Day
- **Every 5 minutes**: Strategy loop runs (entry decisions)
- **Every 1 minute**: Exit monitor runs (stop loss checks)
- **Continuous**: State saved to JSON after every change

### 2:50 PM - EOD Window
- System checks for EOD exit window
- Forces exit of all positions by 3:00 PM
- Cannot enter new positions after 2:50 PM

### 3:00 PM - Market Closes
- System stops trading loops
- Final state saved
- Statistics printed
- Clean shutdown

---

## Monitoring During the Day

### View Current Status

The system prints status updates every 5 minutes:

```
--------------------------------------------------------------------------------
STATUS UPDATE
--------------------------------------------------------------------------------
Date: 2025-12-30
Broker: Zerodha
Daily Direction: CALL @ 23000
Open Positions: 1
Total P&L: ₹+850.00
ROI: +0.85%
--------------------------------------------------------------------------------
```

### Check State File

```bash
# View current state
cat paper_trading/state/trading_state_20251230.json | jq

# Watch live updates (refreshes every 5 seconds)
watch -n 5 'cat paper_trading/state/trading_state_*.json | jq .system_health'
```

### Check Trade Logs

```bash
# View latest trades
tail -f paper_trading/logs/trades_20251230_*.csv

# View all trades today
cat paper_trading/logs/trades_20251230_*.csv
```

---

## Common Commands

### Stop Trading
```bash
# Press Ctrl+C in the terminal
# System will shutdown gracefully and save state
```

### Resume After Crash

If system crashes or you stop it:

```bash
# Just run the same command again
python paper_trading/runner.py
```

System will:
1. Detect previous state
2. Show crash recovery info:
   ```
   ================================================================================
   CRASH RECOVERY DETECTED
   ================================================================================
   Last Activity: 2025-12-30T11:54:00.000+05:30
   Downtime: ~141 minutes
   Active Positions: 1
   Daily P&L: ₹+850.00
   ================================================================================

   Resume from crash? (y/n):
   ```
3. Ask if you want to resume
4. If you choose 'y', resume where it left off

### Switch Brokers Mid-Day

```bash
# Stop current broker (Ctrl+C)
# Start with different broker
python paper_trading/runner.py --broker angelone
```

**Note**: Each broker maintains separate state. Switching means starting fresh with the new broker.

---

## Troubleshooting

### Connection Fails

**Zerodha:**
```bash
# Test connection
python paper_trading/tests/test_zerodha_connection.py
```

**AngelOne:**
```bash
# Test connection
python paper_trading/tests/test_angelone_direct.py
```

### TOTP Error

If you get "Invalid TOTP" error:

1. Check system time is correct:
   ```bash
   date
   ```

2. Verify TOTP manually:
   ```bash
   python3 -c "import pyotp; print(pyotp.TOTP('YOUR_TOTP_KEY').now())"
   ```

3. Check credentials file has correct TOTP key

### Market Data Not Coming

1. Verify market is open (9:15 AM - 3:30 PM, Mon-Fri)
2. Check broker connection status
3. Restart the system

### State File Corrupted

```bash
# Backup corrupted state
mv paper_trading/state/trading_state_20251230.json paper_trading/state/backup_20251230.json

# Start fresh
python paper_trading/runner.py
```

---

## Your Configured Credentials

### Zerodha
- **File**: `paper_trading/config/credentials_zerodha.txt`
- **User ID**: SHM035
- **API Key**: 8uns...aovi ✅
- **Status**: READY

### AngelOne
- **File**: `paper_trading/config/credentials_angelone.txt`
- **Username**: N182640
- **API Key**: GuUL...p2XA ✅
- **Status**: READY

---

## Trading Strategy Reminder

### Entry Conditions
- **OI Unwinding**: Option OI decreasing (covering signal)
- **VWAP Filter**: Price > VWAP
- **Strike**: Based on max OI strike
- **Direction**: CALL or PUT based on OI analysis
- **Limit**: Max 1 trade per day

### Exit Conditions (Checked every 1 minute)
1. **25% Stop Loss**: Initial hard stop
2. **VWAP Stop**: 5% below VWAP
3. **OI Stop**: 10% if OI reverses
4. **Trailing Stop**: 10% from peak after 10% profit
5. **EOD Exit**: Forced exit at 2:50-3:00 PM

### Position Sizing
- **Initial Capital**: ₹100,000 (configurable)
- **Lot Size**: 75 (configurable)
- **Max Positions**: 1 at a time

---

## End of Day Checklist

### Before Closing (After 3:00 PM)

1. **Verify all positions closed**:
   ```bash
   cat paper_trading/state/trading_state_*.json | jq .active_positions
   ```
   Should show: `{}`

2. **Check daily stats**:
   ```bash
   cat paper_trading/state/trading_state_*.json | jq .daily_stats
   ```

3. **Review trade log**:
   ```bash
   cat paper_trading/logs/trades_20251230_*.csv
   ```

4. **Backup important files** (optional):
   ```bash
   cp paper_trading/state/trading_state_20251230.json ~/backups/
   cp paper_trading/logs/trades_20251230_*.csv ~/backups/
   ```

### System Shutdown

System automatically shuts down after market close. If still running:

```bash
# Press Ctrl+C
# System will shutdown gracefully
```

---

## Configuration Files Reference

### Strategy Config
**File**: `paper_trading/config/config.yaml`

Key settings:
- Initial capital
- Lot size
- Stop loss percentages
- VWAP parameters
- Market hours

**To modify**: Edit the YAML file before starting

### Zerodha Credentials
**File**: `paper_trading/config/credentials_zerodha.txt`

**Format**:
```
api_key = YOUR_KEY
api_secret = YOUR_SECRET
user_id = YOUR_ID
user_password = YOUR_PASSWORD
totp_key = YOUR_TOTP_KEY
```

### AngelOne Credentials
**File**: `paper_trading/config/credentials_angelone.txt`

**Format**:
```
api_key = YOUR_KEY
username = YOUR_CLIENT_CODE
password = YOUR_MPIN
totp_token = YOUR_TOTP_TOKEN
```

---

## Emergency Procedures

### System Crashes During Trade

**Don't panic!** State is saved every minute.

1. **Restart immediately**:
   ```bash
   python paper_trading/runner.py
   ```

2. **Review recovery info** when prompted

3. **Choose to resume** (press 'y')

4. **System continues** from last saved state

### Power Outage

Same as crash - just restart when power returns.

**State preserved**:
- All open positions
- Entry prices and times
- Stop losses
- Daily P&L
- VWAP tracking

### Internet Connection Lost

System will attempt to reconnect. If prolonged:

1. **Stop system** (Ctrl+C)
2. **Wait for connection** to restore
3. **Restart system**
4. **Resume from recovery**

---

## Performance Tracking

### During the Day

System prints status every 5 minutes with:
- Current positions
- Today's P&L
- ROI
- Daily direction and strike

### End of Day

Final statistics printed:
```
Final Statistics:
  Total Trades: 1
  Win Rate: 100.0%
  Total P&L: ₹+1,250.00
  ROI: +1.25%
```

### Historical Analysis

Trade logs in CSV format for analysis:
- Entry/exit times
- Entry/exit prices
- P&L per trade
- Exit reasons
- Duration

---

## Monday Morning Checklist

Before 9:15 AM:

- [ ] Navigate to project directory
- [ ] Activate virtual environment (if applicable)
- [ ] Run credential verification (optional)
- [ ] Choose broker (Zerodha/AngelOne/Auto)
- [ ] Start runner.py
- [ ] Verify connection successful
- [ ] Wait for market open
- [ ] Monitor first 5-min candle (9:15-9:20)
- [ ] Watch for entry signal

---

## Quick Commands Cheat Sheet

```bash
# Start with auto-detection
python paper_trading/runner.py

# Start with Zerodha
python paper_trading/runner.py --broker zerodha

# Start with AngelOne
python paper_trading/runner.py --broker angelone

# Verify credentials
python paper_trading/tests/verify_credentials.py

# Test Zerodha connection
python paper_trading/tests/test_zerodha_connection.py

# Test AngelOne connection
python paper_trading/tests/test_angelone_direct.py

# View state
cat paper_trading/state/trading_state_*.json | jq

# View trades
cat paper_trading/logs/trades_*.csv

# Stop (gracefully)
Ctrl+C
```

---

## Support

### Documentation

Complete docs in `paper_trading/docs/`:
- `BROKER_SELECTION_AND_RECOVERY.md` - Broker guide
- `DUAL_LOOP_EXPLAINED.md` - Architecture explanation
- `ANGELONE_TESTING.md` - AngelOne setup
- `ARCHITECTURE.md` - System architecture
- `README.md` - Complete usage guide

### Files Structure

```
paper_trading/
├── runner.py                    # Main entry point
├── config/                      # Credentials & config
├── brokers/                     # Broker implementations
├── core/                        # Trading logic
├── state/                       # State persistence
├── logs/                        # Trade logs
├── tests/                       # Test files
└── docs/                        # Documentation
```

---

## Final Notes

✅ **You're all set for Monday!**

Your system is:
- Fully configured with both Zerodha and AngelOne credentials
- Tested and verified
- Ready for live paper trading
- Protected with crash recovery
- Equipped with state persistence

**Just run**: `python paper_trading/runner.py`

**Good luck with your trading! 🚀📈**

---

**Last Updated**: 2025-12-26
**Status**: ✅ PRODUCTION READY
**Next Trading Day**: Monday, December 30, 2025
