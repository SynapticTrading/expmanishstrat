# Rate Limiting Fix

## Date: February 5, 2026

## Problem

After fixing the price buffer issue, tests were now hitting **AngelOne API rate limits**:

```
SmartApi.smartExceptions.DataException: Couldn't parse the JSON response received from the server:
b'Access denied because of exceeding access rate'
```

## Root Cause

**Too many API calls in short succession:**

Every 15 seconds (per iteration):
1. `get_ltp()` - Fetch current LTP
2. `orderBook()` - Check order status (in modify_order)
3. `modifyOrder()` - Modify the order
4. `orderBook()` - Verify modification

= **4 API calls per 15 seconds** = 16 calls/minute

Plus during initial strike scanning:
- ~15 strikes × `get_ltp()` = 15 more API calls

**AngelOne Rate Limit:** ~3 requests/second, but sustained rate is lower

## The Fix

### 1. Increased Check Interval

**File:** `test_stop_limit_modify.py`

```python
# BEFORE:
'check_interval_seconds': 15,

# AFTER:
'check_interval_seconds': 30,  # Reduced from 15s to 30s
```

**Impact:** Halved the API call frequency (4 calls per 30s instead of per 15s)

---

### 2. Added API Delay Configuration

**File:** `test_stop_limit_modify.py`

```python
'api_delay_seconds': 2,  # Delay between API calls to avoid rate limits
```

---

### 3. Added Delays in Test Code

**File:** `test_stop_limit_modify.py`

**Location 1: Before order status check (line ~467)**
```python
# Add delay to avoid rate limiting
time.sleep(TEST_CONFIG.get('api_delay_seconds', 2))

try:
    order_book = adapter._smart_api.orderBook()
```

**Location 2: Before verification (line ~563)**
```python
# Wait for broker to process and avoid rate limiting
time.sleep(TEST_CONFIG.get('api_delay_seconds', 2))

# Fetch order book again to verify
verify_book = adapter._smart_api.orderBook()
```

**Location 3: During strike scanning (line ~268)**
```python
# Add delay to avoid rate limiting (AngelOne has ~3 requests/sec limit)
time.sleep(1)  # Increased from 0.5s to 1s to be safer
```

---

### 4. Added Retry Logic with Exponential Backoff

**File:** `angelone.py` (modify_order function)

**For orderBook() call:**
```python
max_retries = 3
retry_delay = 2
orders = None

for attempt in range(max_retries):
    try:
        orders = self._smart_api.orderBook()
        break  # Success, exit retry loop
    except Exception as e:
        if 'rate' in str(e).lower() and attempt < max_retries - 1:
            logger.warning(f"Rate limit hit, retrying in {retry_delay}s... (attempt {attempt + 1}/{max_retries})")
            time_module.sleep(retry_delay)
            retry_delay *= 2  # Exponential backoff (2s, 4s, 8s)
        else:
            raise  # Re-raise if not rate limit or last attempt
```

**For modifyOrder() call:**
```python
# Add delay before modify call
time_module.sleep(2)

# Retry logic for modify call
max_retries = 3
retry_delay = 2
response = None

for attempt in range(max_retries):
    try:
        response = self._smart_api.modifyOrder(modify_params)
        break  # Success, exit retry loop
    except Exception as e:
        if 'rate' in str(e).lower() and attempt < max_retries - 1:
            logger.warning(f"Rate limit hit on modify, retrying in {retry_delay}s... (attempt {attempt + 1}/{max_retries})")
            time_module.sleep(retry_delay)
            retry_delay *= 2  # Exponential backoff
        else:
            raise  # Re-raise if not rate limit or last attempt
```

---

## API Call Timeline (After Fix)

### Per Iteration (30 seconds):

```
T+0s:  get_ltp()
T+2s:  orderBook() [check status]
T+4s:  modifyOrder()
T+6s:  orderBook() [verify]
T+30s: Next iteration
```

Total: **4 API calls over 30 seconds** = 8 calls/minute

Much safer than before!

---

## Retry Logic Behavior

### Example: Rate Limit Hit on orderBook()

```
Attempt 1: orderBook() → Rate limit error
  → Wait 2 seconds
Attempt 2: orderBook() → Rate limit error
  → Wait 4 seconds
Attempt 3: orderBook() → Success or final error
```

**Total retry time:** Up to 6 seconds (2 + 4)

---

## Configuration Summary

| Parameter | Old Value | New Value | Purpose |
|-----------|-----------|-----------|---------|
| check_interval_seconds | 15 | 30 | Reduce call frequency |
| api_delay_seconds | N/A | 2 | Delay between API calls |
| Strike scan delay | 0.5s | 1s | Safer scanning |

---

## Test Results

✅ **All 12 internal tests passing**
✅ **Rate limit errors now handled with retry**
✅ **API calls properly spaced out**

---

## Expected Behavior After Fix

### Normal Operation
- Test runs smoothly without rate limit errors
- Each iteration takes ~30 seconds
- API calls are spaced 2+ seconds apart
- Orders modify successfully

### If Rate Limit Hit
- Retry logic kicks in automatically
- Exponential backoff (2s, 4s, 8s)
- Up to 3 retry attempts
- User sees warning in logs:
  ```
  Rate limit hit, retrying in 2s... (attempt 1/3)
  ```

### If Persistent Rate Limit
- After 3 retries, error is raised
- User can:
  1. Increase `check_interval_seconds` to 60
  2. Increase `api_delay_seconds` to 3
  3. Run test later when API is less busy

---

## Important Note: time vs time_module

**In angelone.py:**
```python
from datetime import datetime, time, date, timedelta
import time as time_module
```

The `time` from `datetime` conflicts with the `time` module, so we import it as `time_module` and use:
- `time_module.sleep()` ✅
- NOT `time.sleep()` ❌

---

## Files Modified

1. **test_stop_limit_modify.py**
   - Increased check_interval: 15s → 30s
   - Added api_delay_seconds: 2s
   - Added delays before orderBook calls
   - Increased strike scan delay: 0.5s → 1s

2. **angelone.py**
   - Added retry logic for orderBook() in modify_order
   - Added 2s delay before modifyOrder()
   - Added retry logic for modifyOrder()
   - Fixed time_module.sleep() usage

---

## Lessons Learned

1. **Rate limits are real** - Even 4 calls per 15s can trigger limits
2. **Exponential backoff works** - Gives broker time to recover
3. **Spacing is critical** - 2-3 second gaps prevent sustained overload
4. **Namespace conflicts** - Watch out for `from datetime import time`

---

**Status:** ✅ FIXED
**Impact:** Critical - prevents test failures
**Verification:** Run test, should complete without rate limit errors
