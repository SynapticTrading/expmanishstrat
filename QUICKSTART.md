# Quick Start Guide - Intraday Momentum OI Strategy

## 5-Minute Setup

### Step 1: Install Dependencies

```bash
cd /Users/Algo_Trading/manishsir_options
pip install -r requirements.txt
```

### Step 2: Verify Data Files

Check that these files exist in `DataDump/`:
```bash
ls -lh DataDump/
```

You should see:
- ✅ weekly_expiry.csv
- ✅ monthly_expiry.csv
- ✅ spotprice_2025.csv
- ✅ india_vix_1min_zerodha.csv

### Step 3: Configure Strategy (Optional)

Edit `config/strategy_config.yaml` to customize parameters:

```yaml
# Quick edits:
candle_timeframe: 5              # 3 or 5 min
initial_capital: 1000000         # Your capital
risk_per_trade_percent: 1.0      # Risk per trade
expiry_type: "weekly"            # weekly or monthly

# Backtest period:
backtest:
  start_date: "2025-01-01"
  end_date: "2025-12-31"
```

### Step 4: Run Backtest

```bash
python backtest_runner.py
```

### Step 5: View Results

After backtest completes, check:

1. **Console Output**: Summary statistics printed
2. **HTML Report**: `reports/report_YYYYMMDD_HHMMSS.html` - Open in browser
3. **Trades CSV**: `reports/trades_YYYYMMDD_HHMMSS.csv` - All trades
4. **Logs**: `logs/backtest_YYYYMMDD_HHMMSS.log` - Detailed execution

## What to Look For

### In Console Output:
```
================================================================================
BACKTEST SUMMARY
================================================================================
Initial Capital:       ₹10,00,000.00
Final Capital:         ₹11,25,000.00
Total P&L:             ₹1,25,000.00 (12.50%)
Total Trades:          45
Win Rate:              55.56%
Profit Factor:         1.85
Max Drawdown:          ₹-25,000.00 (-2.50%)
Sharpe Ratio:          1.45
================================================================================
```

### In HTML Report:
- Summary metrics with color-coded P&L
- Performance table with all metrics
- Monthly breakdown
- Recent trades table

### In Trades CSV:
All trades with:
- Entry/Exit times
- Strike, option type
- Entry/Exit prices
- P&L, P&L%
- Exit reason

## Common Adjustments

### Change Risk per Trade
```yaml
risk_per_trade_percent: 0.5  # Risk 0.5% instead of 1%
```

### Tighter Stop Loss
```yaml
initial_stop_loss_percent: 20  # 20% instead of 25%
```

### Different Timeframe
```yaml
candle_timeframe: 3  # 3-minute candles
```

### Test Specific Date Range
```yaml
backtest:
  start_date: "2025-03-01"
  end_date: "2025-03-31"
```

### Use Monthly Expiry
```yaml
expiry_type: "monthly"
```

## Understanding the Strategy

### Entry Logic:
1. ⏰ Time: 9:30 AM - 2:30 PM
2. 📊 OI Analysis: Find max buildup strikes (5 above, 5 below spot)
3. 🎯 Direction: Call if call buildup closer to spot, else Put
4. 📉 Signal: OI unwinding at selected strike + Price > VWAP
5. ✅ Enter: Buy the option

### Exit Logic:
1. 🛑 Stop Loss: 25% before 10% profit
2. 📈 Trailing Stop: 10% trail after 10% profit
3. ⏰ Time Exit: 2:50-3:00 PM mandatory exit

### Position Sizing:
- Risk 1% of capital per trade
- Size = Risk Amount / Stop Loss Amount

## Troubleshooting

### "No trades executed"
```yaml
# Enable debug logging
logging:
  level: "DEBUG"
```
Check logs for why entry conditions aren't met.

### "Memory issues"
Reduce date range:
```yaml
backtest:
  start_date: "2025-01-01"
  end_date: "2025-01-31"  # Just January
```

### "Module not found"
```bash
pip install -r requirements.txt
```

## Next Steps

1. ✅ Run backtest with default settings
2. 📊 Analyze results in HTML report
3. 🔧 Adjust parameters in config file
4. 🔄 Re-run and compare results
5. 📈 Optimize for best risk/reward

## File Reference

```
Quick Access Files:
├── backtest_runner.py          ← RUN THIS
├── config/strategy_config.yaml ← EDIT THIS
├── reports/*.html              ← VIEW RESULTS HERE
└── logs/*.log                  ← CHECK LOGS HERE
```

## Support

- Check README.md for detailed documentation
- Review strategy PDF for strategy explanation
- Check logs/backtest_*.log for detailed execution
- Enable DEBUG logging for troubleshooting

---

**Ready to go!** Just run: `python backtest_runner.py`
