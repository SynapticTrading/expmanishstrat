# Intraday Momentum OI Strategy - Backtesting System

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Proprietary-red.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-production--ready-green.svg)]()

A comprehensive, production-ready backtesting system for the **Intraday Momentum OI Unwinding Strategy** for Nifty options trading in India.

## 🎯 Overview

This system implements a complete backtesting framework for an intraday options trading strategy based on:
- Open Interest (OI) analysis and unwinding detection
- VWAP-based entry signals
- Dynamic stop-loss and trailing profit management
- Strict risk management (1% per trade)

**Strategy Type:** Wealth Creation, Long Volatility
**Market:** Nifty Index Options (Weekly/Monthly)
**Timeframe:** Intraday (3-5 min candles)
**Trading Hours:** 9:30 AM - 3:00 PM IST

## ✨ Features

- ✅ **Exact Strategy Implementation** - Follows strategy document precisely
- ✅ **Configuration-Driven** - All parameters in YAML, no code changes needed
- ✅ **Professional Architecture** - Clean, modular, production-ready code
- ✅ **Comprehensive Reporting** - HTML, CSV, JSON outputs with analytics
- ✅ **Large Dataset Support** - Efficiently handles 5GB+ options data
- ✅ **Detailed Logging** - Debug and trace every decision
- ✅ **Well Documented** - 5 comprehensive documentation files

## 🚀 Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/SynapticTrading/manishsir_options.git
cd manishsir_options

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add your data files to DataDump/
# Required: weekly_expiry.csv, monthly_expiry.csv, spotprice_2025.csv, india_vix_1min_zerodha.csv

# 4. (Optional) Test setup
python test_setup.py

# 5. Run backtest
python backtest_runner.py

# 6. View results
# Open reports/report_*.html in your browser
```

## 📊 Data Requirements

Place your data files in the `DataDump/` folder:

| File | Description | Required Columns |
|------|-------------|------------------|
| `weekly_expiry.csv` | Weekly options data | timestamp, strike, expiry, option_type, open, high, low, close, volume, OI, IV, delta |
| `monthly_expiry.csv` | Monthly options data | Same as weekly |
| `spotprice_2025.csv` | Nifty spot prices | date, open, high, low, close, volume |
| `india_vix_1min_zerodha.csv` | India VIX data | datetime, vix |

**Note:** Data files are not included in the repository due to size. You must provide your own data.

## 📁 Project Structure

```
manishsir_options/
├── config/                     # Configuration files
│   └── strategy_config.yaml    # ⚙️ Edit here to customize strategy
├── strategies/                 # Strategy implementations
│   ├── intraday_momentum_oi.py      # Core strategy logic
│   └── backtrader_strategy.py       # Backtrader integration
├── utils/                      # Utility modules
│   ├── oi_analyzer.py          # OI analysis engine
│   ├── indicators.py           # VWAP calculator
│   ├── data_loader.py          # Data loading & preprocessing
│   ├── reporter.py             # Report generation
│   └── logger.py               # Logging system
├── logs/                       # Auto-generated logs
├── reports/                    # Auto-generated reports
├── DataDump/                   # Your data files (not in repo)
├── backtest_runner.py          # 🚀 Main execution script
├── test_setup.py               # Setup verification
└── requirements.txt            # Python dependencies
```

## ⚙️ Configuration

All strategy parameters can be customized in `config/strategy_config.yaml` **without touching the code**:

```yaml
# Trading Parameters
instrument: NIFTY
expiry_type: weekly              # weekly, monthly, or closest
candle_timeframe: 5              # 3 or 5 minutes

# Entry/Exit Times
entry_start_time: "09:30"
entry_end_time: "14:30"
exit_start_time: "14:50"
exit_end_time: "15:00"

# Stop Loss & Targets
initial_stop_loss_percent: 25    # 25% SL before profit
profit_threshold_for_trailing: 1.1  # 10% profit threshold
trailing_stop_percent: 10        # 10% trailing stop

# Position Sizing
risk_per_trade_percent: 1.0      # Risk 1% per trade
initial_capital: 1000000         # Starting capital (INR)

# Backtesting
backtest:
  start_date: "2025-01-01"
  end_date: "2025-12-31"
  commission: 20                 # Per trade (INR)
  slippage_percent: 0.1
```

## 🎓 Strategy Logic

### Entry Conditions

1. **Time Filter:** 9:30 AM - 2:30 PM
2. **OI Analysis:**
   - Identify 10 strikes (5 below, 5 above spot price)
   - Calculate max Call buildup strike (MaxOICallStrike)
   - Calculate max Put buildup strike (MaxOIPutStrike)
   - Calculate distances from spot
3. **Direction:** Choose Call if CallDistance < PutDistance, else Put
4. **Strike Selection:**
   - Call: Nearest strike above spot (e.g., spot=25965 → 26000)
   - Put: Nearest strike below spot (e.g., spot=25965 → 25950)
5. **Entry Signal:**
   - OI must be unwinding (decreasing) at selected strike
   - Option price must be > VWAP
   - **Both conditions met → BUY OPTION**

### Exit Conditions

1. **Stop Loss:** 25% of entry price (before 10% profit)
2. **Trailing Stop:** 10% trail from highest price (after 10% profit)
3. **Time Exit:** Force exit between 2:50-3:00 PM

### Position Sizing

- Risk 1% of capital per trade
- Position Size = (Risk Amount) / (Stop Loss Amount per unit)

## 📈 Outputs

The backtest generates:

1. **HTML Report** (`reports/report_*.html`)
   - Visual summary with all metrics
   - Performance tables
   - Monthly breakdown
   - Recent trades

2. **Trades CSV** (`reports/trades_*.csv`)
   - All trades for Excel analysis
   - Entry/exit prices, P&L, reasons

3. **Summary JSON** (`reports/summary_*.json`)
   - All metrics in structured format
   - Programmatic access

4. **Logs** (`logs/`)
   - Detailed execution log
   - Trade-specific log

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

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| [README.md](README.md) | Complete project documentation |
| [QUICKSTART.md](QUICKSTART.md) | 5-minute setup guide |
| [STRATEGY_IMPLEMENTATION.md](STRATEGY_IMPLEMENTATION.md) | Technical implementation details |
| [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) | Project overview |
| [FILE_GUIDE.txt](FILE_GUIDE.txt) | File guide with diagrams |

## 🛠️ Tech Stack

- **Python 3.8+**
- **Pandas** - Data manipulation
- **NumPy** - Numerical computing
- **Backtrader** - Backtesting framework
- **PyYAML** - Configuration management

## 🔧 Customization Examples

### Change Risk Per Trade
```yaml
risk_per_trade_percent: 0.5  # 0.5% instead of 1%
```

### Tighter Stop Loss
```yaml
initial_stop_loss_percent: 20  # 20% instead of 25%
```

### Use Monthly Expiry
```yaml
expiry_type: "monthly"
```

### Different Timeframe
```yaml
candle_timeframe: 3  # 3-minute candles
```

## 📊 Performance Metrics

The system calculates:

- Total P&L and P&L percentage
- Win rate and profit factor
- Average win/loss amounts and percentages
- Maximum consecutive wins/losses
- Maximum drawdown (absolute and percentage)
- Sharpe ratio
- Gross profit/loss
- Monthly performance breakdown
- Trade-by-trade analysis

## 🤝 Contributing

This is a proprietary project. For authorized contributors:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is proprietary and confidential. Unauthorized copying or distribution is prohibited.

## ⚠️ Disclaimer

This backtesting system is for research and educational purposes only. Past performance does not guarantee future results. Trading in derivatives involves substantial risk. Always conduct thorough testing and risk assessment before live trading.

## 📞 Support

- 📖 Read the documentation in the repo
- 🐛 Report issues via GitHub Issues
- 💬 For authorized users: Contact the development team

## 🙏 Acknowledgments

- Strategy design and documentation
- Backtrader framework for backtesting infrastructure
- Python community for excellent data analysis tools

---

**Built with precision and attention to detail.**

⭐ If you find this project useful, please star the repository!

