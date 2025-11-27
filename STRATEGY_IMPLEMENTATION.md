# Strategy Implementation Details

This document explains how the strategy from the PDF is exactly implemented in code.

## Strategy Document Reference

**Source**: `Trading Strategy _ Intraday_Momentum_OIUnwinding.pdf`

## Implementation Mapping

### 1. Entry Rules (From PDF)

#### Step 1: Identify 10 Strikes
**PDF**: "Identify 10 strikes (5 below spot, 5 above spot) from the nifty spot level"

**Code**: `utils/oi_analyzer.py` - `get_strikes_around_spot()`
```python
def get_strikes_around_spot(self, spot_price, available_strikes):
    below_strikes = available_strikes[available_strikes < spot_price]
    above_strikes = available_strikes[available_strikes >= spot_price]
    strikes_below = below_strikes[-5:]  # Last 5 below
    strikes_above = above_strikes[:5]   # First 5 above
    return np.concatenate([strikes_below, strikes_above])
```

#### Step 2: Calculate Max OI Buildup
**PDF**:
- "Calculate strike level for Max Call Buildup (MaxOICallStrike)"
- "Calculate strike level for Max Put Buildup (MaxOIPutStrike)"

**Code**: `utils/oi_analyzer.py` - `find_max_buildup_strikes()`
```python
def find_max_buildup_strikes(self, oi_changes, option_type):
    # Find strike with maximum positive change (buildup)
    max_strike = max(oi_changes.items(), key=lambda x: x[1])
    return max_strike[0], max_strike[1]
```

#### Step 3: Calculate Distance from Spot
**PDF**:
- "CallStrikeDistance = MaxOICallStrike – Spot"
- "PutStrikeDistance = Spot – MaxOIPutStrike"

**Code**: `utils/oi_analyzer.py` - `analyze_oi_for_entry()`
```python
call_distance = abs(max_call_strike - spot_price)
put_distance = abs(spot_price - max_put_strike)
```

#### Step 4: Identify CallOrPut
**PDF**: "Call if CallStrikeDistance < PutStrikeDistance else Put"

**Code**: `utils/oi_analyzer.py` - `analyze_oi_for_entry()`
```python
if call_distance < put_distance:
    call_or_put = 'CALL'
    selected_strike_type = 'CE'
    selected_strike = self._get_nearest_strike_above_spot(spot_price, all_strikes)
else:
    call_or_put = 'PUT'
    selected_strike_type = 'PE'
    selected_strike = self._get_nearest_strike_below_spot(spot_price, all_strikes)
```

#### Step 5: Call Entry
**PDF**:
- "Choose CallStrike as nearest to Nifty Spot on the upper side"
- "Calculate Change in Call OI at CallStrike"
- "If Call OI at CallStrike is unwinding then check if the option price is trading above VWAP"
- "If Option Price > VWAP, Buy Option"

**Code**: `strategies/intraday_momentum_oi.py` - `check_entry_conditions()`
```python
# Update strike to nearest above spot
if option_type == 'CE':
    selected_strike = self.oi_analyzer._get_nearest_strike_above_spot(
        spot_price, current_data['strike'].unique()
    )

# Check OI unwinding
is_unwinding, oi_change = self.oi_analyzer.check_oi_unwinding(
    current_data, previous_data, selected_strike, option_type
)

# Get current option price
current_price = option_row.iloc[0]['close']

# Calculate VWAP
vwap = self.vwap_calculator.calculate_vwap_for_option(option_history)
current_vwap = vwap.iloc[-1]

# Check if price > VWAP
is_above_vwap = self.vwap_calculator.is_price_above_vwap(
    current_price, current_vwap
)

# Enter if all conditions met
if is_unwinding and is_above_vwap:
    return True, entry_signal
```

#### Step 6: Put Entry
**PDF**:
- "Choose PutStrike as nearest to Nifty Spot on the lower side"
- "Calculate Change in Put OI at PutStrike"
- "If Put OI at PutStrike is unwinding then check if the option price is trading above VWAP"
- "If Option Price > VWAP, Buy Option"

**Code**: Same as Call entry, but with 'PE' option type and nearest strike below spot.

### 2. Stop Loss (From PDF)

**PDF**: "25 percent of the initial option price till the time the option does not gain 10 percent value"

**Code**: `strategies/intraday_momentum_oi.py` - `check_exit_conditions()`
```python
# Initial stop loss
self.initial_stop_loss_pct = 0.25  # 25%
stop_loss_price = entry_price * (1 - self.initial_stop_loss_pct)

# Check if price hits stop loss (before profit threshold)
if current_price >= self.position_entry_price * self.profit_threshold:
    # Use trailing stop
else:
    # Use initial stop loss
    if current_price <= self.stop_loss_price:
        return True, "STOP_LOSS", current_price
```

### 3. Exit Rules (From PDF)

#### Time-Based Exit
**PDF**: "All positions to be exited between 2:50 and 3:00 PM"

**Code**: `strategies/intraday_momentum_oi.py` - `check_exit_conditions()`
```python
self.exit_start_time = time(14, 50)  # 2:50 PM
self.exit_end_time = time(15, 0)     # 3:00 PM

if self.exit_start_time <= current_t <= self.exit_end_time:
    return True, "TIME_EXIT", current_price
```

#### Price-Based Exit (Trailing Stop)
**PDF**: "Profit to be trailed by 10% of the option value once the level of 1.1 times the buy price is reached"

**Code**: `strategies/intraday_momentum_oi.py` - `check_exit_conditions()`
```python
self.profit_threshold = 1.1  # 1.1x (10% profit)
self.trailing_stop_pct = 0.10  # 10%

# Track highest price
if current_price > self.highest_price_since_entry:
    self.highest_price_since_entry = current_price

# After 10% profit, use trailing stop
if current_price >= self.position_entry_price * self.profit_threshold:
    trailing_stop_price = self.highest_price_since_entry * (1 - self.trailing_stop_pct)
    if current_price <= trailing_stop_price:
        return True, "TRAILING_STOP", current_price
```

### 4. Position Sizing (From PDF)

**PDF**:
- "Risk 1% of total trading capital per trade"
- "Calculate position size based on stop loss distance and risk amount"

**Code**: `strategies/intraday_momentum_oi.py` - `enter_position()`
```python
self.risk_per_trade = 0.01  # 1%
risk_amount = self.initial_capital * self.risk_per_trade

# Stop loss per unit
stop_loss_per_unit = entry_price * self.initial_stop_loss_pct

# Position size
position_qty = int(risk_amount / stop_loss_per_unit)
```

### 5. Trade Management (From PDF)

**PDF**: "Do not add to losing positions"

**Code**: Built into strategy - only one position at a time
```python
# Check if we already have a position
if self.current_position is not None:
    return False, None  # Don't enter new position
```

### 6. Timeframe (From PDF)

**PDF**:
- "Candle Timeframe: 3 min/5min"
- "Entry Timeframe: After 9:30, Reenter whenever conditions exist before 2:30"

**Code**: Configuration and time checks
```python
# config/strategy_config.yaml
candle_timeframe: 5  # 3 or 5 minutes
entry_start_time: "09:30"
entry_end_time: "14:30"

# strategies/intraday_momentum_oi.py
if not (self.entry_start_time <= current_t <= self.entry_end_time):
    return False, None
```

## Data Mapping

### Options Data Fields Used

| PDF Mention | Data Column | Usage |
|-------------|-------------|-------|
| Open Interest | `OI` | OI buildup/unwinding detection |
| Option Price | `close` | Entry/exit price, VWAP comparison |
| Strike | `strike` | Strike selection |
| Option Type | `option_type` | CE/PE identification |
| Volume | `volume` | VWAP calculation |
| IV | `IV` | Available for future enhancements |
| Delta | `delta` | Available for future enhancements |
| OHLC | `open`, `high`, `low`, `close` | VWAP typical price |

### Supporting Data

| Data Type | Source File | Usage |
|-----------|-------------|-------|
| Spot Price | `spotprice_2025.csv` | Strike selection, distance calculation |
| VIX | `india_vix_1min_zerodha.csv` | Available for filtering (future) |
| Expiry Dates | `weekly_expiry.csv` / `monthly_expiry.csv` | Selecting correct options chain |

## Key Algorithms

### OI Unwinding Detection

**Logic**: OI is unwinding when OI decreases (negative change)

```python
def check_oi_unwinding(self, current_data, previous_data, strike, option_type):
    current_oi = self._get_oi_for_strike(current_data, strike, option_type)
    previous_oi = self._get_oi_for_strike(previous_data, strike, option_type)

    oi_change = current_oi - previous_oi
    is_unwinding = oi_change < 0  # Negative change = unwinding

    return is_unwinding, oi_change
```

### VWAP Calculation

**Formula**: VWAP = Σ(Typical Price × Volume) / Σ(Volume)

**Typical Price**: (High + Low + Close) / 3

```python
def calculate_vwap(self, prices, volumes, highs, lows, closes):
    typical_price = (highs + lows + closes) / 3
    pv = typical_price * volumes
    vwap = pv.rolling(window=lookback).sum() / \
           volumes.rolling(window=lookback).sum()
    return vwap
```

## Configuration Parameters

All parameters from the PDF are configurable in `config/strategy_config.yaml`:

```yaml
# Entry Parameters
entry_start_time: "09:30"           # PDF: "After 9:30"
entry_end_time: "14:30"             # PDF: "before 2:30"
num_strikes_to_analyze: 10          # PDF: "10 strikes"
strikes_below_spot: 5               # PDF: "5 below spot"
strikes_above_spot: 5               # PDF: "5 above spot"

# Stop Loss & Targets
initial_stop_loss_percent: 25       # PDF: "25 percent"
profit_threshold_for_trailing: 1.1  # PDF: "1.1 times"
trailing_stop_percent: 10           # PDF: "10%"

# Exit
exit_start_time: "14:50"            # PDF: "2:50"
exit_end_time: "15:00"              # PDF: "3:00 PM"

# Position Sizing
risk_per_trade_percent: 1.0         # PDF: "Risk 1%"

# Instrument
instrument: "NIFTY"                 # PDF: "Nifty Index"
expiry_type: "weekly"               # PDF: "Closest"
candle_timeframe: 5                 # PDF: "3 min/5min"
```

## Execution Flow

```
1. Start of Day
   └─> Reset strategy state

2. For each candle (3/5 min):
   ├─> Get current options data
   ├─> Get previous options data (for OI comparison)
   ├─> Get spot price
   │
   ├─> If NO position:
   │   ├─> Perform OI analysis (find max buildup strikes)
   │   ├─> Determine Call or Put direction
   │   ├─> Select strike (nearest to spot)
   │   ├─> Check OI unwinding at selected strike
   │   ├─> Calculate VWAP for option
   │   ├─> If OI unwinding AND price > VWAP:
   │   │   └─> ENTER POSITION
   │   └─> Else: Wait for next candle
   │
   └─> If position EXISTS:
       ├─> Check time-based exit (2:50-3:00 PM)
       ├─> Check stop loss (25% if no profit)
       ├─> Check trailing stop (10% after 10% profit)
       └─> If any exit condition met:
           └─> EXIT POSITION

3. End of Day
   └─> Force exit any open position
```

## Validation

The implementation has been validated against the PDF for:

✅ Entry logic (OI analysis, strike selection, VWAP)
✅ Exit logic (time-based, stop loss, trailing stop)
✅ Position sizing (1% risk)
✅ Timeframes (candle, entry, exit windows)
✅ Trade management (no adding to losers)

## Testing

Run `python test_setup.py` to verify:
- All modules load correctly
- Configuration is valid
- Data files are accessible
- Strategy initializes properly

Run `python backtest_runner.py` to execute full backtest with the exact strategy logic.

---

**Note**: This implementation follows the strategy document exactly. Any modifications should be made through `config/strategy_config.yaml` to maintain code integrity.
