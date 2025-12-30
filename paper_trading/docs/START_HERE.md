# 🚀 START HERE - Paper Trading System

**Status**: ✅ READY FOR MONDAY TRADING

---

## Quick Start (30 seconds)

```bash
# 1. Go to project directory
cd /Users/Algo_Trading/manishsir_options

# 2. Start paper trading (auto-detects broker)
python paper_trading/runner.py
```

**That's it!** System will:
- Auto-detect broker from credentials (Zerodha or AngelOne)
- Connect automatically
- Start trading when market opens (9:15 AM)
- Monitor positions every minute
- Save state automatically

---

## Your Setup Summary

### ✅ Credentials Configured

**Zerodha** (User: SHM035)
- File: `config/credentials_zerodha.txt`
- Status: ✅ VERIFIED AND READY

**AngelOne** (User: N182640)
- File: `config/credentials_angelone.txt`
- Status: ✅ VERIFIED AND READY

### ✅ System Features

- **Multi-Broker**: Switch between Zerodha and AngelOne anytime
- **Auto-Detection**: Automatically selects broker from credentials
- **Crash Recovery**: Resume from any interruption
- **State Persistence**: All data saved every minute
- **Dual-Loop**: 5-min strategy + 1-min exit monitoring
- **IST Timezone**: All timestamps in Indian Standard Time

---

## Choose Your Broker

### Option 1: Auto-Detect (Easiest)
```bash
python paper_trading/runner.py
```
Uses Zerodha if found, otherwise AngelOne.

### Option 2: Zerodha
```bash
python paper_trading/runner.py --broker zerodha
```

### Option 3: AngelOne
```bash
python paper_trading/runner.py --broker angelone
```

---

## Trading Day Flow

**Before 9:15 AM**: System waits for market open
**9:15 AM**: Market opens, trading begins
**Throughout Day**: 
- 5-min candles analyzed for entry
- 1-min LTP checks for exits
**2:50 PM**: EOD window, no new entries
**3:00 PM**: All positions force-closed, system stops

---

## Monitor Your Trades

### Live Status
System prints status every 5 minutes:
```
STATUS UPDATE
Date: 2025-12-30
Broker: Zerodha
Daily Direction: CALL @ 23000
Open Positions: 1
Total P&L: ₹+850.00
ROI: +0.85%
```

### State File
```bash
cat paper_trading/state/trading_state_*.json | jq
```

### Trade Logs
```bash
cat paper_trading/logs/trades_*.csv
```

---

## If System Crashes

**Don't worry!** Just restart:

```bash
python paper_trading/runner.py
```

System will detect the crash and ask:
```
CRASH RECOVERY DETECTED
Last Activity: 11:54:00 AM
Downtime: ~141 minutes
Active Positions: 1
Daily P&L: ₹+850.00

Resume from crash? (y/n):
```

Press **'y'** to continue where you left off.

---

## Important Files

📄 **MONDAY_START_GUIDE.md** - Complete Monday guide with all commands
📄 **README.md** - Full system documentation
📄 **ARCHITECTURE.md** - System architecture details
📄 **docs/** - All documentation

---

## Verify Everything Works

Run this before Monday:

```bash
python paper_trading/tests/verify_credentials.py
```

Should see:
```
✓ ALL SYSTEMS READY FOR MONDAY TRADING!
```

---

## Stop Trading

Press **Ctrl+C** in the terminal.

System will:
- Exit gracefully
- Save final state
- Print statistics
- Close connections

---

## Strategy Summary

**Entry**: OI unwinding + Price > VWAP (max 1 trade/day)
**Exit**: 4 stop losses + EOD force-close
- 25% initial stop
- 5% VWAP stop
- 10% OI reversal stop
- 10% trailing stop (after 10% profit)
- Mandatory 2:50-3:00 PM exit

**Position**: ₹100,000 capital, 75 lot size

---

## Need Help?

1. Read **MONDAY_START_GUIDE.md** for detailed instructions
2. Check **docs/** folder for specific topics
3. Run verification tests in **tests/** folder
4. Review **README.md** for complete documentation

---

## You're All Set! 🎉

Everything is configured and tested.

**On Monday, just run**:
```bash
python paper_trading/runner.py
```

**Good luck! 📈**

---

**Last Updated**: 2025-12-26 20:52 IST
**Status**: Production Ready ✅
