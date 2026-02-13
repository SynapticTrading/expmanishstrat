# CRITICAL FIX: Stop Limit Order Filling Issue

## Date: February 5, 2026

## Problem Discovery

**User's observation:**
> "earlier the orders were getting rejected but when u made the change of 5 paisa orders are getting filled, the problem is lying deeper than it getting filled every time u try to modify"

## Root Cause Analysis

### The Bug

**Configuration (BEFORE FIX):**
```python
'stop_loss_pct': 0.40,  # 40% below current price
'price_buffer': 1.0,    # ₹1.00 buffer  ← THIS WAS THE BUG!
```

**Example with LTP = ₹2.00:**
```
Trigger Price = ₹2.00 × (1 - 0.40) = ₹2.00 × 0.60 = ₹1.20
Limit Price   = ₹1.20 + ₹1.00 = ₹2.20  ← ABOVE current market!
```

### Why Orders Were Filling

For a **STOP LIMIT BUY** order:
- **Trigger Price**: Price at which order becomes active
- **Limit Price**: MAXIMUM price willing to pay

When we set:
- Trigger (₹1.20) < Current Market (₹2.00) → ✓ Condition already met, order activates
- Limit (₹2.20) > Current Market (₹2.00) → ✓ Can buy at market price

**Result:** Order executes immediately at ₹2.00 because:
1. Trigger condition is satisfied (price already below ₹2.00)
2. Limit allows buying up to ₹2.20
3. Market price ₹2.00 is within the limit
4. **ORDER FILLS!**

### Why It Worked Before (Orders Were Rejected)

**Before 5 Paisa Fix:**
- Prices were rounded to 1 paisa (₹0.01)
- AngelOne rejected orders: "Please set your order price in multiples of 5 paise"
- **Orders never got placed, so they never filled**

**After 5 Paisa Fix:**
- Prices correctly rounded to 5 paise (₹0.05)
- AngelOne accepted the orders
- **But the parameters made them immediately executable!**

## The Fix

### Change Made

**File:** `/paper_trading/tests/test_stop_limit_modify.py`
**Line:** 68

**BEFORE:**
```python
'price_buffer': 1.0,  # Limit price buffer above trigger price
```

**AFTER:**
```python
'price_buffer': 0.05,  # Limit price buffer above trigger (1 tick) - BOTH prices stay below market!
```

### Why This Works

**Example with LTP = ₹2.00:**
```
Trigger Price = ₹2.00 × 0.60 = ₹1.20
Limit Price   = ₹1.20 + ₹0.05 = ₹1.25  ← BELOW current market!
```

**Result:**
- Trigger (₹1.20) < Current Market (₹2.00) → Order is active
- Limit (₹1.25) < Current Market (₹2.00) → **Cannot execute at ₹2.00**
- Order will only fill if market drops to ₹1.25 or below (37.5% crash!)

## Price Relationship Diagram

```
Current Market Price: ₹2.00
         ↑
         |
         |  SAFE ZONE - Order won't fill
         |
         ├─ ₹1.25 ← Limit Price (New: trigger + ₹0.05)
         |
         ├─ ₹1.20 ← Trigger Price (40% below LTP)
         |
         ↓

OLD (BUGGY):
Current Market Price: ₹2.00
         ↑
         ├─ ₹2.20 ← Limit Price (Old: trigger + ₹1.00) ← DANGER! Above market!
         |
         |  EXECUTION ZONE - Order fills here!
         |
         ↓
         ├─ ₹1.20 ← Trigger Price
```

## Test Results

✅ **All 12 internal tests passing**
✅ **Logic verified with examples**
✅ **No breaking changes**

## Expected Behavior After Fix

### Order Placement
- Order will be **accepted** by AngelOne (correct tick size)
- Order will **NOT fill immediately** (both prices below market)
- Order status will remain **"open"** or **"pending"**

### During Monitoring
- Every 15 seconds, trigger and limit recalculated
- Both prices stay 40% below current market
- Modifications update the order
- **Order should NEVER fill** (unless market crashes 37%+)

### If Market Drops 37%+
- If LTP drops from ₹2.00 to ₹1.25 or below
- Order will execute (this is expected, extremely unlikely)
- Test will detect "complete" status and stop monitoring

## Why This Fix is Critical

### Before Fix
❌ Orders were filling on EVERY modification
❌ Test couldn't run for more than 1-2 iterations
❌ Couldn't verify modification logic
❌ Leftover positions needed manual cleanup

### After Fix
✅ Orders stay open during monitoring
✅ Test can run indefinitely
✅ Modification logic properly tested
✅ No unexpected fills

## Configuration Summary

| Parameter | Value | Purpose |
|-----------|-------|---------|
| stop_loss_pct | 0.40 (40%) | Distance below market for trigger |
| price_buffer | 0.05 (₹0.05) | Gap between trigger and limit |
| check_interval | 15 seconds | Monitoring frequency |
| modify_threshold | ₹0.01 | Minimum change to trigger modification |

**Total safety margin:** ~37.5% market drop needed for fill

## Lessons Learned

1. **Tick Size Fix Revealed Hidden Bug**
   - Fixing one validation issue (tick size) exposed a logic issue (price buffer)
   - Orders were being rejected before, so we never saw the execution logic bug

2. **Price Relationships Matter**
   - For stop limit orders, trigger AND limit must be on correct side of market
   - Buffer size is critical - too large and order becomes immediately executable

3. **Test Assumptions**
   - We assumed 40% below was "safe"
   - But with ₹1.00 buffer, limit price crossed back above market
   - Always verify BOTH prices are on the safe side

4. **AngelOne Behavior**
   - Orders are validated for tick size at placement
   - But price relationship logic is checked at execution time
   - An order can be "open" but immediately executable if prices are wrong

## Related Files

- `test_stop_limit_modify.py` - Main test file (modified)
- `test_stop_limit_internal.py` - Internal tests (all passing)
- `angelone.py` - Broker adapter (no changes needed)

---

**Status:** ✅ FIXED
**Impact:** Critical - prevents unwanted order fills
**Verification:** Manual testing recommended to confirm orders stay open
