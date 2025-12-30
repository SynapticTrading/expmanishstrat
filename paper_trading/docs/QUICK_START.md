# Quick Start - Paper Trading

## TL;DR

```bash
# 1. Install dependencies
cd paper_trading
pip install -r requirements.txt

# 2. Test connection
python test_zerodha_connection.py

# 3. Run paper trading (during market hours) - DUAL LOOP VERSION
python dual_loop_runner.py
```

## ⚠️ Important: Use Dual-Loop Runner

**Correct**: `dual_loop_runner.py` - Proper implementation with:
- Loop 1 (5-min): Entry decisions based on candles
- Loop 2 (1-min): Exit decisions based on LTP

**Wrong**: `zerodha_paper_runner.py` - Single loop (deprecated)
- Delayed exits (up to 5 minutes!)
- Worse execution prices

---

## What You Need to Know

### ✅ Credentials: Already Configured
Your Zerodha credentials are saved in `credentials.txt` (secure, not in git).

### ✅ Strategy: Same as Backtest
- Entry: OI unwinding + Price > VWAP
- Exit: 25% SL, VWAP stop, OI stop, Trailing stop, EOD
- 1 trade/day, max 2 positions

### ✅ Output: Trade Logs
All trades logged to `logs/trades_YYYYMMDD_HHMMSS.csv`

---

## Files You Need

| File | What it does |
|------|-------------|
| `zerodha_paper_runner.py` | **Main script - run this** |
| `test_zerodha_connection.py` | Test Zerodha connection |
| `credentials.txt` | Your API credentials (configured) |
| `config.yaml` | Strategy parameters |

---

## Expected Output

```
[09:15:00] NEW TRADING DAY: 2024-12-26
[09:15:00] Daily Direction: CALL @ 23000
[09:30:00] ✓ BUY ORDER EXECUTED
[10:15:00] ✓ SELL ORDER EXECUTED - P&L: ₹+1,500.00
```

---

## Troubleshooting

**Connection failed?**
```bash
python test_zerodha_connection.py
```

**No options data?**
- Must run during market hours (9:15 AM - 3:30 PM)
- Check if it's a trading holiday

**Need help?**
- Read `ZERODHA_SETUP.md` for full guide
- Check `IMPLEMENTATION_SUMMARY.md` for details

---

## Important

⚠️ **Paper trading only** - No real money used
⚠️ **Market hours only** - 9:15 AM - 3:30 PM, Mon-Fri
⚠️ **Test first** - Run for 5-10 days before considering live

---

**Start now**: `python zerodha_paper_runner.py`
