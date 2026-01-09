# Lot Size Implementation Summary

## What Changed

Added **lot size** information to the options data in the universal cache. This allows strategies to know that **1 lot = X units** (e.g., 1 lot = 65 units for NIFTY options).

## Modified Files

### 1. `/contract_manager.py` (Root - Zerodha)
- Added `self.options_lot_size` attribute (default: 65)
- Extracts lot size from Zerodha instruments
- Logs lot size during refresh
- Saves lot size to cache
- Loads lot size from cache

### 2. `/refresh_contracts.py` (Multi-broker refresh script)
**AngelOne path (`_create_cache_from_angelone` function):**
- Extracts lot size from AngelOne instruments
- Logs lot size during processing
- Includes lot size in cache structure

### 3. `/paper_trading/core/contract_manager.py` (Paper trading)
- Added `self.options_lot_size` attribute (default: 65)
- Loads lot size from universal cache
- Logs lot size on initialization
- Added `get_options_lot_size()` public method

## Cache Structure

The `contracts_cache.json` now includes lot size in the options section:

```json
{
  "timestamp": "2026-01-09T12:31:47",
  "symbol": "NIFTY",
  "exchange": "NFO",
  "futures": {
    "contracts": [...],
    "mapping": {...}
  },
  "options": {
    "expiry_dates": [...],
    "mapping": {...},
    "strikes": {
      "min": 12000.0,
      "max": 34500.0,
      "step": 1000.0
    },
    "lot_size": 65   ← NEW FIELD
  }
}
```

## Usage in Paper Trading

```python
from paper_trading.core.contract_manager import ContractManager

manager = ContractManager()

# Get lot size
lot_size = manager.get_options_lot_size()
print(f"1 lot = {lot_size} units")  # Output: 1 lot = 65 units

# Calculate total units for multiple lots
num_lots = 2
total_units = num_lots * lot_size
print(f"{num_lots} lots = {total_units} units")  # Output: 2 lots = 130 units
```

## Automatic Updates

When NSE changes the lot size:

1. **Next day's refresh** (via cronjob):
   ```bash
   python3 refresh_contracts.py --broker {zerodha|angelone}
   ```
   - Fetches latest instruments with new lot size
   - Updates cache with new lot size

2. **Paper trading auto-reloads** (every 5 minutes):
   - Detects cache file change
   - Reloads with new lot size
   - Logs: "Options lot size: 75 units per lot" (if changed to 75)

**Zero manual intervention needed!** ✅

## Current Values

As of 2026-01-09:
- **NIFTY Options Lot Size**: 65 units per lot
- **Source**: Both Zerodha and AngelOne

## Testing Results

### ✅ Test 1: AngelOne Refresh
```bash
$ python3 refresh_contracts.py --broker angelone
...
Options lot size: 65 units per lot
✓ Saved 3 futures and 18 options expiries to cache
```

### ✅ Test 2: Zerodha Refresh
```bash
$ python3 refresh_contracts.py --broker zerodha
...
✓ REFRESH COMPLETED SUCCESSFULLY
```
Cache contains: `"lot_size": 65`

### ✅ Test 3: Paper Trading Load
```python
manager = ContractManager()
print(manager.get_options_lot_size())
# Output: 65
```

### ✅ Test 4: Cache Verification
```bash
$ cat contracts_cache.json | python -c "import json, sys; print(json.load(sys.stdin)['options']['lot_size'])"
65
```

## Benefits

✅ **Accurate lot sizing** - Strategies know exactly how many units in 1 lot

✅ **Auto-updates** - Lot size changes from NSE are automatically captured

✅ **No hardcoding** - Lot size comes from broker data, not hardcoded values

✅ **Backward compatible** - Defaults to 65 if lot_size missing from old cache

✅ **Multi-broker support** - Works with both Zerodha and AngelOne

## Example Use Cases

### 1. Position Sizing
```python
manager = ContractManager()
lot_size = manager.get_options_lot_size()

# Calculate position size
capital = 100000
risk_per_trade = 0.02  # 2%
risk_amount = capital * risk_per_trade  # 2000

# If option premium is 100 per unit
premium = 100
max_lots = risk_amount / (premium * lot_size)
print(f"Max lots to trade: {int(max_lots)}")
```

### 2. P&L Calculation
```python
# Entry
entry_premium = 150  # per unit
lots_traded = 2
units = lots_traded * lot_size
entry_value = entry_premium * units

# Exit
exit_premium = 180  # per unit
exit_value = exit_premium * units

pnl = exit_value - entry_value
print(f"P&L: ₹{pnl:,.2f}")
```

### 3. Margin Calculation
```python
# SPAN margin (approximate)
span_per_lot = 15000  # Example
lots = 5
total_margin = span_per_lot * lots
print(f"Required margin: ₹{total_margin:,.2f}")
```

## API Reference

### Paper Trading Contract Manager

```python
class ContractManager:

    def get_options_lot_size(self) -> int:
        """
        Get NIFTY options lot size.

        Returns:
            int: Lot size (number of units per lot)

        Example:
            >>> manager = ContractManager()
            >>> lot_size = manager.get_options_lot_size()
            >>> print(lot_size)
            65
        """
```

## Notes

- **Lot size is the same** across all strikes and expiries for NIFTY options at any given time
- **NSE may change lot size** periodically (usually announced in advance)
- **Cache auto-updates** daily via cronjob, so lot size always reflects current NSE values
- **Default value is 65** (used if lot_size not found in cache for backward compatibility)

## Status

**Implementation: Complete ✅**

**Testing: Verified ✅**
- ✅ Zerodha refresh captures lot size
- ✅ AngelOne refresh captures lot size
- ✅ Cache saves lot size correctly
- ✅ Paper trading reads lot size correctly
- ✅ Public API works (get_options_lot_size())

**Production Ready: Yes ✅**

**Monitoring:** Lot size will be logged on every paper trading initialization, making it easy to verify:
```
[2026-01-09 12:31:47] ✓ Loaded contracts from universal cache
[2026-01-09 12:31:47] Options lot size: 65 units per lot
```

## Summary

You now have **automatic lot size tracking** that:
- Fetches from broker (both Zerodha and AngelOne)
- Stores in universal cache
- Auto-updates daily via cronjob
- Reloads automatically in paper trading
- Provides easy API: `manager.get_options_lot_size()`

**No manual maintenance required!** 🎉
