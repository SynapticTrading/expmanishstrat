# Paper Trading Setup Guide - Zerodha Version

Complete guide to set up and run paper trading with Zerodha Kite Connect API.

## Overview

This paper trading system uses:
- **Zerodha Kite Connect API** for real-time data
- **Same strategy logic** as the backtesting system
- **Paper broker** for simulated order execution (no real money)

## Quick Start

### 1. Install Dependencies

```bash
cd paper_trading
pip install -r requirements.txt
```

Make sure you have:
- `kiteconnect` - Zerodha Python library
- `pyotp` - For TOTP generation
- `pandas`, `numpy`, `pyyaml` - Data processing

### 2. Credentials Already Configured

Your Zerodha credentials are already saved in `credentials.txt`:

```
✓ API Key: 8unsgy4cfas4aovi
✓ API Secret: 6yhf2fqconnxlfiota5g1acxh2255wz6
✓ User ID: SHM035
✓ Password: Configured
✓ TOTP Key: Configured
```

**IMPORTANT**: The credentials file is in `.gitignore` and will never be committed to git.

### 3. Test Connection

Before running paper trading, verify your connection works:

```bash
python test_zerodha_connection.py
```

Expected output:
```
✓ Connection successful
✓ Profile retrieved
✓ Instruments loaded
✓ All critical tests passed!
```

### 4. Run Paper Trading

```bash
python zerodha_paper_runner.py
```

This will:
1. Connect to Zerodha API
2. Wait for market open (9:15 AM)
3. Process 5-min candles until market close (3:30 PM)
4. Log all trades to `logs/trades_YYYYMMDD_HHMMSS.csv`

## File Structure

```
paper_trading/
├── zerodha_paper_runner.py      # Main script to run
├── zerodha_connection.py        # Zerodha API wrapper
├── zerodha_data_feed.py         # Real-time data fetching
├── test_zerodha_connection.py   # Connection test script
│
├── paper_strategy.py            # Strategy logic (same as backtest)
├── paper_broker.py              # Order execution simulator
│
├── config.yaml                  # Strategy configuration
├── credentials.txt              # Your Zerodha credentials
│
└── logs/                        # Trade logs
    └── trades_YYYYMMDD_HHMMSS.csv
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

## Expected Output

### Console Output

```
================================================================================
PAPER TRADING - Intraday Momentum OI Strategy (Zerodha)
================================================================================

[2024-12-26 09:10:00] Connecting to Zerodha...
[2024-12-26 09:10:01] ✓ Connection successful!
[2024-12-26 09:10:02] Loading instruments...
[2024-12-26 09:10:05] ✓ Instruments loaded
[2024-12-26 09:10:05] ✓ All components initialized

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

[2024-12-26 10:15:00] EXIT SIGNAL: Trailing Stop (10%)
[2024-12-26 10:15:00] ✓ SELL ORDER EXECUTED
  Strike: 23000 CALL
  Exit Price: ₹170.00
  P&L: ₹+1,500.00 (+13.33%)
  Exit Reason: Trailing Stop (10%)

--------------------------------------------------------------------------------
STATUS UPDATE
--------------------------------------------------------------------------------
Date: 2024-12-26
Daily Direction: CALL @ 23000
Trade Taken Today: True
Open Positions: 0

Statistics:
  Total Trades: 1
  Win Rate: 100.0%
  Total P&L: ₹1,500.00
  Current Cash: ₹101,500.00
  ROI: +1.50%
--------------------------------------------------------------------------------
```

### Trade Log (CSV)

File: `logs/trades_20241226_091000.csv`

```csv
entry_time,exit_time,strike,option_type,expiry,entry_price,exit_price,size,pnl,pnl_pct,vwap_at_entry,vwap_at_exit,oi_at_entry,oi_change_at_entry,oi_at_exit,exit_reason
2024-12-26 09:30:00,2024-12-26 10:15:00,23000,CALL,2024-12-26,150.00,170.00,75,1500.00,13.33,145.00,165.00,5000000,-5.23,4800000,Trailing Stop (10%)
```

## Configuration

The strategy uses `config.yaml` with the same parameters as your backtest:

```yaml
entry:
  start_time: "09:30"
  end_time: "14:30"
  strikes_above_spot: 5
  strikes_below_spot: 5

exit:
  initial_stop_loss_pct: 0.25   # 25%
  trailing_stop_pct: 0.10       # 10%
  vwap_stop_pct: 0.05           # 5%
  oi_increase_stop_pct: 0.10    # 10%

position_sizing:
  initial_capital: 100000       # ₹1 lakh

risk_management:
  max_positions: 2
```

## API Rate Limits

Zerodha Kite Connect limits:
- **Orders**: 10 requests/second, 200/minute, 3000/day
- **Historical Data**: 3 requests/second
- **Quotes**: 1 request/second

For this strategy (~210 API calls per day), you're well within limits.

## Troubleshooting

### Connection Failed

**Error**: "Could not connect to Zerodha"

**Solutions**:
1. Verify credentials in `credentials.txt` are correct
2. Check TOTP token is valid (should be 32 characters)
3. Ensure you have an active Zerodha account
4. Check internet connection
5. Verify system time is synchronized (TOTP is time-sensitive)

### Invalid TOTP

**Error**: "Invalid OTP" or "TOTP authentication failed"

**Solutions**:
1. Regenerate TOTP key from Kite web:
   - Login to kite.zerodha.com
   - Go to Settings > Account > Two-Factor Authentication
   - Disable and re-enable TOTP
   - Copy the new 32-character key
2. Update `totp_key` in `credentials.txt`
3. Ensure your system time is correct

### No Options Data

**Error**: "No options found for expiry"

**Possible Causes**:
1. Market is closed (no live data available)
2. Expiry date not found (weekly expiry may have changed)
3. API rate limit exceeded

**Solutions**:
1. Run during market hours (9:15 AM - 3:30 PM, Mon-Fri)
2. Check if it's a trading holiday
3. Verify NFO instruments loaded correctly

### Historical Data Errors

**Error**: "Could not get historical data"

**Solutions**:
1. Run during or shortly after market hours
2. Check instrument token is valid
3. Verify date range is within allowed limits
4. Zerodha may limit historical data requests outside market hours

## Important Notes

### Security

- ✓ `credentials.txt` is in `.gitignore` - never committed to git
- ✓ Never share your API credentials with anyone
- ✓ TOTP key is equivalent to your password - keep it secret
- ✓ Regenerate credentials if compromised

### Paper Trading vs Live

| Aspect | Paper Trading | Live Trading |
|--------|---------------|--------------|
| Money | Simulated | Real |
| Orders | Instant execution | Subject to market liquidity |
| Slippage | None | Yes |
| Brokerage | None | Charged |
| Risk | Zero | Real |

### Data Differences from Backtest

| Data | Backtest | Paper Trading |
|------|----------|---------------|
| Source | CSV files (historical) | Zerodha API (real-time) |
| Accuracy | 100% complete | May have gaps during API issues |
| OI Data | From CSV | From live options chain |
| Timeliness | Perfect (past data) | Real-time with ~5 second lag |

## Next Steps

1. **Test During Market Hours**: Run for 1-2 days to validate
2. **Compare with Backtest**: Check if results align with backtest expectations
3. **Monitor Performance**: Track win rate, P&L, exit reasons
4. **Analyze Logs**: Review trade log CSV for patterns
5. **Go Live (Optional)**: After successful paper trading, consider live trading with minimal capital

## Monitoring

### Real-time Monitoring

The script prints status every 5 minutes:
- Daily direction and strike
- Open positions
- Trade statistics (win rate, P&L, ROI)

### Log Files

All trades are logged to CSV with:
- Entry/exit times and prices
- Strike, option type, expiry
- P&L and P&L percentage
- VWAP and OI at entry/exit
- Exit reason

### Stopping the Script

Press `Ctrl+C` to gracefully shutdown:
- Closes open positions (if any)
- Prints final statistics
- Logs out from Zerodha

## Support

For issues:
1. Run `test_zerodha_connection.py` to verify API access
2. Check logs in `paper_trading/logs/`
3. Verify config in `config.yaml`
4. Review Zerodha API docs: https://kite.trade/docs/connect/v3/

## Disclaimer

Paper trading is for testing only. Past performance (backtest or paper trading) does not guarantee future results. Always start with minimal capital when going live.
