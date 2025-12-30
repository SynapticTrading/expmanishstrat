# Live & Paper Trading Architecture

**Quick Reference - Dual-Loop System**

---

## Core Concept

### Two Independent Loops

**Strategy Loop (Every 5 Minutes)**
- Fetch 5-min OHLCV candles from broker
- Calculate VWAP, check OI changes
- Make entry/exit decisions based on strategy rules
- Update trading strike if spot moved

**Exit Monitor Loop (Continuous - When Position Active)**
- Fetch real-time LTP from broker
- Check all stop losses continuously
- Update trailing stop as price moves
- Execute exit immediately when any stop hit

**Why Two Loops?**
- Entry decisions need VWAP (requires OHLCV candles)
- Exit monitoring needs precision (LTP is fastest)
- Prevents overstating losses (exit at real price, not 5-min delayed)

---

## Paper vs Live Trading

| What | Paper Trading | Live Trading |
|------|---------------|--------------|
| **Price Data** | Real from broker API | Real from broker API |
| **Order Execution** | Simulated (no real order) | Real (sent to exchange) |
| **Order ID** | Synthetic: PAPER_20251223_001 | Broker: 250123000001 |
| **Fill Price** | Current LTP (instant) | Actual fill (0.5-2 tick slippage) |
| **Capital Risk** | Zero | Real money |
| **Monitoring** | Same dual-loop | Same dual-loop |

**Both use identical logic, only execution differs**

---

## Complete Trading Day Example

### 9:15 AM - Market Open

**Strategy Starts:**
- Fetch Nifty options chain
- Max Call OI = 21750 CE (3.5M contracts)
- Max Put OI = 21700 PE (3.8M contracts)
- Current Spot = 21725
- Distance to 21750 = 25 points
- Distance to 21700 = 25 points
- **Direction = CALL** (equidistant, choose CALL)
- **Trading Strike = 21750 CE**

### 9:30 AM - Entry Signal Detected

**Strategy Loop Checks (5-Min Bar):**
- Fetch 21750 CE candle (OHLCV)
- Price = ₹150
- OI = 3.2M (down from 3.5M at 9:15)
- OI change = -8.5% ✓ (unwinding)
- VWAP since 9:15 = ₹148
- Price (₹150) > VWAP (₹148) ✓
- **Both conditions met → ENTER**

**Paper Trading Execution:**
- Generate order_id = `PAPER_20251223_001`
- Simulate BUY 75 qty at ₹150 (current LTP)
- Log entry: 09:30:12, Price ₹150
- **Start LTP monitoring loop**

**Live Trading Execution:**
- Place MARKET order: BUY 75 qty 21750 CE
- Broker confirms order_id = `250123000001`
- Actual fill at ₹150.50 (0.50 slippage)
- Log entry: 09:30:14, Price ₹150.50
- **Start LTP monitoring loop**

**Position Created:**
```
Order ID: PAPER_20251223_001
Entry: ₹150.00 at 09:30:12
Quantity: 75
Initial Stop: ₹112.50 (25% below entry)
Trailing Stop: Not active yet (needs 10% profit)
Peak Price: ₹150.00
Status: OPEN
```

### 9:31-9:34 AM - LTP Monitoring Active

**LTP Loop Running (Every 1-2 Seconds):**
- 09:31:15 → LTP = ₹152 → All stops safe
- 09:32:30 → LTP = ₹158 → All stops safe
- 09:33:45 → LTP = ₹163 → All stops safe
- 09:34:10 → LTP = ₹165 → Profit = 10%!

**Trailing Stop Activates:**
- Profit = (165 - 150) / 150 = 10%
- Trailing stop = 165 × 0.90 = ₹148.50
- Peak price = ₹165

**Position Updated:**
```
Peak Price: ₹165.00
Trailing Stop: ₹148.50 (active now)
Status: OPEN
```

### 9:35 AM - Strategy Loop Runs Again

**5-Min Strategy Check:**
- Fetch 21750 CE candle
- OI still unwinding
- VWAP updated
- Position exists → Skip entry logic
- Continue monitoring

**LTP Loop (Continuous):**
- Still running, checking every second

### 9:36-9:41 AM - Price Climbs Higher

**LTP Loop Updates:**
- 09:36:20 → LTP = ₹170 → New high!
  - Peak price = ₹170
  - Trailing stop = 170 × 0.90 = ₹153.00

- 09:38:45 → LTP = ₹175 → New high!
  - Peak price = ₹175
  - Trailing stop = 175 × 0.90 = ₹157.50

- 09:41:10 → LTP = ₹178 → New high!
  - Peak price = ₹178
  - Trailing stop = 178 × 0.90 = ₹160.20

**Position Updated:**
```
Peak Price: ₹178.00
Trailing Stop: ₹160.20
Unrealized P&L: (178 - 150) × 75 = ₹2,100
Status: OPEN
```

### 9:47:23 AM - Trailing Stop Hit

**LTP Loop Detects Exit:**
- Fetch LTP = ₹159.50
- Compare: 159.50 ≤ 160.20 ✓
- **Trailing stop hit!**

**Paper Trading Exit:**
- Simulate SELL 75 qty at ₹159.50
- Log exit: 09:47:23, Price ₹159.50
- P&L = (159.50 - 150) × 75 = ₹712.50

**Live Trading Exit:**
- Place MARKET order: SELL 75 qty
- Broker confirms fill at ₹159.00 (0.50 slippage)
- Log exit: 09:47:25, Price ₹159.00
- P&L = (159.00 - 150.50) × 75 = ₹637.50

**Position Closed:**
```
Order ID: PAPER_20251223_001
Entry: ₹150.00 at 09:30:12
Exit: ₹159.50 at 09:47:23
Exit Reason: trailing_stop
Peak Reached: ₹178.00
P&L: ₹712.50 (9.5% profit)
Duration: 17 minutes
Status: CLOSED
```

### 9:50 AM Onwards

**Strategy Loop (5-Min):**
- Continues checking for new entry
- OI, VWAP conditions monitored
- Can take another trade if conditions met

**LTP Loop:**
- Stopped (no active position)
- Will restart when next position opened

---

## Modifying Orders Live

### 1. Tighten Trailing Stop

**Scenario:** Price at ₹172, want to lock in more profit

**Before Modification:**
```
Peak Price: ₹178
Trailing Stop: ₹160.20 (10% below peak)
Current LTP: ₹172
```

**Modify Command:**
- Change trailing percentage from 10% to 5%
- New trailing stop = 178 × 0.95 = ₹169.10

**After Modification:**
```
Trailing Stop: ₹169.10 (5% below peak)
```

**Result:**
- Exit sooner, lock in more profit
- Less risk of giving back gains
- LTP loop uses new stop immediately

### 2. Widen Initial Stop Loss

**Scenario:** Entered at ₹150, market choppy, give more room

**Before Modification:**
```
Entry Price: ₹150
Stop Loss: ₹112.50 (25% below entry)
```

**Modify Command:**
- Widen stop from 25% to 30%
- New stop = 150 × 0.70 = ₹105.00

**After Modification:**
```
Stop Loss: ₹105.00 (30% below entry)
```

**Result:**
- More breathing room for position
- Won't exit on normal volatility
- Higher risk but allows trend to develop

### 3. Force Exit Immediately

**Scenario:** News event, want to exit now regardless of stops

**Current State:**
```
LTP: ₹165
All stops: Safe (no stop hit)
```

**Modify Command:**
- Set stop_loss = current_ltp (forces immediate exit)
- OR directly call exit function

**Result:**
- LTP loop detects "stop hit" on next check
- Exits within 1-2 seconds
- Manual override of strategy rules

### 4. Move Trailing Stop to Breakeven

**Scenario:** Locked some profit, now protect capital

**Current State:**
```
Entry: ₹150
Peak: ₹165
Trailing Stop: ₹148.50 (10% below peak)
```

**Modify Command:**
- Move trailing stop to entry price
- New trailing stop = ₹150.00

**After Modification:**
```
Trailing Stop: ₹150.00 (breakeven)
```

**Result:**
- No loss possible (assuming no slippage)
- Still has upside potential
- Capital protected

---

## Why This Beats Backtest

### Problem: 5-Min Only Monitoring

**Example Trade:**
- 09:30: Enter at ₹150
- 09:32: Price drops to ₹145 (trailing stop ₹148)
- 09:35: Next 5-min bar shows ₹142
- **Backtest logs exit at ₹142**
- **Loss overstated by ₹3 per share**

### Solution: LTP Continuous Monitoring

**Same Trade with LTP:**
- 09:30:00: Enter at ₹150
- 09:32:15: LTP = ₹145.50
- 09:32:15: Trailing stop ₹148 hit!
- 09:32:17: Exit at ₹145.50
- **Accurate exit, saved ₹3 per share**

**Over 50 trades, this adds up!**

---

## Data Requirements

### What You Need from Broker

**5-Min Strategy Loop:**
- Spot 5-min OHLCV candles (Nifty)
- Option 5-min OHLCV candles (trading strike)
- Options chain (strikes, OI, expiry)
- API calls: ~210 per day

**LTP Exit Loop:**
- Real-time LTP for active option
- API calls: Continuous when position active (~300-500/day)

**Total API Calls: ~700/day**
- Well within broker limits (typically 10,000/day)

### What You Store in Memory

**VWAP Tracking (per strike):**
- Sum of (typical_price × volume) since 9:15
- Sum of volume since 9:15
- Last update time
- **Total: 24 bytes**

**OI Tracking (per strike):**
- Current OI
- Previous OI (5 min ago)
- **Total: 16 bytes**

**Position Tracking (per active order):**
- Order ID, entry price, quantity
- Stop loss, trailing stop, peak price
- Entry/exit timestamps
- **Total: 200 bytes**

**Maximum: 2 positions = 400 bytes + overhead**
**Total Memory: < 1 KB**

---

## Summary

**Strategy Loop (5-Min)**
- Makes entry/exit decisions
- Uses OHLCV candles for VWAP
- Runs every 5 minutes always

**Exit Loop (Continuous LTP)**
- Monitors active positions only
- Real-time stop loss checks
- Runs every 1-2 seconds when position active

**Paper Trading**
- Uses real market data
- Simulates order execution
- Zero capital risk
- Test strategy first

**Live Trading**
- Uses real market data
- Sends real orders
- Real slippage, real fills
- Go live after paper success

**Order Modification**
- Query current state via order ID
- Modify stops dynamically
- Force exits manually
- Full control during execution

**This architecture gives you:**
- Precise exit execution (LTP tracking)
- Flexible stop management (modify anytime)
- Accurate P&L (no 5-min delay)
- Production-ready for live trading
