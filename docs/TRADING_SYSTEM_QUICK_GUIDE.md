# Trading System Quick Guide

**Paper & Live Trading - Essential Architecture**

---

## The System

### Dual-Loop Design

**Loop 1: Strategy (Every 5 Minutes)**
- Fetch 5-min OHLCV candles
- Check OI unwinding + VWAP conditions
- Make entry decisions

**Loop 2: Exit Monitor (Every 1 Minute)**
- Fetch real-time LTP
- Check all stop losses
- Exit immediately when hit

**Why?** Entry needs VWAP (requires candles). Exit needs more granularity than 5-min (LTP every minute).

---

## Paper vs Live

| | Paper | Live |
|-|-------|------|
| **Data** | Real from broker | Real from broker |
| **Execution** | Simulated | Real orders |
| **Order ID** | PAPER_20251223_001 | 250123000001 |
| **Risk** | Zero | Real money |

**Same logic, different execution**

---

## Example Trade Flow

### 9:30 AM - Entry

**Strategy Loop:**
- 21750 CE at ₹150
- OI unwinding: -8.5% ✓
- Price > VWAP ✓
- **ENTER**

**Execution:**
- Paper: Simulate BUY at ₹150
- Live: Market order, fill at ₹150.50

**Position:**
```
Entry: ₹150
Stop: ₹112.50 (25%)
Trailing: Not active
```

### 9:34 AM - Trailing Activates

**LTP Loop (1-min check):**
- LTP = ₹165
- Profit = 10%
- Trailing stop = ₹148.50 (10% below)

### 9:41 AM - New Peak

**LTP Loop (1-min check):**
- LTP = ₹178
- New trailing stop = ₹160.20

**Position:**
```
Peak: ₹178
Trailing: ₹160.20
Unrealized: +₹2,100
```

### 9:47 AM - Exit

**LTP Loop (1-min check):**
- LTP = ₹159.50
- 159.50 ≤ 160.20 ✓
- **EXIT**

**Execution:**
- Paper: Simulate SELL at ₹159.50
- Live: Market order, fill at ₹159.00

**Result:**
```
P&L: ₹712 (paper) / ₹637 (live)
Duration: 17 minutes
Exit: Trailing stop
```

---

## Modify Orders Live

### Tighten Trailing Stop

**Before:**
- Peak: ₹178
- Trailing: ₹160.20 (10% below)

**Modify:**
- Change to 5% below peak
- New trailing: ₹169.10

**Result:** Lock in more profit, exit sooner

### Widen Stop Loss

**Before:**
- Entry: ₹150
- Stop: ₹112.50 (25%)

**Modify:**
- Change to 30%
- New stop: ₹105

**Result:** More room for volatility

### Force Exit

**Modify:**
- Set stop = current LTP

**Result:** Exit at next 1-min LTP check

### Move to Breakeven

**Modify:**
- Set trailing stop = entry price

**Result:** Zero loss possible

---

## Configuration Settings

### What You Can Change

**Risk Parameters:**
- Initial stop loss % (default: 25%)
- Trailing stop activation profit % (default: 10%)
- Trailing stop distance % (default: 10%)
- VWAP stop distance % (default: 5%)
- OI increase threshold % (default: 10%)

**Trading Rules:**
- Max trades per day (default: 1)
- Max concurrent positions (default: 2)
- Trading start time (default: 9:30 AM)
- Trading end time (default: 2:30 PM)
- End-of-day exit time (default: 2:50 PM)

**Strike Selection:**
- OI lookback strikes (default: ±5 from spot)
- Strike update frequency (default: every 5-min)

**Position Sizing:**
- Lot size (default: 75)
- Capital allocation per trade

**Monitoring:**
- LTP check frequency (default: 1 minute)
- Strategy loop interval (default: 5 minutes)

**Broker Settings:**
- Mode: paper or live
- Order type: MARKET or LIMIT
- Slippage tolerance (live only)

### Configuration File Example

```yaml
risk:
  initial_stop_loss_pct: 25
  trailing_stop_activation_pct: 10
  trailing_stop_distance_pct: 10
  vwap_stop_pct: 5
  oi_increase_threshold_pct: 10

trading:
  max_trades_per_day: 1
  max_concurrent_positions: 2
  start_time: "09:30"
  end_time: "14:30"
  eod_exit_time: "14:50"

strike:
  oi_lookback_range: 5
  update_frequency_min: 5

position:
  lot_size: 75
  capital_per_trade: 100000

monitoring:
  ltp_check_interval_min: 1
  strategy_loop_interval_min: 5

broker:
  mode: paper  # or 'live'
  order_type: MARKET
  slippage_tolerance: 0.5
```

**All parameters can be changed without modifying code**

---

## State Persistence

### JSON State File Example

**File: `state/trading_state_20251223.json`**

```json
{
  "timestamp": "2025-12-23T09:47:23.125+05:30",
  "date": "2025-12-23",
  "session_id": "SESSION_20251223_0915",
  "mode": "paper",

  "active_positions": {
    "PAPER_20251223_001": {
      "order_id": "PAPER_20251223_001",
      "symbol": "NIFTY25DEC21750CE",
      "strike": 21750,
      "option_type": "CE",
      "expiry": "2025-12-26",

      "entry": {
        "price": 150.0,
        "time": "2025-12-23T09:30:12+05:30",
        "quantity": 75,
        "reason": "OI unwinding + Price above VWAP"
      },

      "exit": {
        "price": 159.5,
        "time": "2025-12-23T09:47:23+05:30",
        "reason": "trailing_stop",
        "duration_minutes": 17
      },

      "stop_losses": {
        "initial_stop": 112.5,
        "initial_stop_pct": 25,
        "vwap_stop": null,
        "vwap_stop_active": false,
        "oi_stop_active": false,
        "trailing_stop": 160.2,
        "trailing_stop_pct": 10,
        "trailing_active": true
      },

      "price_tracking": {
        "peak_price": 178.0,
        "peak_time": "2025-12-23T09:41:10+05:30",
        "current_price": 159.5,
        "unrealized_pnl": 712.5,
        "unrealized_pnl_pct": 6.33
      },

      "market_data": {
        "entry_oi": 3200000,
        "current_oi": 3100000,
        "oi_change_pct": -3.12,
        "entry_vwap": 148.0,
        "current_vwap": 152.5
      },

      "status": "CLOSED",
      "pnl": 712.5,
      "pnl_pct": 6.33
    }
  },

  "closed_positions": [
    {
      "order_id": "PAPER_20251223_001",
      "entry_time": "2025-12-23T09:30:12+05:30",
      "exit_time": "2025-12-23T09:47:23+05:30",
      "entry_price": 150.0,
      "exit_price": 159.5,
      "pnl": 712.5,
      "exit_reason": "trailing_stop"
    }
  ],

  "strategy_state": {
    "current_spot": 21735.5,
    "trading_strike": 21750,
    "direction": "CALL",
    "max_call_oi_strike": 21750,
    "max_put_oi_strike": 21700,
    "last_oi_check": "2025-12-23T09:45:00+05:30",

    "vwap_tracking": {
      "21750CE": {
        "sum_typical_price_volume": 1250000.0,
        "sum_volume": 8500,
        "current_vwap": 152.5,
        "bars_since_915": 8,
        "last_update": "2025-12-23T09:45:00+05:30"
      }
    }
  },

  "daily_stats": {
    "trades_today": 1,
    "max_trades_allowed": 1,
    "max_concurrent_positions": 2,
    "current_positions": 0,
    "total_pnl_today": 712.5,
    "win_count": 1,
    "loss_count": 0,
    "win_rate": 100.0
  },

  "portfolio": {
    "initial_capital": 100000.0,
    "current_cash": 100712.5,
    "positions_value": 0.0,
    "total_value": 100712.5,
    "total_return_pct": 0.71
  },

  "api_stats": {
    "calls_5min_loop": 8,
    "calls_1min_ltp": 18,
    "total_calls_today": 26,
    "last_api_call": "2025-12-23T09:47:23+05:30"
  },

  "system_health": {
    "last_heartbeat": "2025-12-23T09:47:23+05:30",
    "broker_connected": true,
    "data_feed_status": "ACTIVE",
    "ltp_loop_running": false,
    "strategy_loop_running": true
  }
}
```

### State Update Frequency

**Every Event:**
- Position entry/exit
- Stop loss modifications
- Order status changes

**Every 5 Minutes (Strategy Loop):**
- VWAP tracking updates
- OI tracking updates
- Trading strike updates

**Every 1 Minute (LTP Loop):**
- Price tracking updates
- Peak price updates
- Trailing stop updates

**End of Day:**
- Final state snapshot
- Daily statistics summary
- Archive to history

### State Recovery

**On System Restart:**
1. Load latest state file
2. Verify active positions with broker
3. Resume monitoring loops
4. Continue from last known state

**On Crash:**
- State auto-saved every update
- No data loss
- Resume positions seamlessly

---

## Data Needs

**From Broker:**
- 5-min candles (strategy loop)
- 1-min LTP (exit monitoring)
- Options chain (OI data)

**API Calls:** ~210/day (5-min) + ~350/day (1-min LTP) = ~560/day

**Memory:** < 1 KB

---

## Summary

✅ **Strategy Loop:** 5-min candles for entry decisions
✅ **Exit Loop:** 1-min LTP checks for precise exits
✅ **Paper Trading:** Zero risk testing with real market data
✅ **Live Trading:** Real execution after paper success
✅ **Order Modification:** Change stops anytime during execution
✅ **Configuration:** All parameters adjustable via config file
✅ **State Persistence:** Full state saved as JSON, resume on restart
✅ **Precise Exits:** LTP monitoring for accurate exit prices

**Start with paper, switch to live when confident**
