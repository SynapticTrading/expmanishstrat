# refresh_contracts.py - Multi-Broker Support

## Overview

The `refresh_contracts.py` script now supports **both Zerodha and AngelOne** brokers for fetching contract data.

## Usage

### Command Line

```bash
# Using Zerodha (default)
python3 refresh_contracts.py --broker zerodha

# Using AngelOne
python3 refresh_contracts.py --broker angelone

# Default (uses Zerodha if no --broker specified)
python3 refresh_contracts.py
```

### What Gets Fetched

| Broker | Futures | Options |
|--------|---------|---------|
| **Zerodha** | ✅ Current, Next, Far Next Month | ✅ All expiries (weekly + monthly) |
| **AngelOne** | ❌ Not fetched | ✅ All expiries (weekly + monthly) |

### Cache File

Both brokers write to the same universal cache file:
```
/Users/Algo_Trading/manishsir_options/contracts_cache.json
```

**Structure:**
```json
{
  "timestamp": "2026-01-09T12:05:27",
  "symbol": "NIFTY",
  "exchange": "NFO",
  "broker": "Zerodha" or "AngelOne",
  "futures": {
    "contracts": [...],    // Empty for AngelOne
    "mapping": {...}       // Empty for AngelOne
  },
  "options": {
    "expiry_dates": [...],
    "mapping": {
      "current_week": "2026-01-13",
      "next_week": "2026-01-20",
      "current_month": "2026-01-27",
      "next_month": "2026-02-24"
    },
    "strikes": {...}
  }
}
```

## Credentials

### Zerodha
Uses `auth_helper.py` with credentials from:
- Default location (configured in auth_helper.py)

### AngelOne
Uses credentials from:
```
/Users/Algo_Trading/manishsir_options/paper_trading/config/credentials_angelone.txt
```

**Format:**
```
api_key=your_api_key
username=N123456
password=your_password
totp_token=your_totp_secret
```

## Cronjob Setup

### Option 1: Zerodha (Recommended if you need futures)

```bash
crontab -e

# Add this line:
30 8 * * * cd /Users/Algo_Trading/manishsir_options && python3 refresh_contracts.py --broker zerodha >> logs/refresh.log 2>&1
```

### Option 2: AngelOne (If you only need options)

```bash
crontab -e

# Add this line:
30 8 * * * cd /Users/Algo_Trading/manishsir_options && python3 refresh_contracts.py --broker angelone >> logs/refresh.log 2>&1
```

## Output Examples

### Zerodha Output

```
======================================================================
DAILY CONTRACT REFRESH (FUTURES + OPTIONS) - 2026-01-09 08:30:00
======================================================================
Broker: ZERODHA

Step 1/3: Authenticating with Zerodha...
✓ Authentication successful

Step 2/3: Refreshing contracts...
✓ Contracts refreshed successfully

Step 3/3: Verifying contracts...

======================================================================
FUTURES CONTRACTS
======================================================================
Current Month:  NIFTY26JANFUT - Expiry: 2026-01-27 (18 days)
Next Month:     NIFTY26FEBFUT - Expiry: 2026-02-24 (46 days)
Far Next Month: NIFTY26MARFUT - Expiry: 2026-03-30 (80 days)

======================================================================
OPTIONS EXPIRY DATES
======================================================================
Current Week:   2026-01-13 (4 days)
Next Week:      2026-01-20 (11 days)
Current Month:  2026-01-27 (18 days)
Next Month:     2026-02-24 (46 days)

======================================================================
FUTURES ROLLOVER CHECK (7-day threshold)
======================================================================
✓ OK: current_month (NIFTY26JANFUT - 18 days to expiry)
✓ OK: next_month (NIFTY26FEBFUT - 46 days to expiry)

======================================================================
OPTIONS ROLLOVER CHECK (2-day threshold)
======================================================================
✓ OK: current_week (2026-01-13 - 4 days to expiry)
✓ OK: current_month (2026-01-27 - 18 days to expiry)

======================================================================
REFRESH COMPLETED SUCCESSFULLY
======================================================================
```

### AngelOne Output

```
======================================================================
DAILY CONTRACT REFRESH (FUTURES + OPTIONS) - 2026-01-09 08:30:00
======================================================================
Broker: ANGELONE

Step 1/3: Authenticating with Angelone...
Generated TOTP: 364407
Connecting to AngelOne...
✓ Connection successful!
✓ Authentication successful

Step 2/3: Loading instruments from AngelOne...
Loading instruments from AngelOne...
✓ Downloaded 179933 instruments
✓ Filtered 40442 NFO instruments
✓ Loaded 1500 NIFTY options
Refreshing contracts...
Found 18 unique options expiry dates
Saved 18 options expiries to cache: contracts_cache.json
✓ Contracts refreshed successfully

Step 3/3: Verifying contracts...

======================================================================
OPTIONS EXPIRY DATES
======================================================================
Current Week:   2026-01-13 (4 days)
Next Week:      2026-01-20 (11 days)
Current Month:  2026-01-27 (18 days)
Next Month:     2026-02-24 (46 days)

======================================================================
OPTIONS ROLLOVER CHECK (2-day threshold)
======================================================================
✓ OK: current_week (2026-01-13 - 4 days to expiry)
✓ OK: current_month (2026-01-27 - 18 days to expiry)

======================================================================
REFRESH COMPLETED SUCCESSFULLY
======================================================================
```

## Paper Trading Integration

Once the cache is refreshed, paper trading can use it with **any broker**:

```bash
# Paper trading with AngelOne (reading from cache)
python3 paper_trading/runner.py --broker angelone

# Paper trading with Zerodha (reading from cache)
python3 paper_trading/runner.py --broker zerodha
```

The paper trading system will:
1. Read options data from the universal cache
2. Use current_week, next_week expiries automatically
3. Monitor cache for updates every 5 minutes
4. Reload automatically when refresh_contracts.py updates the cache

## Important Notes

✅ **Both brokers provide identical NIFTY options expiry data** - Choose based on preference or credential availability

✅ **Cache is broker-agnostic** - Paper trading works with cache from either broker

✅ **Options data is identical** - NSE standardizes NIFTY expiries across all brokers

✅ **Futures only from Zerodha** - AngelOne path doesn't fetch futures contracts

✅ **Automatic reload** - Paper trading detects cache updates from cronjob automatically

## Troubleshooting

### Issue: Authentication failed (Zerodha)

**Solution:** Check `auth_helper.py` credentials configuration

### Issue: Authentication failed (AngelOne)

**Solution:** Verify credentials file at:
```
paper_trading/config/credentials_angelone.txt
```

### Issue: No options data found

**Solution:**
1. Check broker connection
2. Verify instruments loaded successfully
3. Run script manually to see detailed error messages

### Issue: Cache not updating in paper trading

**Solution:**
1. Verify cache file timestamp: `ls -l contracts_cache.json`
2. Check paper trading is monitoring: Look for "Contract monitor loop started"
3. Wait up to 5 minutes for next check cycle

## Logs

All output is logged to:
```
/Users/Algo_Trading/manishsir_options/logs/refresh_contracts.log
```

View logs:
```bash
tail -f logs/refresh_contracts.log
```
