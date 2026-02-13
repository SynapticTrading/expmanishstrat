# Trigger Price Modification Issue

## Date: February 5, 2026

## Problem

After fixing rate limiting, a new issue appeared: **trigger price becomes 0.00 after modification**

### Observed Behavior

```
Iteration 5: LTP changes from ₹1.35 to ₹1.45

Modification Request:
  Trigger: ₹0.80 → ₹0.85
  Limit:   ₹0.85 → ₹0.90

API Response: ✓ Success

Broker Verification:
  Expected trigger: ₹0.85
  Actual trigger: ₹0.00  ← PROBLEM!
  Expected limit: ₹0.90
  Actual limit: ₹0.90    ← OK
```

**Key observation:** Limit price updates correctly, but trigger price becomes 0.00

---

## Investigation

### What We're Sending

The modify_order() function sends all required parameters:

```python
modify_params = {
    'variety': 'STOPLOSS',
    'orderid': '260205001248156',
    'tradingsymbol': 'NIFTY10FEB2627550CE',
    'symboltoken': '58807',
    'exchange': 'NFO',
    'ordertype': 'STOPLOSS_LIMIT',
    'producttype': 'INTRADAY',
    'duration': 'DAY',
    'quantity': '65',
    'price': '0.90',           # Limit price
    'triggerprice': '0.85'     # Trigger price
}
```

### What We're Getting Back

**API Response:** `{'status': True, 'message': 'SUCCESS'}`

**But when we verify on broker:**
- triggerprice: '0' or '0.00' or '' (need to check raw value)
- price: '0.90' ✓ (correct)

---

## Possible Causes

### 1. AngelOne API Limitation
- modifyOrder() might not support trigger price changes for STOPLOSS orders
- This could be an API bug or intentional limitation
- Limit price works, trigger doesn't

### 2. Validation Failure (Silent)
- AngelOne might be rejecting the trigger price due to some rule
- But not returning an error (silent failure)
- Returns success anyway

### 3. Parameter Format Issue
- Maybe triggerprice needs different format during modification
- Perhaps it needs to be sent as a number, not string
- Or maybe there's a different parameter name

### 4. Order Type Specific Behavior
- STOPLOSS_LIMIT orders might have special handling
- Trigger price might be "locked" after initial placement
- Can only modify limit price, not trigger

---

## Debugging Steps Added

### 1. Detailed Logging in angelone.py

Added INFO level logging to see exact parameters being sent:

```python
logger.info(f"Modify order params being sent to AngelOne API:")
logger.info(f"  variety: {modify_params.get('variety')}")
logger.info(f"  orderid: {modify_params.get('orderid')}")
logger.info(f"  tradingsymbol: {modify_params.get('tradingsymbol')}")
logger.info(f"  symboltoken: {modify_params.get('symboltoken')}")
logger.info(f"  exchange: {modify_params.get('exchange')}")
logger.info(f"  ordertype: {modify_params.get('ordertype')}")
logger.info(f"  producttype: {modify_params.get('producttype')}")
logger.info(f"  duration: {modify_params.get('duration')}")
logger.info(f"  price: {modify_params.get('price')}")
logger.info(f"  triggerprice: {modify_params.get('triggerprice')}")
logger.info(f"  quantity: {modify_params.get('quantity')}")
logger.info(f"Modify response from AngelOne: {response}")
```

### 2. Raw Order Data in Test

Added debug output to see exact values from broker:

```python
print(f"\n    DEBUG: Raw order data from broker:")
print(f"      triggerprice: '{verified_order.get('triggerprice')}'")
print(f"      price: '{verified_order.get('price')}'")
print(f"      ordertype: '{verified_order.get('ordertype')}'")
print(f"      variety: '{verified_order.get('variety')}'")
print(f"      orderstatus: '{verified_order.get('orderstatus')}'")
```

---

## Next Steps

### To Debug (Run Test Again)

1. Run the test with logging enabled
2. Check the console output for:
   - Exact params sent to modifyOrder
   - AngelOne's response
   - Raw order data from broker verification
3. Look for any error messages or warnings

### Questions to Answer

1. What is the exact raw value of 'triggerprice' after modification?
   - Is it '0', '0.00', '', or null?

2. Does the AngelOne API response contain any warnings?
   - Check response dict for additional fields

3. Does the ordertype or variety change after modification?
   - Maybe it's converting to a different order type

4. Is there a pattern to when it works vs doesn't?
   - Does it only fail on the first modification?
   - Or every modification?

---

## Potential Workarounds

### Option 1: Cancel and Re-Place (NOT IDEAL)
Instead of modifying, cancel the old order and place a new one.

**Pros:**
- Guaranteed to work
- New order has correct trigger price

**Cons:**
- Not testing the modify functionality
- Risk of missing fills during cancel/replace
- Two API calls instead of one
- Order ID changes

**Implementation:**
```python
# Cancel old order
adapter.cancel_order(order_id)

# Place new order with updated prices
new_order = adapter.place_order(OrderRequest(...,
    trigger_price=new_trigger,
    price=new_limit
))

order_id = new_order.order_id
```

### Option 2: Only Modify Limit Price (PARTIAL)
Accept that trigger can't be modified, only modify limit.

**Pros:**
- Simple
- Limit price works

**Cons:**
- Trigger price becomes stale
- Order behavior changes over time
- Not a real solution

### Option 3: Contact AngelOne Support
Report this as a potential API bug.

**Questions to ask:**
- Does modifyOrder support changing triggerprice for STOPLOSS_LIMIT orders?
- Is there a specific format or parameter needed?
- Are there any restrictions on trigger price modifications?

---

## Comparison: Placement vs Modification

### Initial Placement (WORKS ✓)

```python
# place_order()
order_params = {
    'variety': 'STOPLOSS',
    'ordertype': 'STOPLOSS_LIMIT',
    'triggerprice': '0.80',  # Works!
    'price': '0.85',
    # ... other params
}
response = smart_api.placeOrder(order_params)
# Result: Order placed with trigger=0.80, limit=0.85
```

### Modification (FAILS ✗)

```python
# modify_order()
modify_params = {
    'variety': 'STOPLOSS',
    'ordertype': 'STOPLOSS_LIMIT',
    'triggerprice': '0.85',  # Gets reset to 0.00!
    'price': '0.90',         # Works fine
    # ... other params
}
response = smart_api.modifyOrder(modify_params)
# Result: Trigger becomes 0.00, but limit=0.90 works
```

**Why does placement work but modification doesn't?**
- Different API endpoints
- Different validation rules
- Possible API limitation

---

## Impact

### Current State
- ✅ Order placement works
- ✅ Limit price modification works
- ✅ Rate limiting handled
- ❌ Trigger price modification fails (becomes 0.00)

### Test Implications
- Can still test limit price modifications
- Can't properly test stop loss distance maintenance
- Trigger price gets "stuck" at initial value (then becomes 0.00)
- Order behavior becomes unpredictable

---

## Files Modified for Debugging

1. **angelone.py**
   - Added detailed INFO logging for modify params
   - Added response logging

2. **test_stop_limit_modify.py**
   - Added raw order data debug output
   - Shows exact values from broker

---

## Status

🔍 **INVESTIGATING**

Waiting for test run with enhanced logging to see:
1. Exact parameters being sent
2. Exact response from AngelOne
3. Raw order data from broker

Once we have this data, we can determine if it's:
- API bug
- Parameter format issue
- Validation rule
- Or something else entirely

---

**Next Action:** Run test and review detailed logs
