# Paper Trading System Status

**Last Updated:** 2025-12-29

---

## ✅ What's Working

### System Architecture
- ✅ **Dual-loop design** implemented
  - Strategy loop: Every 5 minutes
  - Exit monitor loop: Every 1 minute
- ✅ **Rate limiting** fixed (was calling API continuously)
- ✅ **State management** with JSON persistence
- ✅ **Paper broker** for simulated execution
- ✅ **Configuration system** with YAML files

### AngelOne Integration
- ✅ **Authentication** working perfectly
- ✅ **Connection** stable and fast
- ✅ **Nifty spot price** (LTP) working
  - Successfully fetching: 25,978.15
- ✅ **Historical candle API** available
- ✅ **Market hours** detection working

### Zerodha Integration
- ✅ **Authentication** working up to TOTP verification (Steps 1-5)
- ✅ **Credentials** loaded correctly
- ✅ **TOTP generation** working
- ❌ **Request token extraction** failing (needs redirect handler)

---

## ❌ What's Missing

### Critical: Options Chain Data

The system needs **5-minute candle data for each option** in the chain:

**For AngelOne Broker:**
1. ❌ `get_next_expiry()` - Find next weekly expiry date
2. ❌ `get_options_chain(expiry, strikes)` - Return DataFrame with:
   - `strike` - Strike price
   - `option_type` - CE or PE
   - `expiry` - Expiry date
   - `close` - Close price of 5-min candle
   - `volume` - Volume of 5-min candle
   - `oi` - Open Interest
   - `instrument_token` - Token for this option

**Required Steps:**
1. Download AngelOne instrument master file
   - URL: `https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json`
2. Parse NFO instruments to find Nifty options
3. Filter by expiry and strikes
4. For each option, call `getCandleData()` to get 5-min candle
5. Build DataFrame with required columns

### For Zerodha (If choosing Zerodha over AngelOne):
- ❌ Fix redirect URL handling
  - Option 1: Run local server on port 80
  - Option 2: Extract request_token from error/browser
  - Option 3: Cache access_token (valid 24 hours)

---

## 📊 Data Flow Comparison

### Backtest (What Works)
```python
# Backtest has entire historical DataFrame
options_df = pd.read_csv('combined_options_5min_2024.csv')

# Strategy gets pre-loaded data
strategy = IntradayMomentumOI(
    options_df=options_df,  # All options data pre-loaded
    oi_analyzer=oi_analyzer
)

# On each 5-min bar, filter from DataFrame
def on_candle(current_time, spot_price):
    # Filter options_df for current strikes
    current_options = options_df[
        (options_df['timestamp'] == current_time) &
        (options_df['strike'].isin(strikes))
    ]
    # Has: strike, option_type, expiry, close, volume, oi
```

### Paper Trading (What We Need)
```python
# Paper trading fetches live data
broker_api = AngelOneBroker(...)

# On each 5-min candle
def strategy_loop():
    # 1. Get spot price ✅ WORKING
    spot_price = broker_api.get_spot_price()  # 25,978.15

    # 2. Get next expiry ❌ MISSING
    expiry = broker_api.get_next_expiry()  # Need to implement

    # 3. Calculate strikes
    strikes = calculate_strikes(spot_price)  # [25950, 26000, 26050...]

    # 4. Get options chain ❌ MISSING
    options_data = broker_api.get_options_chain(expiry, strikes)
    # Should return DataFrame with same columns as backtest:
    # strike, option_type, expiry, close, volume, oi, instrument_token

    # 5. Pass to strategy (same as backtest)
    strategy.on_candle(current_time, spot_price, options_data)
```

---

## 🔧 Implementation Guide

### Option A: Fix AngelOne (Recommended - 30 min)

**File:** `paper_trading/legacy/angelone_connection.py`

**Step 1: Download Instrument Master**
```python
def download_instruments(self):
    """Download AngelOne instrument master file"""
    import requests
    url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
    response = requests.get(url)
    instruments = response.json()

    # Filter NFO (options)
    self.nfo_instruments = [
        i for i in instruments
        if i['exch_seg'] == 'NFO' and i['name'] == 'NIFTY'
    ]
    return self.nfo_instruments
```

**Step 2: Implement get_next_expiry()**
```python
def get_next_expiry(self):
    """Find next weekly Nifty expiry"""
    from datetime import datetime, timedelta

    if not hasattr(self, 'nfo_instruments'):
        self.download_instruments()

    # Get all unique expiry dates
    expiries = set()
    for inst in self.nfo_instruments:
        if inst['instrumenttype'] in ['OPTIDX']:  # Options on index
            expiry = datetime.strptime(inst['expiry'], '%d%b%Y').date()
            if expiry >= datetime.now().date():
                expiries.add(expiry)

    # Return nearest expiry
    return min(expiries) if expiries else None
```

**Step 3: Implement get_options_chain()**
```python
def get_options_chain(self, expiry, strikes):
    """Get options chain with 5-min candle data"""
    import pandas as pd
    from datetime import datetime, timedelta

    if not hasattr(self, 'nfo_instruments'):
        self.download_instruments()

    # Convert expiry to string format
    expiry_str = expiry.strftime('%d%b%Y').upper()

    results = []

    for strike in strikes:
        for opt_type in ['CE', 'PE']:
            # Find instrument
            instrument = next((
                i for i in self.nfo_instruments
                if i['strike'] == strike * 100  # Strike in paise
                and i['expiry'] == expiry_str
                and i['symbol'].endswith(opt_type)
            ), None)

            if not instrument:
                continue

            # Fetch 5-min candle data
            token = instrument['token']
            now = datetime.now()
            from_date = (now - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M")
            to_date = now.strftime("%Y-%m-%d %H:%M")

            candle_data = self.get_candle_data(
                exchange="NFO",
                symbol_token=token,
                interval="FIVE_MINUTE",
                from_date=from_date,
                to_date=to_date
            )

            if candle_data and candle_data.get('status'):
                candles = candle_data['data']
                if candles:
                    latest = candles[-1]  # [timestamp, O, H, L, C, V]

                    results.append({
                        'strike': strike,
                        'option_type': 'CALL' if opt_type == 'CE' else 'PUT',
                        'expiry': expiry,
                        'close': latest[4],  # Close price
                        'volume': latest[5],  # Volume
                        'oi': 0,  # AngelOne doesn't provide OI in candles
                        'instrument_token': token,
                        'tradingsymbol': instrument['symbol']
                    })

    return pd.DataFrame(results)
```

### Option B: Fix Zerodha (Alternative)

**Quick Fix - Extract Request Token:**

Edit `paper_trading/legacy/zerodha_connection.py` line 79:

```python
# OLD (fails):
response = http_session.get(url=url, allow_redirects=True).url

# NEW (extract from error):
try:
    response = http_session.get(url=url, allow_redirects=True).url
    request_token = parse_qs(urlparse(response).query)['request_token'][0]
except requests.exceptions.ConnectionError as e:
    # Extract request_token from error message
    error_str = str(e)
    if 'request_token=' in error_str:
        import re
        match = re.search(r'request_token=([^&\s]+)', error_str)
        if match:
            request_token = match.group(1)
            print(f"[{datetime.now()}] ✓ Request token extracted: {request_token[:20]}...")
        else:
            raise
    else:
        raise
```

---

## 🎯 Recommendation

**Continue with AngelOne** because:
1. ✅ Authentication already working
2. ✅ Connection stable
3. ✅ Spot price working
4. ⏱️ Only ~30 minutes to implement missing methods
5. 📈 All APIs available (candle data, LTP, etc.)

**Zerodha** would require:
- Setting up redirect handler (more complex)
- OR manually copying tokens each day
- Similar effort to get options chain working

---

## 🚀 Next Steps

### Immediate (Choose One):

**Path A: Complete AngelOne** (Recommended)
1. Add instrument download function
2. Implement `get_next_expiry()`
3. Implement `get_options_chain()`
4. Test with paper trading runner
5. Start paper trading! 🎉

**Path B: Fix Zerodha**
1. Add request_token extraction from error
2. Test authentication flow
3. Implement options chain for Zerodha
4. Start paper trading! 🎉

### Later (Enhancement):
- Add WebSocket for real-time LTP
- Add order modification UI
- Add performance dashboard
- Add alerts/notifications
