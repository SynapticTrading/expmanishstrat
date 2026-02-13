# Stop Limit Order Test - Changes Documentation

**Date:** 2026-02-05
**Purpose:** Test stop limit order placement and periodic modification using AngelOne

## Files Created

### 1. `/paper_trading/tests/test_stop_limit_modify.py`
**Purpose:** Test file for placing and modifying stop limit orders

**What it does:**
1. Connects to AngelOne broker
2. Selects NIFTY ATM strike (e.g., 25800 CE)
3. Gets current option price (LTP)
4. Places a stop limit BUY order 20% below current price
5. Every 1 minute:
   - Fetches new LTP
   - Calculates new trigger price (20% below)
   - Modifies the order
   - Logs all details
6. After 5 iterations (5 minutes), cancels the order
7. Saves all logs to JSON file

**Key Features:**
- Uses existing AngelOne adapter methods
- Token-based instrument resolution via ContractManager
- Automatic ATM strike calculation based on spot price
- Configurable parameters (interval, iterations, stop loss %)
- Comprehensive logging to JSON file
- Safe testing (order 20% below, should never execute)

**Configuration:**
```python
TEST_CONFIG = {
    'underlying': 'NIFTY',
    'option_type': 'CE',  # Call option
    'strike_offset': 0,  # ATM
    'quantity': 65,  # 1 lot for NIFTY
    'stop_loss_pct': 0.20,  # 20% below
    'check_interval_seconds': 60,  # 1 minute
    'max_iterations': 5,  # 5 minutes total
    'price_buffer': 1.0,  # Limit price buffer
}
```

## How to Run

### Prerequisites
1. AngelOne credentials configured in:
   ```
   /paper_trading/config/credentials_angelone.txt
   ```

2. Contract cache up-to-date:
   ```bash
   python refresh_contracts.py --broker angelone
   ```

### Run the Test

```bash
# From project root
python -m pytest paper_trading/tests/test_stop_limit_modify.py -v -s
```

**Options:**
- `-v`: Verbose output
- `-s`: Show print statements and logs

### Expected Output

```
STOP LIMIT ORDER TEST - SETUP
================================================================================
✓ Contract manager initialized
✓ Connected to AngelOne
✓ Spot price: NIFTY = ₹25847.35
✓ Selected strike: 25850 (ATM: 25850)
✓ Expiry: 2026-02-10
✓ Token: 58661

STEP 1: GET INITIAL LTP
================================================================================
✓ Initial LTP: ₹150.25
✓ Trigger price (20% below): ₹120.20
✓ Limit price: ₹121.20

STEP 2: PLACE STOP LIMIT ORDER
================================================================================
✓ Order placed successfully
  Order ID: 240205000123456
  Type: STOP LIMIT BUY
  Trigger: ₹120.20
  Limit: ₹121.20
  Quantity: 65

STEP 3: PERIODIC LTP CHECK AND ORDER MODIFICATION
================================================================================

--- Iteration 1/5 ---
Waiting 60 seconds...
Current LTP: ₹152.50
New trigger price (20% below): ₹122.00
New limit price: ₹123.00
✓ Order modified successfully
  Order status: TRIGGER_PENDING

... (continues for 5 iterations)

STEP 4: CANCEL ORDER AND CLEANUP
================================================================================
✓ Order cancelled successfully

STEP 5: SAVE LOGS
================================================================================
✓ Logs saved to: /paper_trading/tests/logs/stop_limit_test_20260205_143022.json

TEST SUMMARY
================================================================================
Total iterations: 5
Successful modifications: 4
Failed modifications: 0
Skipped modifications: 1
================================================================================
```

### Log File Format

The test saves logs to: `/paper_trading/tests/logs/stop_limit_test_YYYYMMDD_HHMMSS.json`

**Sample log:**
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
    "strike": 25850,
    "expiry": "2026-02-10",
    "token": "58661"
  },
  "logs": [
    {
      "iteration": 0,
      "timestamp": "2026-02-05T14:30:22.123456",
      "action": "PLACE_ORDER",
      "order_id": "240205000123456",
      "ltp": 150.25,
      "trigger_price": 120.2,
      "limit_price": 121.2,
      "order_status": "PENDING"
    },
    {
      "iteration": 1,
      "timestamp": "2026-02-05T14:31:22.789012",
      "action": "MODIFY_ORDER",
      "order_id": "240205000123456",
      "ltp": 152.5,
      "trigger_price": 122.0,
      "limit_price": 123.0,
      "order_status": "TRIGGER_PENDING"
    }
    // ... more entries
  ]
}
```

## Research Summary

### AngelOne Adapter - Verified Methods

1. **`place_order()`** (line 479 in angelone.py)
   - ✅ Supports OrderType.SL (STOPLOSS_LIMIT)
   - ✅ Accepts trigger_price parameter
   - ✅ Accepts price (limit price) parameter
   - ✅ Uses token-based system

2. **`modify_order()`** (line 609 in angelone.py)
   - ✅ Can modify trigger_price
   - ✅ Can modify price (limit price)
   - ✅ Can modify quantity
   - ✅ Returns OrderResponse with success status

3. **`get_ltp()`** (line 201 in angelone.py)
   - ✅ Fetches current Last Traded Price
   - ✅ Token-based lookup
   - ✅ Returns float or None

4. **`get_spot_price()`** (line 458 in angelone.py)
   - ✅ Gets NIFTY index price
   - ✅ Used for ATM strike calculation

5. **`cancel_order()`** (line 658 in angelone.py)
   - ✅ Cancels order by order_id
   - ✅ Returns OrderResponse

### Contract Manager

**File:** `/paper_trading/core/contract_manager.py`

- ✅ Loads from `/contracts_cache.json`
- ✅ Method: `get_option_contract(expiry, strike, option_type)`
- ✅ Returns dict with token: `{'token': '58661'}`
- ✅ Structure: `options.instruments[expiry][strike][option_type].token`

### Order Type Mapping

**From angelone.py line 38-43:**
```python
ORDER_TYPE_MAP = {
    OrderType.MARKET: "MARKET",
    OrderType.LIMIT: "LIMIT",
    OrderType.SL: "STOPLOSS_LIMIT",      # ← We use this
    OrderType.SL_M: "STOPLOSS_MARKET"
}
```

## What Was NOT Modified

- ❌ No changes to existing adapter files
- ❌ No changes to contract_manager.py
- ❌ No changes to types.py
- ❌ No changes to existing test files

## Customization Options

You can modify `TEST_CONFIG` in the test file to customize:

1. **Strike Selection:**
   ```python
   'strike_offset': 100,  # 100 points OTM (CE will be cheaper)
   ```

2. **Option Type:**
   ```python
   'option_type': 'PE',  # Test with Put option
   ```

3. **Stop Loss Percentage:**
   ```python
   'stop_loss_pct': 0.15,  # 15% below instead of 20%
   ```

4. **Check Interval:**
   ```python
   'check_interval_seconds': 30,  # Check every 30 seconds
   ```

5. **Number of Iterations:**
   ```python
   'max_iterations': 10,  # Run for 10 minutes
   ```

## Safety Features

1. **Order Never Executes:**
   - Trigger price is 20% below current LTP
   - Market would need to crash 20% for execution
   - Safe for testing during market hours

2. **Automatic Cleanup:**
   - Order is always cancelled at the end
   - Even if test fails, cleanup runs

3. **Comprehensive Logging:**
   - All actions logged to JSON
   - Can review test results later
   - Easy to verify system behavior

## Troubleshooting

### Issue: "Credentials file not found"
**Solution:**
```bash
cp paper_trading/config/credentials_angelone.template.txt \
   paper_trading/config/credentials_angelone.txt
# Then edit the file with your credentials
```

### Issue: "Contract not found"
**Solution:**
```bash
python refresh_contracts.py --broker angelone
```

### Issue: "Failed to connect to AngelOne"
**Solution:**
- Check credentials in credentials_angelone.txt
- Verify TOTP secret is correct
- Ensure API access is enabled in your AngelOne account

### Issue: "Could not fetch LTP"
**Solution:**
- Market may be closed
- Run test during market hours (9:15 AM - 3:30 PM)
- Or check if the selected strike has liquidity

## Verification

You can verify the system by:

1. **Check logs directory:**
   ```bash
   ls -lh paper_trading/tests/logs/
   ```

2. **Review JSON log:**
   ```bash
   cat paper_trading/tests/logs/stop_limit_test_*.json | jq .
   ```

3. **Check AngelOne order book:**
   - Login to AngelOne web/app
   - Check order book for cancelled orders
   - Verify order IDs match log file

## Next Steps

If you want to modify this test for different scenarios:

1. **Test with different strikes:**
   - Change `strike_offset` to test OTM/ITM options

2. **Test with sell orders:**
   - Change `transaction_type` to `TransactionType.SELL`
   - Adjust trigger price calculation (20% above instead of below)

3. **Test with different time intervals:**
   - Change `check_interval_seconds` to test faster/slower updates

4. **Export to Excel:**
   - Add pandas DataFrame creation
   - Export logs to CSV/Excel for analysis

## Contact

For questions or issues, check the project documentation or create an issue in the project repository.
