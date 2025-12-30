# Issue 1: API Timeout Errors and Retry Logic

**Date**: December 29, 2025
**Status**: ✅ SOLVED
**Priority**: High

## Problem

During paper trading execution, the system was experiencing frequent API timeout errors:

```
HTTPSConnectionPool(host='api.kite.trade', port=443): Read timed out. (read timeout=7)
```

**Impact**:
- Candles were being skipped when timeouts occurred
- User reported: "its not loading the next candle"
- Strategy couldn't make entry decisions due to missing data
- Exit monitor couldn't check stop losses without real-time LTP

## Root Cause

1. **Timeout too short**: Original 7-second timeout was insufficient for Zerodha API during market hours
2. **No retry logic**: Single API failures caused entire candle to be skipped
3. **Critical operations affected**:
   - `get_spot_price()` - Nifty spot price fetching
   - `get_ltp()` - Last traded price for options
   - `get_options_chain()` - Full options chain with OI data

## Solution

### 1. Increased Timeout Duration

**File**: `paper_trading/legacy/zerodha_connection.py:102`

```python
# Generate session (with 30s timeout to handle slow API responses)
self.kite = KiteConnect(api_key=self.api_key, timeout=30)
```

Changed from 7 seconds to **30 seconds** to handle slow API responses during high-volume periods.

### 2. Exponential Backoff Retry Logic

Implemented 3-attempt retry with exponential backoff (1s, 2s, 4s delays) for all critical API calls.

#### get_ltp() Implementation

**File**: `paper_trading/legacy/zerodha_connection.py:140-179`

```python
def get_ltp(self, instrument_token, max_retries=3):
    """Get Last Traded Price for instrument with retry logic"""
    import time as time_module

    if not self.kite:
        print(f"[{datetime.now()}] ✗ Not connected. Call connect() first.")
        return None

    for attempt in range(max_retries):
        try:
            ltp_data = self.kite.ltp([instrument_token])
            if ltp_data and instrument_token in ltp_data:
                return ltp_data[instrument_token]['last_price']

            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"[{datetime.now()}] ⚠️  LTP data empty, retrying in {wait_time}s...")
                time_module.sleep(wait_time)
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"[{datetime.now()}] ⚠️  Error getting LTP: {str(e)}")
                print(f"[{datetime.now()}] ⚠️  Retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                time_module.sleep(wait_time)
            else:
                print(f"[{datetime.now()}] ✗ Failed to get LTP after {max_retries} attempts: {str(e)}")

    return None
```

#### get_spot_price() Implementation

**File**: `paper_trading/legacy/zerodha_data_feed.py:66-97`

```python
def get_spot_price(self, max_retries=3):
    """Get current Nifty spot price with retry logic"""
    for attempt in range(max_retries):
        try:
            ltp = self.connection.get_ltp(self.nifty_symbol)
            if ltp is not None:
                return ltp

            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                print(f"[{datetime.now()}] ⚠️  Spot price returned None, retrying in {wait_time}s...")
                time_module.sleep(wait_time)
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"[{datetime.now()}] ⚠️  Error getting spot price: {e}")
                print(f"[{datetime.now()}] ⚠️  Retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                time_module.sleep(wait_time)
            else:
                print(f"[{datetime.now()}] ✗ Failed to get spot price after {max_retries} attempts: {e}")
    return None
```

#### get_options_chain() Improvements

**File**: `paper_trading/legacy/zerodha_data_feed.py:184-203`

Added retry logic to quote fetching within options chain retrieval.

## Results

✅ **Eliminated missed candles** - System now retries on transient failures
✅ **More reliable data** - 3 attempts with increasing delays handles intermittent issues
✅ **Better logging** - Clear visibility when retries are happening
✅ **Graceful degradation** - Only skips candle after all 3 attempts fail

## Testing

Verified in production run on **2025-12-29**:
- Multiple successful retries logged in `reports/paper_trading_log_20251229_135313.txt`
- No missed candles during API slowdowns
- Both strategy loop (5-min) and exit monitor (1-min) working reliably

## Future Improvements

1. **Token refresh mechanism** - Current tokens expire after ~1 hour
2. **Adaptive timeout** - Could increase timeout further during known high-volume periods
3. **Circuit breaker** - Pause system if API failures exceed threshold
4. **Fallback data source** - Secondary data provider if Zerodha API is down

## Related Issues

- [Exit Monitor Implementation](./03_EXIT_MONITOR_IMPLEMENTATION.md) - Exit monitor depends on reliable LTP data
