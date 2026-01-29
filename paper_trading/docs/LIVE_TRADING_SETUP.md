# Live Trading Setup - Implementation Complete

## Overview

The live trading capability has been successfully implemented. The system now supports both paper trading (simulation) and live trading (real orders) with a simple mode switch.

## What Changed

### 1. New Configuration (`config.yaml`)

Added `trading_mode` section:

```yaml
trading_mode:
  mode: "paper"  # Options: "paper" or "live"

  live_settings:
    product_type: "INTRADAY"  # INTRADAY (MIS), DELIVERY (CNC), CARRYFORWARD (NRML)
    order_type: "MARKET"      # MARKET or LIMIT
    max_order_value: 50000    # Maximum order value in ₹
    max_daily_loss: 10000     # Stop trading if loss exceeds this
    require_confirmation: true # Require manual confirmation before first trade
```

### 2. New LiveBroker Class (`paper_trading/core/live_broker.py`)

- **Interface**: Mirrors PaperBroker exactly (same buy/sell signatures)
- **Execution**: Places real orders via adapter.place_order()
- **Safety Features**:
  - Order value limits (rejects orders > max_order_value)
  - Daily loss limits (stops trading if loss > max_daily_loss)
  - Order fill verification (waits for MARKET orders to fill)
  - Duplicate sell protection (_sold flag)
  - Actual price tracking (logs requested vs actual fill prices)
  - Separate logging (live_trades_YYYYMMDD.csv)

- **State Management**: Same StateManager integration for crash recovery
- **Position Tracking**: LivePosition class with order_id for broker tracking

### 3. Modified Runner (`paper_trading/runner.py`)

- **Command-line argument**: `--mode {paper,live}` (overrides config)
- **Confirmation prompt**: Requires "CONFIRM LIVE TRADING" string before starting
- **Automatic broker selection**: Creates LiveBroker or PaperBroker based on mode
- **Mode display**: Shows 🔴 LIVE or 📄 PAPER in banners
- **Account balance**: Shows available cash during confirmation

## Usage

### Paper Trading (Default)

```bash
# Using config default (paper)
python paper_trading/runner.py --broker zerodha

# Explicitly set paper mode
python paper_trading/runner.py --broker zerodha --mode paper
```

### Live Trading

```bash
# Command-line override (recommended for testing)
python paper_trading/runner.py --broker zerodha --mode live
```

**Confirmation prompt:**
```
⚠️  LIVE TRADING MODE ACTIVATED ⚠️
================================================================================

This will place REAL orders with REAL money!
Broker: Zerodha
Product Type: INTRADAY
Order Type: MARKET
Max Order Value: ₹50,000.00
Max Daily Loss: ₹10,000.00

Account Balance: ₹1,25,000.00

================================================================================

Type 'CONFIRM LIVE TRADING' to proceed:
```

### Config-Based Live Trading

Edit `config.yaml`:
```yaml
trading_mode:
  mode: "live"  # Change from "paper" to "live"
```

Then run normally:
```bash
python paper_trading/runner.py --broker zerodha
```

## Safety Features

### 1. Order Value Limits
- Rejects any order exceeding `max_order_value`
- Example: With max_order_value=50000, an order worth ₹60,000 will be rejected

### 2. Daily Loss Limits
- Stops trading if `abs(daily_realized_pnl) > max_daily_loss`
- Example: With max_daily_loss=10000, system stops after ₹10,000 loss

### 3. Confirmation Prompt
- Requires explicit "CONFIRM LIVE TRADING" string (exact match)
- Shows account balance and settings before proceeding
- Can be disabled by setting `require_confirmation: false` (NOT recommended)

### 4. Order Fill Verification
- Waits up to 30 seconds for MARKET orders to fill
- Automatically cancels unfilled orders after timeout
- Tracks actual fill price vs requested price

### 5. Duplicate Sell Protection
- Same `_sold` flag mechanism as PaperBroker
- Prevents race conditions between strategy loop and exit monitor

### 6. Separate Logging
- Live trades logged to: `paper_trading/logs/live_trades_YYYYMMDD.csv`
- Paper trades logged to: `paper_trading/logs/trades_YYYYMMDD.csv`
- Separate cumulative files for each mode

### 7. State Management
- Full crash recovery support (same as paper trading)
- Restores open positions and trade history
- Tracks daily P&L for loss limit enforcement

## Architecture

### Before (Paper Mode)
```
Strategy → PaperBroker.buy() → Simulated execution
```

### Now (Live Mode)
```
Strategy → LiveBroker.buy() → Adapter.place_order() → Real broker API
```

### Key Design Decision
- **LiveBroker mirrors PaperBroker interface** - Strategy code unchanged
- Both brokers have identical buy/sell signatures
- Strategy doesn't know or care which broker it's using
- Clean separation of paper and live logic

## Configuration Options

### Conservative Setup (Recommended for Testing)
```yaml
trading_mode:
  mode: "live"
  live_settings:
    product_type: "INTRADAY"
    order_type: "MARKET"
    max_order_value: 30000     # Max ₹30k per order
    max_daily_loss: 5000       # Stop if loss > ₹5k
    require_confirmation: true
```

### Aggressive Setup
```yaml
trading_mode:
  mode: "live"
  live_settings:
    product_type: "INTRADAY"
    order_type: "MARKET"
    max_order_value: 100000    # Max ₹1L per order
    max_daily_loss: 20000      # Stop if loss > ₹20k
    require_confirmation: false  # Auto-start (RISKY!)
```

## Verification Steps

### 1. Test Paper Mode (Verify Unchanged)
```bash
python paper_trading/runner.py --broker zerodha --mode paper
```
- Should work exactly as before
- No confirmation prompt
- Logs to trades_YYYYMMDD.csv

### 2. Test Live Mode Confirmation
```bash
python paper_trading/runner.py --broker zerodha --mode live
```
- Should show confirmation prompt
- Type anything other than "CONFIRM LIVE TRADING" → exits
- Type "CONFIRM LIVE TRADING" exactly → proceeds

### 3. Verify Safety Checks

**Test order value limit:**
1. Set `max_order_value: 1000` in config
2. Run in live mode
3. Verify orders are rejected if they exceed ₹1,000

**Test daily loss limit:**
1. Set `max_daily_loss: 1000` in config
2. After taking a loss > ₹1,000, verify no new orders placed

### 4. Check Logging
```bash
# Check live trades log exists
ls paper_trading/logs/live_trades_*.csv

# Verify separate from paper trades
ls paper_trading/logs/trades_*.csv

# View live trades
cat paper_trading/logs/live_trades_cumulative.csv
```

### 5. Test AMO Orders (Before Full Live)

**Test order placement WITHOUT market execution:**
1. Run system after market close (after 3:30 PM)
2. System will place AMO (After Market Orders)
3. Orders sit in order book but don't execute
4. Cancel all orders before market open next day
5. This verifies order placement works without risking execution

```bash
# After market close
python paper_trading/runner.py --broker zerodha --mode live

# Before market open next day, cancel all orders
python -c "
from paper_trading.brokers.adapter import create_adapter
from paper_trading.legacy.zerodha_connection import load_credentials_from_file

credentials = load_credentials_from_file('paper_trading/config/credentials_zerodha.txt')
adapter = create_adapter(credentials, broker='zerodha')
adapter.connect()

# Cancel all pending orders
orders = adapter.get_all_orders()
for order in orders:
    if order.status in ['OPEN', 'PENDING']:
        adapter.cancel_order(order.order_id)
        print(f'Cancelled order: {order.order_id}')
"
```

## Rollout Strategy

### Stage 1: Implementation & Testing ✅ COMPLETE
- [x] Implement all changes
- [x] Test paper mode (unchanged)
- [x] Verify imports and syntax
- [x] Test config loading

### Stage 2: AMO Testing (Next)
- [ ] Test live order placement with AMO (after market close)
- [ ] Verify order appears in broker's order book
- [ ] Cancel orders before market open
- [ ] Repeat 2-3 times to ensure stability

### Stage 3: Small Size Live (When Confident)
- [ ] Set lot size to 1 lot (25 qty) in config
- [ ] Run live for 1 week with small size
- [ ] Monitor actual fill prices vs requested prices
- [ ] Verify all safety features work correctly
- [ ] Check state recovery after crashes

### Stage 4: Full Size Live (After Validation)
- [ ] Increase to configured lot size (65 qty)
- [ ] Continue monitoring for 1-2 weeks
- [ ] Review trade logs and P&L
- [ ] Compare paper vs live performance

## Files Created/Modified

### New Files
- `paper_trading/core/live_broker.py` - LiveBroker and LivePosition classes

### Modified Files
- `paper_trading/config/config.yaml` - Added trading_mode section
- `paper_trading/runner.py` - Added mode switch, confirmation prompt, broker initialization

### No Changes Required
- `paper_trading/core/strategy.py` - Strategy unchanged
- `paper_trading/core/broker.py` - PaperBroker unchanged
- `paper_trading/brokers/adapter/` - Adapters unchanged

## Key Advantages

1. **Strategy Unchanged** - IntradayMomentumOIPaper doesn't need modification
2. **Clean Separation** - Paper and live logic completely isolated
3. **Easy Toggle** - Switch modes via config or command-line
4. **Safety First** - Multiple validation layers
5. **Backward Compatible** - Paper trading unaffected
6. **Adapter Ready** - Adapters already support all required methods
7. **State Management** - Same StateManager for crash recovery
8. **Separate Logs** - Live and paper trades in different files

## Troubleshooting

### "Module not found: live_broker"
- Ensure you're running from project root
- Check `paper_trading/core/live_broker.py` exists

### Confirmation prompt doesn't appear
- Check `require_confirmation: true` in config
- Verify mode is set to "live"
- Check adapter connected successfully

### Orders not filling
- Verify market is open
- Check order type is MARKET
- Increase timeout in `_wait_for_fill()` if needed
- Check broker account has sufficient balance

### Daily loss limit not working
- Check `daily_realized_pnl` is being updated in sell()
- Verify loss limit check in buy() method
- Review live trade logs for P&L calculations

## Next Steps

1. **Test AMO Orders** - Place orders after market close, cancel before open
2. **Monitor First Week** - Run with 1 lot for 1 week, monitor closely
3. **Compare Performance** - Compare live vs paper trade results
4. **Tune Safety Limits** - Adjust max_order_value and max_daily_loss based on experience
5. **Add Alerts** - Consider adding email/SMS alerts for live trades

## Support

For issues or questions:
1. Check logs: `paper_trading/logs/session_log_*.txt`
2. Check trade logs: `paper_trading/logs/live_trades_*.csv`
3. Check state files: `paper_trading/state/trading_state_*.json`
4. Review adapter logs for order placement errors

---

**🔴 IMPORTANT: Test thoroughly in paper mode and with AMO before going live! 🔴**
