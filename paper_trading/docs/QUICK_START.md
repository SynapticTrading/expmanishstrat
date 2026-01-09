# Quick Start - Multi-Broker Contract Manager

## TL;DR

```bash
# Refresh cache (choose ONE):
python3 refresh_contracts.py --broker zerodha    # Futures + Options
python3 refresh_contracts.py --broker angelone   # Options only

# Run paper trading (works with cache from either broker):
python3 paper_trading/runner.py --broker angelone
python3 paper_trading/runner.py --broker zerodha
```

## Daily Cronjob (8:30 AM)

```bash
crontab -e

# Choose ONE:
30 8 * * * python3 refresh_contracts.py --broker zerodha >> logs/refresh.log 2>&1
# OR
30 8 * * * cd /Users/Algo_Trading/manishsir_options && python3 refresh_contracts.py --broker angelone >> logs/refresh.log 2>&1
```

## What You Get

✅ **Automatic expiry selection** - No manual configuration needed  
✅ **Auto-reload on cache updates** - Zero downtime  
✅ **Rollover warnings** - 2-day threshold for options  
✅ **Multi-broker support** - Zerodha OR AngelOne  
✅ **Universal cache** - One file for all strategies  

## Current Expiries

Run this to see active expiries:

```bash
python3 -c "
import json
from datetime import datetime

with open('contracts_cache.json') as f:
    data = json.load(f)

mapping = data['options']['mapping']
for k, v in mapping.items():
    expiry_date = datetime.strptime(v, '%Y-%m-%d').date()
    days = (expiry_date - datetime.now().date()).days
    print(f'{k:15} {v}  ({days} days)')
"
```

## File Locations

```
/Users/Algo_Trading/manishsir_options/
├── contracts_cache.json              ← Universal cache (both brokers write here)
├── refresh_contracts.py              ← Run daily with --broker flag
└── paper_trading/
    ├── runner.py                     ← Main trading script
    └── core/contract_manager.py      ← Reads from universal cache
```

## Logs

```bash
# Refresh logs
tail -f logs/refresh_contracts.log

# Paper trading logs (find latest)
ls -lt paper_trading/logs/session_log_*.txt | head -1
tail -f paper_trading/logs/session_log_$(date +%Y%m%d)_*.txt
```

## Verification

After running refresh_contracts.py:

```bash
# Check cache updated
ls -lh contracts_cache.json

# View cache contents
cat contracts_cache.json | python3 -m json.tool | less

# Test paper trading can read it
python3 -c "from paper_trading.core.contract_manager import ContractManager; m=ContractManager(); print('✓ Cache OK')"
```

## That's It!

Everything else is automatic. Paper trading will:
- Load expiries from cache on startup
- Monitor cache every 5 minutes
- Reload automatically when cronjob updates it
- Log: "✓ Contracts reloaded from cronjob update"

**No manual intervention needed! 🎉**

---

For detailed docs, see:
- `REFRESH_CONTRACTS_USAGE.md` - Complete usage guide
- `MULTI_BROKER_IMPLEMENTATION_SUMMARY.md` - Full technical details
- `paper_trading/CONTRACT_MANAGER_INTEGRATION.md` - Integration docs
