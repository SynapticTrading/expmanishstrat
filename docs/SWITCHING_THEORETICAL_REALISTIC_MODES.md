# Switching Between Theoretical and Realistic Execution Modes

## Overview

This document provides step-by-step instructions for switching between **Theoretical** (perfect -25% stops) and **Realistic** (n+1 execution with slippage) modes.

---

## Quick Summary

| Aspect | Theoretical Mode | Realistic Mode |
|--------|------------------|----------------|
| **Stop Loss %** | Exactly -25.00% | -21% to -60% (varies) |
| **Slippage** | 0.0 (none) | 0.001 (0.1%) or higher |
| **Exit Price** | Uses stop loss price | Uses actual next bar price |
| **Use Case** | Strategy development, parameter tuning | Pre-live testing, risk assessment |
| **P&L** | Higher (optimistic) | Lower (realistic) |

---

## Mode 1: Theoretical Execution (Perfect -25% Stops)

### What It Does:
- When stop loss is triggered, uses the **theoretical stop loss price** for P&L calculation
- Results in perfect -25.00% losses
- Ignores Backtrader's n+1 execution delay
- Optimistic performance metrics

### Step-by-Step Configuration:

#### **Step 1: Set Slippage to 0.0**

**File:** `config/strategy_config.yaml`

**Line 51:**
```yaml
# Backtesting Configuration
backtest:
  commission: 0.0005  # 0.05% commission per trade
  slippage: 0.0  # 0% slippage - removed for theoretical testing
```

#### **Step 2: Enable Theoretical Price Override**

**File:** `strategies/intraday_momentum_oi.py`

**Lines 164-171:**
```python
                    if option_data is not None:
                        # Use theoretical exit price if stop was triggered, else use actual execution price
                        if 'stop_loss_triggered_price' in pos_info:
                            # Cap at stop loss price (strict 25% stop)
                            option_exit_price = pos_info['stop_loss']
                        elif 'trailing_stop_triggered_price' in pos_info:
                            # Use trailing stop price
                            option_exit_price = pos_info['trailing_stop']
                        else:
                            option_exit_price = option_data['close']

                        # Calculate P&L based on OPTION prices
```

#### **Step 3: Store Triggered Prices in Stop Loss Logic**

**File:** `strategies/intraday_momentum_oi.py`

**Lines 530-535 (Stop Loss):**
```python
        # ALWAYS check initial stop loss first (for long positions, trigger when price goes DOWN)
        if current_price <= pos_info['stop_loss']:
            self.log(f'🛑 STOP LOSS HIT: {pos_info["option_type"]} {pos_info["strike"]} - '
                    f'Current: ₹{current_price:.2f}, Stop: ₹{pos_info["stop_loss"]:.2f}')
            # Store the theoretical exit price (stop loss price) for accurate P&L calculation
            pos_info['stop_loss_triggered_price'] = current_price
            self.close()
            self.pending_exit = True  # Mark that we have a pending exit
            return  # Exit immediately, don't process more positions
```

**Lines 549-554 (Trailing Stop):**
```python
            # Check trailing stop (for longs: exit if price drops back down)
            if current_price <= trailing_stop:
                self.log(f'📉 TRAILING STOP HIT: {pos_info["option_type"]} {pos_info["strike"]} - '
                        f'Current: ₹{current_price:.2f}, Trailing Stop: ₹{trailing_stop:.2f}')
                # Store the theoretical exit price for accurate P&L calculation
                pos_info['trailing_stop_triggered_price'] = current_price
                self.close()
                self.pending_exit = True  # Mark that we have a pending exit
                return  # Exit immediately, don't process more positions
```

---

## Mode 2: Realistic Execution (n+1 Execution with Slippage)

### What It Does:
- Uses **actual next bar execution price** for P&L calculation
- Includes slippage configuration
- Stop losses vary from -21% to -60% depending on market gaps
- Realistic performance metrics that match live trading

### Step-by-Step Configuration:

#### **Step 1: Enable Slippage**

**File:** `config/strategy_config.yaml`

**Line 51:**
```yaml
# Backtesting Configuration
backtest:
  commission: 0.0005  # 0.05% commission per trade
  slippage: 0.001  # 0.1% slippage - realistic execution
```

**Slippage Guidelines:**
- **0.001 (0.1%)**: Very liquid markets, limit orders
- **0.005 (0.5%)**: Moderately liquid, market orders
- **0.01 (1.0%)**: Fast-moving markets, panic exits

#### **Step 2: Remove Theoretical Price Override**

**File:** `strategies/intraday_momentum_oi.py`

**Lines 164-168:**
```python
                    if option_data is not None:
                        # Use actual execution price (realistic - includes n+1 bar execution delay)
                        option_exit_price = option_data['close']

                        # Calculate P&L based on OPTION prices
```

**Remove these lines (166-171 from theoretical mode):**
```python
# DELETE THIS BLOCK:
if 'stop_loss_triggered_price' in pos_info:
    option_exit_price = pos_info['stop_loss']
elif 'trailing_stop_triggered_price' in pos_info:
    option_exit_price = pos_info['trailing_stop']
else:
    option_exit_price = option_data['close']
```

#### **Step 3: Remove Triggered Price Storage**

**File:** `strategies/intraday_momentum_oi.py`

**Lines 530-535 (Stop Loss):**
```python
        # ALWAYS check initial stop loss first (for long positions, trigger when price goes DOWN)
        if current_price <= pos_info['stop_loss']:
            self.log(f'🛑 STOP LOSS HIT: {pos_info["option_type"]} {pos_info["strike"]} - '
                    f'Current: ₹{current_price:.2f}, Stop: ₹{pos_info["stop_loss"]:.2f}')
            # REMOVED: pos_info['stop_loss_triggered_price'] = current_price
            self.close()
            self.pending_exit = True  # Mark that we have a pending exit
            return  # Exit immediately, don't process more positions
```

**Lines 549-554 (Trailing Stop):**
```python
            # Check trailing stop (for longs: exit if price drops back down)
            if current_price <= trailing_stop:
                self.log(f'📉 TRAILING STOP HIT: {pos_info["option_type"]} {pos_info["strike"]} - '
                        f'Current: ₹{current_price:.2f}, Trailing Stop: ₹{trailing_stop:.2f}')
                # REMOVED: pos_info['trailing_stop_triggered_price'] = current_price
                self.close()
                self.pending_exit = True  # Mark that we have a pending exit
                return  # Exit immediately, don't process more positions
```

---

## Complete Code Changes Side-by-Side

### Change 1: Config File

**File:** `config/strategy_config.yaml` (Line 51)

```yaml
# THEORETICAL MODE:
slippage: 0.0  # 0% slippage - removed for theoretical testing

# REALISTIC MODE:
slippage: 0.001  # 0.1% slippage - realistic execution
```

---

### Change 2: Exit Price Logic

**File:** `strategies/intraday_momentum_oi.py` (Lines 164-173)

```python
# ==================== THEORETICAL MODE ====================
if option_data is not None:
    # Use theoretical exit price if stop was triggered, else use actual execution price
    if 'stop_loss_triggered_price' in pos_info:
        # Cap at stop loss price (strict 25% stop)
        option_exit_price = pos_info['stop_loss']
    elif 'trailing_stop_triggered_price' in pos_info:
        # Use trailing stop price
        option_exit_price = pos_info['trailing_stop']
    else:
        option_exit_price = option_data['close']

    # Calculate P&L based on OPTION prices


# ==================== REALISTIC MODE ====================
if option_data is not None:
    # Use actual execution price (realistic - includes n+1 bar execution delay)
    option_exit_price = option_data['close']

    # Calculate P&L based on OPTION prices
```

---

### Change 3: Stop Loss Trigger Storage

**File:** `strategies/intraday_momentum_oi.py` (Lines 530-535)

```python
# ==================== THEORETICAL MODE ====================
# ALWAYS check initial stop loss first (for long positions, trigger when price goes DOWN)
if current_price <= pos_info['stop_loss']:
    self.log(f'🛑 STOP LOSS HIT: {pos_info["option_type"]} {pos_info["strike"]} - '
            f'Current: ₹{current_price:.2f}, Stop: ₹{pos_info["stop_loss"]:.2f}')
    # Store the theoretical exit price (stop loss price) for accurate P&L calculation
    pos_info['stop_loss_triggered_price'] = current_price  # <-- ADD THIS LINE
    self.close()
    self.pending_exit = True
    return


# ==================== REALISTIC MODE ====================
# ALWAYS check initial stop loss first (for long positions, trigger when price goes DOWN)
if current_price <= pos_info['stop_loss']:
    self.log(f'🛑 STOP LOSS HIT: {pos_info["option_type"]} {pos_info["strike"]} - '
            f'Current: ₹{current_price:.2f}, Stop: ₹{pos_info["stop_loss"]:.2f}')
    # REMOVED: pos_info['stop_loss_triggered_price'] = current_price
    self.close()
    self.pending_exit = True
    return
```

---

### Change 4: Trailing Stop Trigger Storage

**File:** `strategies/intraday_momentum_oi.py` (Lines 549-554)

```python
# ==================== THEORETICAL MODE ====================
# Check trailing stop (for longs: exit if price drops back down)
if current_price <= trailing_stop:
    self.log(f'📉 TRAILING STOP HIT: {pos_info["option_type"]} {pos_info["strike"]} - '
            f'Current: ₹{current_price:.2f}, Trailing Stop: ₹{trailing_stop:.2f}')
    # Store the theoretical exit price for accurate P&L calculation
    pos_info['trailing_stop_triggered_price'] = current_price  # <-- ADD THIS LINE
    self.close()
    self.pending_exit = True
    return


# ==================== REALISTIC MODE ====================
# Check trailing stop (for longs: exit if price drops back down)
if current_price <= trailing_stop:
    self.log(f'📉 TRAILING STOP HIT: {pos_info["option_type"]} {pos_info["strike"]} - '
            f'Current: ₹{current_price:.2f}, Trailing Stop: ₹{trailing_stop:.2f}')
    # REMOVED: pos_info['trailing_stop_triggered_price'] = current_price
    self.close()
    self.pending_exit = True
    return
```

---

## Quick Switch Commands

### To Switch to Theoretical Mode:

```bash
# 1. Update config
sed -i '' 's/slippage: 0.001/slippage: 0.0/g' config/strategy_config.yaml

# 2. Add theoretical price logic (manual edit required in strategies/intraday_momentum_oi.py)
# - Add the if/elif/else block for theoretical prices (lines 166-171)
# - Add pos_info['stop_loss_triggered_price'] = current_price (line 536)
# - Add pos_info['trailing_stop_triggered_price'] = current_price (line 553)

# 3. Run backtest
./run_backtest.sh
```

### To Switch to Realistic Mode:

```bash
# 1. Update config
sed -i '' 's/slippage: 0.0/slippage: 0.001/g' config/strategy_config.yaml

# 2. Remove theoretical price logic (manual edit required in strategies/intraday_momentum_oi.py)
# - Remove the if/elif/else block, keep only: option_exit_price = option_data['close']
# - Remove pos_info['stop_loss_triggered_price'] = current_price (line 536)
# - Remove pos_info['trailing_stop_triggered_price'] = current_price (line 553)

# 3. Run backtest
./run_backtest.sh
```

---

## Verification Checklist

### After Switching to Theoretical Mode:

✅ `slippage: 0.0` in config
✅ Theoretical price override logic present (lines 166-171)
✅ `pos_info['stop_loss_triggered_price']` stored on stop loss hit
✅ `pos_info['trailing_stop_triggered_price']` stored on trailing stop hit
✅ Run backtest and verify: **All stop losses at exactly -25.00%**

### After Switching to Realistic Mode:

✅ `slippage: 0.001` (or higher) in config
✅ Only `option_exit_price = option_data['close']` (no if/elif logic)
✅ NO storage of triggered prices
✅ Run backtest and verify: **Stop losses vary from -21% to -60%**

---

## Performance Comparison

Based on 275 trades over 10 months (Jan-Oct 2025):

| Metric | Theoretical | Realistic | Difference |
|--------|-------------|-----------|------------|
| **Total Return** | ₹903 (+0.90%) | ₹101 (+0.10%) | **-89%** |
| **Average P&L** | ₹3.28 | ₹0.37 | **-89%** |
| **Average P&L%** | 6.41% | 2.47% | **-61%** |
| **Worst Trade** | -₹84.95 | -₹91.35 | **-8%** |
| **Sharpe Ratio** | 2.35 | 0.85 | **-64%** |
| **Max Drawdown** | -0.30% | -0.47% | **+57%** |
| **Win Rate** | 44.36% | 43.64% | **-2%** |

**Key Takeaway:** Realistic execution shows **8.9x worse returns** due to slippage and n+1 execution delays.

---

## When to Use Each Mode

### Use Theoretical Mode When:

1. **Developing Strategy Logic**
   - Testing if stop loss logic works correctly
   - Debugging entry/exit conditions
   - Isolating strategy bugs from execution effects

2. **Parameter Optimization**
   - Finding optimal stop loss percentage
   - Testing different profit thresholds
   - Comparing entry timing strategies

3. **Strategy Comparison**
   - A/B testing different strategies
   - Eliminating slippage noise from comparisons
   - Understanding pure strategy performance

### Use Realistic Mode When:

1. **Pre-Live Testing**
   - Final validation before deploying live
   - Understanding worst-case scenarios
   - Setting realistic profit expectations

2. **Risk Assessment**
   - Calculating maximum possible losses
   - Stress testing the strategy
   - Determining appropriate position sizing

3. **Capital Allocation**
   - Deciding how much capital to deploy
   - Setting stop loss budgets
   - Planning for drawdown scenarios

4. **Broker/Execution Comparison**
   - Testing different slippage values
   - Simulating different execution quality
   - Choosing between brokers

---

## Recommended Workflow

```
Phase 1: Strategy Development (Theoretical Mode)
├── Develop entry/exit logic
├── Test stop loss mechanics
├── Optimize parameters
└── Compare strategy variations

Phase 2: Validation (Realistic Mode - 0.1% slippage)
├── Run realistic backtest
├── Verify risk metrics
├── Assess worst-case losses
└── Adjust position sizes if needed

Phase 3: Stress Testing (Realistic Mode - 1% slippage)
├── Test extreme slippage scenarios
├── Verify strategy still profitable
├── Calculate maximum risk exposure
└── Document failure modes

Phase 4: Live Deployment
├── Start with small position size
├── Monitor actual slippage vs backtest
├── Adjust slippage config based on real data
└── Scale up gradually
```

---

## Troubleshooting

### Problem: Stop losses still at -25% after switching to realistic mode

**Solution:**
- Verify slippage is NOT 0.0 in config
- Check that theoretical price override block is removed
- Ensure triggered price storage lines are removed
- Re-run backtest with `./run_backtest.sh`

### Problem: Stop losses exceed -50% in realistic mode

**Solution:**
- This is normal for same-day expiry options in fast markets
- Consider avoiding same-day expiry: `avoid_same_day_expiry: true` in config
- Use tighter stop loss: Change `initial_stop_loss_pct: 0.25` to `0.20`
- Use 1-minute bars instead of 5-minute bars for faster detection

### Problem: Returns too low in realistic mode

**Solution:**
- This is expected - realistic mode shows true performance
- Consider:
  - Optimizing entry timing
  - Using finer timeframes (1-min bars)
  - Tighter profit thresholds
  - Different strikes (closer to ATM)
  - Filtering for high-volume days only

---

## Summary

**Theoretical Mode**: 3 code changes (1 config + 2 strategy file edits)
**Realistic Mode**: 3 code changes (1 config + 2 strategy file edits)

Both modes are now correctly implemented and verified. Use theoretical for development, realistic for pre-live validation.
