# Detailed Log Example - With Explanations

**Updated:** Now shows explicit Order ID, WHY modified, and HOW modified

---

## Console Output Example

```
================================================================================
STEP 2: PLACE STOP LIMIT ORDER
================================================================================

✓✓✓ ORDER PLACED SUCCESSFULLY ✓✓✓
    Order ID: 240205001234567
    Strike: 27050 CE
    Type: STOP LIMIT BUY (STOPLOSS_LIMIT)
    Product: INTRADAY
    Quantity: 65 (1 lot)

    CALCULATION:
    Current LTP: ₹2.50
    Trigger (20% below): 2.50 × 0.8 = ₹2.00
    Limit (trigger + buffer): 2.00 + 1.00 = ₹3.00

    Gap to trigger: ₹0.50 (20.0%)
    Status: PENDING

    WHY THIS ORDER WILL NEVER FILL:
    • Trigger is 20% below market (₹2.00 vs ₹2.50)
    • We'll keep updating trigger every minute
    • Market would need to crash 20% in <60 seconds to fill
    • This proves our modification logic works!

================================================================================
STEP 3: PERIODIC LTP CHECK AND ORDER MODIFICATION
================================================================================
RUNNING INDEFINITELY - Press Ctrl+C to stop
Order will NEVER fill because trigger stays 20% below market
================================================================================

--- Iteration 1 ---
Waiting 60 seconds...
Order ID: 240205001234567
Current LTP: ₹2.60
Current trigger: ₹2.00
Current limit: ₹3.00

Calculation:
  20% below LTP: 2.60 × 0.8 = ₹2.08
  Limit price: 2.08 + 1.00 = ₹3.08

Changes:
  LTP change: +₹0.10
  Trigger change: +₹0.08 (from ₹2.00 to ₹2.08)

✓ MODIFYING ORDER
    Reason: Trigger change ₹0.08 >= ₹0.50 threshold
    Order ID: 240205001234567
    Strike: 27050 CE

    WHY: Current LTP is ₹2.60
         We need trigger 20% below = ₹2.08
         Old trigger ₹2.00 is outdated

    HOW: Sending modify request with:
         • Trigger: ₹2.00 → ₹2.08 (change: +₹0.08)
         • Limit:   ₹3.00 → ₹3.08

✓✓✓ ORDER MODIFIED SUCCESSFULLY ✓✓✓
    Order ID: 240205001234567
    Status: TRIGGER_PENDING
    Updated trigger: ₹2.08 (was ₹2.00)
    Updated limit: ₹3.08 (was ₹3.00)
    LTP at modification: ₹2.60
    Gap to trigger: ₹0.52 (20.0%)


--- Iteration 2 ---
Waiting 60 seconds...
Order ID: 240205001234567
Current LTP: ₹2.55
Current trigger: ₹2.08
Current limit: ₹3.08

Calculation:
  20% below LTP: 2.55 × 0.8 = ₹2.04
  Limit price: 2.04 + 1.00 = ₹3.04

Changes:
  LTP change: -₹0.05
  Trigger change: -₹0.04 (from ₹2.08 to ₹2.04)

⚠️  SKIPPING MODIFICATION
    Reason: Trigger change ₹0.04 < ₹0.50 threshold
    Order 240205001234567 remains unchanged
    Trigger stays at: ₹2.08
    Limit stays at: ₹3.08


--- Iteration 3 ---
Waiting 60 seconds...
Order ID: 240205001234567
Current LTP: ₹2.75
Current trigger: ₹2.08
Current limit: ₹3.08

Calculation:
  20% below LTP: 2.75 × 0.8 = ₹2.20
  Limit price: 2.20 + 1.00 = ₹3.20

Changes:
  LTP change: +₹0.20
  Trigger change: +₹0.12 (from ₹2.08 to ₹2.20)

⚠️  SKIPPING MODIFICATION
    Reason: Trigger change ₹0.12 < ₹0.50 threshold
    Order 240205001234567 remains unchanged
    Trigger stays at: ₹2.08
    Limit stays at: ₹3.08


--- Iteration 4 ---
Waiting 60 seconds...
Order ID: 240205001234567
Current LTP: ₹3.20
Current trigger: ₹2.08
Current limit: ₹3.08

Calculation:
  20% below LTP: 3.20 × 0.8 = ₹2.56
  Limit price: 2.56 + 1.00 = ₹3.56

Changes:
  LTP change: +₹0.45
  Trigger change: +₹0.48 (from ₹2.08 to ₹2.56)

⚠️  SKIPPING MODIFICATION
    Reason: Trigger change ₹0.48 < ₹0.50 threshold
    Order 240205001234567 remains unchanged
    Trigger stays at: ₹2.08
    Limit stays at: ₹3.08


--- Iteration 5 ---
Waiting 60 seconds...
Order ID: 240205001234567
Current LTP: ₹3.80
Current trigger: ₹2.08
Current limit: ₹3.08

Calculation:
  20% below LTP: 3.80 × 0.8 = ₹3.04
  Limit price: 3.04 + 1.00 = ₹4.04

Changes:
  LTP change: +₹0.60
  Trigger change: +₹0.96 (from ₹2.08 to ₹3.04)

✓ MODIFYING ORDER
    Reason: Trigger change ₹0.96 >= ₹0.50 threshold
    Order ID: 240205001234567
    Strike: 27050 CE

    WHY: Current LTP is ₹3.80
         We need trigger 20% below = ₹3.04
         Old trigger ₹2.08 is outdated

    HOW: Sending modify request with:
         • Trigger: ₹2.08 → ₹3.04 (change: +₹0.96)
         • Limit:   ₹3.08 → ₹4.04

✓✓✓ ORDER MODIFIED SUCCESSFULLY ✓✓✓
    Order ID: 240205001234567
    Status: TRIGGER_PENDING
    Updated trigger: ₹3.04 (was ₹2.08)
    Updated limit: ₹4.04 (was ₹3.08)
    LTP at modification: ₹3.80
    Gap to trigger: ₹0.76 (20.0%)


[Continues indefinitely...]

[User presses Ctrl+C]

^C
================================================================================
STOPPED BY USER (Ctrl+C)
================================================================================
Total iterations completed: 5
Proceeding to cleanup...

================================================================================
STEP 4: CANCEL ORDER AND CLEANUP
================================================================================
✓ Order cancelled successfully

================================================================================
STEP 5: SAVE LOGS
================================================================================
✓ Logs saved to: stop_limit_test_20260205_100023.json

================================================================================
TEST SUMMARY
================================================================================
Total iterations: 5
Successful modifications: 2
Failed modifications: 0
Skipped modifications: 3
================================================================================
```

---

## JSON Log File Example

**File:** `stop_limit_test_20260205_100023.json`

```json
{
  "test_config": {
    "underlying": "NIFTY",
    "option_type": "CE",
    "strike_offset": 0,
    "quantity": 65,
    "stop_loss_pct": 0.2,
    "check_interval_seconds": 60,
    "max_iterations": null,
    "price_buffer": 1.0
  },
  "test_params": {
    "strike": 27050,
    "expiry": "2026-02-10",
    "token": "58661"
  },
  "logs": [
    {
      "iteration": 0,
      "timestamp": "2026-02-05T10:00:23.456789",
      "action": "PLACE_ORDER",
      "order_id": "240205001234567",
      "strike": 27050,
      "option_type": "CE",
      "product_type": "INTRADAY",
      "ltp": 2.5,
      "trigger_price": 2.0,
      "limit_price": 3.0,
      "gap_to_trigger": 0.5,
      "gap_percentage": 20.0,
      "order_status": "PENDING",
      "explanation": "Placed stop limit BUY order 240205001234567 for strike 27050 CE at LTP ₹2.50. Set trigger at ₹2.00 (20% below LTP) and limit at ₹3.00. Gap to trigger is ₹0.50 (20.0%). Order will not fill unless market crashes 20% before next modification."
    },
    {
      "iteration": 1,
      "timestamp": "2026-02-05T10:01:25.123456",
      "action": "MODIFY_ORDER",
      "order_id": "240205001234567",
      "strike": 27050,
      "option_type": "CE",
      "ltp": 2.6,
      "ltp_change": 0.1,
      "old_trigger_price": 2.0,
      "new_trigger_price": 2.08,
      "trigger_change": 0.08,
      "old_limit_price": 3.0,
      "new_limit_price": 3.08,
      "limit_change": 0.08,
      "order_status": "TRIGGER_PENDING",
      "gap_to_trigger": 0.52,
      "gap_percentage": 20.0,
      "explanation": "Modified order 240205001234567 because LTP changed to ₹2.60. Calculated 20% below = ₹2.08. Updated trigger from ₹2.00 to ₹2.08 (change: +₹0.08). Gap to trigger is now ₹0.52 (20.0%)."
    },
    {
      "iteration": 2,
      "timestamp": "2026-02-05T10:02:26.789012",
      "action": "SKIP_MODIFY",
      "order_id": "240205001234567",
      "ltp": 2.55,
      "ltp_change": -0.05,
      "old_trigger_price": 2.08,
      "new_trigger_price": 2.04,
      "trigger_change": -0.04,
      "old_limit_price": 3.08,
      "new_limit_price": 3.04,
      "reason": "trigger_change_below_threshold",
      "threshold": 0.5,
      "explanation": "Trigger change ₹0.04 is less than ₹0.50 threshold, keeping order unchanged"
    },
    {
      "iteration": 3,
      "timestamp": "2026-02-05T10:03:27.345678",
      "action": "SKIP_MODIFY",
      "order_id": "240205001234567",
      "ltp": 2.75,
      "ltp_change": 0.2,
      "old_trigger_price": 2.08,
      "new_trigger_price": 2.2,
      "trigger_change": 0.12,
      "old_limit_price": 3.08,
      "new_limit_price": 3.2,
      "reason": "trigger_change_below_threshold",
      "threshold": 0.5,
      "explanation": "Trigger change ₹0.12 is less than ₹0.50 threshold, keeping order unchanged"
    },
    {
      "iteration": 4,
      "timestamp": "2026-02-05T10:04:28.901234",
      "action": "SKIP_MODIFY",
      "order_id": "240205001234567",
      "ltp": 3.2,
      "ltp_change": 0.45,
      "old_trigger_price": 2.08,
      "new_trigger_price": 2.56,
      "trigger_change": 0.48,
      "old_limit_price": 3.08,
      "new_limit_price": 3.56,
      "reason": "trigger_change_below_threshold",
      "threshold": 0.5,
      "explanation": "Trigger change ₹0.48 is less than ₹0.50 threshold, keeping order unchanged"
    },
    {
      "iteration": 5,
      "timestamp": "2026-02-05T10:05:29.567890",
      "action": "MODIFY_ORDER",
      "order_id": "240205001234567",
      "strike": 27050,
      "option_type": "CE",
      "ltp": 3.8,
      "ltp_change": 0.6,
      "old_trigger_price": 2.08,
      "new_trigger_price": 3.04,
      "trigger_change": 0.96,
      "old_limit_price": 3.08,
      "new_limit_price": 4.04,
      "limit_change": 0.96,
      "order_status": "TRIGGER_PENDING",
      "gap_to_trigger": 0.76,
      "gap_percentage": 20.0,
      "explanation": "Modified order 240205001234567 because LTP changed to ₹3.80. Calculated 20% below = ₹3.04. Updated trigger from ₹2.08 to ₹3.04 (change: +₹0.96). Gap to trigger is now ₹0.76 (20.0%)."
    },
    {
      "iteration": "final",
      "timestamp": "2026-02-05T10:05:30.123456",
      "action": "CANCEL_ORDER",
      "order_id": "240205001234567",
      "order_status": "CANCELLED"
    }
  ]
}
```

---

## Key Features of Detailed Logging

### ✅ Order ID Always Shown
Every log entry shows: `"order_id": "240205001234567"`

### ✅ WHY Modified - Explicit Reasons
```json
"explanation": "Modified order 240205001234567 because LTP changed to ₹3.80.
                Calculated 20% below = ₹3.04.
                Updated trigger from ₹2.08 to ₹3.04 (change: +₹0.96).
                Gap to trigger is now ₹0.76 (20.0%)."
```

### ✅ HOW Modified - Shows Changes
```json
"old_trigger_price": 2.08,
"new_trigger_price": 3.04,
"trigger_change": 0.96,
"old_limit_price": 3.08,
"new_limit_price": 4.04,
"limit_change": 0.96
```

### ✅ Calculation Shown
Console shows:
```
Calculation:
  20% below LTP: 3.80 × 0.8 = ₹3.04
  Limit price: 3.04 + 1.00 = ₹4.04
```

### ✅ Gap Always Tracked
```json
"gap_to_trigger": 0.76,
"gap_percentage": 20.0
```

### ✅ Skip Reasons Explained
```json
"reason": "trigger_change_below_threshold",
"threshold": 0.5,
"explanation": "Trigger change ₹0.12 is less than ₹0.50 threshold, keeping order unchanged"
```

---

## What Each Log Entry Contains

### PLACE_ORDER Entry
- Order ID ✓
- Strike & option type ✓
- Product type (INTRADAY) ✓
- Initial LTP ✓
- Initial trigger & limit ✓
- Gap to trigger ✓
- Full explanation ✓

### MODIFY_ORDER Entry
- Order ID ✓
- Strike & option type ✓
- Current LTP & change ✓
- Old trigger & new trigger ✓
- Trigger change amount ✓
- Old limit & new limit ✓
- Limit change amount ✓
- Order status ✓
- Gap to trigger ✓
- Full explanation (WHY & HOW) ✓

### SKIP_MODIFY Entry
- Order ID ✓
- Current LTP ✓
- Calculated trigger (not applied) ✓
- Reason for skipping ✓
- Threshold value ✓
- Full explanation ✓

### CANCEL_ORDER Entry
- Order ID ✓
- Final status (CANCELLED) ✓

---

## Excel Import Format

The JSON can be imported to Excel showing:

| Iteration | Action | Order ID | LTP | Old Trigger | New Trigger | Change | Reason |
|-----------|--------|----------|-----|-------------|-------------|--------|--------|
| 0 | PLACE | 240205001234567 | 2.50 | - | 2.00 | - | Initial placement |
| 1 | MODIFY | 240205001234567 | 2.60 | 2.00 | 2.08 | +0.08 | LTP changed, trigger outdated |
| 2 | SKIP | 240205001234567 | 2.55 | 2.08 | 2.04 | -0.04 | Below threshold |
| 3 | SKIP | 240205001234567 | 2.75 | 2.08 | 2.20 | +0.12 | Below threshold |
| 4 | SKIP | 240205001234567 | 3.20 | 2.08 | 2.56 | +0.48 | Below threshold |
| 5 | MODIFY | 240205001234567 | 3.80 | 2.08 | 3.04 | +0.96 | LTP changed significantly |
| final | CANCEL | 240205001234567 | - | - | - | - | Test complete |

---

**Every action is now fully explained with Order ID, WHY, and HOW!**
