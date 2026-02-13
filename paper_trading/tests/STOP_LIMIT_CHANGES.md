# Stop Limit Order Testing - Complete Code Changes

## Overview
This document details all code changes made to implement and fix the stop limit order testing system for AngelOne broker.

**Date**: February 5, 2026
**Purpose**: Create a testing system that places far OTM stop limit orders and continuously modifies them to ensure they never fill
**Final Configuration**: 40% stop loss with 15-second check intervals

---

## Table of Contents
1. [Bug Fixes](#bug-fixes)
2. [New Features](#new-features)
3. [Configuration Changes](#configuration-changes)
4. [New Files Created](#new-files-created)
5. [Test Results](#test-results)

---

## Bug Fixes

### 1. Critical: modify_order() Missing Required API Fields

**File**: `/paper_trading/brokers/adapter/plugins/angelone.py` (lines 609-656)

**Problem**: The modify_order() method was only sending 5 parameters to AngelOne API, but the API requires 11 fields. This caused modifications to fail silently - the API would return success but the order wouldn't actually be modified on the broker side.

**Before**:
```python
def modify_order(self, order_id: str, changes: dict) -> OrderResponse:
    if not self._connected:
        return OrderResponse(...)

    try:
        modify_params = {
            'variety': 'NORMAL',
            'orderid': order_id,
            'price': str(changes.get('price', 0)),
            'triggerprice': str(changes.get('trigger_price', 0)),
            'quantity': str(changes.get('quantity', 0))
        }
        # Missing: tradingsymbol, symboltoken, exchange, ordertype, producttype, duration

        response = self._smart_api.modifyOrder(modify_params)
        # ...
```

**After**:
```python
def modify_order(self, order_id: str, changes: dict) -> OrderResponse:
    """
    Modify existing order.
    FIXED VERSION - Includes all required AngelOne API fields.
    """
    if not self._connected:
        return OrderResponse(success=False, order_id=order_id,
                           status=OrderStatus.REJECTED, message="Not connected")

    try:
        # STEP 1: Fetch full order book to get current order details
        logger.debug(f"Fetching order book to get details for order {order_id}")
        orders = self._smart_api.orderBook()

        if not orders or not orders.get('status'):
            return OrderResponse(success=False, order_id=order_id,
                               status=OrderStatus.REJECTED,
                               message="Could not fetch order book")

        # STEP 2: Find our order in the order book
        order_data = None
        for o in orders.get('data', []):
            if str(o.get('orderid')) == str(order_id):
                order_data = o
                break

        if not order_data:
            return OrderResponse(success=False, order_id=order_id,
                               status=OrderStatus.REJECTED,
                               message=f"Order {order_id} not found in order book")

        # STEP 3: Build modify_params with ALL required fields from current order
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

        # STEP 4: Apply modifications
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

        # STEP 5: Call API
        response = self._smart_api.modifyOrder(modify_params)
        # ... rest of response handling
```

**Impact**: Critical fix - without this, order modifications don't actually work

---

### 2. Wrong Variety Parameter for Stop Loss Orders

**File**: `/paper_trading/brokers/adapter/plugins/angelone.py` (lines 538-552)

**Problem**: Using variety="NORMAL" for all orders. AngelOne requires variety="STOPLOSS" for stop loss order types (SL, SL_M).

**Error Message**: "Invalid Order Type (AB1020)"

**Before**:
```python
order_params = {
    'variety': 'NORMAL',  # Wrong for stop loss orders!
    'tradingsymbol': trading_symbol,
    'symboltoken': str(token),
    # ...
}
```

**After**:
```python
# IMPORTANT: For stop loss orders, variety must be "STOPLOSS", not "NORMAL"
variety = 'STOPLOSS' if order.order_type in [OrderType.SL, OrderType.SL_M] else 'NORMAL'

order_params = {
    'variety': variety,  # Now correct!
    'tradingsymbol': trading_symbol,
    'symboltoken': str(token),
    # ...
}
```

**Impact**: Orders would be rejected without this fix

---

### 3. Wrong Tick Size (Rounding to 1 Paise Instead of 5 Paise)

**File**: `/paper_trading/tests/test_stop_limit_modify.py`

**Problem**: AngelOne requires prices in 5 paise (₹0.05) multiples, but code was rounding to 1 paise (₹0.01).

**Error Message**: "Please set your order price in multiples of 5 paise and place order again."

**Before**:
```python
trigger_price = round(ltp * (1 - TEST_CONFIG['stop_loss_pct']), 2)  # Wrong!
limit_price = round(trigger_price + TEST_CONFIG['price_buffer'], 2)  # Wrong!
```

**After**:
```python
def _round_to_tick_size(self, price, tick_size=0.05):
    """
    Round price to nearest tick size (AngelOne requires 5 paise multiples).
    Example: 2.43 -> 2.45, 2.47 -> 2.45
    """
    return round(price / tick_size) * tick_size

# Usage:
trigger_price = self._round_to_tick_size(ltp * (1 - TEST_CONFIG['stop_loss_pct']))
limit_price = self._round_to_tick_size(trigger_price + TEST_CONFIG['price_buffer'])
```

**Impact**: Orders would be rejected without this fix

---

### 4. Credentials Field Name Mismatch

**File**: `/paper_trading/tests/test_stop_limit_modify.py` (lines 186-202)

**Problem**: Test was reading wrong field names from credentials file, causing connection to fail.

**Error Message**: "object of type 'NoneType' has no len()"

**Before**:
```python
return {
    'api_key': credentials.get('api_key'),
    'username': credentials.get('client_code'),    # Wrong field name!
    'password': credentials.get('mpin'),            # Wrong field name!
    'totp_token': credentials.get('totp_secret')    # Wrong field name!
}
```

**After**:
```python
return {
    'api_key': credentials.get('api_key'),
    'username': credentials.get('username'),      # Correct
    'password': credentials.get('password'),      # Correct
    'totp_token': credentials.get('totp_token')   # Correct
}
```

**Impact**: Connection would fail without this fix

---

### 5. Logging Bug - Showing Wrong Old/New Trigger Values

**File**: `/paper_trading/tests/test_stop_limit_modify.py`

**Problem**: The log was showing trigger_change = 0.0 for all modifications because we were updating current_trigger before saving the old value.

**Before**:
```python
# Modify order
modify_response = adapter.modify_order(order_id, {
    'trigger_price': new_trigger,
    'price': new_limit
})

# Update current values (THIS IS THE BUG!)
current_trigger = new_trigger
current_limit = new_limit

# Log modification - old and new are now the same!
logs.append({
    'old_trigger_price': current_trigger,  # Wrong - already updated!
    'new_trigger_price': new_trigger,
    'trigger_change': new_trigger - current_trigger,  # Always 0!
})
```

**After**:
```python
# SAVE old values BEFORE modification
old_trigger = broker_trigger
old_limit = broker_limit

# Modify order
modify_response = adapter.modify_order(order_id, {
    'trigger_price': new_trigger,
    'price': new_limit
})

# Update current values AFTER saving old values
current_trigger = new_trigger
current_limit = new_limit

# Log modification with CORRECT old values
logs.append({
    'broker_old_trigger_price': old_trigger,  # Correct!
    'requested_trigger_price': new_trigger,
    'actual_trigger_price': current_trigger,
    'trigger_change': current_trigger - old_trigger,  # Now correct!
})
```

**Impact**: Logs were misleading, showing no changes when changes were actually happening

---

### 6. No Order Status Verification Before Modification

**File**: `/paper_trading/tests/test_stop_limit_modify.py`

**Problem**: Code was trying to modify orders even if they were already filled, rejected, or cancelled.

**Before**:
```python
# Just blindly modify without checking status
modify_response = adapter.modify_order(order_id, changes)
```

**After**:
```python
# STEP 1: Check order status BEFORE modifying
order_book = adapter._smart_api.orderBook()
current_order = None
for o in order_book.get('data', []):
    if str(o.get('orderid')) == str(order_id):
        current_order = o
        break

order_status = current_order.get('orderstatus', '').lower()
modifiable_statuses = ['open', 'pending', 'trigger pending', 'trigger_pending']

if order_status not in modifiable_statuses:
    print(f"\n❌ CANNOT MODIFY: Order status is '{order_status}'")
    print(f"   Order can only be modified if status is: {modifiable_statuses}")
    print(f"   Breaking monitoring loop...")
    break

# Only modify if status is valid
modify_response = adapter.modify_order(order_id, changes)
```

**Impact**: Prevents errors when trying to modify non-modifiable orders

---

### 7. No Broker Verification After Modification

**File**: `/paper_trading/tests/test_stop_limit_modify.py`

**Problem**: Code was trusting the API response without verifying the order was actually modified on the broker side.

**Added Feature**:
```python
# STEP 3: VERIFY modification actually worked on broker side
print(f"\n{'='*80}")
print("VERIFYING MODIFICATION ON BROKER...")
print(f"{'='*80}")

time.sleep(1)  # Wait for broker to process

verify_book = adapter._smart_api.orderBook()
verified_order = None
for o in verify_book.get('data', []):
    if str(o.get('orderid')) == str(order_id):
        verified_order = o
        break

if verified_order:
    actual_trigger = float(verified_order.get('triggerprice', 0))
    actual_limit = float(verified_order.get('price', 0))

    print(f"Expected Trigger: ₹{new_trigger:.2f}")
    print(f"Actual Trigger:   ₹{actual_trigger:.2f}")
    print(f"Expected Limit:   ₹{new_limit:.2f}")
    print(f"Actual Limit:     ₹{actual_limit:.2f}")

    if abs(actual_trigger - new_trigger) < 0.01 and abs(actual_limit - new_limit) < 0.01:
        print(f"\n✓✓✓ MODIFICATION VERIFIED ON BROKER ✓✓✓")
        verification_status = "VERIFIED"
    else:
        print(f"\n❌ MODIFICATION FAILED ON BROKER!")
        print(f"   Broker still showing old prices")
        verification_status = "FAILED"
else:
    print(f"❌ Could not verify - order not found in order book")
    verification_status = "NOT_FOUND"
```

**Impact**: Critical for detecting silent modification failures

---

### 8. No Immediate Terminal Output

**File**: `/paper_trading/tests/test_stop_limit_modify.py` (lines 46-55)

**Problem**: Test appeared frozen for 10-30 seconds during connection because master instruments download was happening silently.

**Before**:
```python
logging.basicConfig(level=logging.INFO)
```

**After**:
```python
# Setup logging with immediate output
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Force stdout to flush immediately (no buffering)
sys.stdout.reconfigure(line_buffering=True)

# Also flush after every print
print("Message")
sys.stdout.flush()
```

**Impact**: User can see what's happening in real-time

---

## New Features

### 1. Far OTM Strike Selection with Lowest Price Finding

**File**: `/paper_trading/tests/test_stop_limit_modify.py` (lines 204-257)

**Purpose**: Find the lowest priced option among far OTM strikes (500-1900 points from ATM)

**Implementation**:
```python
def _find_lowest_priced_far_otm(self, adapter, contract_manager, atm_strike):
    """
    Find the lowest priced option among far OTM strikes.

    Strategy:
    1. Generate strike range: ATM + 500 to ATM + 1900 (step 100)
    2. Fetch LTP for each strike
    3. Return the strike with lowest price
    """
    expiry = contract_manager.get_options_expiry('current_week')

    # Generate far OTM strikes
    far_otm_strikes = range(
        atm_strike + TEST_CONFIG['far_otm_min'],      # ATM + 500
        atm_strike + TEST_CONFIG['far_otm_max'] + TEST_CONFIG['far_otm_step'],  # ATM + 1900
        TEST_CONFIG['far_otm_step']                    # Step 100
    )

    print(f"\n{'='*80}")
    print(f"SCANNING FAR OTM STRIKES FOR LOWEST PRICE")
    print(f"{'='*80}")
    print(f"ATM Strike: {atm_strike}")
    print(f"Scanning: {atm_strike + TEST_CONFIG['far_otm_min']} to {atm_strike + TEST_CONFIG['far_otm_max']}")
    print(f"Total strikes to check: {len(list(far_otm_strikes))}")

    strike_prices = {}

    for strike in far_otm_strikes:
        contract = contract_manager.get_option_contract(
            expiry, strike, TEST_CONFIG['option_type']
        )

        if contract:
            token = contract.get('token')
            ltp = adapter.get_ltp('NFO', 'NIFTY', token, strike, TEST_CONFIG['option_type'])

            if ltp and ltp > 0:
                strike_prices[strike] = (token, expiry, ltp)
                print(f"  Strike {strike}: ₹{ltp:.2f}")

            time.sleep(0.5)  # Rate limiting

    if not strike_prices:
        raise Exception("Could not find any valid far OTM strikes with prices")

    # Find lowest priced strike
    lowest_strike = min(strike_prices.keys(), key=lambda s: strike_prices[s][2])
    token, expiry, ltp = strike_prices[lowest_strike]

    print(f"\n✓ SELECTED LOWEST PRICED STRIKE:")
    print(f"  Strike: {lowest_strike}")
    print(f"  Price: ₹{ltp:.2f}")
    print(f"  Distance from ATM: {lowest_strike - atm_strike} points")

    return lowest_strike, token, expiry, ltp
```

**Impact**: Ensures we test with truly far OTM options that are unlikely to fill

---

### 2. Comprehensive Logging with WHY and HOW

**File**: `/paper_trading/tests/test_stop_limit_modify.py`

**Purpose**: Log every modification with complete context

**Log Structure**:
```python
log_entry = {
    # IDENTIFICATION
    'iteration': iteration,
    'timestamp': datetime.now().isoformat(),
    'order_id': order_id,

    # CURRENT MARKET STATE
    'current_ltp': current_ltp,
    'ltp_change_from_start': current_ltp - initial_ltp,
    'ltp_change_pct': ((current_ltp - initial_ltp) / initial_ltp) * 100,

    # WHY MODIFIED - Calculation details
    'stop_loss_pct': TEST_CONFIG['stop_loss_pct'],
    'calculated_trigger': new_trigger,
    'calculated_limit': new_limit,
    'calculation': f"{current_ltp} * (1 - {TEST_CONFIG['stop_loss_pct']}) = {new_trigger}",

    # HOW MODIFIED - Old vs New values
    'broker_old_trigger_price': old_trigger,
    'broker_old_limit_price': old_limit,
    'requested_trigger_price': new_trigger,
    'requested_limit_price': new_limit,
    'actual_trigger_price': current_trigger,
    'actual_limit_price': current_limit,

    # CHANGES
    'trigger_change': current_trigger - old_trigger,
    'limit_change': current_limit - old_limit,

    # VERIFICATION
    'verification_status': verification_status,

    # SAFETY MARGINS
    'distance_to_trigger_pct': ((current_ltp - current_trigger) / current_ltp) * 100,
    'distance_to_trigger_rupees': current_ltp - current_trigger,

    # REASON
    'modification_reason': 'Periodic update to maintain 40% stop loss distance'
}
```

**Impact**: Complete audit trail for debugging and verification

---

### 3. Auto-Cancel on Ctrl+C

**File**: `/paper_trading/tests/test_stop_limit_modify.py`

**Purpose**: Clean up pending orders when user stops the test

**Implementation**:
```python
try:
    # Main monitoring loop
    while True:
        # ... monitoring code ...
        time.sleep(TEST_CONFIG['check_interval_seconds'])

except KeyboardInterrupt:
    print(f"\n\n{'='*80}")
    print("KEYBOARD INTERRUPT - CLEANING UP")
    print(f"{'='*80}")

    # Cancel the order
    print(f"\nCancelling order {order_id}...")
    cancel_response = adapter.cancel_order(order_id)

    if cancel_response.success:
        print(f"✅ Order cancelled successfully")
    else:
        print(f"⚠️  Cancel response: {cancel_response.message}")
        print(f"   (Order may have already been filled/cancelled)")

    # Save logs before exiting
    self._save_logs(logs, log_file)

    print(f"\n{'='*80}")
    print("TEST STOPPED BY USER")
    print(f"{'='*80}")
```

**Impact**: Prevents leftover pending orders

---

### 4. Dynamic Configuration

**File**: `/paper_trading/tests/test_stop_limit_modify.py` (lines 58-70)

**Purpose**: Easy configuration changes without modifying code

**Configuration**:
```python
TEST_CONFIG = {
    # Contract selection
    'underlying': 'NIFTY',
    'option_type': 'CE',

    # Far OTM selection
    'far_otm_min': 500,        # Minimum distance from ATM (points)
    'far_otm_max': 1900,       # Maximum distance from ATM (points)
    'far_otm_step': 100,       # Step size for strike scanning

    # Order parameters
    'quantity': 65,            # Lot size for NIFTY
    'stop_loss_pct': 0.40,     # 40% below current price
    'price_buffer': 1.0,       # Limit = Trigger + ₹1.00

    # Monitoring
    'check_interval_seconds': 15,  # Check every 15 seconds
    'modify_threshold': 0.01,      # Only modify if change > ₹0.01
}
```

**Impact**: Easy to adjust parameters for different market conditions

---

## Configuration Changes

### Change 1: Stop Loss Percentage (20% → 40%)

**Reason**: Order was filling with 20% gap because market was dropping during 60-second wait periods

**Before**: `'stop_loss_pct': 0.20`
**After**: `'stop_loss_pct': 0.40`

**Impact**: Much safer margin, order unlikely to fill

---

### Change 2: Check Interval (60s → 15s)

**Reason**: 60 seconds was too long - market could drop 20% in that time

**Before**: `'check_interval_seconds': 60`
**After**: `'check_interval_seconds': 15`

**Impact**: More responsive to market changes

---

### Change 3: Modification Threshold (₹0.50 → ₹0.01)

**Reason**: ₹0.50 was too high, causing missed modifications

**Before**: `'modify_threshold': 0.50`
**After**: `'modify_threshold': 0.01`

**Impact**: More frequent modifications to keep trigger price accurate

---

## New Files Created

### 1. `/paper_trading/tests/test_stop_limit_modify.py`

**Purpose**: Main integration test for stop limit order monitoring
**Lines**: 680
**Features**:
- Far OTM strike selection with lowest price finding
- Stop limit order placement with proper variety and tick size
- Continuous monitoring with periodic modifications
- Order status verification before modification
- Broker-side verification after modification
- Comprehensive logging with WHY and HOW
- Auto-cancel on Ctrl+C
- JSON log file generation

---

### 2. `/paper_trading/tests/test_stop_limit_internal.py`

**Purpose**: Internal unit tests (no broker connection required)
**Lines**: 447
**Tests**: 12 passing tests

**Test Coverage**:
1. `test_round_to_tick_size` - Verify 5 paise rounding
2. `test_calculate_trigger_and_limit_prices` - Price calculation logic
3. `test_far_otm_range_generation` - Strike range generation
4. `test_order_status_check_modifiable` - Status validation
5. `test_order_status_check_not_modifiable` - Reject bad statuses
6. `test_modify_order_fetches_order_details` - Verify all 11 API fields
7. `test_logging_structure` - Log format validation
8. `test_verification_logic_success` - Broker verification success case
9. `test_verification_logic_failure` - Broker verification failure case
10. `test_price_change_threshold` - Modification threshold logic
11. `test_variety_parameter_for_stop_loss` - Correct variety selection
12. `test_credentials_loading` - Field name mapping

---

### 3. `/paper_trading/tests/check_open_positions.py`

**Purpose**: Quick script to check and cancel pending orders
**Lines**: 139
**Features**:
- List all open positions with P&L
- List all pending orders
- Option to cancel all pending orders
- Interactive prompts for safety

---

### 4. `/paper_trading/tests/get_today_history.py`

**Purpose**: View complete order history for today
**Lines**: 237
**Features**:
- Order book with all statuses
- Positions with P&L summary
- Trade book with executed trades
- Total buy/sell values
- Option to cancel pending orders

---

### 5. `/paper_trading/tests/close_position.py`

**Purpose**: Close open positions quickly with MARKET orders
**Lines**: 178
**Features**:
- List all open positions
- Interactive close confirmation
- Places opposite MARKET order to square off
- Handles both long and short positions

---

## Test Results

### Internal Tests (All Passing)

```
$ python -m pytest paper_trading/tests/test_stop_limit_internal.py -v

test_stop_limit_internal.py::TestStopLimitLogic::test_round_to_tick_size PASSED
test_stop_limit_internal.py::TestStopLimitLogic::test_calculate_trigger_and_limit_prices PASSED
test_stop_limit_internal.py::TestStopLimitLogic::test_far_otm_range_generation PASSED
test_stop_limit_internal.py::TestOrderStatusValidation::test_order_status_check_modifiable PASSED
test_stop_limit_internal.py::TestOrderStatusValidation::test_order_status_check_not_modifiable PASSED
test_stop_limit_internal.py::TestModifyOrderFix::test_modify_order_fetches_order_details PASSED
test_stop_limit_internal.py::TestLogging::test_logging_structure PASSED
test_stop_limit_internal.py::TestBrokerVerification::test_verification_logic_success PASSED
test_stop_limit_internal.py::TestBrokerVerification::test_verification_logic_failure PASSED
test_stop_limit_internal.py::TestPriceThreshold::test_price_change_threshold PASSED
test_stop_limit_internal.py::TestVarietyParameter::test_variety_parameter_for_stop_loss PASSED
test_stop_limit_internal.py::TestCredentials::test_credentials_loading PASSED

============================== 12 passed in 0.24s ==============================
```

### Integration Test (Live AngelOne)

**Status**: Successfully tested with real broker
**Results**:
- ✅ Far OTM strike selection working
- ✅ Order placement successful with correct variety
- ✅ Tick size rounding correct (no rejection errors)
- ✅ Modifications working on broker side
- ✅ Broker verification detecting actual prices
- ✅ Logging capturing all details
- ✅ Auto-cancel on Ctrl+C working
- ✅ With 40% stop loss and 15s interval, order never fills

---

## Summary of Changes

### Critical Fixes (System Would Not Work Without These)
1. ✅ modify_order() missing 6 required API fields
2. ✅ Wrong variety parameter for stop loss orders
3. ✅ Wrong tick size (1 paise instead of 5 paise)
4. ✅ Credentials field name mismatch

### Important Fixes (System Would Work But With Issues)
5. ✅ Logging bug showing wrong old/new values
6. ✅ No order status verification before modification
7. ✅ No broker-side verification after modification
8. ✅ No immediate terminal output

### New Features
9. ✅ Far OTM strike selection with lowest price finding
10. ✅ Comprehensive logging with WHY and HOW
11. ✅ Auto-cancel on Ctrl+C
12. ✅ Dynamic configuration
13. ✅ 12 internal unit tests
14. ✅ Helper scripts (check positions, history, close)

### Configuration Optimizations
15. ✅ Stop loss: 20% → 40%
16. ✅ Check interval: 60s → 15s
17. ✅ Modify threshold: ₹0.50 → ₹0.01

---

## Files Modified Summary

| File | Lines Changed | Type | Status |
|------|--------------|------|--------|
| angelone.py | ~100 | Modified | ✅ Fixed |
| test_stop_limit_modify.py | 680 | New | ✅ Complete |
| test_stop_limit_internal.py | 447 | New | ✅ 12/12 tests passing |
| check_open_positions.py | 139 | New | ✅ Working |
| get_today_history.py | 237 | New | ✅ Working |
| close_position.py | 178 | New | ✅ Working |

**Total Lines of Code**: ~1,800 lines
**Total Tests**: 12 passing
**Total Bugs Fixed**: 8
**Total Features Added**: 6

---

## Next Steps

The system is now fully functional and tested. To use it:

1. **Run the test**:
   ```bash
   python paper_trading/tests/test_stop_limit_modify.py
   ```

2. **Monitor in real-time**: Watch terminal output for immediate feedback

3. **Stop safely**: Press Ctrl+C to auto-cancel orders and save logs

4. **Check logs**: Review JSON file in `paper_trading/tests/logs/`

5. **Verify no leftover orders**:
   ```bash
   python paper_trading/tests/check_open_positions.py
   ```

---

**End of Document**
