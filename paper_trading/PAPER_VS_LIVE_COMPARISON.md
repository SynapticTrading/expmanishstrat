# Paper Trading vs Live Trading - Quick Reference

## Mode Selection

### Via Command-Line (Recommended)
```bash
# Paper mode
python paper_trading/runner.py --broker zerodha --mode paper

# Live mode
python paper_trading/runner.py --broker zerodha --mode live
```

### Via Config File
Edit `paper_trading/config/config.yaml`:
```yaml
trading_mode:
  mode: "paper"  # or "live"
```

Command-line argument `--mode` overrides config file.

## Key Differences

| Feature | Paper Mode 📄 | Live Mode 🔴 |
|---------|---------------|--------------|
| **Orders** | Simulated | Real orders via broker API |
| **Money** | Virtual capital (₹100k default) | Real money from broker account |
| **Execution** | Instant at requested price | Subject to market conditions |
| **Slippage** | None (assumes perfect fill) | Real slippage possible |
| **Confirmation** | None required | Requires "CONFIRM LIVE TRADING" |
| **Safety Limits** | None (unlimited trading) | Order value & daily loss limits |
| **Trade Logs** | `logs/trades_YYYYMMDD.csv` | `logs/live_trades_YYYYMMDD.csv` |
| **Broker Charges** | Not simulated | Real brokerage & taxes |
| **Order Tracking** | Position ID only | Broker order ID tracked |
| **State Recovery** | Full recovery support | Full recovery support |

## Broker Classes

### PaperBroker (Paper Mode)

**Location:** `paper_trading/core/broker.py`

**Initialization:**
```python
broker = PaperBroker(
    initial_capital=100000,
    state_manager=state_manager,
    logs_dir='paper_trading/logs',
    broker_name='Zerodha'
)
```

**Buy Method:**
```python
position = broker.buy(
    strike=25000,
    option_type='CALL',
    expiry='2025-01-30',
    price=150.0,
    size=65,
    vwap=150.0,
    oi=10000,
    oi_change=0.05
)
# Returns: PaperPosition (instant fill at requested price)
# Cash: Deducted immediately (price * size)
```

**Sell Method:**
```python
success = broker.sell(
    position=position,
    price=180.0,
    vwap=180.0,
    oi=12000,
    reason='Profit Target'
)
# Returns: True (instant exit at requested price)
# Cash: Credited immediately (price * size)
# P&L: Calculated instantly
```

### LiveBroker (Live Mode)

**Location:** `paper_trading/core/live_broker.py`

**Initialization:**
```python
broker = LiveBroker(
    adapter=adapter,  # BrokerAdapter instance
    config=config,    # Full config dict
    state_manager=state_manager,
    logs_dir='paper_trading/logs'
)
```

**Buy Method:**
```python
position = broker.buy(
    strike=25000,
    option_type='CALL',
    expiry='2025-01-30',
    price=150.0,  # Requested price (ignored for MARKET orders)
    size=65,
    vwap=150.0,
    oi=10000,
    oi_change=0.05
)
# Returns: LivePosition with broker order_id
# Process:
#   1. Safety checks (order value, daily loss)
#   2. Place order via adapter
#   3. Wait for fill (30s timeout for MARKET orders)
#   4. Get actual fill price
#   5. Create position with actual price
# Actual fill: May differ from requested price due to market conditions
```

**Sell Method:**
```python
success = broker.sell(
    position=position,
    price=180.0,  # Requested price (ignored for MARKET orders)
    vwap=180.0,
    oi=12000,
    reason='Profit Target'
)
# Returns: True if successful, False if failed
# Process:
#   1. Duplicate sell protection
#   2. Place sell order via adapter
#   3. Wait for fill (30s timeout for MARKET orders)
#   4. Get actual exit price
#   5. Calculate P&L with actual prices
#   6. Update daily_realized_pnl
# Actual exit: May differ from requested price
```

## Position Classes

### PaperPosition

```python
class PaperPosition:
    strike: int
    option_type: str          # 'CALL' or 'PUT'
    expiry: str
    entry_price: float
    size: int
    entry_time: datetime
    vwap_at_entry: float
    oi_at_entry: float
    oi_change_at_entry: float

    # Trailing stop tracking
    peak_price: float
    trailing_stop_active: bool

    # Exit tracking
    exit_price: float
    exit_time: datetime
    exit_reason: str
    pnl: float
    pnl_pct: float
```

### LivePosition

Same as PaperPosition, plus:
```python
    order_id: str             # Broker order ID for entry
    exit_order_id: str        # Broker order ID for exit
```

## Safety Features (Live Mode Only)

### 1. Order Value Limit
```yaml
max_order_value: 50000  # ₹50,000
```

**Behavior:**
- Calculates: `order_value = price * size`
- If `order_value > max_order_value`: Reject order
- Returns: `None` instead of position

**Example:**
```python
# price=800, size=65 → order_value=52,000
# 52,000 > 50,000 → REJECTED
```

### 2. Daily Loss Limit
```yaml
max_daily_loss: 10000  # ₹10,000
```

**Behavior:**
- Tracks: `daily_realized_pnl` (cumulative P&L for the day)
- If `abs(daily_realized_pnl) > max_daily_loss`: Reject new orders
- Returns: `None` instead of position

**Example:**
```python
# Trade 1: -₹6,000
# Trade 2: -₹5,000
# daily_realized_pnl = -₹11,000
# abs(-11,000) = 11,000 > 10,000 → NO MORE ORDERS TODAY
```

### 3. Order Fill Verification
```python
def _wait_for_fill(order_id, timeout=30):
    # Polls adapter.get_order() every 1 second
    # Returns True if status == COMPLETE
    # Returns False if timeout or REJECTED/CANCELLED
```

**Behavior:**
- For MARKET orders: Wait up to 30 seconds for fill
- If timeout: Cancel order, return None
- If filled: Get actual fill price, create position

### 4. Confirmation Prompt
```yaml
require_confirmation: true
```

**Prompt:**
```
Type 'CONFIRM LIVE TRADING' to proceed: _
```

**Exact match required** - typing anything else exits the program.

To disable (NOT recommended):
```yaml
require_confirmation: false
```

## Trade Logs

### Paper Trading Logs

**Daily log:** `paper_trading/logs/trades_YYYYMMDD_HHMMSS.csv`
**Cumulative:** `paper_trading/logs/trades_cumulative.csv`

**Fields:**
- entry_time, exit_time
- broker (e.g., "Zerodha", "AngelOne")
- strike, option_type, expiry
- entry_price, exit_price, size
- pnl, pnl_pct
- vwap_at_entry, vwap_at_exit
- oi_at_entry, oi_change_at_entry, oi_at_exit
- exit_reason

### Live Trading Logs

**Daily log:** `paper_trading/logs/live_trades_YYYYMMDD_HHMMSS.csv`
**Cumulative:** `paper_trading/logs/live_trades_cumulative.csv`

**Fields:** Same as paper logs, plus:
- entry_order_id (broker's order ID for entry)
- exit_order_id (broker's order ID for exit)

## State Recovery (Crash Recovery)

Both modes support full state recovery:

### Paper Mode Recovery
```python
broker.restore_positions(saved_positions)
broker.restore_trade_history(closed_positions)
# Cash is restored from state file
```

### Live Mode Recovery
```python
broker.restore_positions(saved_positions)
broker.restore_trade_history(closed_positions)
# Daily P&L is recalculated from closed trades
# No cash tracking (uses broker's actual balance)
```

**State file location:** `paper_trading/state/trading_state_YYYYMMDD.json`

## Strategy Integration

Strategy code is **identical** for both modes:

```python
# Strategy doesn't know or care which broker it's using
self.strategy = IntradayMomentumOIPaper(
    config=config,
    broker=broker,  # Can be PaperBroker or LiveBroker
    oi_analyzer=oi_analyzer,
    state_manager=state_manager,
    contract_manager=contract_manager,
    adapter=adapter
)

# Entry logic (same for both modes)
position = self.broker.buy(
    strike=selected_strike,
    option_type=direction,
    expiry=expiry,
    price=ltp,
    size=lot_size,
    vwap=vwap,
    oi=oi,
    oi_change=oi_change
)

# Exit logic (same for both modes)
success = self.broker.sell(
    position=position,
    price=current_ltp,
    vwap=current_vwap,
    oi=current_oi,
    reason='Stop Loss'
)
```

## Testing Checklist

### Before Going Live

- [ ] Test paper mode extensively
- [ ] Verify all safety limits work
- [ ] Test crash recovery in paper mode
- [ ] Review paper trade logs for accuracy
- [ ] Test AMO orders (after market close)
- [ ] Verify order placement works
- [ ] Cancel AMO orders before market open
- [ ] Start with 1 lot (25 qty) for first week
- [ ] Monitor actual fill prices vs requested
- [ ] Check daily P&L calculations
- [ ] Verify state recovery in live mode

### During Live Trading

- [ ] Monitor session logs: `logs/session_log_YYYYMMDD_HHMMSS.txt`
- [ ] Check live trade logs: `logs/live_trades_cumulative.csv`
- [ ] Verify order IDs in broker's dashboard
- [ ] Compare actual fills vs expected prices
- [ ] Monitor daily P&L vs loss limits
- [ ] Check state files for accuracy
- [ ] Test recovery after intentional restart

## Common Scenarios

### Scenario 1: Order Rejected (Value Limit)

**Paper Mode:**
```
Cost: ₹52,000
✓ BUY ORDER EXECUTED
```

**Live Mode:**
```
Order value: ₹52,000
Max allowed: ₹50,000
✗ Order rejected: Value exceeds max
Returns: None
```

### Scenario 2: Slippage

**Paper Mode:**
```
Requested: ₹150.00
Filled: ₹150.00 (perfect fill)
```

**Live Mode:**
```
Requested: ₹150.00
Filled: ₹152.35 (real market price)
P&L calculated with actual price
```

### Scenario 3: Order Doesn't Fill

**Paper Mode:**
```
N/A - instant fill always
```

**Live Mode:**
```
Order placed: 123ABC
Waiting for fill...
Timeout after 30s
Cancelling order 123ABC
Returns: None
```

### Scenario 4: Daily Loss Limit Hit

**Paper Mode:**
```
Trade 1: -₹6,000
Trade 2: -₹5,000
Trade 3: -₹3,000
Total: -₹14,000
Still allows more trades
```

**Live Mode:**
```
Trade 1: -₹6,000
Trade 2: -₹5,000
Daily P&L: -₹11,000
Max loss: ₹10,000
✗ Order rejected: Daily loss exceeds max
No more trades today
```

## Quick Reference Commands

```bash
# Paper mode (default)
python paper_trading/runner.py --broker zerodha

# Explicitly paper mode
python paper_trading/runner.py --broker zerodha --mode paper

# Live mode (with confirmation)
python paper_trading/runner.py --broker zerodha --mode live

# View help
python paper_trading/runner.py --help

# Check paper trades
cat paper_trading/logs/trades_cumulative.csv

# Check live trades
cat paper_trading/logs/live_trades_cumulative.csv

# View session log
tail -f paper_trading/logs/session_log_*.txt

# View state
cat paper_trading/state/trading_state_*.json | jq .
```

## Configuration Quick Reference

```yaml
# Paper mode (safe, default)
trading_mode:
  mode: "paper"

# Live mode (real money)
trading_mode:
  mode: "live"
  live_settings:
    product_type: "INTRADAY"      # MIS
    order_type: "MARKET"          # Market orders
    max_order_value: 50000        # ₹50k max per order
    max_daily_loss: 10000         # Stop at ₹10k loss
    require_confirmation: true    # Require user confirmation
```

---

**Remember:** Live mode executes real orders with real money. Always test in paper mode first!
