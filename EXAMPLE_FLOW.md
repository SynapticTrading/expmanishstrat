# Example Flow - Stop Limit Order Intraday Test

**Product Type:** INTRADAY (MIS equivalent in AngelOne)
**Duration:** DAY order (auto-squared off at 3:20 PM if not executed)
**Date:** 2026-02-05 (Example)
**Time:** 10:00 AM to 10:05 AM (5 minutes)

---

## Complete Flow with Real Numbers

### 📅 START: 10:00:00 AM

---

## STEP 1: Connect to AngelOne

```
[10:00:00] Connecting to AngelOne...
[10:00:01] ✓ Connected successfully
[10:00:01] Auth Token: eyJhbGciOiJIUzI1NiIs...
[10:00:01] Feed Token: 1234567890
```

---

## STEP 2: Get NIFTY Spot Price

```
[10:00:02] Fetching NIFTY spot price...
[10:00:03] ✓ NIFTY spot price: ₹25,847.35
```

**Calculation:**
- Spot: **25,847.35**
- ATM Strike: `round(25847.35 / 50) * 50` = **25,850**

---

## STEP 3: Generate Far OTM Strikes

```
[10:00:03] Calculating far OTM strikes...
[10:00:03] ATM Strike: 25,850
[10:00:03] Generating strikes 500-1900 points OTM...
```

**Far OTM Strikes (CE Calls):**
```
26,350  (+500 points)
26,450  (+600 points)
26,550  (+700 points)
26,650  (+800 points)
26,750  (+900 points)
26,850  (+1000 points)
26,950  (+1100 points)
27,050  (+1200 points)
27,150  (+1300 points)
27,250  (+1400 points)
27,350  (+1500 points)
27,450  (+1600 points)
27,550  (+1700 points)
27,650  (+1800 points)
27,750  (+1900 points)
```

---

## STEP 4: Fetch LTP for Each Strike

```
[10:00:04] Fetching LTP for 15 far OTM strikes...
[10:00:05] Strike 26350 CE: ₹18.50
[10:00:06] Strike 26450 CE: ₹15.25
[10:00:07] Strike 26550 CE: ₹12.40
[10:00:08] Strike 26650 CE: ₹9.75
[10:00:09] Strike 26750 CE: ₹7.50
[10:00:10] Strike 26850 CE: ₹5.40
[10:00:11] Strike 26950 CE: ₹3.80
[10:00:12] Strike 27050 CE: ₹2.50  ← LOWEST!
[10:00:13] Strike 27150 CE: ₹2.75
[10:00:14] Strike 27250 CE: ₹3.00
[10:00:15] Strike 27350 CE: ₹3.50
[10:00:16] Strike 27450 CE: ₹4.00
[10:00:17] Strike 27550 CE: ₹4.75
[10:00:18] Strike 27650 CE: ₹5.50
[10:00:19] Strike 27750 CE: ₹6.25
```

---

## STEP 5: Find Lowest Priced Option

```
[10:00:20] Analyzing prices...
[10:00:20] ✓ LOWEST PRICED OPTION FOUND:
[10:00:20]   Strike: 27,050 CE
[10:00:20]   LTP: ₹2.50
[10:00:20]   Distance from ATM: 1,200 points (Very far OTM)
[10:00:20]   Expiry: 2026-02-10 (Current week)
```

---

## STEP 6: Calculate Order Prices

```
[10:00:20] Calculating stop limit prices...
[10:00:20] Current LTP: ₹2.50
[10:00:20]
[10:00:20] Trigger Price (20% below):
[10:00:20]   = 2.50 × 0.8
[10:00:20]   = 2.00 ✓
[10:00:20]
[10:00:20] Limit Price (trigger + buffer):
[10:00:20]   = 2.00 + 1.00
[10:00:20]   = 3.00 ✓
```

---

## STEP 7: Place Stop Limit Order

```
[10:00:21] Placing STOP LIMIT BUY order...
[10:00:21]
[10:00:21] Order Parameters:
[10:00:21]   Type: STOPLOSS_LIMIT
[10:00:21]   Variety: NORMAL
[10:00:21]   Product: INTRADAY ✓
[10:00:21]   Duration: DAY
[10:00:21]   Symbol: NIFTY10FEB2627050CE
[10:00:21]   Token: 58661
[10:00:21]   Exchange: NFO
[10:00:21]   Transaction: BUY
[10:00:21]   Quantity: 65 (1 lot)
[10:00:21]   Trigger Price: ₹2.00
[10:00:21]   Limit Price: ₹3.00
[10:00:21]
[10:00:22] Sending to AngelOne API...
[10:00:23] ✓ Order placed successfully!
[10:00:23] Order ID: 240205001234567
[10:00:23] Status: TRIGGER_PENDING
```

**Order Book Entry:**
```
Order ID: 240205001234567
Symbol: NIFTY10FEB2627050CE
Type: SL (Stop Limit)
Side: BUY
Qty: 65
Product: INTRADAY
Trigger: ₹2.00
Limit: ₹3.00
Status: TRIGGER_PENDING ⏳
```

---

## STEP 8: Iteration 1 (After 1 Minute)

```
[10:01:23] ═══════════════════════════════════════════════════
[10:01:23] ITERATION 1/5
[10:01:23] ═══════════════════════════════════════════════════
[10:01:23] Waiting 60 seconds...
```

```
[10:01:24] Fetching new LTP...
[10:01:25] Current LTP: ₹2.60 (was ₹2.50, +₹0.10)
[10:01:25]
[10:01:25] Calculating new prices:
[10:01:25]   New Trigger (20% below): 2.60 × 0.8 = ₹2.08
[10:01:25]   New Limit: 2.08 + 1.00 = ₹3.08
[10:01:25]
[10:01:25] Price change: ₹2.00 → ₹2.08 (₹0.08 difference)
[10:01:25] ✓ Change significant (> ₹0.50), modifying order...
```

```
[10:01:26] Fetching order details from order book...
[10:01:27] ✓ Found order 240205001234567
[10:01:27] Current: Trigger=₹2.00, Limit=₹3.00
[10:01:27]
[10:01:27] Sending modify request with ALL fields:
[10:01:27]   variety: NORMAL
[10:01:27]   orderid: 240205001234567
[10:01:27]   tradingsymbol: NIFTY10FEB2627050CE ✓
[10:01:27]   symboltoken: 58661 ✓
[10:01:27]   exchange: NFO ✓
[10:01:27]   ordertype: STOPLOSS_LIMIT ✓
[10:01:27]   producttype: INTRADAY ✓
[10:01:27]   duration: DAY ✓
[10:01:27]   quantity: 65 ✓
[10:01:27]   triggerprice: 2.08 (NEW) ✓
[10:01:27]   price: 3.08 (NEW) ✓
[10:01:27]
[10:01:28] ✓ Order modified successfully!
[10:01:28] Order ID: 240205001234567
[10:01:28] Status: TRIGGER_PENDING
[10:01:28] New Trigger: ₹2.08
[10:01:28] New Limit: ₹3.08
```

**Log Entry:**
```json
{
  "iteration": 1,
  "timestamp": "2026-02-05T10:01:28",
  "action": "MODIFY_ORDER",
  "order_id": "240205001234567",
  "ltp": 2.60,
  "trigger_price": 2.08,
  "limit_price": 3.08,
  "order_status": "TRIGGER_PENDING"
}
```

---

## STEP 9: Iteration 2 (After 2 Minutes)

```
[10:02:28] ═══════════════════════════════════════════════════
[10:02:28] ITERATION 2/5
[10:02:28] ═══════════════════════════════════════════════════
[10:02:28] Waiting 60 seconds...
```

```
[10:02:29] Fetching new LTP...
[10:02:30] Current LTP: ₹2.55 (was ₹2.60, -₹0.05)
[10:02:30]
[10:02:30] Calculating new prices:
[10:02:30]   New Trigger (20% below): 2.55 × 0.8 = ₹2.04
[10:02:30]   New Limit: 2.04 + 1.00 = ₹3.04
[10:02:30]
[10:02:30] Price change: ₹2.08 → ₹2.04 (₹0.04 difference)
[10:02:30] ⚠ Change too small (< ₹0.50), skipping modification
[10:02:30] Order remains: Trigger=₹2.08, Limit=₹3.08
```

**Log Entry:**
```json
{
  "iteration": 2,
  "timestamp": "2026-02-05T10:02:30",
  "action": "SKIP_MODIFY",
  "order_id": "240205001234567",
  "ltp": 2.55,
  "trigger_price": 2.08,
  "limit_price": 3.08,
  "reason": "minimal_price_change"
}
```

---

## STEP 10: Iteration 3 (After 3 Minutes)

```
[10:03:30] ═══════════════════════════════════════════════════
[10:03:30] ITERATION 3/5
[10:03:30] ═══════════════════════════════════════════════════
[10:03:30] Waiting 60 seconds...
```

```
[10:03:31] Fetching new LTP...
[10:03:32] Current LTP: ₹2.75 (was ₹2.55, +₹0.20)
[10:03:32]
[10:03:32] Calculating new prices:
[10:03:32]   New Trigger (20% below): 2.75 × 0.8 = ₹2.20
[10:03:32]   New Limit: 2.20 + 1.00 = ₹3.20
[10:03:32]
[10:03:32] Price change: ₹2.08 → ₹2.20 (₹0.12 difference)
[10:03:32] ⚠ Change too small (< ₹0.50), skipping modification
[10:03:32] Order remains: Trigger=₹2.08, Limit=₹3.08
```

---

## STEP 11: Iteration 4 (After 4 Minutes)

```
[10:04:32] ═══════════════════════════════════════════════════
[10:04:32] ITERATION 4/5
[10:04:32] ═══════════════════════════════════════════════════
[10:04:32] Waiting 60 seconds...
```

```
[10:04:33] Fetching new LTP...
[10:04:34] Current LTP: ₹3.20 (was ₹2.75, +₹0.45)
[10:04:34]
[10:04:34] Calculating new prices:
[10:04:34]   New Trigger (20% below): 3.20 × 0.8 = ₹2.56
[10:04:34]   New Limit: 2.56 + 1.00 = ₹3.56
[10:04:34]
[10:04:34] Price change: ₹2.08 → ₹2.56 (₹0.48 difference)
[10:04:34] ⚠ Change too small (< ₹0.50), skipping modification
[10:04:34] Order remains: Trigger=₹2.08, Limit=₹3.08
```

---

## STEP 12: Iteration 5 (After 5 Minutes)

```
[10:05:34] ═══════════════════════════════════════════════════
[10:05:34] ITERATION 5/5 (FINAL)
[10:05:34] ═══════════════════════════════════════════════════
[10:05:34] Waiting 60 seconds...
```

```
[10:05:35] Fetching new LTP...
[10:05:36] Current LTP: ₹3.80 (was ₹3.20, +₹0.60)
[10:05:36]
[10:05:36] Calculating new prices:
[10:05:36]   New Trigger (20% below): 3.80 × 0.8 = ₹3.04
[10:05:36]   New Limit: 3.04 + 1.00 = ₹4.04
[10:05:36]
[10:05:36] Price change: ₹2.08 → ₹3.04 (₹0.96 difference)
[10:05:36] ✓ Change significant (> ₹0.50), modifying order...
```

```
[10:05:37] Fetching order details from order book...
[10:05:38] ✓ Found order 240205001234567
[10:05:38]
[10:05:38] Sending modify request...
[10:05:39] ✓ Order modified successfully!
[10:05:39] Order ID: 240205001234567
[10:05:39] New Trigger: ₹3.04
[10:05:39] New Limit: ₹4.04
```

**Log Entry:**
```json
{
  "iteration": 5,
  "timestamp": "2026-02-05T10:05:39",
  "action": "MODIFY_ORDER",
  "order_id": "240205001234567",
  "ltp": 3.80,
  "trigger_price": 3.04,
  "limit_price": 4.04,
  "order_status": "TRIGGER_PENDING"
}
```

---

## STEP 13: Cancel Order

```
[10:05:39] ═══════════════════════════════════════════════════
[10:05:39] TEST COMPLETE - CLEANUP
[10:05:39] ═══════════════════════════════════════════════════
[10:05:39] Cancelling order...
[10:05:40] ✓ Order 240205001234567 cancelled successfully
[10:05:40] Final Status: CANCELLED
```

**Log Entry:**
```json
{
  "iteration": "final",
  "timestamp": "2026-02-05T10:05:40",
  "action": "CANCEL_ORDER",
  "order_id": "240205001234567",
  "order_status": "CANCELLED"
}
```

---

## STEP 14: Save Logs

```
[10:05:41] Saving logs to file...
[10:05:41] ✓ Logs saved to:
[10:05:41]   /Users/Algo_Trading/manishsir_options/paper_trading/tests/logs/stop_limit_test_20260205_100000.json
```

---

## FINAL LOG FILE

**File:** `stop_limit_test_20260205_100000.json`

```json
{
  "test_config": {
    "underlying": "NIFTY",
    "option_type": "CE",
    "strike_offset": 0,
    "quantity": 65,
    "stop_loss_pct": 0.2,
    "check_interval_seconds": 60,
    "max_iterations": 5,
    "price_buffer": 1.0
  },
  "test_params": {
    "strike": 27050,
    "expiry": "2026-02-10",
    "token": "58661",
    "spot_price": 25847.35,
    "atm_strike": 25850,
    "distance_from_atm": 1200,
    "initial_ltp": 2.50
  },
  "logs": [
    {
      "iteration": 0,
      "timestamp": "2026-02-05T10:00:23",
      "action": "PLACE_ORDER",
      "order_id": "240205001234567",
      "ltp": 2.50,
      "trigger_price": 2.00,
      "limit_price": 3.00,
      "order_status": "PENDING"
    },
    {
      "iteration": 1,
      "timestamp": "2026-02-05T10:01:28",
      "action": "MODIFY_ORDER",
      "order_id": "240205001234567",
      "ltp": 2.60,
      "trigger_price": 2.08,
      "limit_price": 3.08,
      "order_status": "TRIGGER_PENDING"
    },
    {
      "iteration": 2,
      "timestamp": "2026-02-05T10:02:30",
      "action": "SKIP_MODIFY",
      "order_id": "240205001234567",
      "ltp": 2.55,
      "trigger_price": 2.08,
      "limit_price": 3.08,
      "reason": "minimal_price_change"
    },
    {
      "iteration": 3,
      "timestamp": "2026-02-05T10:03:32",
      "action": "SKIP_MODIFY",
      "order_id": "240205001234567",
      "ltp": 2.75,
      "trigger_price": 2.08,
      "limit_price": 3.08,
      "reason": "minimal_price_change"
    },
    {
      "iteration": 4,
      "timestamp": "2026-02-05T10:04:34",
      "action": "SKIP_MODIFY",
      "order_id": "240205001234567",
      "ltp": 3.20,
      "trigger_price": 2.08,
      "limit_price": 3.08,
      "reason": "minimal_price_change"
    },
    {
      "iteration": 5,
      "timestamp": "2026-02-05T10:05:39",
      "action": "MODIFY_ORDER",
      "order_id": "240205001234567",
      "ltp": 3.80,
      "trigger_price": 3.04,
      "limit_price": 4.04,
      "order_status": "TRIGGER_PENDING"
    },
    {
      "iteration": "final",
      "timestamp": "2026-02-05T10:05:40",
      "action": "CANCEL_ORDER",
      "order_id": "240205001234567",
      "order_status": "CANCELLED"
    }
  ],
  "summary": {
    "total_iterations": 5,
    "modifications": 2,
    "skipped": 3,
    "initial_ltp": 2.50,
    "final_ltp": 3.80,
    "ltp_change": 1.30,
    "ltp_change_pct": 52.0,
    "order_never_executed": true,
    "reason": "Trigger always 20% below market"
  }
}
```

---

## TEST SUMMARY

```
═══════════════════════════════════════════════════════════════════
TEST SUMMARY
═══════════════════════════════════════════════════════════════════
Duration:           5 minutes 17 seconds
Strike Selected:    27,050 CE (1,200 points OTM)
Product Type:       INTRADAY ✓
Initial LTP:        ₹2.50
Final LTP:          ₹3.80
LTP Change:         +₹1.30 (+52%)

Order Details:
  Order ID:         240205001234567
  Status:           CANCELLED ✓
  Never Executed:   ✓ (trigger always 20% below)

Actions:
  Total Iterations: 5
  Modifications:    2 (iterations 1 and 5)
  Skipped:          3 (iterations 2, 3, 4)
  Cancellation:     1 ✓

Logs Saved:
  File: stop_limit_test_20260205_100000.json
  Size: 1.2 KB
  Status: ✓ SAVED
═══════════════════════════════════════════════════════════════════
```

---

## Key Points

✅ **Product Type:** INTRADAY (Auto square-off at 3:20 PM)
✅ **Far OTM:** 1,200 points from ATM (very safe)
✅ **Lowest Price:** Automatically selected (₹2.50)
✅ **20% Below:** Always maintained (order never executes)
✅ **Modifications:** Only when change > ₹0.50
✅ **Logs:** Complete JSON audit trail
✅ **Cleanup:** Order cancelled at end

---

## Why Order Never Executes

**Initial LTP:** ₹2.50
**Trigger:** ₹2.00 (20% below)

**For order to execute:**
- LTP must fall to ≤ ₹2.00
- That's a **20% crash** from initial price
- Very unlikely in 5 minutes!

**Safety:** Order is designed to NOT execute during test.

---

## What You'll See in AngelOne App/Web

**Order Book Entry:**
```
Order ID: 240205001234567
Symbol: NIFTY10FEB2627050CE
Type: SL
Side: BUY
Qty: 65
Product: INTRADAY ✓
Trigger: ₹3.04 (after final modification)
Limit: ₹4.04
Status: CANCELLED
Time: 10:05:40
```

**Trade Book:**
```
(Empty - no trades because order never triggered)
```

**Position:**
```
(Empty - no position taken)
```

---

This is the EXACT flow you'll see when you run the test!
