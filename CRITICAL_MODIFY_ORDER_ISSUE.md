# CRITICAL ISSUE: modify_order() Implementation is Incomplete

**Date:** 2026-02-05
**Severity:** HIGH
**Impact:** modify_order() will likely FAIL when called

---

## Problem Summary

The current `modify_order()` implementation in `/paper_trading/brokers/adapter/plugins/angelone.py` (lines 609-656) is missing **required parameters** that the AngelOne SmartAPI expects.

---

## Current Implementation (Line 619-632)

```python
modify_params = {
    'variety': 'NORMAL',
    'orderid': order_id
}

if 'price' in changes:
    modify_params['price'] = str(changes['price'])
if 'quantity' in changes:
    modify_params['quantity'] = str(changes['quantity'])
if 'trigger_price' in changes:
    modify_params['triggerprice'] = str(changes['trigger_price'])

response = self._smart_api.modifyOrder(modify_params)
```

**Parameters sent:** 2-5 parameters
- ✓ `variety`: 'NORMAL'
- ✓ `orderid`: Order ID
- ? `price`: Optional
- ? `quantity`: Optional
- ? `triggerprice`: Optional

---

## AngelOne API Requirements

According to AngelOne SmartAPI documentation, `modifyOrder` requires:

| Parameter | Type | Required | Current Status |
|-----------|------|----------|----------------|
| `variety` | string | ✓ | ✓ PRESENT |
| `orderid` | string | ✓ | ✓ PRESENT |
| `ordertype` | string | ✓ | **✗ MISSING** |
| `producttype` | string | ✓ | **✗ MISSING** |
| `duration` | string | ✓ | **✗ MISSING** |
| `price` | string | ✓ | ? OPTIONAL |
| `quantity` | string | ✓ | ? OPTIONAL |
| `tradingsymbol` | string | ✓ | **✗ MISSING** |
| `symboltoken` | string | ✓ | **✗ MISSING** |
| `exchange` | string | ✓ | **✗ MISSING** |
| `triggerprice` | string | For SL orders | ? OPTIONAL |

### Missing Critical Fields

1. **`ordertype`**: e.g., "STOPLOSS_LIMIT" - **REQUIRED**
2. **`producttype`**: e.g., "INTRADAY" - **REQUIRED**
3. **`duration`**: e.g., "DAY" - **REQUIRED**
4. **`tradingsymbol`**: e.g., "NIFTY10FEB2626000CE" - **REQUIRED**
5. **`symboltoken`**: e.g., "58661" - **REQUIRED**
6. **`exchange`**: e.g., "NFO" - **REQUIRED**

---

## Why This Wasn't Caught

The `place_order()` method (lines 538-560) includes all these fields:

```python
order_params = {
    'variety': 'NORMAL',
    'tradingsymbol': trading_symbol,      # ✓ Present
    'symboltoken': str(token),            # ✓ Present
    'transactiontype': order.transaction_type.value,
    'exchange': 'NFO',                    # ✓ Present
    'ordertype': self.ORDER_TYPE_MAP.get(order.order_type, "MARKET"),  # ✓ Present
    'producttype': self.PRODUCT_MAP.get(order.product_type, "INTRADAY"),  # ✓ Present
    'duration': 'DAY',                    # ✓ Present
    'quantity': str(order.quantity)
}
```

But `modify_order()` doesn't include them!

---

## Impact

**Stop limit order modification will FAIL** because:
1. AngelOne API will reject the request (missing required fields)
2. Error message: "Invalid parameters" or similar
3. Order will NOT be modified
4. Our test will fail on Test 5 (modify order test)

---

## Solution

We need to FIX the `modify_order()` method to include all required fields.

### Option 1: Store Order Details (Recommended)

Modify the adapter to store order details when placing orders, so we can retrieve them for modification:

```python
# In __init__:
self._order_details = {}  # Store {order_id: {tradingsymbol, symboltoken, etc.}}

# In place_order (after successful placement):
self._order_details[order_id] = {
    'tradingsymbol': trading_symbol,
    'symboltoken': token,
    'exchange': 'NFO',
    'ordertype': self.ORDER_TYPE_MAP.get(order.order_type),
    'producttype': self.PRODUCT_MAP.get(order.product_type),
    'duration': 'DAY',
    'transactiontype': order.transaction_type.value,
    'quantity': str(order.quantity)
}

# In modify_order:
if order_id not in self._order_details:
    # Fallback: fetch from order book
    order_info = self.get_order(order_id)
    # Extract details from order_info

stored_details = self._order_details.get(order_id, {})

modify_params = {
    'variety': 'NORMAL',
    'orderid': order_id,
    'tradingsymbol': stored_details.get('tradingsymbol'),
    'symboltoken': stored_details.get('symboltoken'),
    'exchange': stored_details.get('exchange', 'NFO'),
    'ordertype': stored_details.get('ordertype', 'MARKET'),
    'producttype': stored_details.get('producttype', 'INTRADAY'),
    'duration': stored_details.get('duration', 'DAY'),
    'quantity': stored_details.get('quantity')
}

# Then add the changes
if 'price' in changes:
    modify_params['price'] = str(changes['price'])
if 'trigger_price' in changes:
    modify_params['triggerprice'] = str(changes['trigger_price'])
if 'quantity' in changes:
    modify_params['quantity'] = str(changes['quantity'])
```

### Option 2: Fetch from Order Book

Query the order book to get order details before modifying:

```python
def modify_order(self, order_id: str, changes: dict) -> OrderResponse:
    # Get current order details
    order_info = self.get_order(order_id)
    if not order_info:
        return OrderResponse(success=False, message="Order not found")

    # Extract required fields from order_info
    # Then build modify_params with all required fields
```

### Option 3: Pass Full Order Context

Change the method signature to accept full order context:

```python
def modify_order(self, order_id: str, changes: dict,
                 order_context: dict = None) -> OrderResponse:
    """
    Args:
        order_context: Dict with tradingsymbol, symboltoken, exchange, etc.
    """
```

---

## Recommended Fix (Minimal Change)

**Enhance modify_order() to fetch missing details from order book:**

```python
def modify_order(self, order_id: str, changes: dict) -> OrderResponse:
    """Modify existing order."""
    if not self._connected:
        return OrderResponse(
            success=False,
            order_id=order_id,
            status=OrderStatus.REJECTED,
            message="Not connected"
        )

    try:
        # Get current order details to extract required fields
        current_order = self.get_order(order_id)
        if not current_order:
            return OrderResponse(
                success=False,
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message="Order not found in order book"
            )

        # Get full order from AngelOne order book to extract tradingsymbol, etc.
        orders = self._smart_api.orderBook()
        if not orders or not orders.get('status'):
            return OrderResponse(
                success=False,
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message="Could not fetch order book"
            )

        # Find our order in the order book
        order_data = None
        for o in orders.get('data', []):
            if str(o.get('orderid')) == str(order_id):
                order_data = o
                break

        if not order_data:
            return OrderResponse(
                success=False,
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message="Order not found in order book"
            )

        # Build modify_params with ALL required fields
        modify_params = {
            'variety': order_data.get('variety', 'NORMAL'),
            'orderid': order_id,
            'tradingsymbol': order_data.get('tradingsymbol'),
            'symboltoken': order_data.get('symboltoken'),
            'exchange': order_data.get('exchange', 'NFO'),
            'ordertype': order_data.get('ordertype', 'MARKET'),
            'producttype': order_data.get('producttype', 'INTRADAY'),
            'duration': order_data.get('duration', 'DAY'),
            'quantity': str(order_data.get('quantity', 0))
        }

        # Apply changes
        if 'price' in changes:
            modify_params['price'] = str(changes['price'])
        else:
            modify_params['price'] = str(order_data.get('price', 0))

        if 'trigger_price' in changes:
            modify_params['triggerprice'] = str(changes['trigger_price'])
        else:
            modify_params['triggerprice'] = str(order_data.get('triggerprice', 0))

        if 'quantity' in changes:
            modify_params['quantity'] = str(changes['quantity'])

        response = self._smart_api.modifyOrder(modify_params)

        if response and response.get('status'):
            return OrderResponse(
                success=True,
                order_id=order_id,
                status=OrderStatus.PENDING,
                message="Order modified"
            )
        else:
            return OrderResponse(
                success=False,
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message=response.get('message', 'Modification failed')
            )

    except Exception as e:
        logger.error(f"Order modification error: {e}")
        return OrderResponse(
            success=False,
            order_id=order_id,
            status=OrderStatus.REJECTED,
            message=str(e)
        )
```

---

## Testing Plan

1. **Run Test 5** (modify order test) - This will likely FAIL with current code
2. **Apply the fix** to angelone.py
3. **Re-run Test 5** - Should PASS after fix
4. **Run full integration test** - Should work end-to-end

---

## Action Required

**DO NOT RUN THE FULL TEST YET!**

Instead:
1. Run component tests 1-4 (these don't use modify)
2. Run component test 5 to CONFIRM the issue
3. Apply the fix to angelone.py
4. Re-run test 5 to verify fix
5. Then run the full integration test

---

## Files to Modify

**File:** `/paper_trading/brokers/adapter/plugins/angelone.py`
**Method:** `modify_order()` (lines 609-656)
**Change:** Add logic to fetch and include all required AngelOne API fields

---

## Summary

- ✗ **Current code WILL FAIL** when modifying stop limit orders
- ✓ **Fix is straightforward** - fetch order details and include required fields
- ✓ **Testing plan in place** - component tests will verify the fix
- ⚠️ **DO NOT proceed with full test until fix is applied**

---

**Next Steps:**
1. Review this document
2. Apply the recommended fix
3. Run component tests to verify
4. Document the fix in a separate file
