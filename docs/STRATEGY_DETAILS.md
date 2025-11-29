# Strategy Implementation Details

## Overview

This document provides detailed information about the Intraday Momentum OI Unwinding Strategy implementation.

## Strategy Workflow

### Phase 1: Daily Market Analysis (Once per day)

**Timing**: At market open (first bar of the day after 9:15 AM)

**Steps**:
1. Get current spot price
2. Identify closest weekly expiry
3. Select 10 strikes around spot (5 above, 5 below)
4. For each strike, fetch current OI data
5. Calculate:
   - Max Call OI buildup strike
   - Max Put OI buildup strike
   - Distance from spot for each
6. Determine direction:
   - If Call buildup closer → Direction = CALL
   - If Put buildup closer → Direction = PUT
7. Select trading strike:
   - CALL direction: Nearest strike ≥ spot
   - PUT direction: Nearest strike < spot

**Output**: Direction (CALL/PUT), Strike, Expiry for the day

### Phase 2: Entry Signal Generation (9:30 AM - 2:30 PM IST)

**Conditions** (all must be TRUE):

1. **Within entry window**: 9:30 AM - 2:30 PM IST
2. **Position availability**: Active trades < max_positions (default: 3)
3. **OI Unwinding**:
   - Current OI < Previous OI (for selected strike)
   - Indicates short covering (for Calls) or long unwinding (for Puts)
4. **Price above VWAP**:
   - Option close price > VWAP (anchored to day open)
   - Confirms momentum in the unwinding direction

**Action**: BUY option (CE or PE based on direction)

**Position Tracking**:
- Store entry price
- Set initial stop loss: Entry price × (1 - 0.25) = 75% of entry
- Initialize highest price tracker

### Phase 3: Position Management (During market hours)

**Continuous monitoring of each open position**:

#### A. Initial Stop Loss (Before profit threshold)
- **Trigger**: Current price ≤ Stop loss price
- **Stop Loss**: 25% below entry price
- **Action**: Close position immediately

#### B. Profit Threshold Check
- **Threshold**: Price reaches 110% of entry (10% profit)
- **Action**: Activate trailing stop mechanism

#### C. Trailing Stop (After profit threshold reached)
- **Calculation**: Highest price × (1 - 0.10) = 90% of highest
- **Update**: Recalculated whenever price makes new high
- **Trigger**: Current price ≤ Trailing stop
- **Action**: Close position to lock profits

#### D. Time-based Management
- **At 2:50 PM IST**: Start preparing to close
- **By 3:00 PM IST**: Force close all positions
- **Reason**: Avoid overnight risk, this is an intraday strategy

### Phase 4: Exit Execution

**Exit scenarios**:

1. **Stop Loss Hit**: Close at market
2. **Trailing Stop Hit**: Close at market
3. **End of Day**: Close all positions at market (2:50-3:00 PM)

**Position Cleanup**:
- Log trade details (entry/exit time, price, PnL)
- Remove from active positions
- Decrement active trade counter

## Technical Implementation

### Data Handling

#### Spot Price Data
- **Format**: 1-minute OHLCV bars
- **Timezone**: IST (Asia/Kolkata)
- **Feed**: Backtrader PandasData feed
- **Usage**: Main data feed for strategy timing

#### Options Data
- **Format**: 1-minute OHLCV + OI data
- **Structure**: Separate rows for each strike/type/timestamp
- **Access**: Via OIAnalyzer class (not directly fed to Backtrader)
- **Reason**: Options data structure doesn't fit standard Backtrader feed

### OI Analysis Module (`src/oi_analyzer.py`)

**Key Methods**:

```python
get_strikes_near_spot(spot, timestamp, expiry, num_above, num_below)
# Returns: DataFrame of options near spot, list of strikes

calculate_max_oi_buildup(options_df, spot)
# Returns: max_call_strike, max_put_strike, call_distance, put_distance

determine_direction(call_distance, put_distance)
# Returns: 'CALL' or 'PUT'

calculate_oi_change(strike, option_type, timestamp, expiry)
# Returns: current_oi, oi_change, oi_change_pct

is_unwinding(oi_change)
# Returns: True if OI is decreasing
```

**OI History Tracking**:
- Maintains dictionary: `{strike_type_expiry: latest_oi}`
- Updated on each OI query
- Used to calculate change from previous bar

### VWAP Calculation

**Anchored to market open**:
```python
typical_price = (high + low + close) / 3
cumulative_tpv = Σ(typical_price × volume)
cumulative_volume = Σ(volume)
VWAP = cumulative_tpv / cumulative_volume
```

**Reset**: Every day at market open (9:15 AM IST)

**Fallback**: If volume is zero, use volume = 1 to avoid division by zero

### Position Sizing

**Current Implementation**: Fixed lot size (1 lot default)

**Future Enhancement** (configurable in strategy):
```python
risk_amount = capital × risk_per_trade_pct
position_size = risk_amount / (entry_price × stop_loss_pct)
```

## Risk Management Features

### 1. Maximum Concurrent Positions
- **Limit**: 3 positions (configurable)
- **Purpose**: Prevent over-exposure
- **Enforcement**: Check before each entry

### 2. Stop Loss Mechanism
- **Type**: Percentage-based
- **Initial**: 25% of entry price
- **Transition**: Switches to trailing after 10% profit
- **Execution**: Checked on every bar

### 3. Trailing Stop
- **Activation**: After 10% profit
- **Trail**: 10% from highest price
- **Dynamic**: Adjusts upward only (never downward)

### 4. Time-based Risk Control
- **Entry cutoff**: 2:30 PM (no new entries after)
- **Exit enforcement**: All positions closed by 3:00 PM
- **Purpose**: Avoid illiquidity and overnight risk

### 5. Day-of-Week Filter (Optional)
- **Setting**: `avoid_monday_tuesday: true`
- **Rationale**: Monday/Tuesday are close to weekly expiry
- **Behavior**: Skip trading on these days

## Performance Metrics

### Calculated Metrics

1. **Return Metrics**:
   - Total Return (₹)
   - Total Return (%)
   - Average PnL per trade

2. **Win Rate**:
   - Number of winning trades
   - Number of losing trades
   - Win rate percentage

3. **Risk Metrics**:
   - Sharpe Ratio (annualized)
   - Maximum Drawdown (₹)
   - Maximum Drawdown (%)
   - Profit Factor (gross profit / gross loss)

4. **Trade Quality**:
   - Best trade
   - Worst trade
   - Average holding period

### Report Generation

**JSON Metrics**: Machine-readable performance data

**CSV Trade Log**: Detailed trade-by-trade breakdown

**Visualizations**:
- Equity curve with drawdown
- Trade PnL distribution
- Win/loss pie chart
- Cumulative PnL progression

## Configuration System

**YAML-based**: `config/strategy_config.yaml`

**Structure**:
```yaml
strategy: {...}        # Strategy metadata
data: {...}           # Data sources and dates
market: {...}         # Market specifications
entry: {...}          # Entry parameters
exit: {...}           # Exit rules
position_sizing: {...} # Capital and sizing
risk_management: {...} # Risk controls
backtest: {...}       # Backtest settings
reporting: {...}      # Output configuration
```

**Flexibility**: All parameters can be changed without code modification

## Backtrader Integration

### Cerebro Setup

```python
cerebro = bt.Cerebro()
cerebro.adddata(spot_feed)         # Spot price feed
cerebro.addstrategy(IntradayMomentumOI, ...)  # Strategy
cerebro.broker.setcash(100000)     # Initial capital
cerebro.broker.setcommission(0.0005)  # 0.05% commission
cerebro.addanalyzer(...)           # Various analyzers
results = cerebro.run()            # Execute backtest
```

### Strategy Methods

**Lifecycle**:
1. `__init__()`: Initialize indicators and variables
2. `next()`: Called on each bar (main logic)
3. `notify_order()`: Handle order fills
4. `notify_trade()`: Handle trade completion
5. `stop()`: Cleanup and final reporting

### Order Management

**Order Types Used**:
- Market orders only (for simplicity and slippage simulation)

**Order Flow**:
1. Strategy generates signal
2. `self.buy()` or `self.close()` called
3. Order submitted to broker
4. Broker executes (with commission/slippage)
5. `notify_order()` called with execution details

## Assumptions and Simplifications

### 1. Simplified Option Price Tracking
- Strategy uses spot price as proxy for position value in stop loss calculations
- Real implementation would track actual option price

### 2. Market Orders
- All orders are market orders
- Real trading would use limit orders for better fills

### 3. Liquidity Assumption
- Assumes all orders fill immediately
- Real market may have slippage and partial fills

### 4. Commission Model
- Flat percentage commission
- Real brokerage may have tiered or per-lot fees

### 5. Data Gaps
- Assumes clean, continuous data
- Real data may have gaps or errors

## Extensibility

### Adding New Entry Signals

Modify `check_entry_conditions()` in strategy:

```python
def check_entry_conditions(self, dt):
    # Existing checks...
    
    # Add custom condition
    if my_custom_indicator > threshold:
        return option_price
    
    return None
```

### Adding New Indicators

Create in `src/indicators.py`:

```python
class MyIndicator(bt.Indicator):
    lines = ('signal',)
    params = (('period', 14),)
    
    def __init__(self):
        # Initialize
        pass
    
    def next(self):
        # Calculate on each bar
        self.lines.signal[0] = calculation
```

### Custom Exit Rules

Modify `manage_positions()` in strategy:

```python
def manage_positions(self, dt):
    # Existing management...
    
    # Add custom exit
    if custom_exit_condition:
        self.close()
```

## Validation and Testing

### Data Validation
- Check timezone consistency
- Verify OI data completeness
- Ensure date ranges match

### Strategy Validation
- Test with small date range first
- Verify entry signals are generated
- Check exit logic is working
- Validate position sizing

### Performance Validation
- Compare metrics across different periods
- Test sensitivity to parameters
- Validate against expected behavior

## Known Limitations

1. **Memory Usage**: Large options file (2GB) requires significant RAM
2. **Processing Time**: 1-minute data for 10 months takes time to process
3. **OI Data Dependency**: Strategy requires high-quality OI data
4. **Simplified Execution**: Assumes perfect fills at mid-price

## Future Enhancements

- [ ] Real-time option price tracking in position management
- [ ] Dynamic position sizing based on risk
- [ ] Multiple expiry handling
- [ ] Greeks-based entry/exit
- [ ] Machine learning for OI pattern recognition
- [ ] Walk-forward optimization
- [ ] Multi-instrument support (BankNifty, FinNifty)

---

**Version**: 1.0.0  
**Last Updated**: 2025-01-27

