# Paper Trading Tests

This folder contains all test scripts for the paper trading system.

---

## Test Files

### 1. `test_realtime_ltp_monitor.py`
**Purpose:** Verify real-time LTP monitoring works correctly

**What it tests:**
- Fetches LTP for a specific option every 60 seconds
- Verifies LTP values change (not cached/stale)
- Confirms API calls are working
- Simulates what the exit monitor does

**When to use:**
- After fixing exit monitor issues
- To verify API is returning fresh data
- To debug LTP fetching problems

**How to run:**
```bash
cd /Users/Algo_Trading/manishsir_options
python3 paper_trading/tests/test_realtime_ltp_monitor.py
```

**Expected output:**
```
REAL-TIME LTP MONITORING TEST
✓ Connected to Zerodha
✓ Loaded instruments

[14:23:15] ⏱️  Starting 1-minute LTP monitoring...
[14:23:15] Current LTP: ₹43.95
[14:24:15] Current LTP: ₹44.45  (Changed: +₹0.50)
[14:25:15] Current LTP: ₹42.85  (Changed: -₹1.60)
```

**Related issues:**
- [Issue #04: Exit Monitor Using Stale Data](../../docs/paper_trading/issues/04_exit_monitor_using_stale_data.md)

---

### 2. `test_zerodha_standalone.py`
**Purpose:** Test Zerodha authentication flow independently

**What it tests:**
- Zerodha login process (username + password + TOTP)
- HTTP session management
- Request token generation
- Access token generation
- Shows exactly where authentication fails (if it does)

**When to use:**
- Debugging connection issues
- Verifying credentials are correct
- Understanding the auth flow
- Before running full paper trading

**How to run:**
```bash
cd /Users/Algo_Trading/manishsir_options
python3 paper_trading/tests/test_zerodha_standalone.py
```

**Expected output:**
```
ZERODHA AUTHENTICATION TEST
[STEP 1] Creating HTTP session...
[STEP 2] Getting login URL...
[STEP 3] Logging in with credentials...
[STEP 4] Generating TOTP...
[STEP 5] Getting request token...
[STEP 6] Generating access token...
✓ Authentication successful!
```

---

### 3. `test_zerodha_full.py`
**Purpose:** Test full Zerodha integration including instrument loading

**What it tests:**
- Connection to Zerodha
- Data feed creation
- Instrument loading (NFO exchange)
- NIFTY option filtering
- Expiry date handling
- Complete end-to-end flow

**When to use:**
- After successful authentication test
- To verify instrument data is loading
- To check performance of API calls
- Before running paper trading

**How to run:**
```bash
cd /Users/Algo_Trading/manishsir_options
python3 paper_trading/tests/test_zerodha_full.py
```

**Expected output:**
```
ZERODHA FULL INTEGRATION TEST
[1] Loading credentials...
✓ Loaded for user: ABC123
[2] Creating connection...
[3] Connecting to Zerodha...
✓ Connected in 4.32s
[4] Creating data feed...
✓ Data feed created
[5] Loading instruments...
✓ Loaded 15,234 instruments in 2.15s
[6] Filtering NIFTY options...
✓ Found 1,456 NIFTY options
```

---

### 4. `test_zerodha_expiry_format.py`
**Purpose:** Check Zerodha expiry date format in instruments

**What it tests:**
- Fetches NFO instruments
- Filters NIFTY options
- Shows expiry column data type
- Displays sample expiry values
- Verifies expiry format is correct

**When to use:**
- Debugging expiry date parsing issues
- Verifying weekly expiry format
- Understanding instrument data structure
- After Zerodha API changes

**How to run:**
```bash
cd /Users/Algo_Trading/manishsir_options
python3 paper_trading/tests/test_zerodha_expiry_format.py
```

**Expected output:**
```
Connecting...
Fetching NFO instruments...
Total NIFTY options: 1,456

Expiry column type: datetime64[ns]
Sample expiry values:
['2025-01-02' '2025-01-09' '2025-01-16' '2025-01-23' '2025-01-30']
```

---

## Test Order (Recommended)

When troubleshooting or verifying the system, run tests in this order:

1. **test_zerodha_standalone.py** - Verify authentication works
2. **test_zerodha_expiry_format.py** - Check expiry format is correct
3. **test_zerodha_full.py** - Verify full integration works
4. **test_realtime_ltp_monitor.py** - Verify real-time LTP fetching works

---

## Common Issues

### Authentication Fails
**Test:** `test_zerodha_standalone.py`
**Fix:** Check credentials in `paper_trading/config/credentials_zerodha.txt`

### Instruments Not Loading
**Test:** `test_zerodha_full.py`
**Possible causes:**
- Network issues
- Zerodha API downtime
- Invalid session

### LTP Not Changing
**Test:** `test_realtime_ltp_monitor.py`
**Possible causes:**
- Reading from stale data source
- API call not happening
- Using cached/shared variable

### Expiry Format Wrong
**Test:** `test_zerodha_expiry_format.py`
**Possible causes:**
- Zerodha API changed format
- Date parsing logic needs update
- Wrong column name

---

## Running All Tests

To run all tests sequentially:

```bash
cd /Users/Algo_Trading/manishsir_options

echo "=== Test 1: Authentication ==="
python3 paper_trading/tests/test_zerodha_standalone.py
echo ""

echo "=== Test 2: Expiry Format ==="
python3 paper_trading/tests/test_zerodha_expiry_format.py
echo ""

echo "=== Test 3: Full Integration ==="
python3 paper_trading/tests/test_zerodha_full.py
echo ""

echo "=== Test 4: Real-time LTP ==="
python3 paper_trading/tests/test_realtime_ltp_monitor.py
```

---

## Test Data Requirements

All tests require:
- Valid Zerodha credentials in `paper_trading/config/credentials_zerodha.txt`
- Active internet connection
- Market hours (for LTP tests)
- NFO exchange instruments (loaded automatically)

---

## Related Documentation

- [Trading System Quick Guide](../../docs/TRADING_SYSTEM_QUICK_GUIDE.md)
- [Live vs Paper Trading Architecture](../../docs/LIVE_PAPER_TRADING_ARCHITECTURE.md)
- [Paper Trading Issues](../../docs/paper_trading/issues/README.md)
- [Setup Guide](../../docs/paper_trading/SETUP_GUIDE.md)

---

## Contributing

When adding new tests:

1. Follow the naming convention: `test_*.py`
2. Add comprehensive docstring explaining purpose
3. Include clear print statements showing progress
4. Document expected output
5. Update this README with test description
6. Add to "Test Order" section if relevant

---

**Last Updated:** 2025-12-29
