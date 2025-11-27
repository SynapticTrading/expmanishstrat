# Intraday Momentum OI Unwinding Strategy - Backtesting System

A comprehensive backtesting system for the Intraday Momentum OI Unwinding strategy for Nifty options trading.

## Strategy Overview

**Strategy Name:** Intraday_Momentum_OI
**Type:** Wealth Creation, Long Volatility
**Market:** Nifty Index Options
**Timeframe:** Intraday (3-5 min candles)

### Core Concept

The strategy identifies momentum trades based on Open Interest (OI) unwinding:
- Monitors OI changes across strikes near spot price
- Detects short covering (Call OI unwinding) or long unwinding (Put OI unwinding)
- Enters when OI unwinding + price above VWAP
- Manages with dynamic stop-loss and trailing profit targets

## Project Structure

```
manishsir_options/
├── config/
│   └── strategy_config.yaml          # Configuration file (MODIFY THIS)
├── strategies/
│   ├── intraday_momentum_oi.py       # Core strategy logic
│   └── backtrader_strategy.py        # Backtrader wrapper
├── utils/
│   ├── config_loader.py              # Configuration management
│   ├── data_loader.py                # Data loading and preprocessing
│   ├── oi_analyzer.py                # Open Interest analysis
│   ├── indicators.py                 # VWAP and other indicators
│   ├── logger.py                     # Logging configuration
│   └── reporter.py                   # Report generation
├── data/                              # Additional data (if needed)
├── logs/                              # Log files (auto-generated)
├── reports/                           # Backtest reports (auto-generated)
├── DataDump/                          # Source data files
│   ├── weekly_expiry.csv
│   ├── monthly_expiry.csv
│   ├── spotprice_2025.csv
│   └── india_vix_1min_zerodha.csv
├── backtest_runner.py                 # Main backtest script
├── requirements.txt                   # Python dependencies
└── README.md                          # This file
```

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Verify Data Files

Ensure the following data files are present in `DataDump/`:
- `weekly_expiry.csv` - Weekly options data with OI, IV, Delta, OHLCV
- `monthly_expiry.csv` - Monthly options data
- `spotprice_2025.csv` - Nifty spot prices
- `india_vix_1min_zerodha.csv` - India VIX data

## Configuration

All strategy parameters can be modified in `config/strategy_config.yaml` **without touching the core strategy code**.

### Key Configuration Parameters

```yaml
# Instrument & Expiry
instrument: "NIFTY"
expiry_type: "weekly"              # weekly, monthly, or closest

# Timeframe
candle_timeframe: 5                # 3 or 5 minutes
entry_start_time: "09:30"
entry_end_time: "14:30"
exit_start_time: "14:50"
exit_end_time: "15:00"

# OI Analysis
num_strikes_to_analyze: 10         # 5 below + 5 above spot
strikes_below_spot: 5
strikes_above_spot: 5

# VWAP
vwap_lookback_periods: 20          # Number of candles

# Stop Loss & Targets
initial_stop_loss_percent: 25      # 25% SL before 10% profit
profit_threshold_for_trailing: 1.1 # 1.1x (10% profit) to activate trailing
trailing_stop_percent: 10          # 10% trailing stop

# Position Sizing
risk_per_trade_percent: 1.0        # Risk 1% of capital per trade
initial_capital: 1000000           # 10 lakhs

# Trade Management
max_positions_per_day: 5
max_concurrent_positions: 1

# Backtesting
backtest:
  start_date: "2025-01-01"
  end_date: "2025-12-31"
  commission: 20                    # INR per trade
  slippage_percent: 0.1
```

## Usage

### Run Backtest

```bash
python backtest_runner.py
```

This will:
1. Load configuration from `config/strategy_config.yaml`
2. Load all data files
3. Run the backtest
4. Generate comprehensive reports in `reports/` folder
5. Save logs in `logs/` folder

### Output

The backtest generates:

1. **Logs** (`logs/` folder):
   - `backtest_YYYYMMDD_HHMMSS.log` - Detailed execution log
   - `trades_YYYYMMDD_HHMMSS.log` - Trade-specific log

2. **Reports** (`reports/` folder):
   - `report_YYYYMMDD_HHMMSS.html` - Interactive HTML report
   - `trades_YYYYMMDD_HHMMSS.csv` - All trades in CSV
   - `summary_YYYYMMDD_HHMMSS.json` - Summary statistics
   - `monthly_YYYYMMDD_HHMMSS.csv` - Monthly breakdown

### Sample Output

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

## Strategy Logic (Exact Implementation)

### Entry Conditions

1. **Time Filter**: 9:30 AM to 2:30 PM
2. **OI Analysis**:
   - Identify 10 strikes (5 below, 5 above spot)
   - Calculate max Call buildup strike (MaxOICallStrike)
   - Calculate max Put buildup strike (MaxOIPutStrike)
   - Calculate distances from spot
   - Choose Call if CallDistance < PutDistance, else Put

3. **Strike Selection**:
   - **Call**: Nearest strike above spot (e.g., if spot = 25965, choose 26000)
   - **Put**: Nearest strike below spot (e.g., if spot = 25965, choose 25950)

4. **Entry Signal**:
   - OI must be unwinding (decreasing) at selected strike
   - Option price must be > VWAP
   - **If both conditions met → BUY OPTION**

### Exit Conditions

1. **Stop Loss** (before 10% profit):
   - 25% of entry price

2. **Trailing Stop** (after 10% profit):
   - Trail by 10% from highest price

3. **Time-Based Exit**:
   - Force exit between 2:50 PM - 3:00 PM

### Position Sizing

- Risk 1% of capital per trade
- Position Size = (Risk Amount) / (Stop Loss Amount per unit)

## Data Requirements

### Options Data Columns

```
timestamp, strike, expiry, option_type, open, high, low, close, volume,
underlying_price, futures_price, IV, time_to_expiry, delta, OI
```

### Spot Price Data Columns

```
date, open, high, low, close, volume
```

### VIX Data Columns

```
datetime, vix
```

## Customization

### Modify Strategy Parameters

Edit `config/strategy_config.yaml` to change:
- Timeframes
- Stop loss levels
- Position sizing
- Entry/exit times
- Risk parameters

**No code changes needed!**

### Extend to BankNifty

```yaml
instrument: "BANKNIFTY"
expiry_type: "weekly"
```

### Change Candle Timeframe

```yaml
candle_timeframe: 3  # or 5
```

## Modules Overview

### 1. `strategies/intraday_momentum_oi.py`
Core strategy implementation following the exact logic from the strategy document.

### 2. `utils/oi_analyzer.py`
- Identifies strikes around spot
- Calculates OI buildup and unwinding
- Determines entry direction (Call/Put)

### 3. `utils/indicators.py`
- VWAP calculation for options
- Other technical indicators

### 4. `utils/data_loader.py`
- Loads all data files
- Filters by date, expiry, trading hours
- Provides data access methods

### 5. `utils/reporter.py`
- Generates HTML, CSV, JSON reports
- Calculates performance metrics
- Monthly breakdowns

### 6. `backtest_runner.py`
- Main entry point
- Orchestrates entire backtest workflow
- Handles data flow and strategy execution

## Performance Metrics

The backtest reports include:

- Total P&L and P&L %
- Win rate and profit factor
- Average win/loss
- Max consecutive wins/losses
- Maximum drawdown
- Sharpe ratio
- Monthly performance
- Trade-by-trade details

## Logging

### Log Levels

Configure in `config/strategy_config.yaml`:

```yaml
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR
  log_trades: True
  log_oi_analysis: True
  log_signals: True
```

### Trade Logs

All entry/exit signals are logged with:
- Timestamp
- Strike and option type
- Entry/exit prices
- OI change
- VWAP values
- Exit reason
- P&L

## Important Notes

1. **Data Quality**: Ensure data files have no missing values for critical columns (OI, close, volume)

2. **Trading Hours**: Strategy only trades between 9:30 AM - 2:30 PM, exits by 3:00 PM

3. **Expiry Selection**: Uses closest expiry by default. Monitor performance on Monday/Tuesday as noted in strategy doc.

4. **Position Limits**: Maximum 5 trades per day, 1 concurrent position (configurable)

5. **Slippage & Commission**: Configured in backtest settings, adjust based on broker

## Troubleshooting

### Issue: "No trades executed"

- Check if data covers the configured date range
- Verify entry time is within 9:30 - 14:30
- Check if OI unwinding is occurring in the data
- Enable DEBUG logging to see detailed analysis

### Issue: "No spot price found"

- Ensure `spotprice_2025.csv` has data for trading dates
- Check timestamp format matches

### Issue: "Memory error with large CSV files"

- Data files are processed in chunks internally
- If issues persist, filter data to specific date ranges

## Future Enhancements

- [ ] Add support for BankNifty and other instruments
- [ ] Implement additional entry filters (VIX threshold, etc.)
- [ ] Add position pyramiding option
- [ ] Create visualization of entry/exit points on charts
- [ ] Add walk-forward optimization
- [ ] Implement live trading integration

## License

Proprietary - For authorized use only

## Contact

For questions or support, contact the strategy developer.

---

**Remember**: This is a backtesting system. Past performance does not guarantee future results. Always test thoroughly before live trading.
