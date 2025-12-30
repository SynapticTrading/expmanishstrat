# Paper Trading - Intraday Momentum OI Strategy

Complete paper trading implementation using **the same strategy logic** as the backtesting system, but with real-time data from **Zerodha Kite Connect API**.

## Quick Start

📖 **[Read the Full Setup Guide - Zerodha](ZERODHA_SETUP.md)** for detailed instructions.

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Credentials Already Configured

Your Zerodha credentials are saved in `credentials.txt` (already configured).

### 3. Test Connection

```bash
python test_zerodha_connection.py
```

### 4. Run Paper Trading (DUAL-LOOP VERSION)

```bash
python dual_loop_runner.py
```

**Important**: Use `dual_loop_runner.py`, not `zerodha_paper_runner.py`!
- ✅ `dual_loop_runner.py` - Correct (2 loops: 5-min entries, 1-min exits)
- ❌ `zerodha_paper_runner.py` - Wrong (single 5-min loop, delayed exits)

## What's Included

### Core Components

- ✅ **paper_strategy.py** - Same strategy logic as backtest
  - OI unwinding detection
  - VWAP-based entry signals
  - 4-layer stop loss system (25% SL, VWAP, OI, Trailing)
  - 1 trade per day, max 2 concurrent positions

- ✅ **paper_broker.py** - Simulated order execution
  - Buy/sell order simulation
  - Position tracking
  - P&L calculation
  - Trade logging to CSV

- ✅ **paper_runner.py** - Main execution script
  - 5-min candle processing
  - Real-time monitoring
  - Graceful shutdown
  - Status updates

- ✅ **data_feed.py** - Real-time data fetching
  - Spot price (Nifty)
  - 5-min candles
  - Options chain (needs implementation)

- ✅ **config.yaml** - Strategy configuration
  - Same parameters as backtest
  - Entry/exit times
  - Stop loss percentages
  - Position sizing

### Supporting Files

- **angelone_connection.py** - AngelOne API wrapper
- **test_connection.py** - API connection test
- **credentials.template.txt** - Credentials template

## Strategy Logic (Same as Backtest)

### Entry (9:30 AM - 2:30 PM)
1. OI must be unwinding (decreasing)
2. Option price must be above VWAP
3. Max 1 trade per day
4. Max 2 concurrent positions

### Exit
1. **Stop Loss (25%)** - Hard stop at 25% loss
2. **VWAP Stop (5%)** - Exit if >5% below VWAP (only in loss)
3. **OI Stop (10%)** - Exit if OI increases >10% (only in loss)
4. **Trailing Stop (10%)** - After 10% profit, trail by 10%
5. **EOD Exit (2:50-3:00 PM)** - Force close all positions

## What Needs Completion

### Data Feed Implementation

The `data_feed.py` module has placeholders for:

1. **Options Chain Fetching** - `get_options_chain()` function
   - Need to map strikes/expiries to AngelOne instrument tokens
   - Fetch LTP and OI for each option
   - Build DataFrame with required columns

See comments in `data_feed.py` for implementation details.

## Output

### Real-time Status
```
STATUS UPDATE
--------------------------------------------------------------------------------
Date: 2024-12-26
Daily Direction: CALL @ 23000
Trade Taken Today: True
Open Positions: 1

Statistics:
  Total Trades: 1
  Win Rate: 100.0%
  Total P&L: ₹1,500.00
  Current Cash: ₹90,250.00
  ROI: +2.50%
```

### Trade Log (CSV)
```csv
entry_time,exit_time,strike,option_type,expiry,entry_price,exit_price,size,pnl,pnl_pct,exit_reason
2024-12-26 09:30:00,2024-12-26 10:15:00,23000,CALL,2024-12-26,150.00,170.00,75,1500.00,13.33,Trailing Stop (10%)
```

## Important Notes

- ⚠️ No real money used (paper trading only)
- ⚠️ Same strategy logic as backtest (minimal changes)
- ⚠️ All trades logged to `logs/trades_YYYYMMDD_HHMMSS.csv`
- ⚠️ Never commit `credentials.txt` to git!

## Documentation

- 📖 [SETUP_GUIDE.md](SETUP_GUIDE.md) - Complete setup instructions
- 📖 [AngelOne API Docs](https://smartapi.angelbroking.com/docs) - Official API documentation

## Troubleshooting

See [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed troubleshooting steps.

Quick checks:
- ✓ API credentials correct?
- ✓ TOTP token valid?
- ✓ Market hours (9:15 AM - 3:30 PM, Mon-Fri)?
- ✓ Network connection stable?
