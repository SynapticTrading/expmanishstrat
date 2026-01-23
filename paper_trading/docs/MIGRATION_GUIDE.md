# Migration Guide: Evolution of the Broker Architecture

> This document explains the three stages of the broker architecture evolution, from the initial implementation to the fully adapter-based system with token lookups.

---

## Table of Contents

1. [The Problem: Broker Symbol Nomenclature](#the-problem-broker-symbol-nomenclature)
2. [Stage 1: Initial Architecture (Dec 2025)](#stage-1-initial-architecture-dec-2025)
3. [Stage 2: Hybrid Architecture (Early Jan 2026)](#stage-2-hybrid-architecture-early-jan-2026)
4. [Stage 3: Fully Adapter-Based (Jan 2026)](#stage-3-fully-adapter-based-jan-2026)
5. [The Solution: Token-Based Instrument Resolution](#the-solution-token-based-instrument-resolution)
6. [Comparison: All Three Stages](#comparison-all-three-stages)
7. [File Changes Summary](#file-changes-summary)
8. [How to Use the New System](#how-to-use-the-new-system)

---

## The Problem: Broker Symbol Nomenclature

### Each Broker Has Different Symbol Formats

When trading NIFTY options, each broker uses a **different symbol format**:

```
SAME OPTION CONTRACT:
  Underlying: NIFTY
  Strike: 23000
  Type: Call (CE)
  Expiry: January 23, 2026

DIFFERENT SYMBOLS PER BROKER:
  ┌─────────────┬─────────────────────────┐
  │ Broker      │ Symbol Format           │
  ├─────────────┼─────────────────────────┤
  │ Zerodha     │ NIFTY2612323000CE       │
  │ AngelOne    │ NIFTY23JAN26C23000      │
  │ Upstox      │ NIFTY26JAN2326000CE     │
  │ Dhan        │ NIFTY-Jan2026-23000-CE  │
  └─────────────┴─────────────────────────┘
```

### Why This Was a Problem

**Old Approach: Symbol Construction**
```python
# ERROR-PRONE: Each broker needs different code
def build_zerodha_symbol(strike, option_type, expiry):
    # Zerodha: NIFTY{YY}{MMM}{STRIKE}{CE/PE}
    exp_code = expiry.strftime("%y%b").upper()  # "26JAN"
    return f"NIFTY{exp_code}{strike}{option_type}"

def build_angelone_symbol(strike, option_type, expiry):
    # AngelOne: NIFTY{DD}{MMM}{YY}{C/P}{STRIKE}
    exp_code = expiry.strftime("%d%b%y").upper()  # "23JAN26"
    opt_char = "C" if option_type == "CE" else "P"
    return f"NIFTY{exp_code}{opt_char}{strike}"

# Problems:
# 1. Format changes when brokers update their APIs
# 2. Edge cases (monthly vs weekly expiry formats differ)
# 3. Hard to maintain and test
# 4. Each new broker = new symbol construction code
```

### The Solution: Use Instrument Tokens

Every broker provides **instrument tokens** - unique numeric IDs that never change format:

```
SAME OPTION CONTRACT:
  ┌─────────────┬─────────────┬─────────────────────────┐
  │ Broker      │ Token       │ Symbol (for reference)  │
  ├─────────────┼─────────────┼─────────────────────────┤
  │ Zerodha     │ 17654274    │ NIFTY2612323000CE       │
  │ AngelOne    │ 48756       │ NIFTY23JAN26C23000      │
  └─────────────┴─────────────┴─────────────────────────┘

# Token-based lookup: ALWAYS WORKS
token = contract_manager.get_instrument_token("2026-01-23", 23000, "CE")
# Returns: "17654274" (Zerodha) or "48756" (AngelOne)
```

---

## Stage 1: Initial Architecture (Dec 2025)

### What Existed Initially

The original paper trading system used a simple `BrokerInterface` pattern with broker-specific implementations.

```
paper_trading/
├── brokers/
│   ├── base.py           ← BrokerInterface (abstract class)
│   ├── zerodha.py        ← ZerodhaBroker implementation
│   └── angelone.py       ← AngelOneBroker implementation
├── utils/
│   └── factory.py        ← create_broker() factory
└── runner.py             ← Used broker_api only
```

### The Original BrokerInterface

```python
# paper_trading/brokers/base.py (Original)

from abc import ABC, abstractmethod

class BrokerInterface(ABC):
    """Abstract base class for broker implementations"""

    @abstractmethod
    def connect(self):
        """Connect to broker API"""
        pass

    @abstractmethod
    def get_spot_price(self, symbol="NIFTY 50"):
        """Get current spot price"""
        pass

    @abstractmethod
    def get_ltp(self, instrument_token):
        """Get Last Traded Price"""
        pass

    @abstractmethod
    def get_options_chain(self, expiry, strikes):
        """Get options chain data"""
        pass

    @abstractmethod
    def logout(self):
        """Logout from broker"""
        pass

    @property
    @abstractmethod
    def name(self):
        """Broker name"""
        pass
```

### The Original ZerodhaBroker

```python
# paper_trading/brokers/zerodha.py (Original)

from paper_trading.brokers.base import BrokerInterface
from paper_trading.legacy.zerodha_connection import ZerodhaConnection
from paper_trading.legacy.zerodha_data_feed import ZerodhaDataFeed

class ZerodhaBroker(BrokerInterface):
    """Zerodha Kite Connect broker implementation"""

    def __init__(self, api_key, api_secret, user_id, user_password, totp_key):
        self.connection = ZerodhaConnection(
            api_key=api_key,
            api_secret=api_secret,
            user_id=user_id,
            user_password=user_password,
            totp_key=totp_key
        )
        self.data_feed = None
        self._connected = False

    @property
    def name(self):
        return "Zerodha"

    def connect(self):
        kite = self.connection.connect()
        if kite:
            self.data_feed = ZerodhaDataFeed(self.connection)
            self._connected = True
            return True
        return False

    def get_spot_price(self, symbol="NIFTY 50"):
        if not self._connected or not self.data_feed:
            return None
        return self.data_feed.get_spot_price()

    def get_options_chain(self, expiry, strikes):
        if not self._connected or not self.data_feed:
            return None
        return self.data_feed.get_options_chain(expiry, strikes)

    def logout(self):
        if self._connected:
            self.connection.logout()
            self._connected = False
```

### The Original Factory

```python
# paper_trading/utils/factory.py (Original)

from paper_trading.brokers.zerodha import ZerodhaBroker
from paper_trading.brokers.angelone import AngelOneBroker

def create_broker(credentials, broker_type=None):
    """Create broker instance based on credentials"""

    # Auto-detect broker type
    if broker_type is None:
        if 'api_secret' in credentials:
            broker_type = 'zerodha'
        elif 'username' in credentials:
            broker_type = 'angelone'

    if broker_type == 'zerodha':
        return ZerodhaBroker(
            api_key=credentials['api_key'],
            api_secret=credentials['api_secret'],
            user_id=credentials['user_id'],
            user_password=credentials['user_password'],
            totp_key=credentials['totp_key']
        )
    elif broker_type == 'angelone':
        return AngelOneBroker(
            api_key=credentials['api_key'],
            username=credentials['username'],
            password=credentials['password'],
            totp_token=credentials['totp_token']
        )
```

### How Runner.py Worked (Stage 1)

```python
# runner.py (Stage 1 - Dec 2025)

from paper_trading.utils.factory import create_broker

class UniversalPaperTrader:
    def __init__(self, config_path, credentials_path, broker_type=None):
        # Create broker using old factory
        self.broker_api = create_broker(credentials, broker_type)
        print(f"✓ Broker: {self.broker_api.name}")

        # NO adapter, NO contract_manager, NO token lookups

    def connect(self):
        if not self.broker_api.connect():
            raise Exception(f"Failed to connect to {self.broker_api.name}")

    def _strategy_loop(self):
        while self.running:
            # Market status
            if not self.broker_api.is_market_open():
                break

            # Market data
            spot_price = self.broker_api.get_spot_price()
            options_data = self.broker_api.get_options_chain(expiry, strikes)

            # Strategy logic
            self.strategy.on_candle(current_time, spot_price, options_data)

            # Wait
            self.broker_api.wait_for_next_candle()

    def cleanup(self):
        self.broker_api.logout()
```

### Stage 1 Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    STAGE 1: INITIAL (Dec 2025)                   │
├─────────────────────────────────────────────────────────────────┤
│                         RUNNER.PY                                │
│                                                                  │
│   broker_api = create_broker(credentials)                       │
│                    │                                            │
│                    ▼                                            │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │              ZerodhaBroker / AngelOneBroker              │  │
│   │                                                          │  │
│   │  broker_api.connect()                                    │  │
│   │  broker_api.get_spot_price()                             │  │
│   │  broker_api.get_options_chain(expiry, strikes)           │  │
│   │  broker_api.is_market_open()                             │  │
│   │  broker_api.wait_for_next_candle()                       │  │
│   │  broker_api.logout()                                     │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                  │
│   NO adapter, NO tokens, NO contract_manager                    │
└─────────────────────────────────────────────────────────────────┘
```

### Problems with Stage 1

1. **No standard interface for orders**: Each broker has different order params
2. **No token-based lookups**: Symbol construction was error-prone
3. **No contract management**: Expiry dates were hardcoded or broker-specific
4. **Tight coupling**: Strategy knew about broker internals

---

## Stage 2: Hybrid Architecture (Early Jan 2026)

### What Was Added

The adapter layer was created to solve the symbol nomenclature problem, but was only partially integrated.

```
paper_trading/
├── brokers/
│   ├── base.py           ← BrokerInterface (STILL USED)
│   ├── zerodha.py        ← ZerodhaBroker (STILL USED for market data)
│   ├── angelone.py       ← AngelOneBroker (STILL USED for market data)
│   └── adapter/          ← NEW (partially integrated)
│       ├── base.py       ← BrokerAdapter (new unified interface)
│       ├── types.py      ← Standard types
│       ├── factory.py    ← create_adapter()
│       └── plugins/
│           ├── zerodha.py   ← ZerodhaAdapter
│           ├── angelone.py  ← AngelOneAdapter
│           └── paper.py     ← PaperAdapter
├── core/
│   └── contract_manager.py  ← NEW (token lookups)
└── runner.py             ← Used BOTH broker_api AND adapter
```

### How Runner.py Worked (Stage 2 - Hybrid)

```python
# runner.py (Stage 2 - Hybrid)

from paper_trading.utils.factory import create_broker      # OLD
from paper_trading.brokers.adapter import create_adapter   # NEW

class UniversalPaperTrader:
    def __init__(self, ...):
        # OLD: Created broker_api using old factory
        self.broker_api = create_broker(credentials, broker_type)

        # NEW: Contract manager for token lookups
        self.contract_manager = ContractManager()

        # NEW: Adapter (but only for token lookups)
        self.adapter = None  # Created in initialize()

    def initialize(self):
        # OLD: Load instruments via broker_api
        self.broker_api.load_instruments()

        # NEW: Create adapter with contract_manager
        self.adapter = create_adapter(credentials, contract_manager=self.contract_manager)
        # Hack: Share connection with broker_api
        self.adapter._connected = True
        self.adapter._kite = self.broker_api.connection

    def _strategy_loop(self):
        # OLD: Market data via broker_api
        spot_price = self.broker_api.get_spot_price()
        options_data = self.broker_api.get_options_chain(expiry, strikes)

        # OLD: Market status via broker_api
        if not self.broker_api.is_market_open():
            break

        # OLD: Utilities via broker_api
        self.broker_api.wait_for_next_candle()

    def cleanup(self):
        # OLD: Logout via broker_api
        self.broker_api.logout()
```

### Stage 2 Data Flow (Confusing)

```
┌─────────────────────────────────────────────────────────────────┐
│                    STAGE 2: HYBRID (Early Jan 2026)              │
├─────────────────────────────────────────────────────────────────┤
│                         RUNNER.PY                                │
│                                                                  │
│   broker_api = create_broker()     ← OLD (ZerodhaBroker)        │
│   adapter = create_adapter()       ← NEW (ZerodhaAdapter)       │
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │  Market data: broker_api (OLD)                          │  │
│   │    spot = broker_api.get_spot_price()                   │  │
│   │    options = broker_api.get_options_chain()             │  │
│   │    is_open = broker_api.is_market_open()                │  │
│   │    broker_api.wait_for_next_candle()                    │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │  Token lookups: adapter (NEW)                           │  │
│   │    token = adapter._resolve_instrument()                │  │
│   │    contract = contract_manager.get_option_contract()    │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                  │
│   PROBLEM: Two systems, confusing which to use!                 │
└─────────────────────────────────────────────────────────────────┘
```

### Problems with Stage 2 (Hybrid)

1. **Two interfaces to maintain**: `broker_api` (old) and `adapter` (new)
2. **Inconsistent usage**: Market data used old, tokens used new
3. **Code duplication**: Same functionality in two places
4. **Connection sharing hack**: Had to manually share kite connection
5. **Confusion**: Which interface to use for what?

---

## Stage 3: Fully Adapter-Based (Jan 2026)

### What Exists Now

```
paper_trading/
├── brokers/
│   ├── base.py           ← DEPRECATED (not used)
│   ├── zerodha.py        ← DEPRECATED (not used)
│   ├── angelone.py       ← DEPRECATED (not used)
│   └── adapter/          ← PRIMARY (fully integrated)
│       ├── base.py       ← BrokerAdapter (abstract class)
│       ├── types.py      ← Standard enums & dataclasses
│       ├── factory.py    ← create_adapter()
│       └── plugins/
│           ├── zerodha.py   ← ZerodhaAdapter (ALL operations)
│           ├── angelone.py  ← AngelOneAdapter (ALL operations)
│           └── paper.py     ← PaperAdapter (simulated)
└── runner.py             ← Uses ONLY adapter
```

### How Runner.py Works (After)

```python
# runner.py (AFTER - Fully Migrated)

class UniversalPaperTrader:
    def __init__(self, ...):
        # NEW: Only adapter, no broker_api
        self.adapter = None  # Initialized in connect()

    def connect(self):
        # NEW: Single adapter handles everything
        self.adapter = create_adapter(credentials, contract_manager=cm)
        self.adapter.connect()

    def _strategy_loop(self):
        # NEW: ALL operations via adapter
        spot_price = self.adapter.get_spot_price()
        options_data = self.adapter.get_options_chain(expiry, strikes)

        if not self.adapter.is_market_open():
            break

        self.adapter.wait_for_next_candle()

    def cleanup(self):
        # NEW: Cleanup via adapter
        self.adapter.logout()
```

### Benefits of Full Migration

1. **Single interface**: Only `adapter` - no confusion
2. **Consistent usage**: All operations go through adapter
3. **Easy to extend**: Add new broker = add new plugin
4. **Token-based**: No symbol construction needed

```
FULLY MIGRATED DATA FLOW (Clear):

┌─────────────────────────────────────────────────────────────────┐
│                         RUNNER.PY                                │
│                                                                  │
│   adapter = create_adapter(credentials, contract_manager=cm)    │
│                                                                  │
│   # ALL operations via adapter:                                 │
│   adapter.connect()                                             │
│   spot = adapter.get_spot_price()                               │
│   options = adapter.get_options_chain(expiry, strikes)          │
│   is_open = adapter.is_market_open()                            │
│   adapter.wait_for_next_candle()                                │
│   adapter.logout()                                              │
│                                                                  │
│   # Token lookups also via adapter (using contract_manager):    │
│   token = adapter._resolve_instrument("NIFTY", "CE", 23000, exp)│
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ZERODHA ADAPTER                             │
│                                                                  │
│   Internally uses:                                              │
│   • Kite Connect API for market data                            │
│   • ContractManager for token lookups                           │
│   • ZerodhaDataFeed for options chain                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## The Solution: Token-Based Instrument Resolution

### How Token Fetching Works

#### Step 1: Refresh Contracts Cache

```bash
python refresh_contracts.py --broker zerodha
```

This downloads ALL instruments from the broker and extracts NIFTY options:

```python
# refresh_contracts.py does this:

1. Download instruments from broker API
   Zerodha: kite.instruments("NFO")
   AngelOne: Download from OpenAPIScripMaster.json

2. Filter NIFTY options
   - instrumenttype == "OPTIDX"
   - name == "NIFTY"

3. Extract and save to contracts_cache.json:
   {
     "broker": "zerodha",
     "updated_at": "2026-01-19T08:30:00",
     "options": {
       "expiries": {
         "current_week": "2026-01-23",
         "next_week": "2026-01-30",
         "current_month": "2026-01-30"
       },
       "lot_size": 75,
       "contracts": [
         {
           "expiry": "2026-01-23",
           "strike": 23000,
           "option_type": "CE",
           "token": "17654274",           ← INSTRUMENT TOKEN
           "symbol": "NIFTY2612323000CE"  ← Broker symbol (reference)
         },
         {
           "expiry": "2026-01-23",
           "strike": 23000,
           "option_type": "PE",
           "token": "17654530",
           "symbol": "NIFTY2612323000PE"
         },
         // ... hundreds more contracts
       ]
     }
   }
```

#### Step 2: ContractManager Loads Cache

```python
# paper_trading/core/contract_manager.py

class ContractManager:
    def __init__(self):
        # Load from universal cache
        self.cache = self._load_cache("contracts_cache.json")

    def get_option_contract(self, expiry, strike, option_type):
        """
        Look up contract by standard params - returns token + symbol

        Args:
            expiry: "2026-01-23" (standard YYYY-MM-DD format)
            strike: 23000 (integer)
            option_type: "CE" or "PE"

        Returns:
            {"token": "17654274", "symbol": "NIFTY2612323000CE"}
        """
        for contract in self.cache['options']['contracts']:
            if (contract['expiry'] == expiry and
                contract['strike'] == strike and
                contract['option_type'] == option_type):
                return {
                    'token': contract['token'],
                    'symbol': contract['symbol']
                }
        return None

    def get_instrument_token(self, expiry, strike, option_type):
        """Convenience method - returns just the token"""
        contract = self.get_option_contract(expiry, strike, option_type)
        return contract['token'] if contract else None

    def has_instrument_tokens(self):
        """Check if cache has tokens (vs just symbols)"""
        contracts = self.cache.get('options', {}).get('contracts', [])
        if contracts:
            return 'token' in contracts[0]
        return False
```

#### Step 3: Adapter Uses Tokens for API Calls

```python
# paper_trading/brokers/adapter/plugins/zerodha.py

class ZerodhaAdapter(BrokerAdapter):

    def get_ltp(self, underlying, option_type, strike, expiry):
        """Get LTP using token-based lookup"""

        # Step 1: Resolve to token (NOT symbol construction!)
        contract = self._resolve_instrument(underlying, option_type, strike, expiry)
        # contract = {"token": "17654274", "symbol": "NIFTY2612323000CE"}

        if not contract:
            return None

        token = contract.get('token')

        # Step 2: Use token for API call
        if token:
            # Token-based quote (preferred - numeric token)
            data = self._kite.quote([f"NFO:{int(token)}"])
            key = f"NFO:{int(token)}"
            if key in data:
                return data[key].get('last_price')

        # Fallback: symbol-based (if no token)
        symbol = contract.get('symbol')
        if symbol:
            data = self._kite.ltp([f"NFO:{symbol}"])
            key = f"NFO:{symbol}"
            if key in data:
                return data[key].get('last_price')

        return None

    def _resolve_instrument(self, underlying, option_type, strike, expiry):
        """
        Resolve standard params to instrument token.
        Uses ContractManager - NO symbol construction!
        """
        if not self.contract_manager:
            return None

        if option_type in ('CE', 'PE'):
            return self.contract_manager.get_option_contract(expiry, strike, option_type)

        return None
```

### Token Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        TOKEN-BASED RESOLUTION                           │
└─────────────────────────────────────────────────────────────────────────┘

STANDARD INPUT (same for all brokers):
┌─────────────────────────────────────────────────────────────────────────┐
│  underlying="NIFTY", option_type="CE", strike=23000, expiry="2026-01-23"│
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      CONTRACT MANAGER                                    │
│                                                                         │
│  contract_manager.get_option_contract("2026-01-23", 23000, "CE")       │
│                                                                         │
│  Looks up in contracts_cache.json:                                      │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ {                                                                │   │
│  │   "expiry": "2026-01-23",                                       │   │
│  │   "strike": 23000,                                              │   │
│  │   "option_type": "CE",                                          │   │
│  │   "token": "17654274",        ← THIS IS WHAT WE NEED            │   │
│  │   "symbol": "NIFTY2612323000CE"                                 │   │
│  │ }                                                                │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           BROKER API CALL                                │
│                                                                         │
│  Zerodha:  kite.quote(["NFO:17654274"])                                │
│  AngelOne: smart_api.ltpData("NFO", symbol, "48756")                   │
│                                                                         │
│  Token works regardless of symbol format changes!                       │
└─────────────────────────────────────────────────────────────────────────┘
```

### Why Tokens Are Better

| Aspect | Symbol Construction | Token Lookup |
|--------|---------------------|--------------|
| Format changes | Breaks when broker updates | Never breaks |
| Weekly vs Monthly | Different formats | Same lookup |
| New broker | Write new construction code | Just cache tokens |
| Debugging | "Why is symbol wrong?" | Token is numeric ID |
| Maintenance | High - format edge cases | Low - just cache refresh |

---

## File Changes Summary

### Files Modified in Migration

| File | Change |
|------|--------|
| `paper_trading/runner.py` | Removed `broker_api`, uses only `adapter` |
| `paper_trading/brokers/adapter/base.py` | Added `logout()`, `load_instruments()`, `get_options_chain()` |
| `paper_trading/brokers/adapter/plugins/zerodha.py` | Added `logout()`, `get_next_expiry()` |
| `paper_trading/brokers/adapter/plugins/angelone.py` | Added `logout()`, `get_next_expiry()` |
| `paper_trading/brokers/adapter/plugins/paper.py` | Added `logout()`, `get_next_expiry()` |
| `BROKER_ADAPTER.md` | Updated to reflect full migration |

### Files Now Deprecated (Not Used)

| File | Status |
|------|--------|
| `paper_trading/brokers/base.py` | DEPRECATED - BrokerInterface not used |
| `paper_trading/brokers/zerodha.py` | DEPRECATED - ZerodhaBroker not used |
| `paper_trading/brokers/angelone.py` | DEPRECATED - AngelOneBroker not used |
| `paper_trading/utils/factory.py` | DEPRECATED - `create_broker()` not used |

### Files That Power the New System

| File | Purpose |
|------|---------|
| `contracts_cache.json` | Token cache (refreshed by cronjob) |
| `refresh_contracts.py` | Fetches tokens from broker, updates cache |
| `paper_trading/core/contract_manager.py` | Loads cache, provides token lookups |
| `paper_trading/brokers/adapter/factory.py` | `create_adapter()` factory |
| `paper_trading/brokers/adapter/plugins/*.py` | Broker-specific implementations |

---

## How to Use the New System

### 1. Refresh Contracts Cache

```bash
# Run once daily (or via cronjob before market open)
python refresh_contracts.py --broker zerodha
```

### 2. Run Paper Trading

```bash
# With explicit broker
python paper_trading/runner.py --broker zerodha

# Or auto-detect from credentials
python paper_trading/runner.py
```

### 3. Use in Strategy Code

```python
# Strategy receives adapter - uses standard params everywhere
class MyStrategy:
    def __init__(self, adapter, contract_manager):
        self.adapter = adapter
        self.contract_manager = contract_manager

    def get_option_ltp(self, strike, option_type, expiry):
        # Method 1: Via adapter (standard params)
        ltp = self.adapter.get_ltp("NIFTY", option_type, strike, expiry)

        # Method 2: Get token directly if needed
        token = self.contract_manager.get_instrument_token(expiry, strike, option_type)

        return ltp
```

### 4. Switch Brokers (Zero Code Changes)

```bash
# Switch to AngelOne - just change the command
python paper_trading/runner.py --broker angelone

# Strategy code stays EXACTLY the same!
# Only the credentials file changes.
```

---

## Comparison: All Three Stages

| Aspect | Stage 1 (Dec 2025) | Stage 2 (Hybrid) | Stage 3 (Full Migration) |
|--------|-------------------|------------------|--------------------------|
| **Primary Interface** | `broker_api` only | `broker_api` + `adapter` | `adapter` only |
| **Factory** | `create_broker()` | Both factories | `create_adapter()` |
| **Market Data** | `broker_api.get_spot_price()` | `broker_api.get_spot_price()` | `adapter.get_spot_price()` |
| **Options Chain** | `broker_api.get_options_chain()` | `broker_api.get_options_chain()` | `adapter.get_options_chain()` |
| **Token Lookups** | None | `adapter._resolve_instrument()` | `adapter._resolve_instrument()` |
| **Contract Manager** | None | Available | Fully integrated |
| **Symbol Resolution** | Broker-specific | Token-based (partial) | Token-based (full) |
| **Add New Broker** | New class + factory update | Complex | Add plugin + register |
| **Code Clarity** | Simple but limited | Confusing | Clean and unified |

### Evolution Timeline

```
Dec 2025                     Early Jan 2026                   Jan 2026
────────────────────────────────────────────────────────────────────────►

STAGE 1: INITIAL             STAGE 2: HYBRID                  STAGE 3: FULL
│                            │                                │
│  broker_api only           │  broker_api (market data)      │  adapter only
│  No tokens                 │  adapter (token lookups)       │  Token-based
│  No contract_manager       │  contract_manager added        │  Fully integrated
│                            │  Connection sharing hack       │  Clean architecture
└────────────────────────────┴────────────────────────────────┴──────────────────

Files Used:                  Files Used:                      Files Used:
├── brokers/base.py ✓        ├── brokers/base.py ✓            ├── brokers/base.py ✗
├── brokers/zerodha.py ✓     ├── brokers/zerodha.py ✓         ├── brokers/zerodha.py ✗
├── utils/factory.py ✓       ├── utils/factory.py ✓           ├── utils/factory.py ✗
                             ├── brokers/adapter/ ✓           ├── brokers/adapter/ ✓
                             └── core/contract_manager.py ✓   └── core/contract_manager.py ✓

✓ = Used    ✗ = Deprecated
```

---

## Summary

| Stage | Interface | Token Support | Complexity |
|-------|-----------|---------------|------------|
| Stage 1 (Initial) | `broker_api` only | None | Simple but limited |
| Stage 2 (Hybrid) | Both `broker_api` + `adapter` | Partial | Confusing |
| Stage 3 (Full) | `adapter` only | Full | Clean and unified |

**The token-based system ensures that your trading code never breaks due to broker symbol format changes. You simply refresh the cache, and the tokens handle the rest.**

### Key Takeaways

1. **Stage 1** was simple but couldn't handle symbol nomenclature differences between brokers
2. **Stage 2** added the adapter but created confusion by having two interfaces
3. **Stage 3** completes the migration - single `adapter` interface handles everything
4. **Token-based lookups** eliminate symbol construction bugs forever
5. **Adding a new broker** is now just: create plugin file + register in factory
