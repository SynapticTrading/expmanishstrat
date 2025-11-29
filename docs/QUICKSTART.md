# Quick Start Guide

## Get Started in 5 Minutes

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Verify Data Files

Check that these files exist:
- `DataDump/spotprice_2025.csv`
- `DataDump/weekly_expiry.csv`

### 3. Run Default Backtest

```bash
python backtest_runner.py
```

That's it! The backtest will run with default settings (1-minute candles, Jan-Oct 2025).

## Understanding the Output

### Console Output
You'll see:
- Real-time strategy decisions
- Entry/exit signals
- Final performance summary

### Generated Files (in `reports/` folder)
- `backtest_metrics.json` - Performance numbers
- `trades.csv` - All trades with entry/exit details
- `equity_curve.png` - Visual portfolio performance
- `trade_analysis.png` - Trade distribution charts

## Quick Customizations

### Change Timeframe

Edit `config/strategy_config.yaml`:
```yaml
data:
  timeframe: 3  # 3-minute candles instead of 1-minute
```

### Change Date Range

```yaml
data:
  start_date: "2025-03-01"
  end_date: "2025-06-30"
```

### Change Capital

```yaml
position_sizing:
  initial_capital: 200000  # ₹2 Lakhs instead of ₹1 Lakh
```

### Skip Monday/Tuesday

```yaml
risk_management:
  avoid_monday_tuesday: true
```

## Next Steps

- Read the full [README.md](../README.md) for detailed documentation
- Experiment with different parameters in `config/strategy_config.yaml`
- Analyze the generated reports in the `reports/` folder
- Review the strategy PDF for deeper understanding

## Common Issues

**"ModuleNotFoundError"**  
→ Run: `pip install -r requirements.txt`

**"File not found: DataDump/..."**  
→ Ensure data files are in the correct location

**"No trades generated"**  
→ Check date range and verify options data exists for those dates

## Command Reference

```bash
# Run with default config
python backtest_runner.py

# Run with custom config
python backtest_runner.py --config config/my_config.yaml

# View help
python backtest_runner.py --help
```

---

Happy backtesting! 🚀

