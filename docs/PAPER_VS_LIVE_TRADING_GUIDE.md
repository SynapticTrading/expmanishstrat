# Paper vs Live Trading Guide
**Simple, Non-Technical Overview**

---

## Current Strategy Behavior (Backtest)

### What Happens Every Day

**9:15 AM - Market Open**
- Fetch all NIFTY weekly options data for today
- Find nearest Thursday expiry
- Look at strikes ±5 from current spot price
- Find which strike has maximum Call OI and maximum Put OI
- Compare distances to decide direction (CALL or PUT)
- Set initial trading strike

**9:30 AM - 2:30 PM - Trading Window**

Every 5 minutes:
- Check current Nifty spot price
- Update trading strike if spot moved to different level
- Check if OI is decreasing (unwinding)
- Calculate VWAP since 9:15 AM
- If OI unwinding + Price above VWAP → Enter trade
- If in position → Check 4 stop losses

**2:50 PM - End of Day**
- Force exit all positions by 3:00 PM

### How Strikes Are Selected

**For CALL Direction:**
- Choose strike at or just above current spot (ATM or slightly OTM)
- Example: Spot = 21725 → Strike = 21750 CE

**For PUT Direction:**
- Choose strike just below current spot (OTM)
- Example: Spot = 21725 → Strike = 21700 PE

**Strike Updates:**
- Every 5 minutes, check if spot moved
- If spot = 21703 → Use 21750
- If spot = 21697 → Use 21700
- Can change 15-20 times per day if market choppy

### Stop Loss Mechanisms

**All managed in strategy code, checked every 5 minutes:**

1. **Initial Stop Loss (25%)** - Always active
2. **VWAP Stop (5% below VWAP)** - Only when trade is losing
3. **OI Stop (OI increased >10%)** - Only when trade is losing
4. **Trailing Stop (10% from peak)** - Only when profit >10%

**Trailing Stop Logic:**
- Activates when profit reaches 10%
- Sets stop at 10% below highest price
- Updates every 5 min as price makes new highs
- Only moves up, never down
- Triggers when current price drops to stop level

### Granular Exit Execution (LTP vs 5-Min)

**Decision Making:** 5-minute aggregated candles
**Exit Execution:** Real-time LTP tracking

**Why This Matters:**
- Entry/Exit decisions made on 5-min candles (strategy signals)
- BUT stop loss checks use real-time LTP to capture exact exit point
- Prevents overstating losses in backtest vs actual execution
- Most responsive and accurate exit timing

**Architecture:**

**For Paper Trading:**
- Generate **synthetic order IDs** when position opened
- Track position using this ID
- **Monitor exits using real-time LTP** from broker (every 1 minute)
- **Simulate order execution** at the real market LTP (no actual order sent)
- Know exactly where stop loss was hit (precise price & timestamp)
- Can query/modify order parameters using synthetic ID

**For Live Trading:**
- Use **broker-provided order ID** when position opened
- Track position using broker order ID
- **Monitor exits using real-time LTP** from broker API (every 1 minute)
- Place actual market orders when stop loss hit
- Query actual fill prices and timestamps from broker
- Can modify stop loss levels programmatically using order ID

**Example Flow:**

```
09:30:10 → 5-min candle check → Enter trade signal
09:30:12 → Place order → Get order_id = "PAPER_20251223_001" (paper) or "250123000001" (live)
09:31:00 → Check LTP → Price still safe (LTP = ₹148.00)
09:32:00 → Check LTP → Trailing stop hit (LTP = ₹145.50)
09:32:05 → Exit using order_id → Exact exit logged at ₹145.50

vs

09:30:10 → 5-min candle check → Enter at ₹150
09:35:10 → 5-min candle check → Trailing stop hit at ₹142 (but actually hit at ₹145.50 at 09:32)
          → Loss overstated by ₹3.50 per share
```

**Implementation Requirements:**

1. **Synthetic Order ID Format (Paper):**
   ```python
   order_id = f"PAPER_{date}_{sequence_num}"
   # Example: PAPER_20251223_001
   ```

2. **Order Tracking State:**
   ```python
   {
       "order_id": "PAPER_20251223_001",
       "entry_time": "2025-12-23T09:30:12",
       "entry_price": 150.0,
       "stop_loss": 145.0,
       "trailing_stop": 145.0,
       "peak_price": 150.0,
       "current_status": "OPEN",
       "exit_price": None,
       "exit_time": None
   }
   ```

3. **LTP Monitoring Loop:**
   - Separate from 5-min strategy loop
   - Checks only active positions (via order_id)
   - Fetches real-time LTP every 1 minute
   - Compares against stop levels
   - Triggers exit if stop hit
   - Updates order state immediately

4. **Query/Modify Operations:**
   ```python
   # Query order
   position = get_order_by_id("PAPER_20251223_001")

   # Modify stop loss
   update_order_stop(order_id="PAPER_20251223_001", new_stop=147.0)

   # Check exact exit point
   if position['exit_time']:
       print(f"Exited at {position['exit_price']} at {position['exit_time']}")
   ```

**Benefits:**
- ✅ Accurate exit price tracking (not rounded to 5-min)
- ✅ Better backtest-to-live consistency
- ✅ Can analyze exact stop loss trigger points
- ✅ Modify stops dynamically during execution
- ✅ Paper trading matches live trading behavior more closely

---

## What Data We Need to Track (Live/Paper)

### Minimal State in Memory

**For VWAP Calculation:**
- Running sum of (typical_price × volume) since 9:15 AM
- Running sum of volume since 9:15 AM
- Last update timestamp
- Just 3 numbers per strike - NO data caching needed

**For OI Change:**
- Current OI value
- Previous bar's OI value (5 min ago)
- Just 2 numbers per strike

**For Position Tracking:**
- Entry price, time, strike, expiry
- Highest price since entry (for trailing stop)
- All stop loss levels
- Current P&L

**For Order Management (New - Granular Exits):**
- Order ID (synthetic for paper, broker-provided for live)
- Order status (OPEN, CLOSED)
- Entry/exit timestamps (precise to the second)
- Entry/exit prices (exact fill prices)
- Stop loss levels (initial, trailing, VWAP, OI)
- Peak price seen (for trailing stop calculation)

**Example Order State Structure:**
```python
active_orders = {
    "PAPER_20251223_001": {
        "symbol": "NIFTY25DEC21750CE",
        "entry_time": "2025-12-23T09:30:12",
        "entry_price": 150.0,
        "quantity": 75,
        "stop_loss": 112.5,           # Initial 25%
        "vwap_stop": None,            # Calculated when losing
        "oi_stop": False,             # Boolean flag
        "trailing_stop": None,        # Activates at 10% profit
        "peak_price": 150.0,
        "current_status": "OPEN",
        "exit_price": None,
        "exit_time": None,
        "exit_reason": None           # "trailing_stop", "initial_sl", etc.
    }
}
```

**Total Memory Footprint:**
- ~50-100 bytes per strike being tracked (VWAP/OI data)
- ~200-300 bytes per active order (position tracking)
- Max 2 concurrent positions = ~600 bytes
- Negligible compared to backtest's 4M row dataset

### What We DON'T Need

- Historical price bars
- Full day's options data stored
- Past days' data
- Heavy DataFrame caching (backtest only)

---

## Critical: Data Fetch Mechanism

### You Need BOTH 5-Min Candles AND LTP

**IMPORTANT:** This strategy requires **BOTH** data types for different purposes:

1. **5-Min Aggregated Candles** → Entry decisions, VWAP calculation
2. **Real-Time LTP** → Stop loss monitoring, exit execution

### Why You Can't Use ONLY LTP

**What LTP Gives You:**
```
09:17:23 → LTP = 21750.50  (just one price point)
09:20:00 → LTP = 21760.00  (just one price point)
```

**Problem for Entry Decisions:** LTP returns only the last traded price at that moment. You get individual price ticks, not aggregated candles.

**For entry logic, you need:**
- VWAP calculation: `(High + Low + Close) / 3 × Volume`
- LTP has NO High, Low, or Volume data ❌

### Why You NEED LTP

**For Stop Loss Monitoring:**
```
09:31:45 → LTP = 145.50  (current price)
          → Trailing stop = 145.00
          → Stop hit! Exit immediately at 145.50
```

**Benefits:**
- ✅ Real-time price updates (not delayed till next 5-min candle)
- ✅ Precise exit execution (know exact price when stop hit)
- ✅ Prevents overstating losses (exit at 145.50, not wait till 142 at next 5-min bar)
- ✅ Lightweight and fast (single price point, no OHLCV overhead)
- ✅ Most responsive for stop loss monitoring

### Data Fetching Strategy

**1. For Entry Decisions (Every 5 Minutes):**

Use `getCandleData()` for exchange-aggregated candles:
```python
# 5-min candles for VWAP calculation and entry logic
candles = getCandleData(
    exchange="NSE",
    symboltoken="99926000",  # Nifty 50
    interval="FIVE_MINUTE"
)

# Returns completed 5-min OHLCV candles:
['2025-12-18T09:15:00+05:30', 21750, 21765, 21745, 21760, 123456]
#  [Timestamp,              Open,  High,  Low,   Close, Volume]
```

**2. For Exit Monitoring (Every 1 Minute When Position Active):**

**Use real-time LTP (granular exit monitoring)**
```python
# Real-time LTP for immediate stop loss checks
ltp_data = getLTP(
    exchange="NFO",
    symboltoken="option_token"
)
current_price = ltp_data['ltp']

# Check against all stop losses
if current_price <= trailing_stop:
    # Exit immediately
```

**Why LTP for Exits:**
- Real-time price, no waiting for candle completion
- Lightweight API call (just one price value)
- Perfect for simple price comparisons
- Most responsive exit execution

### Who Creates These Candles?

**The EXCHANGE (NSE/BSE) aggregates them, NOT the broker:**

1. All trades between 09:15:00 - 09:19:59 happen on NSE
2. NSE aggregates all trades in this 5-min window:
   - First trade price → Open
   - Highest trade price → High
   - Lowest trade price → Low
   - Last trade price → Close
   - Sum of all quantities → Volume
3. At 09:20:00, NSE publishes the completed candle
4. Broker (AngelOne/Zerodha) fetches from NSE
5. You call `getCandleData()` and get the official exchange candle

**These are the SAME candles shown on:**
- Zerodha Kite charts
- TradingView
- Any other platform

### Perfect Alignment with Backtest

**Backtest uses:** Exchange-aggregated 5-min candles from CSV
**Live/Paper uses:** Exchange-aggregated 5-min candles from API

**Result:** Exact same behavior, perfect consistency

### Data Fetch Schedule

**Every 5 minutes at candle close + 10 seconds:**

```
09:20:10 → Fetch completed 09:15-09:20 candle
09:25:10 → Fetch completed 09:20-09:25 candle
09:30:10 → Fetch completed 09:25-09:30 candle
...
15:30:10 → Fetch completed 15:25-15:30 candle
```

**10-second delay ensures:**
- Candle has completed
- Exchange has published data
- Broker API has received it
- Data is available for you to fetch

### What to Fetch and When

**5-Min Strategy Loop - Entry Decisions:**

**For Spot Price:**
```python
spot_candles = getCandleData(
    exchange="NSE",
    symboltoken="99926000",  # Nifty 50 Index
    interval="FIVE_MINUTE"
)
current_spot = spot_candles[-1][4]  # Latest 5-min close
```

**For Options Price (VWAP calculation):**
```python
option_candles = getCandleData(
    exchange="NFO",
    symboltoken="option_token",
    interval="FIVE_MINUTE"
)
# Get OHLCV from latest 5-min candle
open_price = option_candles[-1][1]
high_price = option_candles[-1][2]
low_price = option_candles[-1][3]
close_price = option_candles[-1][4]
volume = option_candles[-1][5]

# Calculate for VWAP
typical_price = (high_price + low_price + close_price) / 3
# Add to running totals
```

**For Options OI:**
```python
# Use Quote/Market Data API (candles don't have OI)
quotes = getMarketData(
    mode="FULL",
    instruments=[list_of_option_tokens]
)
current_oi = quotes['data']['fetched'][0]['oi']
```

**Exit Loop - Stop Loss Monitoring (Every 1 Minute):**

**For Options Price (Stop Loss Checks):**
```python
# Real-time LTP for immediate stop loss checks
ltp_data = getLTP(
    exchange="NFO",
    symboltoken="option_token"
)
current_price = ltp_data['ltp']

# Check stop losses
if current_price <= order_state['trailing_stop']:
    # Exit position immediately at current_price
    exit_order(order_id, exit_price=current_price)
```

### Summary

**Use BOTH Data Types:**

✅ **For Entry Decisions:** `getCandleData()` with `interval="FIVE_MINUTE"`
- Returns exchange-aggregated OHLCV candles
- Same as Zerodha/TradingView charts
- Has all data needed for VWAP calculation
- Perfect backtest-to-live consistency
- Checked every 5 minutes

✅ **For Exit Monitoring:** `getLTP()`
- Real-time price for immediate stop loss checks
- Lightweight and fast (single price value)
- Prevents overstating losses (precise exit points)
- Checked every 1 minute when position active
- More granular than 5-min for trailing stop updates

❌ **Don't use ONLY LTP for everything:**
- Only gives single price points
- Missing High, Low, Volume needed for VWAP
- Can't calculate VWAP correctly
- Doesn't match backtest behavior for entry logic

**The strategy:** 5-min candles for entry decisions, real-time LTP for exit execution.

---

## Paper Trading Architecture

### Overview

Use real-time market data but simulate order execution without sending to broker.

### Components Needed

**1. Data Feed (Real-Time)**
- Connect to Zerodha/AngelOne WebSocket or API
- Fetch every 5 minutes:
  - Nifty spot price
  - Options chain (current strikes, OI, LTP)
- Update running totals for VWAP
- Track last 2 OI values for change calculation

**2. Virtual Broker (Simulated)**
- Maintains virtual positions in memory
- When strategy says "BUY":
  - Record entry price from live market
  - Create position in virtual portfolio
  - NO actual order to exchange
- When strategy says "SELL":
  - Record exit price from live market
  - Calculate P&L
  - Update virtual portfolio
  - NO actual order to exchange

**3. Strategy Engine (Unchanged)**
- Use exact same backtest strategy code
- Swap data source only (CSV → Live API)
- All logic remains identical

### How It Works

**9:15 AM**
1. Fetch live instruments from broker
2. Filter to weekly expiry options
3. Find strikes ±5 from spot
4. Fetch OI for these strikes
5. Determine direction (CALL/PUT)
6. Set initial trading strike
7. Initialize VWAP running totals

**Every 5 Minutes (9:30 AM - 2:30 PM) - Strategy Loop**
1. Fetch current spot price (5-min candle)
2. Update trading strike if needed
3. Fetch current OI for trading strike
4. Update VWAP running totals
5. Calculate OI change from last bar
6. Check entry conditions
7. If conditions met → Create virtual position with synthetic order ID

**Every 1 Minute (When Position Active) - LTP Exit Monitoring Loop**
1. Fetch current option LTP from broker (real-time)
2. Check all stop losses against current LTP
3. Update trailing stop if new high detected
4. If stop hit → **Simulate order execution** at current LTP using order ID
5. Log exact exit price and timestamp (no actual order sent to broker)

**Note:** Two separate loops run concurrently:
- **5-min loop:** Entry decisions, strike updates, OI/VWAP tracking
- **LTP loop:** Checks active positions every 1 minute for exits (more granular)

**What You See:**
- Live updates every 5 minutes (strategy decisions)
- **LTP checks every 1 minute** when position active (exit monitoring)
- P&L calculated using **real market prices from broker**
- No money at risk (orders not actually sent)
- Trades logged to CSV with precise timestamps

### Advantages

- Test strategy with **real market conditions and real-time prices**
- No capital risk (simulated order execution only)
- See exactly how strategy behaves live
- Identify issues before going live
- Uses actual broker data (same as live trading)

### Limitations

- Cannot account for:
  - **Slippage** (assumes instant fill at current LTP; real trades face 0.5-2 tick slippage)
  - **Order rejection** by broker (margin, RMS checks, etc.)
  - **Partial fills** (paper assumes full quantity executed)
  - **Exchange delays** (paper assumes instant execution)
  - **Network/API failures** during critical moments

---

## Live Trading Architecture

### Overview

Use real-time market data AND send real orders to broker.

### Components Needed

**1. Data Feed (Real-Time)**
- Same as paper trading
- Zerodha/AngelOne WebSocket/API for live prices

**2. Real Broker Integration**
- Connect to broker's API (Zerodha Kite Connect or AngelOne SmartAPI)
- When strategy says "BUY":
  - Place MARKET order via API
  - Wait for order confirmation
  - Record actual fill price
- When strategy says "SELL":
  - Place MARKET order via API
  - Wait for execution
  - Record actual exit price

**3. Order Types Available**

**Zerodha:**
- MARKET, LIMIT, SL (Stop Loss), SL-M (Stop Loss Market)
- NO native trailing stop loss
- Must implement trailing stop in code

**AngelOne:**
- MARKET, LIMIT, STOPLOSS_LIMIT, STOPLOSS_MARKET
- ROBO orders exist but trailing stop **NOT working via API** (as of 2025)
- Must implement trailing stop in code
- References:
  - [ROBO order example](https://smartapi.angelone.in/smartapi/forum/topic/3961/robo-order-example-with-trailing-sl)
  - [Trailing stoploss not working](https://smartapi.angelbroking.com/topic/1466/trailing-stoploss-in-robo-order-no-relevant-information)
  - [For ROBO order trailing stop loss not working](https://smartapi.angelbroking.com/topic/4275/for-robo-order-trailing-stop-loss-not-working)

**Recommendation:**
- Use simple MARKET orders for both entry and exit
- Manage trailing stop in strategy code (every 5 min check)
- Works with ANY broker

### How It Works

**Same Dual-Loop Logic as Paper Trading, BUT with Real Orders:**

**5-Min Strategy Loop - When Entering Trade:**
1. Strategy signals BUY (based on 5-min candle)
2. Place order: "BUY 75 qty NFO:NIFTY24JAN21750CE at MARKET"
3. Wait for broker confirmation
4. Receive broker order ID (e.g., "250123000001")
5. Record actual fill price (may differ slightly from trigger price)
6. Store position details with order ID

**LTP Exit Monitoring Loop - When Exiting Trade:**
1. Fetch real-time LTP using broker API (every 1 minute)
2. Check stop loss hit (1-min granularity)
3. Place order: "SELL 75 qty NFO:NIFTY24JAN21750CE at MARKET"
4. Reference original order ID for tracking
5. Wait for execution confirmation
6. Record actual exit price and exact timestamp
7. Calculate real P&L
8. Log trade to database

**Key Difference from Paper:**
- Paper: Synthetic order IDs, simulated fills at current price
- Live: Real broker order IDs, actual fill prices (with slippage)

**Error Handling:**
- API timeout → Retry 3 times
- Order rejected → Log error, skip trade
- Network failure → Alert, halt trading
- Exchange errors → Log and notify

---

## Key Differences: Paper vs Live

| Aspect | Paper Trading | Live Trading |
|--------|--------------|--------------|
| **Price Data** | Real-time from broker | Real-time from broker |
| **Entry Decisions** | 5-min candles | 5-min candles |
| **Exit Monitoring** | Real-time LTP (every 1 min) | Real-time LTP (every 1 min) |
| **Order ID** | Synthetic (PAPER_YYYYMMDD_NNN) | Broker-provided (real) |
| **Order Execution** | Simulated at real market LTP | Sent to exchange via broker |
| **Fill Price** | Current market LTP (instant) | Actual fill price (may differ) |
| **Slippage** | Not simulated (assumes instant fill) | Real (usually 0.5-2 ticks) |
| **Capital Risk** | Zero | Real money at risk |
| **Order Confirmation** | Instant | 1-5 seconds delay |
| **Broker Rejection** | Never happens | Possible (margin, RMS checks) |
| **Logging** | CSV file | Database + broker statement |
| **Memory Usage** | Minimal (running totals) | Minimal (running totals) |
| **API Calls** | ~210/day (5-min) + LTP when active | Same + order calls |
| **Stop Loss** | Code-managed (LTP checks) | Code-managed (LTP checks) |
| **Trailing Stop** | Code-managed (LTP updates) | Code-managed (LTP updates) |
| **Order Query** | In-memory dict lookup | Broker API query |
| **Order Modify** | Update dict in code | Broker API modify order |

---

## Broker Comparison

### Zerodha Kite API

**Order Types:**
- MARKET, LIMIT, SL, SL-M
- NO native trailing stop loss
- Must implement in code

**API Rate Limits:**
- 3 requests per second
- WebSocket for real-time data (no rate limit)

**Recommendation:**
- Good for algorithmic trading
- Stable API
- Large user base

### AngelOne SmartAPI

**Order Types:**
- MARKET, LIMIT, STOPLOSS_LIMIT, STOPLOSS_MARKET
- ROBO variety exists but **trailing stop NOT functional via API**
- Must implement in code

**API Rate Limits:**
- Similar to Zerodha
- WebSocket available

**Trailing Stop Reality:**
- Works in UI/App for manual trading
- Does NOT work via SmartAPI for algo trading
- Parameter exists but not supported programmatically

**Recommendation:**
- Use simple order types only
- Implement trailing stop in strategy code

---

## Implementation Roadmap

### Phase 1: Paper Trading (2-3 Weeks)

**Week 1: Setup**
- Get broker API credentials
- Set up WebSocket connection
- Test data fetching every 5 minutes

**Week 2: Integration**
- Create virtual broker class
- Adapt strategy to use live data feed
- Initialize VWAP running totals
- Test OI change calculation

**Week 3: Testing**
- Run paper trading for 1 week
- Verify strike selection logic
- Validate OI unwinding detection
- Check stop loss triggers
- Verify trailing stop updates

### Phase 2: Live Trading (After 1 Week Paper Success)

**Week 4: Go Live**
- Switch virtual broker to real broker
- Start with minimum capital (1 lot only)
- Monitor first 5 trades manually
- Scale up gradually after 20 successful trades

---

## Daily Operations

### Paper Trading Day

**Pre-Market (Before 9:15 AM)**
- Start trading script
- Verify API connection
- Check logs folder exists

**During Market (9:15 AM - 3:30 PM)**
- Script runs automatically
- Logs update every 5 minutes
- Can monitor in terminal

**Post-Market (After 3:30 PM)**
- Review trades CSV
- Check P&L
- Analyze any issues
- No manual intervention needed

### Live Trading Day

**Pre-Market (Before 9:15 AM)**
- Start trading script
- Verify API connection
- Check broker margin available
- Confirm account balance

**During Market (9:15 AM - 3:30 PM)**
- Script runs automatically
- **Monitor actively for first few days**
- Watch for order rejections
- Check positions match expectations

**Post-Market (After 3:30 PM)**
- Verify all positions closed
- Reconcile P&L with broker statement
- Check for any API errors
- Backup trade logs
- Active monitoring required until confident

---

## Risk Management

### Paper Trading

- No financial risk
- Test for minimum 1 week
- Look for:
  - Correct strike selection
  - OI unwinding detection accuracy
  - VWAP calculation correctness
  - Stop loss triggers
  - Trailing stop behavior
  - End-of-day exits

### Live Trading

**Start Small:**
- 1 lot only for first week
- Increase to 2 lots after 20 successful trades
- Monitor daily P&L

**Safety Checks:**
- Max 1 trade per day (already in strategy)
- Max 2 concurrent positions (already in strategy)
- Daily loss limit: Set in broker RMS
- Overall stop loss: Monitor manually

**What Can Go Wrong:**

1. **API Failure** → Position stuck open
   - Solution: Manual exit via broker app

2. **Order Rejection** → Missed entry/exit
   - Solution: Check broker margin before market

3. **Wrong Strike Selected** → Loss
   - Solution: Verify in paper trading first

4. **Trailing Stop Not Triggered** → Profit given back
   - Solution: Test thoroughly in paper mode

5. **Slippage** → Worse execution than expected
   - Solution: Account for 1-2 tick slippage in P&L expectations

---

## Summary

### Paper Trading

- **Use Case:** Test strategy with real market data, zero risk
- **Duration:** 1-2 weeks minimum before going live
- **Memory:** Minimal (running totals, last OI values)
- **API Calls:** ~210 per day (well within limits)
- **Complexity:** Medium
- **Recommendation:** Start here

### Live Trading

- **Use Case:** Real trading with real capital
- **Start Date:** Only after successful paper trading
- **Memory:** Minimal (same as paper)
- **API Calls:** ~210 + order confirmations
- **Complexity:** High
- **Recommendation:** Start with 1 lot only

### Both Modes Share

- Same strategy logic
- Same 5-minute entry decisions
- Same real-time LTP exit monitoring (1-min stop loss checks)
- Same stop loss management (in code, NOT broker-native)
- Same trailing stop implementation (in code)
- Same strike selection rules
- Same VWAP calculation (running totals)
- Same OI tracking method (current + previous)
- Same order tracking via IDs (synthetic vs broker-provided)

### Critical Understanding

**Dual-Loop Architecture:**

- ✅ **5-min loop:** Entry decisions, strike selection, OI/VWAP tracking
- ✅ **LTP loop:** Real-time exit monitoring for active positions only
- ✅ **Order IDs:** Synthetic (paper) or broker-provided (live)
- ✅ **Granular exits:** Know exact price/time when stop loss hit
- ✅ **Query/modify:** Track and adjust positions via order ID

**Trailing Stop Loss:**

- ❌ **NOT available** via Zerodha API
- ❌ **NOT working** via AngelOne SmartAPI (despite parameter existing)
- ✅ **Must implement in code** (already done in backtest strategy)
- ✅ **Checked every 1 minute via LTP** (not 5 min) when position active
- Uses simple MARKET orders to exit when triggered

**Data Storage:**

- ❌ **NO heavy caching needed** (backtest approach not required)
- ✅ **Just maintain running totals** (VWAP: 3 numbers per strike)
- ✅ **Track last 2 OI values** (for change calculation)
- ✅ **Order state dict** (200-300 bytes per active position)
- Minimal memory footprint

**Next Step:** Implement paper trading first, test for 1-2 weeks, then go live with minimal capital.
