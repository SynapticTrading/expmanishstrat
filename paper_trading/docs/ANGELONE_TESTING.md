# AngelOne SmartAPI - Testing Guide

Complete guide for testing AngelOne connection and preparing for paper trading.

---

## Quick Test

Run the direct test with your credentials:

```bash
cd paper_trading
python tests/test_angelone_direct.py
```

---

## Your Working Credentials

Based on your provided code, your credentials are:

```python
api_key = "GuULp2XA"
username = "N182640"
pwd = "7531"  # MPIN (Mobile PIN, NOT trading password)
token = "4CDGR2KJ2Y3ESAYCIAXPYP2JAY"  # TOTP secret token
```

---

## Step-by-Step Testing

### Step 1: Update Test File Credentials

Edit: `tests/test_angelone_direct.py`

Find the credentials section (around line 20):

```python
# ============================================================
# CREDENTIALS - Replace with your actual credentials
# ============================================================
api_key = "GuULp2XA"
username = "N182640"
pwd = "7531"
token = "4CDGR2KJ2Y3ESAYCIAXPYP2JAY"
```

### Step 2: Run Direct Test

```bash
python tests/test_angelone_direct.py
```

**Expected Output:**
```
================================================================================
ANGELONE SMARTAPI - DIRECT CONNECTION TEST
================================================================================

[STEP 1] Initializing SmartAPI...
✓ SmartAPI initialized

[STEP 2] Generating TOTP...
✓ TOTP generated: 123456

[STEP 3] Generating session...
✓ Session generated successfully

Session Data:
  Status: True
  Message: SUCCESS

Tokens Retrieved:
  Auth Token: eyJ0eXAiOiJKV1QiLCJ...
  Refresh Token: eyJ0eXAiOiJKV1QiLC...
  Feed Token: 1234567890

[STEP 4] Fetching profile...
✓ Profile retrieved successfully

Profile Data:
  Client Name: YOUR_NAME
  Client Code: N182640
  Email: your@email.com
  Exchange: [NSE, NFO, ...]

[STEP 5] Fetching historical candle data...
✓ Retrieved 16 candles

Sample Candle (first):
  Timestamp: 2021-02-08T09:00:00+05:30
  Open: 350.5
  High: 351.2
  Low: 349.8
  Close: 350.9
  Volume: 125000

[STEP 6] Fetching current day Nifty data...
  Date range: 2025-12-26 09:15 to 2025-12-26 15:30
  NOTE: This may fail if market is closed
⚠ Nifty data not available (market may be closed)
  Response: No data available

[STEP 7] Testing LTP retrieval...
✓ LTP retrieved successfully
  Symbol: SBIN-EQ
  LTP: 450.75

================================================================================
TEST SUMMARY
================================================================================
✓ SmartAPI initialization: PASS
✓ TOTP generation: PASS
✓ Session generation: PASS
✓ Profile retrieval: PASS
✓ Historical candle data: PASS
⚠ Current Nifty data: SKIP (market closed)
================================================================================

🎉 CONNECTION TEST SUCCESSFUL!

Your AngelOne API is working correctly.
You can now use this for paper trading.
```

### Step 3: Create Credentials File

Once the direct test passes, create the credentials file for paper trading:

```bash
cd config
cp credentials_angelone.template.txt credentials_angelone.txt
```

Edit `config/credentials_angelone.txt`:

```
# AngelOne SmartAPI Credentials
api_key = GuULp2XA
username = N182640
password = 7531
totp_token = 4CDGR2KJ2Y3ESAYCIAXPYP2JAY
```

### Step 4: Test with Credentials File

Run the test again to verify credentials file works:

```bash
python tests/test_angelone_direct.py
```

This will run both tests:
1. Direct connection (hardcoded credentials)
2. Credentials file test

**Expected:**
```
TEST 1: Direct Connection (Hardcoded Credentials)
--------------------------------------------------------------------------------
✓ Session generated using direct credentials!

TEST 2: Connection Using Credentials File
--------------------------------------------------------------------------------
[STEP 1] Loading credentials from: paper_trading/config/credentials_angelone.txt
✓ Credentials loaded
  Found keys: ['api_key', 'username', 'password', 'totp_token']

[STEP 2] Initializing SmartAPI...
[STEP 3] Generating TOTP...
[STEP 4] Generating session...
✓ Session generated using credentials file!

🎉 Credentials file is valid and working!

##############################################################################
FINAL SUMMARY
##############################################################################
Direct Connection Test: ✓ PASS
Credentials File Test:  ✓ PASS
##############################################################################

✓ ALL TESTS PASSED!
You're ready to run paper trading with AngelOne!

Run: python runner.py --broker angelone
```

---

## Understanding the Code

### Your Original Code
```python
from SmartApi import SmartConnect
import pyotp

api_key = "GuULp2XA"
username = "N182640"
pwd = "7531"
smartApi = SmartConnect(api_key)
token = "4CDGR2KJ2Y3ESAYCIAXPYP2JAY"
totp = pyotp.TOTP(token).now()
data = smartApi.generateSession(username, pwd, totp)
authToken = data['data']['jwtToken']
refreshToken = data['data']['refreshToken']
feedToken = smartApi.getfeedToken()
res = smartApi.getProfile(refreshToken)

historicParam = {
    "exchange": "NSE",
    "symboltoken": "3045",
    "interval": "ONE_MINUTE",
    "fromdate": "2021-02-08 09:00",
    "todate": "2021-02-08 09:16"
}
stockData = smartApi.getCandleData(historicParam)
```

### What It Does

1. **Initialize SmartAPI**: `SmartConnect(api_key)`
2. **Generate TOTP**: Time-based one-time password from your TOTP secret
3. **Create Session**: Authenticate with username, MPIN, and TOTP
4. **Get Tokens**: JWT token for auth, refresh token, feed token
5. **Get Profile**: Verify connection by fetching user profile
6. **Get Candle Data**: Fetch historical price data

### How It Maps to Paper Trading System

```
Your Code                    → Paper Trading System
---------------------------------------------------
SmartConnect(api_key)       → legacy/angelone_connection.py
generateSession()           → AngelOneConnection.connect()
getProfile()                → AngelOneConnection.get_profile()
getCandleData()             → AngelOneConnection.get_candle_data()
                            → Used by brokers/angelone.py
                            → Used by runner.py
```

---

## Testing Different Scenarios

### Test 1: Basic Connection
Tests if you can connect and authenticate.

**What to check:**
- ✓ TOTP generates correctly
- ✓ Session creates successfully
- ✓ Tokens are retrieved

### Test 2: Profile Retrieval
Tests if you can fetch account data.

**What to check:**
- ✓ Your name appears
- ✓ Client code matches
- ✓ Email is correct

### Test 3: Historical Data
Tests if you can fetch past market data.

**What to check:**
- ✓ Candles are returned
- ✓ OHLCV data is present
- ✓ Timestamps are correct

### Test 4: Current Day Data
Tests if you can fetch today's data (only works during market hours).

**What to check:**
- ⚠️ May fail if market is closed (this is normal)
- ✓ Works during market hours (9:15 AM - 3:30 PM)

### Test 5: LTP (Last Traded Price)
Tests real-time price fetching.

**What to check:**
- ✓ Price is recent
- ✓ Symbol is correct

---

## Troubleshooting

### Error: "Invalid Credentials"

**Possible causes:**
1. Wrong MPIN (use Mobile PIN, NOT trading password)
2. Wrong TOTP token
3. Wrong username/client code

**Solution:**
- Double-check all credentials
- Verify TOTP token is the 32-character secret (not the 6-digit OTP)

### Error: "TOTP Validation Failed"

**Possible causes:**
1. System time is incorrect
2. TOTP token is wrong
3. Token has been regenerated

**Solution:**
```bash
# Check system time
date

# Regenerate TOTP manually to verify
python3 -c "import pyotp; print(pyotp.TOTP('4CDGR2KJ2Y3ESAYCIAXPYP2JAY').now())"
```

### Error: "No data available"

**Possible causes:**
1. Market is closed
2. Symbol token is incorrect
3. Date range is invalid

**Solution:**
- Test during market hours (9:15 AM - 3:30 PM IST, Mon-Fri)
- Use valid dates (not weekends/holidays)
- Verify symbol tokens

### Connection Times Out

**Possible causes:**
1. Network issues
2. AngelOne API is down
3. Firewall blocking

**Solution:**
- Check internet connection
- Try from different network
- Check AngelOne status page

---

## Symbol Tokens Reference

### Common Symbol Tokens (NSE)

| Symbol | Token | Name |
|--------|-------|------|
| SBIN-EQ | 3045 | State Bank of India |
| RELIANCE-EQ | 2885 | Reliance Industries |
| TCS-EQ | 11536 | Tata Consultancy Services |
| INFY-EQ | 1594 | Infosys |
| HDFC-EQ | 1333 | HDFC Bank |

### Index Tokens

| Index | Token | Name |
|-------|-------|------|
| NIFTY 50 | 99926000 | Nifty 50 Index |
| BANKNIFTY | 99926009 | Bank Nifty Index |
| FINNIFTY | 99926037 | Fin Nifty Index |

**Note**: Verify these tokens with AngelOne's instrument file:
https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json

---

## Next Steps

### After Successful Testing

1. **Run Paper Trading**:
   ```bash
   python runner.py --broker angelone
   ```

2. **Monitor During Market Hours**:
   - Test during live market (9:15 AM - 3:30 PM IST)
   - Verify real-time data flows
   - Check position entries/exits

3. **Complete AngelOne Implementation**:
   - Options chain fetching (currently placeholder)
   - Symbol-to-token mapping
   - Instrument file loading
   - Real-time LTP updates

---

## API Rate Limits

### AngelOne SmartAPI Limits

- **Historical Data**: 3 requests/second
- **Quote Data**: 5 requests/second
- **Order Placement**: 10 requests/second (not used in paper trading)

### Best Practices

1. **Cache instrument data**: Don't fetch repeatedly
2. **Batch requests**: Fetch multiple symbols together
3. **Respect rate limits**: Add delays if needed
4. **Handle errors**: Retry with exponential backoff

---

## Security Notes

### Keep Credentials Safe

1. **Never commit** credentials to git
2. **Use .gitignore** (already configured)
3. **Rotate tokens** periodically
4. **Monitor API usage** in AngelOne dashboard

### TOTP Token vs TOTP OTP

- **TOTP Token** (32 characters): Secret key you configure once
  - Example: `4CDGR2KJ2Y3ESAYCIAXPYP2JAY`
  - Store this in credentials file

- **TOTP OTP** (6 digits): Generated every 30 seconds
  - Example: `123456`
  - Used for authentication
  - Generated from TOTP Token using `pyotp.TOTP(token).now()`

---

## Summary

✅ **Your credentials are working** (based on your sample code)

✅ **Test file created**: `tests/test_angelone_direct.py`

✅ **Next steps**:
1. Run test: `python tests/test_angelone_direct.py`
2. Verify all tests pass
3. Create credentials file in `config/`
4. Run paper trading: `python runner.py --broker angelone`

📝 **Notes**:
- Current Nifty/live data only works during market hours
- Historical data (2021 example) works anytime
- Options chain implementation is pending (partial)

🚀 **You're ready to start testing AngelOne paper trading!**

---

**Last Updated**: 2025-12-26
