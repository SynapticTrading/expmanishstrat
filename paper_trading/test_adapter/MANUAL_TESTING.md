# Manual Testing Guide for Adapter Fetches

This guide explains how to manually test LTP, quotes, and all market data fetching capabilities of the adapter system.

## Prerequisites

1. **Contracts cache must be populated:**
   ```bash
   python refresh_contracts.py --broker zerodha
   python refresh_contracts.py --broker angelone
   ```

2. **Broker credentials must be configured** in `config/config.yaml`

3. **Market must be open** (or test during market hours for live data)

## Test Scripts Available

### 1. 🚀 Complete Test Suite: `manual_test_fetches.py`

Comprehensive test that covers ALL fetching capabilities.

**Usage:**
```bash
# Test Zerodha adapter
python paper_trading/test_adapter/manual_test_fetches.py --broker zerodha

# Test AngelOne adapter
python paper_trading/test_adapter/manual_test_fetches.py --broker angelone
```

**What it tests:**
- ✅ Contract resolution from cache
- ✅ Token verification
- ✅ Spot price fetching
- ✅ Market status check
- ✅ LTP fetching (CE and PE)
- ✅ Full quote fetching (OHLC, volume, OI, bid/ask)
- ✅ Multiple quotes fetching (batch)
- ✅ Option chain fetching
- ✅ Token-based approach verification

**Sample Output:**
```
================================================================================
  1. CONTRACT RESOLUTION TEST
================================================================================
📅 Current Week Expiry: 2026-01-27
💹 NIFTY Spot Price: 23456.75
🎯 ATM Strike: 23450

🔍 Resolving CE Contract...
✅ CE Contract Found:
   Symbol: NIFTY26JAN23450CE
   Token: 12345678
   Zerodha Token: 12345678
   Strike: 23450
   Lot Size: 65

================================================================================
  2. LTP FETCHING TEST (Token-Based)
================================================================================
Testing LTP fetch for Strike: 23450, Expiry: 2026-01-27

📊 Fetching CE LTP...
✅ CE LTP: ₹150.50

📊 Fetching PE LTP...
✅ PE LTP: ₹145.75
```

---

### 2. ⚡ Quick Check: `quick_check_ltp.py`

Fast test for a specific strike price.

**Usage:**
```bash
# Check ATM strike
python paper_trading/test_adapter/quick_check_ltp.py --broker zerodha --strike 23500

# Check specific strike with different expiry
python paper_trading/test_adapter/quick_check_ltp.py --broker angelone --strike 24000 --expiry next_week
```

**Options:**
- `--broker`: zerodha or angelone (required)
- `--strike`: Strike price to test (required)
- `--expiry`: current_week, next_week, current_month, next_month (default: current_week)

**What it tests:**
- ✅ Quick LTP check for CE and PE
- ✅ Full quote details
- ✅ Contract availability in cache
- ✅ Token verification

**Sample Output:**
```
🔧 Initializing ZERODHA adapter...
🔗 Connecting to zerodha...
✅ Connected to zerodha

📅 Expiry: 2026-01-27
🎯 Strike: 23500

🔍 Checking cache for contracts...
✅ Contracts found in cache

🔑 Token Verification:
   CE zerodha_instrument_token: 12345678
   PE zerodha_instrument_token: 87654321

💹 Fetching NIFTY spot price...
   Spot: ₹23,456.75

📊 CE Option (Strike: 23500):
   Symbol: NIFTY26JAN23500CE
   ✅ LTP: ₹140.50

   📈 Fetching full CE quote...
   ✅ Full Quote:
      LTP:     ₹140.50
      Open:    ₹135.00
      High:    ₹145.00
      Low:     ₹134.00
      Volume:  125,450
      OI:      2,345,600
```

---

### 3. 🔄 Broker Comparison: `compare_brokers.py`

Compare Zerodha and AngelOne side-by-side for the same contract.

**Usage:**
```bash
python paper_trading/test_adapter/compare_brokers.py --strike 23500
```

**What it tests:**
- ✅ Both brokers with same contract
- ✅ Response time comparison
- ✅ Price difference analysis
- ✅ Data completeness comparison
- ✅ Token-based approach verification

**Sample Output:**
```
================================================================================
COMPARISON SUMMARY
================================================================================

📊 Side-by-Side Comparison:

Metric                    Zerodha              AngelOne
----------------------------------------------------------------------
Connection Time:            2.45s                3.12s
Spot Price:               ₹23456.75 (0.234s)   ₹23456.80 (0.312s)
CE LTP:                   ₹ 140.50 (0.156s)    ₹ 140.55 (0.189s)
   Price Difference:      ₹0.05
PE LTP:                   ₹ 135.25 (0.142s)    ₹ 135.20 (0.178s)
   Price Difference:      ₹0.05

⚡ Response Time Analysis:
   Zerodha avg:   0.149s
   AngelOne avg:  0.184s
   🏆 Faster: Zerodha

🔐 Token-Based Approach:
   ✅ Both adapters use TOKEN-ONLY lookups
   ✅ No manual symbol construction
   ✅ All data fetched from contracts_cache.json
```

---

## Understanding the Output

### Contract Resolution
```
✅ CE Contract Found:
   Symbol: NIFTY26JAN23450CE
   Token: 12345678
   Zerodha Token: 12345678
   Strike: 23450
   Lot Size: 65
```
- **Symbol**: Broker's trading symbol (for reference only)
- **Token**: Universal token (used by AngelOne)
- **Zerodha Token**: Zerodha-specific instrument token
- **Strike**: Strike price
- **Lot Size**: Number of shares per lot

### LTP (Last Traded Price)
```
✅ CE LTP: ₹150.50
```
- Most recent trade price
- Fastest to fetch
- Used for quick price checks

### Full Quote
```
✅ Full Quote:
   LTP:     ₹150.50
   Open:    ₹145.00
   High:    ₹155.00
   Low:     ₹144.00
   Close:   ₹148.00
   Volume:  10,000
   OI:      50,000
   Bid:     ₹150.00
   Ask:     ₹151.00
```
- **LTP**: Last traded price
- **OHLC**: Open, High, Low, Close
- **Volume**: Number of contracts traded
- **OI**: Open Interest (outstanding contracts)
- **Bid/Ask**: Best buy/sell prices

### Option Chain
```
Strike    Type    Close      Volume      OI
------------------------------------------------------------
23400     CE      ₹180.50    15,000      125,000
23400     PE      ₹130.25    12,000      98,000
23450     CE      ₹150.75    25,000      235,000
23450     PE      ₹145.50    22,000      215,000
```
- Multiple strikes at once
- Shows CE and PE for each strike
- Useful for analyzing option spreads

---

## Token-Based Approach Verification

All scripts verify the token-based approach:

### ✅ What Should Happen:
1. **Adapter queries ContractManager** for contract
2. **ContractManager reads contracts_cache.json**
3. **Returns contract with token** (zerodha_instrument_token or token)
4. **Adapter uses token** to call broker API
5. **No symbol construction** at runtime

### ❌ What Should NOT Happen:
- Manual symbol construction like `f"NIFTY{expiry}{strike}CE"`
- Symbol-based API calls
- Runtime symbol formatting

### Verification Output:
```
🔐 Token-Based Approach:
   ✅ Both adapters use TOKEN-ONLY lookups
   ✅ No manual symbol construction
   ✅ All data fetched from contracts_cache.json
```

---

## Common Issues and Solutions

### Issue: "Contract not found in cache"
**Solution:**
```bash
python refresh_contracts.py --broker zerodha
```
Or for AngelOne:
```bash
python refresh_contracts.py --broker angelone
```

### Issue: "Missing zerodha_instrument_token"
**Solution:**
The cache was generated for AngelOne. Refresh for Zerodha:
```bash
python refresh_contracts.py --broker zerodha
```

### Issue: "Missing token field"
**Solution:**
The cache was generated for Zerodha. Refresh for AngelOne:
```bash
python refresh_contracts.py --broker angelone
```

### Issue: "Failed to connect"
**Possible causes:**
1. Invalid credentials in `config/config.yaml`
2. Network issues
3. Broker API is down
4. TOTP/2FA issues

**Check:**
```bash
# Verify config exists
cat config/config.yaml | grep -A 5 "zerodha:"

# Test connection manually
python -c "from paper_trading.brokers.adapter.factory import create_adapter; ..."
```

### Issue: "Market is closed"
**Note:**
- Some data may not be available outside market hours (9:15 AM - 3:30 PM)
- LTP will show previous close price
- Quotes may have stale data

---

## Testing Different Scenarios

### Test ATM Options
```bash
# Find current spot price first
python paper_trading/test_adapter/manual_test_fetches.py --broker zerodha

# Then test ATM strike
python paper_trading/test_adapter/quick_check_ltp.py --broker zerodha --strike <ATM_STRIKE>
```

### Test OTM Options
```bash
# Test 100 points OTM
python paper_trading/test_adapter/quick_check_ltp.py --broker zerodha --strike 23600
```

### Test Different Expiries
```bash
# Current week (default)
python paper_trading/test_adapter/quick_check_ltp.py --broker zerodha --strike 23500

# Next week
python paper_trading/test_adapter/quick_check_ltp.py --broker zerodha --strike 23500 --expiry next_week

# Current month
python paper_trading/test_adapter/quick_check_ltp.py --broker zerodha --strike 23500 --expiry current_month
```

### Test Multiple Strikes
```bash
# Use the full test suite - it tests 5 strikes automatically
python paper_trading/test_adapter/manual_test_fetches.py --broker zerodha
```

---

## Performance Benchmarking

### Response Time Expectations:

**Zerodha:**
- LTP: 0.1-0.2s
- Full Quote: 0.15-0.3s
- Option Chain (10 strikes): 0.5-1.0s

**AngelOne:**
- LTP: 0.15-0.25s
- Full Quote: 0.2-0.4s
- Option Chain (10 strikes): 1.0-2.0s (due to rate limiting)

### Run Comparison Test:
```bash
python paper_trading/test_adapter/compare_brokers.py --strike 23500
```

This will show:
- Connection times
- Average response times
- Which broker is faster
- Price differences (if any)

---

## Automated Testing

For automated unit tests (mocked APIs):
```bash
# Run all unit tests
pytest paper_trading/test_adapter/ -v

# Run with coverage
pytest paper_trading/test_adapter/ --cov=paper_trading.brokers.adapter

# Run specific test file
pytest paper_trading/test_adapter/test_base.py -v
```

---

## Best Practices

1. **Always refresh cache before testing:**
   ```bash
   python refresh_contracts.py --broker zerodha
   ```

2. **Test during market hours** for live data

3. **Use comparison script** to verify both brokers work the same way

4. **Check token fields** in cache before testing

5. **Monitor response times** - sudden slowness may indicate API issues

6. **Verify token-based approach** - should see "TOKEN-BASED" in logs

---

## Troubleshooting Checklist

- [ ] Contracts cache exists and is recent
- [ ] Cache has correct token fields for the broker
- [ ] Broker credentials are configured
- [ ] Network connection is working
- [ ] Broker API is operational
- [ ] Testing during market hours (for live data)
- [ ] Strike price exists in cache
- [ ] Expiry is valid (not expired)

---

## Support

If tests fail:
1. Check the error message carefully
2. Verify cache is up to date
3. Check broker API status
4. Review the log output
5. Try the other broker to compare

For token-based approach issues:
- Verify cache structure has required token fields
- Check ContractManager is properly initialized
- Ensure adapter receives ContractManager instance
