# Paper Trading Setup Guide

This guide will help you set up and run the paper trading system for the Intraday Momentum OI strategy.

## Overview

The paper trading system uses the **exact same strategy logic** as the backtesting system, but with real-time data from AngelOne. It simulates order execution without using real money, allowing you to:

1. Validate the strategy in live market conditions
2. Test data feed integration
3. Monitor real-time performance
4. Build confidence before going live

## File Structure

```
paper_trading/
├── config.yaml                    # Strategy configuration (same params as backtest)
├── credentials.template.txt       # Template for API credentials
├── credentials.txt               # Your actual credentials (DO NOT COMMIT!)
│
├── paper_broker.py               # Simulates order execution
├── paper_strategy.py             # Strategy logic (same as backtest)
├── paper_runner.py               # Main execution script
├── data_feed.py                  # Real-time data fetching
│
├── angelone_connection.py        # AngelOne API wrapper
├── test_connection.py            # Test API connection
│
└── logs/                         # Trade logs and outputs
    └── trades_YYYYMMDD_HHMMSS.csv
```

## Setup Steps

### 1. Install Dependencies

```bash
cd paper_trading
pip install -r requirements.txt
```

### 2. Configure API Credentials

#### Option A: Using credentials file (Recommended)

1. Copy the template:
   ```bash
   cp credentials.template.txt credentials.txt
   ```

2. Edit `credentials.txt` with your AngelOne credentials:
   ```
   api_key = your_api_key
   username = your_client_code
   password = your_mpin
   totp_token = your_totp_token
   ```

3. **IMPORTANT**: Never commit `credentials.txt` to git!

#### Option B: Using environment variables

Set environment variables:
```bash
export ANGELONE_API_KEY="your_api_key"
export ANGELONE_USERNAME="your_client_code"
export ANGELONE_PASSWORD="your_mpin"
export ANGELONE_TOTP_TOKEN="your_totp_token"
```

### 3. Test API Connection

Before running paper trading, verify your API connection works:

```bash
python test_connection.py
```

Expected output:
```
✓ TEST PASSED: Connection successful
✓ TEST PASSED: Profile retrieved successfully
✓ TEST PASSED: Retrieved candle data points
🎉 ALL CRITICAL TESTS PASSED!
```

### 4. Review Configuration

Check `config.yaml` and verify all parameters match your backtest config:

```yaml
entry:
  start_time: "09:30"
  end_time: "14:30"

exit:
  initial_stop_loss_pct: 0.25  # 25%
  trailing_stop_pct: 0.10      # 10%
  vwap_stop_pct: 0.05          # 5%
  oi_increase_stop_pct: 0.10   # 10%

position_sizing:
  initial_capital: 100000      # ₹1 lakh

risk_management:
  max_positions: 2
```

## Running Paper Trading

### Basic Usage

```bash
python paper_runner.py
```

This will:
1. Connect to AngelOne API
2. Wait for market open (9:15 AM)
3. Process 5-min candles until market close (3:30 PM)
4. Log all trades to `logs/trades_YYYYMMDD_HHMMSS.csv`

### Expected Output

```
================================================================================
PAPER TRADING - Intraday Momentum OI Strategy
================================================================================

[2024-12-26 09:10:00] Connecting to AngelOne...
[2024-12-26 09:10:01] ✓ Connected successfully
[2024-12-26 09:10:01] Initializing components...
[2024-12-26 09:10:01] ✓ All components initialized

[2024-12-26 09:15:00] Market is open, starting...

================================================================================
[2024-12-26 09:15:00] NEW TRADING DAY: 2024-12-26
================================================================================
[2024-12-26 09:15:00] Daily Direction Determined:
  Direction: CALL
  Strike: 23000
  Expiry: 2024-12-26

[2024-12-26 09:30:00] Entry Check:
  Strike: 23000 CALL
  Price: ₹150.00, VWAP: ₹145.00
  OI: 5,000,000, Change: -5.23%
  Unwinding: True, Price>VWAP: True

[2024-12-26 09:30:00] ✓ ENTRY SIGNAL!
[2024-12-26 09:30:00] ✓ BUY ORDER EXECUTED
  Strike: 23000 CALL
  Entry Price: ₹150.00
  Size: 75
  Cost: ₹11,250.00
  Remaining Cash: ₹88,750.00

...
```

## Strategy Logic (Same as Backtest)

### Entry Conditions (9:30 AM - 2:30 PM)

1. **OI Unwinding**: OI must be decreasing (short covering/long unwinding)
2. **Price > VWAP**: Option price must be above VWAP
3. **Max 1 trade per day**
4. **Max 2 concurrent positions**

### Exit Conditions

1. **Stop Loss (25%)**: Exit if price drops 25% from entry
2. **VWAP Stop (5%)**: Exit if price is >5% below VWAP (only in loss)
3. **OI Stop (10%)**: Exit if OI increases >10% from entry (only in loss)
4. **Trailing Stop (10%)**: After 10% profit, trail by 10%
5. **EOD Exit (2:50-3:00 PM)**: Force close all positions

## Monitoring

### Real-time Status

The script prints status updates every 5 minutes:

```
--------------------------------------------------------------------------------
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
--------------------------------------------------------------------------------
```

### Trade Log

All trades are logged to CSV:

```csv
entry_time,exit_time,strike,option_type,expiry,entry_price,exit_price,size,pnl,pnl_pct,vwap_at_entry,vwap_at_exit,oi_at_entry,oi_change_at_entry,oi_at_exit,exit_reason
2024-12-26 09:30:00,2024-12-26 10:15:00,23000,CALL,2024-12-26,150.00,170.00,75,1500.00,13.33,145.00,165.00,5000000,-5.23,4800000,Trailing Stop (10%)
```

## Important Notes

### API Rate Limits

- **Orders**: 10 requests/second
- **Market Data**: No strict limit via WebSocket
- **Historical Data**: 3 requests/second

For this strategy (~210 API calls/day), you're well within limits.

### Data Feed Implementation

**Current Status**: The data feed module (`data_feed.py`) has placeholder functions that need to be completed:

1. `get_options_chain()` - Fetch real options chain from AngelOne
2. Instrument token mapping - Map strikes/expiries to AngelOne tokens

**To Complete**:
1. Get instrument list from AngelOne (NIFTY options)
2. Filter for current/next expiry
3. Fetch LTP and OI for each strike
4. Build DataFrame with required columns

See `data_feed.py` for implementation details.

### Differences from Backtest

| Aspect | Backtest | Paper Trading |
|--------|----------|---------------|
| Data Source | CSV files | AngelOne API (real-time) |
| Execution | Backtrader engine | Custom loop (5-min candles) |
| Orders | Simulated (instant) | Simulated (instant, no broker) |
| Strategy Logic | ✓ Same | ✓ Same |
| Entry/Exit Rules | ✓ Same | ✓ Same |
| Stop Losses | ✓ Same | ✓ Same |

## Troubleshooting

### Connection Failed

- Verify API credentials in `credentials.txt`
- Check TOTP token is valid
- Ensure API access is enabled in AngelOne account
- Check network connection

### No Options Data

- Verify `get_options_chain()` is properly implemented
- Check expiry dates are valid (current/next week)
- Ensure strikes are calculated correctly around spot price

### Market Closed

- Script automatically waits for market open (9:15 AM)
- Exits when market closes (3:30 PM)
- Only runs on weekdays (Mon-Fri)

### Missing Candles

- AngelOne has historical data limits
- Use recent dates for testing
- Check candle interval is set to FIVE_MINUTE

## Next Steps

1. **Complete Data Feed**: Implement `get_options_chain()` in `data_feed.py`
2. **Test During Market Hours**: Run for 1-2 days to validate
3. **Compare with Backtest**: Check if results align with backtest expectations
4. **Monitor Performance**: Track win rate, P&L, and exit reasons
5. **Go Live**: After successful paper trading, consider live trading with minimal capital

## Safety Checks

- ✓ No real money used (paper trading only)
- ✓ All trades logged to CSV
- ✓ Same strategy logic as backtest
- ✓ Graceful shutdown on Ctrl+C
- ✓ API credentials never committed to git

## Support

For issues or questions:
1. Check AngelOne API documentation: https://smartapi.angelbroking.com/docs
2. Review backtest strategy: `strategies/intraday_momentum_oi.py`
3. Check logs in `paper_trading/logs/`

## Disclaimer

Paper trading is for testing only. Past performance (backtest or paper trading) does not guarantee future results. Always start with minimal capital when going live.
