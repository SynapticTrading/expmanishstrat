# Issue 13: Cumulative Trades Log Implementation

**Date:** 2025-12-30
**Severity:** MEDIUM (Feature Enhancement)
**Status:** ✅ IMPLEMENTED

---

## Requirement

Need **two separate trade logs:**

1. **Daily CSV** - Fresh file per session (for daily analysis)
2. **Cumulative CSV** - All trades across all sessions (for historical tracking)

**Use Case:**
- Server runs as daily cron job
- Each day creates new session
- Need to track individual day performance
- Also need complete trading history

## Implementation

### 1. Dual CSV Setup in Broker

**File:** `paper_trading/core/broker.py:48-77`

```python
def __init__(self, initial_capital=100000, state_manager=None):
    # ... existing code ...

    # Setup daily trade log file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    self.daily_trade_log = Path('paper_trading/logs') / f'trades_{timestamp}.csv'
    self.daily_trade_log.parent.mkdir(parents=True, exist_ok=True)

    # Setup cumulative trade log file
    self.cumulative_trade_log = Path('paper_trading/logs') / 'trades_cumulative.csv'

    # CSV fieldnames
    self.csv_fieldnames = [
        'entry_time', 'exit_time', 'strike', 'option_type', 'expiry',
        'entry_price', 'exit_price', 'size', 'pnl', 'pnl_pct',
        'vwap_at_entry', 'vwap_at_exit', 'oi_at_entry', 'oi_change_at_entry',
        'oi_at_exit', 'exit_reason'
    ]

    # Write header to daily CSV
    with open(self.daily_trade_log, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=self.csv_fieldnames)
        writer.writeheader()

    # Create cumulative CSV if it doesn't exist (with header)
    if not self.cumulative_trade_log.exists():
        with open(self.cumulative_trade_log, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.csv_fieldnames)
            writer.writeheader()
```

### 2. Log to Both CSVs

**File:** `paper_trading/core/broker.py:177-206`

```python
def _log_trade(self, position, vwap_at_exit, oi_at_exit):
    """Log trade to both daily and cumulative CSV files"""
    trade_data = {
        'entry_time': position.entry_time.strftime('%Y-%m-%d %H:%M:%S'),
        'exit_time': position.exit_time.strftime('%Y-%m-%d %H:%M:%S'),
        'strike': position.strike,
        'option_type': position.option_type,
        'expiry': position.expiry,
        'entry_price': position.entry_price,
        'exit_price': position.exit_price,
        'size': position.size,
        'pnl': position.pnl,
        'pnl_pct': position.pnl_pct,
        'vwap_at_entry': position.vwap_at_entry,
        'vwap_at_exit': vwap_at_exit,
        'oi_at_entry': position.oi_at_entry,
        'oi_change_at_entry': position.oi_change_at_entry,
        'oi_at_exit': oi_at_exit,
        'exit_reason': position.exit_reason
    }

    # Write to daily CSV
    with open(self.daily_trade_log, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=self.csv_fieldnames)
        writer.writerow(trade_data)

    # Append to cumulative CSV
    with open(self.cumulative_trade_log, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=self.csv_fieldnames)
        writer.writerow(trade_data)
```

## File Structure

```
paper_trading/
├── logs/
│   ├── trades_20251229_093000.csv     # Day 1 trades
│   ├── trades_20251230_140550.csv     # Day 2 trades
│   ├── trades_20251231_091500.csv     # Day 3 trades
│   └── trades_cumulative.csv          # ALL trades from all days
```

### Daily CSV Example:
```csv
entry_time,exit_time,strike,option_type,expiry,entry_price,exit_price,size,pnl,pnl_pct,...
2025-12-30 14:25:19,2025-12-30 14:26:51,25900.0,PUT,2025-12-30,5.0,6.7,75,127.5,34.0,...
```

### Cumulative CSV Example:
```csv
entry_time,exit_time,strike,option_type,expiry,entry_price,exit_price,size,pnl,pnl_pct,...
2025-12-29 10:45:00,2025-12-29 14:25:30,23900.0,PE,2025-12-29,18.5,23.2,75,352.5,25.4,...
2025-12-30 14:25:19,2025-12-30 14:26:51,25900.0,PUT,2025-12-30,5.0,6.7,75,127.5,34.0,...
2025-12-31 11:15:22,2025-12-31 14:50:15,24500.0,CE,2025-12-31,12.0,15.5,75,262.5,29.2,...
```

## Benefits

### Daily CSV Benefits:
- ✅ Clean daily analysis
- ✅ Easy to email/share single day
- ✅ Per-session debugging
- ✅ Daily P&L calculation

### Cumulative CSV Benefits:
- ✅ Complete trading history
- ✅ Long-term performance analysis
- ✅ Win rate over time
- ✅ Strategy evolution tracking
- ✅ Monthly/yearly reports

## Usage Examples

### Analyze Single Day:
```python
import pandas as pd

# Read today's trades
df = pd.read_csv('paper_trading/logs/trades_20251230_140550.csv')
daily_pnl = df['pnl'].sum()
print(f"Today's P&L: ₹{daily_pnl:,.2f}")
```

### Analyze All Time:
```python
# Read all trades
df = pd.read_csv('paper_trading/logs/trades_cumulative.csv')
total_pnl = df['pnl'].sum()
win_rate = (df['pnl'] > 0).mean() * 100
print(f"All-time P&L: ₹{total_pnl:,.2f}")
print(f"Win Rate: {win_rate:.1f}%")
```

### Monthly Report:
```python
df = pd.read_csv('paper_trading/logs/trades_cumulative.csv')
df['entry_time'] = pd.to_datetime(df['entry_time'])
df['month'] = df['entry_time'].dt.to_period('M')

monthly_pnl = df.groupby('month')['pnl'].sum()
print(monthly_pnl)
```

## Verification

**After implementing:**

1. ✅ Each session creates new daily CSV
2. ✅ All trades append to cumulative CSV
3. ✅ Both files have same format
4. ✅ No data loss on restart
5. ✅ Historical data preserved

**Test Scenario:**
```
Day 1: 1 trade → daily_20251229.csv (1 trade), cumulative.csv (1 trade)
Day 2: 1 trade → daily_20251230.csv (1 trade), cumulative.csv (2 trades)
Day 3: 2 trades → daily_20251231.csv (2 trades), cumulative.csv (4 trades)
```

## Impact

- ✅ Professional trade tracking
- ✅ Easy performance analysis
- ✅ Historical records maintained
- ✅ Daily and all-time metrics available
- ✅ Ready for production deployment

## Related Issues

- **Complementary:** Issue 11 (Portfolio carryover) - Together enable multi-day tracking

## Files Modified

1. `paper_trading/core/broker.py:48-77` - Dual CSV setup
2. `paper_trading/core/broker.py:177-206` - Log to both files

## Production Notes

**Backup Strategy:**
```bash
# Weekly backup of cumulative trades
0 0 * * 0 cp paper_trading/logs/trades_cumulative.csv \
          backups/trades_cumulative_$(date +\%Y\%m\%d).csv
```

**File Size Management:**
- Daily CSVs: Minimal (1-10 trades per day)
- Cumulative CSV: Grows ~1KB per trade
- 1 year ≈ 250 trading days ≈ 250 trades ≈ 250KB
- No cleanup needed for years
