# Broker Selection & Crash Recovery Guide

Complete guide for using the universal paper trading system with multiple brokers and automatic crash recovery.

---

## Table of Contents

1. [Broker Support](#broker-support)
2. [Setup Instructions](#setup-instructions)
3. [Running Paper Trading](#running-paper-trading)
4. [Crash Recovery](#crash-recovery)
5. [File Structure](#file-structure)

---

## Broker Support

The system now supports **multiple brokers** with the same strategy logic:

### Supported Brokers

| Broker | Status | Features |
|--------|--------|----------|
| **Zerodha** | ✅ Fully Implemented | All features working |
| **AngelOne** | ✅ Partially Implemented | Core features, needs options chain completion |

### Broker Selection

The system automatically detects which broker to use based on:
1. Command line argument `--broker`
2. Credentials file format
3. Available credentials files

---

## Setup Instructions

### 1. Choose Your Broker

#### Option A: Zerodha (Recommended)

**Create credentials file**:
```bash
cp credentials_zerodha.txt.template credentials_zerodha.txt
```

**Edit with your Zerodha credentials**:
```
api_key = YOUR_API_KEY
api_secret = YOUR_API_SECRET
user_id = YOUR_USER_ID
user_password = YOUR_PASSWORD
totp_key = YOUR_TOTP_KEY
```

#### Option B: AngelOne

**Create credentials file**:
```bash
cp credentials_angelone.template.txt credentials_angelone.txt
```

**Edit with your AngelOne credentials**:
```
api_key = YOUR_API_KEY
username = YOUR_CLIENT_CODE
password = YOUR_MPIN
totp_token = YOUR_TOTP_TOKEN
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Test Connection

**For Zerodha**:
```bash
python test_zerodha_connection.py
```

**For AngelOne**:
```bash
python test_connection.py  # (if you have AngelOne implementation)
```

---

## Running Paper Trading

### Basic Usage

The universal runner automatically detects your broker:

```bash
python paper_trader.py
```

This will:
1. Look for credentials files (Zerodha first, then AngelOne)
2. Auto-detect broker type from credentials
3. Connect and start trading

### Specify Broker Explicitly

```bash
# Use Zerodha
python paper_trader.py --broker zerodha

# Use AngelOne
python paper_trader.py --broker angelone
```

### Custom Paths

```bash
python paper_trader.py \
    --broker zerodha \
    --credentials paper_trading/credentials_zerodha.txt \
    --config paper_trading/config.yaml
```

### Expected Output

```
================================================================================
UNIVERSAL PAPER TRADING SYSTEM
================================================================================

Loading configuration...
Loading credentials from: paper_trading/credentials_zerodha.txt
Creating broker instance...
✓ Broker: Zerodha

[2025-12-26 20:30:00+05:30] Checking for previous session...
[2025-12-26 20:30:00+05:30] No previous state found - starting fresh

[2025-12-26 20:30:01+05:30] Connecting to Zerodha...
[2025-12-26 20:30:02+05:30] ✓ Connected to Zerodha

[2025-12-26 20:30:03+05:30] Initializing new session...
[2025-12-26 20:30:03+05:30] Session initialized: SESSION_20251226_2030

================================================================================
[2025-12-26 20:30:05+05:30] Starting DUAL-LOOP paper trading...
  Broker: Zerodha
  Loop 1: Strategy Loop - Every 5 minutes (Entry decisions)
  Loop 2: Exit Monitor Loop - Every 1 minute (LTP-based exits)
================================================================================
```

---

## Crash Recovery

### How It Works

The system saves state to JSON file every:
- Position entry/exit (immediate)
- 5-min strategy loop
- 1-min LTP loop

If system crashes, state is preserved with:
- All active positions
- Strategy state (direction, strike, VWAP tracking)
- Daily stats (trades, P&L)
- Portfolio (cash, positions)

### Recovery Scenario

**Scenario**: System crashes at 11:54 AM with 1 active position

#### 1. Crash Happens

```
[11:54:23] Processing position...
[CRASH - Power outage / System error]
```

State file saved at 11:54:00 contains:
- Active position details
- Current P&L
- Strategy state
- VWAP tracking

#### 2. System Restarts (e.g., 2:15 PM)

```bash
python paper_trader.py
```

#### 3. Automatic Recovery Detection

```
================================================================================
CRASH RECOVERY DETECTED
================================================================================
Last Activity: 2025-12-26T11:54:00.000+05:30
Downtime: ~141 minutes
Active Positions: 1
Daily P&L: ₹+850.00
================================================================================

Resume from crash? (y/n):
```

#### 4. User Chooses to Resume

```
Resume from crash? (y/n): y

================================================================================
RESUMING SESSION FROM CRASH
================================================================================
Crash Time: 2025-12-26T11:54:00.000+05:30
Recovery Time: 2025-12-26 14:15:00+05:30
Downtime: 141 minutes
Active Positions: 1

✓ Session resumed successfully
================================================================================

[14:15:01] Resuming from previous session...
[14:15:02] Restoring strategy state...
  Restored direction: CALL
  Restored strike: 23000
[14:15:03] ✓ All components initialized

[14:15:05] Starting DUAL-LOOP paper trading...
  Broker: Zerodha
  MODE: RECOVERY (resumed from crash)
```

#### 5. Normal Operation Continues

System continues where it left off:
- Monitors existing position
- Applies same stop losses
- Continues 1-min LTP checks
- Can take new positions if strategy allows

### Recovery Features

✅ **Preserves**:
- Active positions (entry price, time, quantity)
- Stop losses (initial, trailing, VWAP, OI)
- Peak prices (for trailing stops)
- Daily direction and strike
- VWAP tracking state
- Daily stats (trade count, P&L, win rate)
- Portfolio state (cash, positions value)

✅ **Resumes**:
- Exit monitoring (1-min LTP checks)
- Strategy loop (5-min candles)
- Position tracking
- State persistence

✅ **Handles**:
- Market closed during recovery (waits for open)
- Stale positions (EOD exit if needed)
- Invalid state (starts fresh if corrupted)

### Manual Recovery

If automatic recovery fails, manually load state:

```python
from paper_trading.state_manager import StateManager

# Load state
sm = StateManager()
state = sm.load(date_str="20251226")  # YYYYMMDD

# Check recovery info
recovery_info = sm.get_recovery_info()
print(f"Active positions: {recovery_info['active_positions_count']}")
print(f"Daily P&L: ₹{recovery_info['daily_stats']['total_pnl_today']}")

# Resume session
sm.resume_session()
```

---

## File Structure

### Broker-Specific Files

```
paper_trading/
├── broker_interface.py              # Abstract base class
├── zerodha_broker.py               # Zerodha implementation ✅
├── angelone_broker.py              # AngelOne implementation ⚠️
├── broker_factory.py               # Broker factory (auto-detection)
│
├── credentials_zerodha.txt         # Your Zerodha creds (gitignored)
├── credentials_angelone.txt        # Your AngelOne creds (gitignored)
├── credentials_angelone.template.txt  # Template
│
├── paper_trader.py                 # Universal runner ✅
├── dual_loop_runner.py             # Old Zerodha-specific runner
│
├── state/                          # State persistence
│   └── trading_state_YYYYMMDD.json
│
└── logs/                           # Trade logs
    └── trades_YYYYMMDD_HHMMSS.csv
```

### State File Format

**Location**: `paper_trading/state/trading_state_YYYYMMDD.json`

**Structure**:
```json
{
  "timestamp": "2025-12-26T11:54:00.000+05:30",
  "session_id": "SESSION_20251226_0915",
  "mode": "paper",

  "active_positions": {
    "PAPER_20251226_001": {
      "strike": 23000,
      "option_type": "CALL",
      "entry": { "price": 150.0, "time": "...", "quantity": 75 },
      "stop_losses": { ... },
      "price_tracking": { "peak_price": 178.0, ... },
      "status": "OPEN"
    }
  },

  "strategy_state": {
    "direction": "CALL",
    "trading_strike": 23000,
    "vwap_tracking": { ... }
  },

  "system_health": {
    "last_heartbeat": "2025-12-26T11:54:00.000+05:30",
    "recovered": false,
    "recovery_time": null
  }
}
```

After recovery, `recovered: true` and `recovery_time` are set.

---

## Broker Comparison

### Zerodha

**Pros**:
- ✅ Full implementation
- ✅ Reliable API
- ✅ Options chain available
- ✅ Historical data

**Cons**:
- Must have Zerodha account

**Setup Complexity**: Low

### AngelOne

**Pros**:
- Alternative to Zerodha
- SmartAPI support

**Cons**:
- ⚠️ Options chain needs completion
- ⚠️ Instrument mapping required

**Setup Complexity**: Medium

**Status**: Partially implemented (core features work, options chain needs work)

---

## Command Reference

### Start Paper Trading

```bash
# Auto-detect broker
python paper_trader.py

# Specify Zerodha
python paper_trader.py --broker zerodha

# Specify AngelOne
python paper_trader.py --broker angelone

# Custom credentials
python paper_trader.py --credentials my_creds.txt

# Custom config
python paper_trader.py --config my_config.yaml

# Full custom
python paper_trader.py \
    --broker zerodha \
    --credentials paper_trading/credentials_zerodha.txt \
    --config paper_trading/config.yaml
```

### Check State

```bash
# View current state
cat paper_trading/state/trading_state_$(date +%Y%m%d).json | jq

# Watch live updates
watch -n 5 'cat paper_trading/state/trading_state_*.json | jq .system_health'
```

### View Trade Log

```bash
# Latest trades
cat paper_trading/logs/trades_*.csv | tail -n 10

# All trades today
cat paper_trading/logs/trades_$(date +%Y%m%d)_*.csv
```

---

## Recovery Examples

### Example 1: Crash with Position

**11:30 AM**: Entry at ₹150
**11:54 AM**: System crashes (position at ₹165, up 10%)
**2:15 PM**: System restarts

**Recovery**:
- Loads position (entry ₹150, current ₹165)
- Fetches current LTP (e.g., ₹170)
- Trailing stop activated (10% profit reached)
- Continues monitoring

### Example 2: Crash Before EOD

**2:30 PM**: Position active
**2:45 PM**: System crashes
**2:52 PM**: System restarts (market closes 3:00 PM)

**Recovery**:
- Loads position
- Detects EOD time window (2:50-3:00 PM)
- Forces exit immediately
- Logs trade with EOD exit reason

### Example 3: Crash Overnight

**Yesterday 2:30 PM**: Position exited
**Today 9:00 AM**: System restarts

**Recovery**:
- Loads yesterday's state
- No active positions found
- Starts fresh session for today
- Previous stats preserved in closed_positions

---

## Troubleshooting

### Recovery Not Working

**Problem**: "No previous state found"

**Solutions**:
1. Check state file exists: `ls paper_trading/state/`
2. Verify date: State file is per-day (YYYYMMDD)
3. Check permissions: Ensure writable

### Broker Auto-Detection Fails

**Problem**: "Cannot determine broker type"

**Solutions**:
1. Use `--broker` flag explicitly
2. Check credentials file format
3. Ensure required keys present

### State Corrupted

**Problem**: JSON parsing error

**Solutions**:
1. Backup state file
2. Start fresh session
3. Check disk space/permissions

---

## Summary

✅ **Multi-Broker Support**
- Zerodha (fully implemented)
- AngelOne (partial, works for basic use)
- Auto-detection from credentials

✅ **Crash Recovery**
- Automatic detection on restart
- Preserves all positions and state
- Resumes monitoring immediately
- No data loss

✅ **State Persistence**
- JSON file per trading day
- IST timestamps
- Full audit trail
- Crash-safe writes

✅ **Easy Switching**
- Same command for any broker
- Just swap credentials file
- No code changes needed

**Use**: `python paper_trader.py` for broker-agnostic paper trading with automatic crash recovery!
