# Intraday Momentum OI Unwinding Strategy - Backtest System

## Overview

This is a comprehensive backtesting system for the **Intraday Momentum OI Unwinding Strategy** designed for Nifty weekly options. The strategy identifies and trades based on Open Interest (OI) unwinding patterns (short covering/long unwinding) combined with VWAP confirmations.

## Strategy Description

### Core Concept
- **Identification**: Detects direction based on maximum Call/Put OI buildup near spot price
- **Entry Signal**: OI unwinding (decrease) at selected strike + Option price above VWAP
- **Exit**: Time-based (EOD) or trailing stop after 10% profit
- **Risk Management**: 25% initial stop loss, 10% trailing stop after profit threshold

### Key Features
- ✅ **1-minute candle backtesting** for high granularity
- ✅ **IST timezone handling** for Indian market hours
- ✅ **Weekly expiry options** analysis
- ✅ **OI change tracking** for short covering/long unwinding detection
- ✅ **VWAP anchored to market open**
- ✅ **Configurable parameters** via YAML
- ✅ **Comprehensive reporting** with metrics and visualizations

## Project Structure

```
manishsir_options/
├── config/
│   └── strategy_config.yaml      # Strategy configuration (editable)
├── src/
│   ├── __init__.py
│   ├── config_loader.py          # Configuration loader
│   ├── data_loader.py            # Data loading & preprocessing
│   ├── oi_analyzer.py            # OI analysis module
│   ├── indicators.py             # Custom indicators (VWAP)
│   └── reporter.py               # Performance reporting
├── strategies/
│   ├── __init__.py
│   └── intraday_momentum_oi.py   # Main strategy implementation
├── DataDump/
│   ├── spotprice_2025.csv        # Spot price data (1-min)
│   └── weekly_expiry.csv         # Options data with OI
├── reports/                      # Generated reports (output)
├── logs/                         # Log files (output)
├── docs/                         # Documentation
├── backtest_runner.py            # Main backtest script
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

## Installation

### Prerequisites
- Python 3.8+
- pip

### Setup

1. **Install dependencies**:
```bash
pip install -r requirements.txt
```

2. **Verify data files**:
Ensure the following files exist in `DataDump/`:
- `spotprice_2025.csv` - Spot price data (1-minute granularity, IST timezone)
- `weekly_expiry.csv` - Options data with OI information

## Configuration

Edit `config/strategy_config.yaml` to customize strategy parameters:

### Key Configurable Parameters

```yaml
data:
  timeframe: 1                    # Candle timeframe in minutes (1, 3, 5, etc.)
  start_date: "2025-01-01"        # Backtest start date
  end_date: "2025-10-31"          # Backtest end date

entry:
  start_time: "09:30"             # Entry window start (IST)
  end_time: "14:30"               # Last entry time (IST)
  strikes_above_spot: 5           # Strikes to analyze above spot
  strikes_below_spot: 5           # Strikes to analyze below spot

exit:
  exit_start_time: "14:50"        # Start closing positions (IST)
  exit_end_time: "15:00"          # Force close all by (IST)
  initial_stop_loss_pct: 0.25     # 25% stop loss initially
  profit_threshold: 1.10          # 110% for trailing stop activation
  trailing_stop_pct: 0.10         # 10% trailing stop

position_sizing:
  initial_capital: 100000         # Starting capital (₹1L)
  position_size: 1                # Lots per trade
  risk_per_trade_pct: 0.01        # 1% risk per trade

risk_management:
  max_positions: 3                # Max concurrent positions
  avoid_monday_tuesday: false     # Skip Mon/Tue (near expiry)
```

## Usage

### Run Backtest

**Basic usage**:
```bash
python backtest_runner.py
```

**With custom config**:
```bash
python backtest_runner.py --config config/custom_config.yaml
```

### Output

The backtest generates:

1. **Console Output**: Real-time progress and summary metrics
2. **Reports folder** (`reports/`):
   - `backtest_metrics.json` - Performance metrics
   - `trades.csv` - Detailed trade log
   - `equity_curve.png` - Equity curve and drawdown chart
   - `trade_analysis.png` - Trade distribution analysis

### Example Output

```
================================================================================
                          BACKTEST RESULTS
================================================================================

Capital:
  Initial Capital:        ₹100,000.00
  Final Value:            ₹115,432.50
  Total Return:           ₹15,432.50
  Total Return %:         15.43%

Trade Statistics:
  Total Trades:           48
  Winning Trades:         32
  Losing Trades:          16
  Win Rate:               66.67%

Profitability:
  Total PnL:              ₹15,432.50
  Average PnL:            ₹321.51
  Average PnL %:          3.21%
  Best Trade:             ₹2,150.00
  Worst Trade:            ₹-875.00
  Profit Factor:          2.34

Risk Metrics:
  Sharpe Ratio:           1.85
  Max Drawdown:           ₹-3,250.00
  Max Drawdown %:         -3.25%
================================================================================
```

## Strategy Logic Details

### Entry Process

1. **Market Analysis** (Daily, at market open):
   - Identify 10 strikes around spot (5 above, 5 below)
   - Calculate max Call OI buildup strike
   - Calculate max Put OI buildup strike
   - Determine direction: CALL if Call buildup closer to spot, else PUT

2. **Strike Selection**:
   - **For CALL direction**: Nearest strike ≥ spot
   - **For PUT direction**: Nearest strike < spot

3. **Entry Conditions** (From 9:30 AM to 2:30 PM IST):
   - OI at selected strike is unwinding (decreasing)
   - Option price > VWAP
   - → **BUY OPTION**

### Exit Process

1. **Stop Loss** (Before profit threshold):
   - 25% of entry price

2. **Trailing Stop** (After 10% profit):
   - Trail by 10% from highest price reached

3. **Time-based Exit**:
   - All positions closed between 2:50 - 3:00 PM IST

## Data Requirements

### Spot Price CSV Format
```csv
date,open,high,low,close,volume
2025-01-01 09:15:00+05:30,23637.65,23681.7,23633.35,23649.55,0
```

### Options CSV Format
```csv
timestamp,strike,expiry,option_type,open,high,low,close,volume,underlying_price,futures_price,IV,time_to_expiry,delta,OI
2025-01-01 09:15:00+05:30,22000,2025-01-02,CE,1421.75,1427.15,1421.75,1427.15,975,23649.55,23651.94,0.759,0.0016,0.976,12255300
```

**Required columns**:
- `timestamp`: Date-time in IST (with timezone)
- `strike`: Strike price
- `expiry`: Expiry date
- `option_type`: CE (Call) or PE (Put)
- `open`, `high`, `low`, `close`: Option prices
- `volume`: Trading volume
- `OI`: Open Interest

## Customization

### Change Timeframe

Edit `config/strategy_config.yaml`:
```yaml
data:
  timeframe: 3  # Change to 3-minute candles
```

### Modify Entry/Exit Times

```yaml
entry:
  start_time: "10:00"  # Start entries at 10 AM
  end_time: "14:00"    # Last entry at 2 PM
```

### Adjust Risk Parameters

```yaml
exit:
  initial_stop_loss_pct: 0.20     # 20% stop loss
  trailing_stop_pct: 0.15         # 15% trailing stop

position_sizing:
  initial_capital: 200000         # ₹2L capital
  position_size: 2                # 2 lots per trade
```

### Skip Monday/Tuesday Trading

```yaml
risk_management:
  avoid_monday_tuesday: true      # Skip near-expiry days
```

## Advanced Usage

### Custom Strategy Modifications

The strategy implementation is in `strategies/intraday_momentum_oi.py`. Key methods:

- `analyze_market()`: Daily market analysis
- `check_entry_conditions()`: Entry signal logic
- `manage_positions()`: Position management and stops

### Adding Custom Indicators

Add new indicators in `src/indicators.py`:

```python
class MyIndicator(bt.Indicator):
    lines = ('myline',)
    
    def next(self):
        self.lines.myline[0] = # your calculation
```

### Custom Analyzers

Backtrader analyzers are already added. Access them in the strategy:

```python
results = cerebro.run()
strategy = results[0]
sharpe = strategy.analyzers.sharpe.get_analysis()
```

## Troubleshooting

### Issue: "Memory Error" when loading data
**Solution**: The options CSV is very large (2GB). Ensure you have sufficient RAM (8GB+).

### Issue: "Timezone errors"
**Solution**: Verify timestamps in CSVs include timezone info (`+05:30` for IST).

### Issue: "No trades generated"
**Solution**: 
- Check if OI data is available for the selected dates
- Verify entry conditions are not too restrictive
- Check log output for strategy signals

### Issue: "Import errors"
**Solution**: Ensure all dependencies are installed:
```bash
pip install -r requirements.txt --upgrade
```

## Performance Optimization

For faster backtesting:

1. **Reduce date range** in config
2. **Increase timeframe** (e.g., 3 or 5 minutes instead of 1)
3. **Filter options data** to only relevant strikes
4. **Use SSD** for faster data loading

## Contributing

This is a private strategy implementation. Modifications should be tracked via git.

## References

- **Strategy Document**: `Trading Strategy _ Intraday_Momentum_OIUnwinding.pdf`
- **Backtrader Documentation**: https://www.backtrader.com/docu/
- **NIFTY Options**: NSE India

## License

Private use only.

## Contact

For questions about this implementation, contact the development team.

---

**Last Updated**: 2025-01-27  
**Version**: 1.0.0

