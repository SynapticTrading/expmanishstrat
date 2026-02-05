# Revert Guide - Order Fill Confirmation Fix

## Date Applied: 2026-02-04
## Base Commit: 7e0c70a (live branch)

---

## Quick Revert (One Command)

To revert ALL changes instantly:

```bash
cd /Users/Algo_Trading/manishsir_options
git checkout 7e0c70a -- paper_trading/core/live_broker.py
```

This will restore the file to its exact state before the fix.

---

## Files Modified

### Only 1 file was changed:

```
paper_trading/core/live_broker.py
```

---

## Changes Made

### Change 1: Added New Method `_wait_until_order_resolved()`

**Location**: After line 442 (after `_wait_for_fill()` method)

**Lines Added**: Approximately 105 lines (lines 444-548)

**What was added**:
```python
def _wait_until_order_resolved(self, order_id, timeout=None):
    """
    Wait for order to reach a final state (COMPLETE, REJECTED, or CANCELLED).

    # ... full method implementation ...
    """
```

**To revert this change only**:
- Delete lines 444-548 (the entire `_wait_until_order_resolved` method)
- This method didn't exist before, so just remove it entirely

---

### Change 2: Modified `buy()` Method

**Location**: Lines 181-234 (approximately)

**Original Code (7e0c70a)**:
```python
print(f"[{datetime.now()}] ✓ Order placed: {response.order_id}")

# 4. Wait for fill (for MARKET orders)
actual_price = price
if self.order_type == OrderType.MARKET:
    filled = self._wait_for_fill(response.order_id, timeout=30)
    if not filled:
        print(f"[{datetime.now()}] ⚠️  Order not filled within timeout, attempting cancel...")
        self.adapter.cancel_order(response.order_id)
        return None

    # 5. Get actual fill price with retry logic
    print(f"[{datetime.now()}] Fetching fill price from broker...")
    order_status = self._get_order_with_retry(response.order_id)  # Uses config defaults

    if order_status and order_status.average_price:
        actual_price = order_status.average_price
        slippage = actual_price - price
        slippage_pct = (slippage / price) * 100 if price > 0 else 0

        print(f"[{datetime.now()}] ✓ Order filled at ₹{actual_price:.2f}")
        if abs(slippage) > 0.01:  # Show slippage if > 1 paisa
            print(f"[{datetime.now()}]   Slippage: ₹{slippage:+.2f} ({slippage_pct:+.2f}%)")
    else:
        print(f"[{datetime.now()}] ⚠️  Could not get fill price after retries, using requested price ₹{price:.2f}")

# 6. Create position object
```

**New Code (After Fix)**:
```python
print(f"[{datetime.now()}] ✓ Order placed: {response.order_id}")

# 4. Wait for order to reach final state (COMPLETE, REJECTED, or CANCELLED)
# This is the KEY fix - don't create position until we KNOW what happened
order_status = self._wait_until_order_resolved(
    response.order_id,
    timeout=120  # 2 minutes max wait
)

if not order_status:
    # Could not get status even after 2 minutes
    print(f"[{datetime.now()}] ✗ Could not determine order status after 2 minutes")
    print(f"[{datetime.now()}] ⚠️  Attempting to cancel order {response.order_id}...")
    self.adapter.cancel_order(response.order_id)
    return None  # Go to next candle

# 5. Handle different order statuses
if order_status.status == OrderStatus.REJECTED:
    # Order was rejected by broker
    print(f"[{datetime.now()}] ✗ Order {response.order_id} was REJECTED by broker")
    if order_status.message:
        print(f"[{datetime.now()}]   Reason: {order_status.message}")
    return None  # Go to next candle

elif order_status.status == OrderStatus.CANCELLED:
    # Order was cancelled
    print(f"[{datetime.now()}] ✗ Order {response.order_id} was CANCELLED")
    return None  # Go to next candle

elif order_status.status == OrderStatus.COMPLETE:
    # ✅ Order is FILLED - Proceed with position creation

    # Get fill price
    if order_status.average_price:
        actual_price = order_status.average_price
        slippage = actual_price - price
        slippage_pct = (slippage / price) * 100 if price > 0 else 0

        print(f"[{datetime.now()}] ✓ Order filled at ₹{actual_price:.2f}")
        if abs(slippage) > 0.01:  # Show slippage if > 1 paisa
            print(f"[{datetime.now()}]   Slippage: ₹{slippage:+.2f} ({slippage_pct:+.2f}%)")
    else:
        # Status is COMPLETE but no fill price (rare API issue)
        # Use requested price as fallback since we confirmed order filled
        print(f"[{datetime.now()}] ⚠️  Order is COMPLETE but no fill price available")
        print(f"[{datetime.now()}] ⚠️  Using requested price ₹{price:.2f}")
        actual_price = price

else:
    # Order is still PENDING/OPEN after timeout
    print(f"[{datetime.now()}] ⚠️  Order {response.order_id} still in state: {order_status.status.value}")
    print(f"[{datetime.now()}] ⚠️  Attempting to cancel...")
    self.adapter.cancel_order(response.order_id)
    return None  # Go to next candle

# 6. Create position object (ONLY if order was COMPLETE)
```

**To revert this change**:
Replace lines 181-234 with the original code shown above.

---

### Change 3: Modified `sell()` Method

**Location**: Lines 312-378 (approximately)

**Original Code (7e0c70a)**:
```python
print(f"[{datetime.now()}] ✓ Sell order placed: {response.order_id}")

# 4. Wait for fill
actual_exit_price = price
if self.order_type == OrderType.MARKET:
    filled = self._wait_for_fill(response.order_id, timeout=30)
    if not filled:
        print(f"[{datetime.now()}] ✗ Sell order not filled within timeout")
        position._sold = False
        return False

    # 5. Get actual exit price with retry logic
    print(f"[{datetime.now()}] Fetching exit fill price from broker...")
    order_status = self._get_order_with_retry(response.order_id)  # Uses config defaults

    if order_status and order_status.average_price:
        actual_exit_price = order_status.average_price
        slippage = actual_exit_price - price
        slippage_pct = (slippage / price) * 100 if price > 0 else 0

        print(f"[{datetime.now()}] ✓ Sell order filled at ₹{actual_exit_price:.2f}")
        if abs(slippage) > 0.01:  # Show slippage if > 1 paisa
            print(f"[{datetime.now()}]   Slippage: ₹{slippage:+.2f} ({slippage_pct:+.2f}%)")
    else:
        print(f"[{datetime.now()}] ⚠️  Could not get exit fill price after retries, using requested price ₹{price:.2f}")

# 6. Calculate P&L
```

**New Code (After Fix)**:
```python
print(f"[{datetime.now()}] ✓ Sell order placed: {response.order_id}")

# 4. Wait for order to reach final state (COMPLETE, REJECTED, or CANCELLED)
order_status = self._wait_until_order_resolved(
    response.order_id,
    timeout=120  # 2 minutes max wait
)

if not order_status:
    # Could not get status even after 2 minutes
    print(f"[{datetime.now()}] ✗ Could not determine exit order status after 2 minutes")
    print(f"[{datetime.now()}] ⚠️  Attempting to cancel order {response.order_id}...")
    self.adapter.cancel_order(response.order_id)
    position._sold = False  # Reset so exit can be retried
    return False

# 5. Handle different order statuses
if order_status.status == OrderStatus.REJECTED:
    # Exit order was rejected by broker
    print(f"[{datetime.now()}] ✗ Exit order {response.order_id} was REJECTED by broker")
    if order_status.message:
        print(f"[{datetime.now()}]   Reason: {order_status.message}")
    position._sold = False  # Reset so exit can be retried
    return False

elif order_status.status == OrderStatus.CANCELLED:
    # Exit order was cancelled
    print(f"[{datetime.now()}] ✗ Exit order {response.order_id} was CANCELLED")
    position._sold = False  # Reset so exit can be retried
    return False

elif order_status.status == OrderStatus.COMPLETE:
    # ✅ Exit order is FILLED - Proceed with P&L calculation

    # Get exit fill price
    if order_status.average_price:
        actual_exit_price = order_status.average_price
        slippage = actual_exit_price - price
        slippage_pct = (slippage / price) * 100 if price > 0 else 0

        print(f"[{datetime.now()}] ✓ Sell order filled at ₹{actual_exit_price:.2f}")
        if abs(slippage) > 0.01:  # Show slippage if > 1 paisa
            print(f"[{datetime.now()}]   Slippage: ₹{slippage:+.2f} ({slippage_pct:+.2f}%)")
    else:
        # Status is COMPLETE but no fill price (rare API issue)
        # Use requested price as fallback since we confirmed order filled
        print(f"[{datetime.now()}] ⚠️  Exit order is COMPLETE but no fill price available")
        print(f"[{datetime.now()}] ⚠️  Using requested price ₹{price:.2f}")
        actual_exit_price = price

else:
    # Exit order is still PENDING/OPEN after timeout
    print(f"[{datetime.now()}] ⚠️  Exit order {response.order_id} still in state: {order_status.status.value}")
    print(f"[{datetime.now()}] ⚠️  Attempting to cancel...")
    self.adapter.cancel_order(response.order_id)
    position._sold = False  # Reset so exit can be retried
    return False

# 6. Calculate P&L (ONLY if exit order was COMPLETE)
```

**To revert this change**:
Replace lines 312-378 with the original code shown above.

---

## Summary of Changes

| Change | Lines | What Changed |
|--------|-------|--------------|
| **New Method** | 444-548 | Added `_wait_until_order_resolved()` |
| **buy() Method** | 181-234 | Replaced order fill logic |
| **sell() Method** | 312-378 | Replaced order fill logic |

**Total**: ~200 lines modified/added

---

## Step-by-Step Manual Revert

If you want to revert manually:

### Step 1: Remove `_wait_until_order_resolved()` Method

1. Open `paper_trading/core/live_broker.py`
2. Find the method (around line 444)
3. Delete from `def _wait_until_order_resolved(` until the end of the method (before `def _log_trade(`)

### Step 2: Revert `buy()` Method

1. Find the `buy()` method (around line 134)
2. Locate the section starting with `# 4. Wait for order to reach final state`
3. Replace it with the original code:
   - Change `_wait_until_order_resolved` back to `_wait_for_fill`
   - Remove all the status checking logic
   - Keep the simple fallback: `print("Using requested price")`

### Step 3: Revert `sell()` Method

1. Find the `sell()` method (around line 267)
2. Locate the section starting with `# 4. Wait for order to reach final state`
3. Replace it with the original code (same changes as buy method)

---

## Using Git to Revert

### Option 1: Revert Entire File (Recommended)

```bash
cd /Users/Algo_Trading/manishsir_options

# Revert to 7e0c70a version
git checkout 7e0c70a -- paper_trading/core/live_broker.py

# Verify
git diff 7e0c70a -- paper_trading/core/live_broker.py
# Output should be empty (no differences)
```

### Option 2: Create Backup Before Reverting

```bash
# Create backup of current (fixed) version
cp paper_trading/core/live_broker.py paper_trading/core/live_broker.py.with_fix

# Revert to original
git checkout 7e0c70a -- paper_trading/core/live_broker.py

# Later, to restore the fix:
cp paper_trading/core/live_broker.py.with_fix paper_trading/core/live_broker.py
```

### Option 3: Use Diff Patch

```bash
# Revert using the diff file
cd /Users/Algo_Trading/manishsir_options
patch -R paper_trading/core/live_broker.py < ORDER_FILL_FIX_CHANGES.diff
```

---

## Verification After Revert

To verify revert was successful:

```bash
# Should show no differences
git diff 7e0c70a -- paper_trading/core/live_broker.py

# Check specific methods exist/don't exist
grep "_wait_until_order_resolved" paper_trading/core/live_broker.py
# After revert: Should show nothing (method doesn't exist)
```

---

## Backup Files Created

For your records, these files contain the changes:

1. **`ORDER_FILL_FIX_CHANGES.diff`**
   - Complete git diff of all changes
   - Can be used with `patch` command to revert

2. **`ORDER_FILL_CONFIRMATION_FIX.md`**
   - Detailed explanation of the issue and fix

3. **`ORDER_FILL_FIX_APPLIED.md`**
   - Summary and test results

4. **`test_order_fill_confirmation.py`**
   - Test file to verify fix works

5. **`REVERT_GUIDE_ORDER_FILL_FIX.md`** (this file)
   - Complete revert instructions

---

## Before and After Comparison

### Before (7e0c70a):
- ❌ Uses fallback price if can't fetch status
- ❌ Creates position even if order pending
- ❌ Ghost positions possible
- ⚠️ Uses `_wait_for_fill()` with 30s timeout

### After (With Fix):
- ✅ Waits for definitive order status
- ✅ Only creates position if COMPLETE
- ✅ No ghost positions
- ✅ Uses `_wait_until_order_resolved()` with 120s timeout

---

## When to Revert

Consider reverting if:
- ⚠️ Orders timing out too frequently (increase timeout instead)
- ⚠️ Want to go back to old behavior for any reason
- ⚠️ Find issues with the new logic

Consider KEEPING the fix if:
- ✅ Want accurate position tracking
- ✅ Don't want ghost positions
- ✅ Want to wait for confirmed fills

---

## Re-applying the Fix

If you revert and want to re-apply later:

```bash
# Restore from backup
cp paper_trading/core/live_broker.py.with_fix paper_trading/core/live_broker.py

# Or re-apply the patch
patch paper_trading/core/live_broker.py < ORDER_FILL_FIX_CHANGES.diff

# Or re-run the test file as reference
# (The test file shows the complete logic)
```

---

## Contact/Reference

**Fix Applied**: 2026-02-04
**Base Commit**: 7e0c70a
**Modified File**: `paper_trading/core/live_broker.py`
**Test File**: `test_order_fill_confirmation.py`
**Test Result**: All 6 scenarios passed ✅

---

## Quick Reference Commands

```bash
# View current changes
git diff 7e0c70a -- paper_trading/core/live_broker.py

# Revert to original
git checkout 7e0c70a -- paper_trading/core/live_broker.py

# Check if reverted successfully
git diff 7e0c70a -- paper_trading/core/live_broker.py
# Should output: (nothing)

# View the diff file
cat ORDER_FILL_FIX_CHANGES.diff
```

---

*Revert Guide Created: 2026-02-04*
*All changes documented for easy reversal*
