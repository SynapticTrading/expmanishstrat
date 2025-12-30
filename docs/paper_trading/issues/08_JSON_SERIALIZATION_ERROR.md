# Issue 08: JSON Serialization Error - Numpy Types

**Date:** 2025-12-30
**Severity:** HIGH
**Status:** ✅ FIXED

---

## Problem

State file failed to save with error:
```
✗ Error saving state: Object of type int64 is not JSON serializable
```

This occurred after every trade execution and position update, preventing state persistence.

## Root Cause

Broker API (Zerodha/Kite) returns data with **numpy types** (`int64`, `float64`) instead of native Python types. When saving to JSON:

```python
# From Zerodha API
oi_value = 38216850  # Type: numpy.int64
price = 20.50        # Type: numpy.float64

# In state_manager.py
json.dump(self.state, f, indent=2)  # ❌ FAILS - Can't serialize numpy types
```

### Where Numpy Types Came From:
1. **OI values** from options chain
2. **Price data** from broker quotes
3. **Volume data** from market data
4. **Strike prices** from instruments

## Solution

### 1. Added Numpy Import
**File:** `paper_trading/core/state_manager.py:10`

```python
import numpy as np
```

### 2. Created Type Converter Method
**File:** `paper_trading/core/state_manager.py:41-62`

```python
def convert_to_native_types(self, obj):
    """
    Recursively convert numpy types to native Python types for JSON serialization

    Args:
        obj: Object to convert

    Returns:
        Object with native Python types
    """
    if isinstance(obj, dict):
        return {key: self.convert_to_native_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [self.convert_to_native_types(item) for item in obj]
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    else:
        return obj
```

### 3. Updated Save Method
**File:** `paper_trading/core/state_manager.py:389-398`

```python
def save(self):
    """Save state to JSON file"""
    if self.state_file and self.state:
        try:
            # Convert numpy types to native Python types before saving
            state_to_save = self.convert_to_native_types(self.state)
            with open(self.state_file, 'w') as f:
                json.dump(state_to_save, f, indent=2)
        except Exception as e:
            print(f"[{self.get_ist_now()}] ✗ Error saving state: {e}")
```

## Verification

**Before Fix:**
```
[2025-12-30 11:15:25] ✗ Error saving state: Object of type int64 is not JSON serializable
[2025-12-30 11:16:13] ✗ Error saving state: Object of type int64 is not JSON serializable
```

**After Fix:**
```
[2025-12-30 11:15:25] ✓ State saved successfully
Portfolio: ₹100,127.50 (saved correctly)
```

## Impact

- ✅ State persistence now works
- ✅ Portfolio values saved correctly
- ✅ OI and price data preserved
- ✅ Recovery from crashes possible

## Related Issues

- Issue 09: Portfolio state not updating (needed this fix first)
- Issue 10: Strategy state not saving (needed this fix first)

## Prevention

**Always convert broker API data to native types:**
```python
# Good practice when receiving broker data
oi = int(broker_data['OI'])
price = float(broker_data['price'])
```

## Files Modified

1. `paper_trading/core/state_manager.py` - Added numpy conversion logic
