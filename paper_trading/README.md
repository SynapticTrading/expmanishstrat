# Paper Trading System

Universal paper trading system with multi-broker support, automatic crash recovery, and clean architecture.

**Status**: ✅ PRODUCTION READY FOR MONDAY TRADING

---

## 🚀 Quick Start

```bash
# Navigate to project
cd /Users/Algo_Trading/manishsir_options

# Start paper trading (auto-detects broker)
python paper_trading/runner.py
```

That's it! System will:
- Auto-detect broker (Zerodha or AngelOne)
- Connect automatically
- Start trading when market opens (9:15 AM)
- Monitor positions every minute
- Save state automatically

---

## 📋 Choose Your Broker

```bash
# Auto-detect (Zerodha if both found)
python paper_trading/runner.py

# Use Zerodha
python paper_trading/runner.py --broker zerodha

# Use AngelOne
python paper_trading/runner.py --broker angelone
```

---

## ✅ Current Setup

**Zerodha** (User: SHM035)
- File: `config/credentials_zerodha.txt`
- Status: ✅ VERIFIED AND READY

**AngelOne** (User: N182640)
- File: `config/credentials_angelone.txt`
- Status: ✅ VERIFIED AND READY

**Verification**: Run `python tests/verify_credentials.py` before trading

---

## 📁 Project Structure

```
paper_trading/
├── runner.py                    # Main entry point
├── README.md                    # This file
├── requirements.txt             # Dependencies
│
├── brokers/                     # Broker implementations
│   ├── base.py                  # Interface
│   ├── zerodha.py               # Zerodha (full)
│   └── angelone.py              # AngelOne (partial)
│
├── core/                        # Trading logic
│   ├── broker.py                # Paper broker (simulated orders)
│   ├── strategy.py              # Trading strategy
│   └── state_manager.py         # State persistence & recovery
│
├── utils/                       # Utilities
│   └── factory.py               # Broker auto-detection
│
├── config/                      # Configuration
│   ├── config.yaml              # Strategy parameters
│   ├── credentials_zerodha.txt  # Zerodha credentials
│   └── credentials_angelone.txt # AngelOne credentials
│
├── tests/                       # Test suite
│   ├── verify_credentials.py   # Verify setup
│   ├── test_zerodha_connection.py
│   └── test_angelone_direct.py
│
├── docs/                        # Complete documentation
│   ├── START_HERE.md            # ⭐ Start here!
│   ├── MONDAY_START_GUIDE.md    # Complete Monday guide
│   ├── SETUP_COMPLETE.txt       # Setup verification
│   ├── ARCHITECTURE.md          # System architecture
│   ├── BROKER_SELECTION_AND_RECOVERY.md
│   ├── ANGELONE_TESTING.md
│   └── [7 more docs]
│
├── state/                       # Auto-created
│   └── trading_state_YYYYMMDD.json
│
├── logs/                        # Auto-created
│   └── trades_YYYYMMDD_HHMMSS.csv
│
└── legacy/                      # Old code (kept for reference)
```

---

## 📚 Documentation

**Getting Started**:
- 📄 **[docs/START_HERE.md](docs/START_HERE.md)** - Quick reference guide (read this first!)
- 📄 **[docs/MONDAY_START_GUIDE.md](docs/MONDAY_START_GUIDE.md)** - Complete guide for Monday trading
- 📄 **[docs/SETUP_COMPLETE.txt](docs/SETUP_COMPLETE.txt)** - Setup verification summary

**Architecture & Features**:
- 📄 **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture details
- 📄 **[docs/DUAL_LOOP_EXPLAINED.md](docs/DUAL_LOOP_EXPLAINED.md)** - Why two loops (5-min + 1-min)
- 📄 **[docs/BROKER_SELECTION_AND_RECOVERY.md](docs/BROKER_SELECTION_AND_RECOVERY.md)** - Broker & crash recovery

**Broker Setup**:
- 📄 **[docs/ANGELONE_TESTING.md](docs/ANGELONE_TESTING.md)** - AngelOne setup and testing
- 📄 **[docs/ZERODHA_SETUP.md](docs/ZERODHA_SETUP.md)** - Zerodha setup guide

**Implementation Details**:
- 📄 **[docs/FIXED_IMPLEMENTATION.md](docs/FIXED_IMPLEMENTATION.md)** - What was fixed (1-min LTP)
- 📄 **[docs/IMPLEMENTATION_COMPLETE.md](docs/IMPLEMENTATION_COMPLETE.md)** - Implementation checklist
- 📄 **[docs/IMPLEMENTATION_SUMMARY.md](docs/IMPLEMENTATION_SUMMARY.md)** - Summary

---

## ✨ Features

### Multi-Broker Support
- ✅ **Zerodha**: Fully implemented with all features
- ✅ **AngelOne**: Partially implemented (core features working)
- ✅ **Auto-detection**: Automatically selects broker from credentials
- ✅ **Easy switching**: Just change credentials file

### Dual-Loop Architecture
- **Loop 1 (Strategy)**: Runs every 5 minutes
  - Fetches 5-min candles
  - Makes entry decisions (OI unwinding + VWAP)
  - Updates strategy state

- **Loop 2 (Exit Monitor)**: Runs every 1 minute
  - Fetches current LTP for positions
  - Checks 4 stop losses
  - Forces EOD exit (2:50-3:00 PM)

### State Persistence & Crash Recovery
- **JSON format**: Human-readable state files
- **IST timestamps**: All times in Indian Standard Time
- **Auto-save**: After every position change and loop iteration
- **Crash recovery**: Auto-detects and prompts to resume
- **Full restoration**: All positions, stops, P&L preserved

---

## 🎯 Trading Strategy

### Entry Conditions
- **OI Unwinding**: Option OI decreasing (covering signal)
- **VWAP Filter**: Price > VWAP
- **Strike**: Based on max OI strike
- **Direction**: CALL or PUT based on OI analysis
- **Limit**: Maximum 1 trade per day

### Exit Conditions (Checked every 1 minute)
1. **25% Stop Loss**: Initial hard stop
2. **VWAP Stop**: 5% below VWAP
3. **OI Stop**: 10% if OI reverses
4. **Trailing Stop**: 10% from peak (after 10% profit reached)
5. **EOD Exit**: Forced exit at 2:50-3:00 PM

### Position Sizing
- **Initial Capital**: ₹100,000 (configurable in config.yaml)
- **Lot Size**: 75 (configurable)
- **Max Positions**: 1 at a time

---

## 📊 Monitoring

### Live Status
System prints status every 5 minutes:
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

### State File
```bash
# View current state
cat state/trading_state_*.json | jq

# Watch live updates (refreshes every 5 seconds)
watch -n 5 'cat state/trading_state_*.json | jq .system_health'
```

### Trade Logs
```bash
# View latest trades
tail -f logs/trades_*.csv

# View all trades today
cat logs/trades_$(date +%Y%m%d)_*.csv
```

---

## 🔄 Crash Recovery

If system crashes or stops, just restart:

```bash
python runner.py
```

You'll see:
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

Press **'y'** to continue where you left off with all data intact!

---

## 🛠️ Installation

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Credentials

**Zerodha**:
```bash
cd config
# credentials_zerodha.txt already configured ✅
```

**AngelOne**:
```bash
cd config
# credentials_angelone.txt already configured ✅
```

### 3. Verify Setup
```bash
python tests/verify_credentials.py
```

Should show: `✓ ALL SYSTEMS READY FOR MONDAY TRADING!`

---

## 🧪 Testing

### Verify Credentials
```bash
python tests/verify_credentials.py
```

### Test Zerodha Connection
```bash
python tests/test_zerodha_connection.py
```

### Test AngelOne Connection
```bash
python tests/test_angelone_direct.py
```

---

## ⚠️ Troubleshooting

### Connection Fails
- Run connection test for your broker (see Testing section)
- Check credentials file format
- Verify TOTP key is correct

### TOTP Error
```bash
# Verify TOTP manually
python3 -c "import pyotp; print(pyotp.TOTP('YOUR_TOTP_KEY').now())"
```

### Market Data Not Coming
- Verify market is open (9:15 AM - 3:30 PM IST, Mon-Fri)
- Check broker connection status
- Restart the system

### State File Corrupted
```bash
# Backup corrupted state
mv state/trading_state_*.json state/backup_*.json

# Start fresh
python runner.py
```

---

## 🎓 Learn More

- **Architecture**: See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **Broker Guide**: See [docs/BROKER_SELECTION_AND_RECOVERY.md](docs/BROKER_SELECTION_AND_RECOVERY.md)
- **Dual-Loop Explained**: See [docs/DUAL_LOOP_EXPLAINED.md](docs/DUAL_LOOP_EXPLAINED.md)
- **Complete Docs**: Browse [docs/](docs/) folder

---

## 🚦 Status

- ✅ **Zerodha**: Fully implemented and verified
- ✅ **AngelOne**: Core features working, tested and verified
- ✅ **State Persistence**: Implemented with IST timestamps
- ✅ **Crash Recovery**: Implemented with auto-detection
- ✅ **Clean Architecture**: Modular and well-documented
- ✅ **Production Ready**: All tests passing

---

## 📅 Monday Checklist

Before 9:15 AM:

- [ ] Navigate to project: `cd /Users/Algo_Trading/manishsir_options`
- [ ] Run verification: `python tests/verify_credentials.py` (optional)
- [ ] Start system: `python runner.py`
- [ ] Verify connection successful
- [ ] Wait for market open
- [ ] Monitor first 5-min candle (9:15-9:20)
- [ ] Watch for entry signal

**Stop trading**: Press `Ctrl+C` (system shuts down gracefully)

---

## 🆘 Support

For detailed help, see:
1. **[docs/START_HERE.md](docs/START_HERE.md)** - Quick start
2. **[docs/MONDAY_START_GUIDE.md](docs/MONDAY_START_GUIDE.md)** - Complete Monday guide
3. **[docs/](docs/)** folder - All documentation

---

## 🎉 You're Ready!

Your system is fully configured with:
- ✅ Both Zerodha and AngelOne credentials
- ✅ Automatic broker detection
- ✅ Crash recovery
- ✅ State persistence
- ✅ Clean architecture
- ✅ Complete documentation

**Just run**: `python runner.py`

**Good luck with your Monday trading! 📈🚀**

---

**Last Updated**: 2025-12-26 20:55 IST
**Version**: 1.0
**Status**: Production Ready ✅
