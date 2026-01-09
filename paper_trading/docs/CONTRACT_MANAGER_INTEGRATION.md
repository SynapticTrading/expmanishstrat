# Contract Manager Integration - Paper Trading

## Overview

The paper trading system now includes an intelligent contract management system that automatically handles options expiry selection, cache updates, and rollover warnings for both **Zerodha** and **AngelOne** brokers.

## Key Features

### 1. ✅ Automatic Expiry Selection
- Automatically selects current week, next week, current month, and next month expiries
- No manual expiry date configuration needed
- Always uses the nearest appropriate expiry

### 2. ✅ 5-Minute Monitor Thread
- Checks for contract cache updates every 5 minutes
- Automatically reloads contracts when cache is updated by cronjob
- Zero downtime - no need to restart the strategy

### 3. ✅ Multi-Broker Support
- Works seamlessly with both Zerodha and AngelOne
- Broker-specific cache files prevent conflicts
- Same interface for both brokers

### 4. ✅ Rollover Warnings
- Warns when expiry is approaching (2 days threshold)
- Suggests next expiry to roll over to
- Prevents trading on expiry day

### 5. ✅ Cache Management
- Universal cache file at root level:
  - `/Users/Algo_Trading/manishsir_options/contracts_cache.json`
  - Contains both futures and options data
  - Paper trading uses only options data
- Refreshed by root-level `refresh_contracts.py` script
- No broker-specific cache files needed

## Architecture

```
/Users/Algo_Trading/manishsir_options/
├── contracts_cache.json           ← Universal cache (futures + options)
├── refresh_contracts.py           ← Cronjob refresh script (updates cache)
└── paper_trading/
    ├── core/
    │   ├── contract_manager.py    ← Reads options from universal cache
    │   ├── broker.py
    │   ├── state_manager.py
    │   └── strategy.py
    └── runner.py                  ← Main runner with integration
```

## How It Works

### 1. Initialization (On Startup)

```python
# runner.py initialization flow:
1. Connect to broker (Zerodha/AngelOne)
2. Load broker instruments
3. Initialize ContractManager
   - Reads from universal cache: /Users/Algo_Trading/manishsir_options/contracts_cache.json
   - Extracts only options data (current_week, next_week, etc.)
   - Ignores futures data
4. Show active expiry and rollover warnings
5. Start contract monitor thread (5-min interval)
```

**Console Output:**
```
[2026-01-09 11:30:00+05:30] Loading instruments...
[2026-01-09 11:30:05+05:30] Initializing contract manager (reading from universal cache)...
[2026-01-09 11:30:05+05:30] ✓ Loaded contracts from universal cache: /Users/Algo_Trading/manishsir_options/contracts_cache.json
[2026-01-09 11:30:05+05:30] ✓ Contract manager initialized
[2026-01-09 11:30:05+05:30] Active Weekly Expiry: 2026-01-13 (4 days)
[2026-01-09 11:30:05+05:30] ✓ Contract monitor loop started (checks every 300s)
```

### 2. Expiry Selection (During Trading)

```python
# runner.py _get_options_data() method:
if self.contract_manager:
    expiry = self.contract_manager.get_options_expiry('current_week')
else:
    expiry = self.broker_api.get_next_expiry()  # Fallback
```

**Priority:**
1. Use ContractManager if available (✓ Recommended)
2. Fall back to broker's expiry detection
3. Return empty DataFrame if no expiry found

### 3. Automatic Cache Reload (Every 5 Minutes)

```python
# _contract_monitor_loop() checks:
while running:
    sleep(300)  # 5 minutes

    # Check if cache file modified (by cronjob)
    if cache_file.mtime > last_loaded_mtime:
        print("✓ Contracts reloaded from cronjob update")
        reload_contracts()
        update_active_expiry()
        check_rollover_warnings()
```

**Timeline:**
```
08:00 AM - Strategy running with 2026-01-13 expiry (4 days)
08:30 AM - Cronjob executes: python refresh_contracts.py
08:30 AM - Cache file updated
08:35 AM - Monitor thread detects change (5-min cycle)
08:35 AM - Contracts reloaded automatically
08:35 AM - Logs: "✓ Contracts reloaded from cronjob update"
```

## Usage

### Running Paper Trading

```bash
# Standard usage (contract manager enabled by default)
python3 paper_trading/runner.py --broker zerodha
python3 paper_trading/runner.py --broker angelone

# Contract manager automatically:
# - Selects current week expiry
# - Monitors for cache updates every 5 minutes
# - Warns about upcoming rollovers
```

### Manual Contract Refresh

```bash
# Refresh universal cache (from root directory)
cd /Users/Algo_Trading/manishsir_options

# Using Zerodha (futures + options)
python3 refresh_contracts.py --broker zerodha

# Using AngelOne (options only)
python3 refresh_contracts.py --broker angelone
```

### Automated Daily Refresh (Cronjob)

```bash
# Edit crontab
crontab -e

# Option 1: Use Zerodha (includes futures)
30 8 * * * cd /Users/Algo_Trading/manishsir_options && python3 refresh_contracts.py --broker zerodha >> logs/refresh.log 2>&1

# Option 2: Use AngelOne (options only)
30 8 * * * cd /Users/Algo_Trading/manishsir_options && python3 refresh_contracts.py --broker angelone >> logs/refresh.log 2>&1
```

**Note:** Choose ONE broker for the cronjob. Both provide identical NIFTY options expiry data.

## Configuration

### Enable/Disable Contract Manager

```python
# In runner.py __init__:
self.use_contract_manager = True  # Enable (default)
self.use_contract_manager = False # Disable (fallback to broker)
```

### Change Monitor Interval

```python
# In runner.py __init__:
self.contract_monitor_interval = 300  # 5 minutes (default)
self.contract_monitor_interval = 600  # 10 minutes
self.contract_monitor_interval = 180  # 3 minutes
```

### Cache Validity

```python
# In contract_manager.py:
def _is_cache_stale(self, max_age_hours=24):  # Default: 24 hours
    # Change to 12 hours:
    def _is_cache_stale(self, max_age_hours=12):
```

## Contract Manager API

### Get Expiry Dates

```python
# Get specific expiry types
current_week = contract_manager.get_options_expiry('current_week')
next_week = contract_manager.get_options_expiry('next_week')
current_month = contract_manager.get_options_expiry('current_month')
next_month = contract_manager.get_options_expiry('next_month')

# Returns: "2026-01-13" or None
```

### Get All Expiry Dates

```python
all_expiries = contract_manager.get_all_options_expiry_dates()
# Returns: ['2026-01-13', '2026-01-20', '2026-01-27', ...]
```

### Calculate Days to Expiry

```python
days = contract_manager._calculate_days_to_expiry('2026-01-13')
# Returns: 4 (for example)
```

### Check Rollover Need

```python
needs_rollover = contract_manager.should_rollover_options(
    expiry_type='current_week',
    days_threshold=2
)
# Returns: True if <= 2 days to expiry
```

### Get Rollover Target

```python
next_expiry = contract_manager.get_options_rollover_target('current_week')
# Returns: "2026-01-20" (next week expiry)
```

### ATM Strike Calculation

```python
spot_price = 25850.0
atm_strike = contract_manager.get_atm_strike(spot_price)
# Returns: 25850 (rounded to strike step)
```

### Strike Range

```python
strikes = contract_manager.get_strike_range(
    center_strike=25850,
    num_strikes=5
)
# Returns: [25600, 25650, 25700, 25750, 25800, 25850, 25900, 25950, 26000, 26050, 26100]
```

## Benefits

### 1. Zero Maintenance
- No manual expiry configuration needed
- Automatic rollover when expiry approaches
- Cronjob updates contracts automatically

### 2. Continuous Operation
- 24/7 running without restarts
- Automatic cache reload on cronjob updates
- No downtime for contract updates

### 3. Multi-Broker Ready
- Same code for Zerodha and AngelOne
- Broker-specific caching prevents conflicts
- Consistent interface across brokers

### 4. Safety Features
- Rollover warnings (2-day threshold)
- Fallback to broker expiry if manager fails
- Cache staleness detection (24-hour max)

### 5. Logging & Monitoring
- Clear logs for all contract operations
- Cache update notifications
- Rollover warnings logged to console

## Troubleshooting

### Issue: Contract manager initialization failed

**Symptom:**
```
⚠️  Contract manager initialization failed: [error]
Falling back to broker's expiry detection...
```

**Solution:**
- Check broker connection
- Verify instruments loaded successfully
- Check cache directory exists and is writable
- Review error message for specific issue

**Fallback:** Broker's `get_next_expiry()` will be used automatically

### Issue: No cache updates detected

**Symptom:**
- Cronjob runs but strategy doesn't reload contracts

**Solution:**
1. Check cronjob logs: `tail -f paper_trading/logs/refresh.log`
2. Verify cache file timestamp: `ls -l paper_trading/cache/`
3. Check monitor interval (default: 5 minutes)
4. Review contract monitor loop logs

### Issue: Wrong expiry selected

**Symptom:**
- Strategy uses unexpected expiry date

**Solution:**
1. Check contract mapping: `cat paper_trading/cache/contracts_cache_*.json | jq .options.mapping`
2. Verify current week logic in `_create_options_mapping()`
3. Check broker's expiry dates available
4. Review logs for expiry selection messages

### Issue: Rollover warnings not appearing

**Symptom:**
- No warnings when expiry is close

**Solution:**
1. Check threshold: `should_rollover_options(days_threshold=2)`
2. Verify days calculation: `_calculate_days_to_expiry()`
3. Check contract manager is enabled
4. Review initialization logs

## Technical Details

### Thread Safety
- Monitor thread runs independently
- File system operations are atomic
- Cache reload completes before updating references
- No race conditions between threads

### Performance
- Minimal overhead: Single `stat()` syscall every 5 minutes
- Cache reload takes <100ms
- No impact on trading logic
- Efficient file modification time checking

### Cache File Structure

The universal cache at `/Users/Algo_Trading/manishsir_options/contracts_cache.json`:

```json
{
  "timestamp": "2026-01-09T11:30:00",
  "symbol": "NIFTY",
  "exchange": "NFO",
  "futures": {
    "contracts": [...],           ← Ignored by paper trading
    "mapping": {...}              ← Ignored by paper trading
  },
  "options": {
    "expiry_dates": [
      "2026-01-13",
      "2026-01-20",
      "2026-01-27"
    ],
    "mapping": {                  ← Used by paper trading
      "current_week": "2026-01-13",
      "next_week": "2026-01-20",
      "current_month": "2026-01-27",
      "next_month": "2026-02-24"
    },
    "strikes": {
      "min": 12000.0,
      "max": 34500.0,
      "step": 50.0
    }
  }
}
```

**Note:** Paper trading only reads the `options` section and ignores `futures`.

## Summary

The contract manager integration provides:

✅ Automatic expiry selection (current_week, next_week, etc.)
✅ 5-minute monitoring for cache updates
✅ Zero downtime contract refresh
✅ Multi-broker support (Zerodha + AngelOne)
✅ Rollover warnings (2-day threshold)
✅ Cronjob-ready refresh script
✅ Comprehensive logging
✅ Graceful fallbacks

The system is now truly zero-maintenance for 24/7 server deployment!
