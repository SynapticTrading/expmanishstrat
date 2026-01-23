# Broker Adapter Migration - Complete Documentation

## Overview

This document describes the complete migration from a broker-specific architecture to a unified **Broker Adapter Architecture** with **Instrument Token Resolution**.

---

## Part 1: What Existed Before Migration

### Previous Architecture

```
paper_trading/
├── brokers/
│   ├── base.py              # BrokerInterface (abstract class)
│   ├── zerodha.py           # ZerodhaBroker (implements BrokerInterface)
│   ├── angelone.py          # AngelOneBroker (implements BrokerInterface)
│   └── __init__.py
├── utils/
│   └── factory.py           # create_broker() - created ZerodhaBroker/AngelOneBroker
├── core/
│   ├── strategy.py          # IntradayMomentumOIPaper
│   ├── broker.py            # PaperBroker (simulated order execution)
│   ├── contract_manager.py  # Expiry dates only, NO tokens
│   └── state_manager.py
├── legacy/
│   ├── zerodha_connection.py
│   ├── zerodha_data_feed.py
│   └── angelone_connection.py
└── runner.py                # Used broker_api (BrokerInterface)
```

### Previous Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         RUNNER.PY                                │
│                                                                  │
│   broker_api = create_broker(credentials)  ← ZerodhaBroker      │
│                                                                  │
│   # All broker calls went through broker_api:                   │
│   spot = broker_api.get_spot_price()                            │
│   options = broker_api.get_options_chain(expiry, strikes)       │
│   is_open = broker_api.is_market_open()                         │
│   broker_api.wait_for_next_candle()                             │
│   broker_api.logout()                                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BROKER INTERFACE                              │
│               (paper_trading/brokers/base.py)                   │
│                                                                  │
│   class BrokerInterface(ABC):                                   │
│       connect()                                                  │
│       get_spot_price()                                          │
│       get_ltp(instrument_token)                                 │
│       get_quote(instrument_token)                               │
│       get_historical_data(...)                                  │
│       get_instruments(exchange)                                 │
│       get_options_chain(expiry, strikes)                        │
│       logout()                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┴─────────────────────┐
        ▼                                           ▼
┌──────────────────┐                    ┌──────────────────┐
│  ZerodhaBroker   │                    │  AngelOneBroker  │
│  (zerodha.py)    │                    │  (angelone.py)   │
│                  │                    │                  │
│  Uses:           │                    │  Uses:           │
│  - ZerodhaConn   │                    │  - AngelOneConn  │
│  - ZerodhaFeed   │                    │  - SmartAPI      │
└──────────────────┘                    └──────────────────┘
```

### Previous Contract Cache Structure

```json
{
  "timestamp": "2026-01-19T...",
  "symbol": "NIFTY",
  "exchange": "NFO",
  "futures": {
    "contracts": [...],
    "mapping": {"current_month": {...}}
  },
  "options": {
    "expiry_dates": ["2026-01-23", "2026-01-30", ...],
    "mapping": {"current_week": "2026-01-23", ...},
    "strikes": {"min": 20000, "max": 26000, "step": 50},
    "lot_size": 75
    // NO INSTRUMENT TOKENS!
  }
}
```

### Problems with Previous Architecture

1. **Broker-Specific Code Scattered** - Strategy/runner had to know about broker differences
2. **No Token Resolution** - Had to construct symbols manually (error-prone)
3. **Different Symbol Formats** - Zerodha: `NIFTY2612323000CE`, AngelOne: different format
4. **Hard to Add Brokers** - Each new broker required changes in multiple files
5. **No Unified Interface** - `BrokerInterface` was too low-level

---

## Part 2: The Migration Plan

### Goals

1. Create a **Broker Adapter** layer that strategies use exclusively
2. Implement **Token-Based Resolution** via ContractManager
3. Make strategies **completely broker-agnostic**
4. Centralize all broker-specific logic in adapter plugins

### Implementation Tasks (Completed)

| # | Task | File(s) | Status |
|---|------|---------|--------|
| 1 | Add instrument tokens to cache | `refresh_contracts.py` | ✅ |
| 2 | Add token lookup methods | `contract_manager.py` | ✅ |
| 3 | Create adapter types | `brokers/adapter/types.py` | ✅ |
| 4 | Create adapter base class | `brokers/adapter/base.py` | ✅ |
| 5 | Create adapter factory | `brokers/adapter/factory.py` | ✅ |
| 6 | Create Zerodha adapter | `brokers/adapter/plugins/zerodha.py` | ✅ |
| 7 | Create AngelOne adapter | `brokers/adapter/plugins/angelone.py` | ✅ |
| 8 | Create Paper adapter | `brokers/adapter/plugins/paper.py` | ✅ |
| 9 | Create package exports | `brokers/adapter/__init__.py` | ✅ |
| 10 | Update strategy | `core/strategy.py` | ✅ |
| 11 | Fully migrate runner | `runner.py` | ✅ |

---

## Part 3: Current Architecture (Post-Migration)

### New Directory Structure

```
paper_trading/
├── brokers/
│   ├── adapter/                    # NEW - Primary interface
│   │   ├── __init__.py             # Package exports
│   │   ├── types.py                # Standard enums & dataclasses
│   │   ├── base.py                 # BrokerAdapter ABC
│   │   ├── factory.py              # create_adapter()
│   │   └── plugins/
│   │       ├── __init__.py
│   │       ├── zerodha.py          # ZerodhaAdapter
│   │       ├── angelone.py         # AngelOneAdapter
│   │       └── paper.py            # PaperAdapter
│   │
│   ├── base.py                     # DEPRECATED - BrokerInterface
│   ├── zerodha.py                  # DEPRECATED - ZerodhaBroker
│   ├── angelone.py                 # DEPRECATED - AngelOneBroker
│   └── __init__.py
│
├── core/
│   ├── strategy.py                 # Uses adapter for token lookups
│   ├── broker.py                   # PaperBroker (unchanged)
│   ├── contract_manager.py         # UPDATED - Token lookup methods
│   └── state_manager.py
│
├── utils/
│   └── factory.py                  # DEPRECATED - create_broker()
│
└── runner.py                       # FULLY MIGRATED - Uses adapter only
```

### New Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         RUNNER.PY                                │
│                                                                  │
│   adapter = create_adapter(credentials, contract_manager=cm)    │
│   adapter.connect()                                             │
│                                                                  │
│   # ALL broker calls go through adapter:                        │
│   spot = adapter.get_spot_price()                               │
│   options = adapter.get_options_chain(expiry, strikes)          │
│   is_open = adapter.is_market_open()                            │
│   adapter.wait_for_next_candle()                                │
│   adapter.logout()                                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BROKER ADAPTER                              │
│               (paper_trading/brokers/adapter/)                  │
│                                                                  │
│   class BrokerAdapter(ABC):                                     │
│       # Connection                                              │
│       connect() → bool                                          │
│       disconnect() → None                                       │
│       logout() → None                                           │
│       is_connected() → bool                                     │
│       broker_name → str                                         │
│                                                                  │
│       # Market Data (STANDARD params - broker-agnostic)         │
│       get_spot_price(underlying) → float                        │
│       get_ltp(underlying, opt_type, strike, expiry) → float    │
│       get_quote(underlying, opt_type, strike, expiry) → Quote  │
│       get_option_chain(underlying, expiry, strikes) → DataFrame│
│       get_options_chain(expiry, strikes) → DataFrame           │
│                                                                  │
│       # Orders (for live trading)                               │
│       place_order(OrderRequest) → OrderResponse                 │
│       modify_order(order_id, changes) → OrderResponse           │
│       cancel_order(order_id) → OrderResponse                    │
│                                                                  │
│       # Positions & Account                                     │
│       get_positions() → List[Position]                          │
│       get_holdings() → List[Position]                           │
│       get_funds() → Funds                                       │
│                                                                  │
│       # Utilities                                               │
│       is_market_open() → bool                                   │
│       load_instruments() → bool                                 │
│       get_next_expiry() → str                                   │
│       wait_for_next_candle(interval) → None                     │
│                                                                  │
│       # INTERNAL - Token Resolution                             │
│       _resolve_instrument(underlying, opt_type, strike, expiry) │
│           → Uses ContractManager for token lookup               │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│ ZerodhaAdapter│      │AngelOneAdapter│     │ PaperAdapter │
│              │      │              │      │              │
│ ORDER_TYPE:  │      │ ORDER_TYPE:  │      │ Simulated    │
│ SL → "SL"    │      │ SL → "STOP.."│      │ Uses real    │
│              │      │              │      │ data adapter │
│ PRODUCT:     │      │ PRODUCT:     │      │              │
│ MIS/CNC/NRML │      │ INTRADAY/... │      │              │
└──────────────┘      └──────────────┘      └──────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
   KiteConnect            SmartAPI            (delegates)
```

### New Contract Cache Structure

```json
{
  "timestamp": "2026-01-19T...",
  "symbol": "NIFTY",
  "exchange": "NFO",
  "futures": {
    "contracts": [...],
    "mapping": {"current_month": {...}}
  },
  "options": {
    "expiry_dates": ["2026-01-23", "2026-01-30", ...],
    "mapping": {"current_week": "2026-01-23", ...},
    "strikes": {"min": 20000, "max": 26000, "step": 50},
    "lot_size": 75,
    "instruments": {                          // NEW!
      "2026-01-23": {
        "23000": {
          "CE": {"token": "123456", "symbol": "NIFTY2612323000CE"},
          "PE": {"token": "123457", "symbol": "NIFTY2612323000PE"}
        },
        "23050": {
          "CE": {"token": "123458", "symbol": "NIFTY2612323050CE"},
          "PE": {"token": "123459", "symbol": "NIFTY2612323050PE"}
        }
      }
    }
  }
}
```

### ContractManager New Methods

```python
class ContractManager:
    # EXISTING methods
    get_options_expiry(expiry_type) → str
    get_all_options_expiry_dates() → List[str]
    get_options_lot_size() → int
    get_atm_strike(spot_price) → int
    should_rollover_options(expiry_type, threshold) → bool

    # NEW methods for token resolution
    get_instrument_token(expiry, strike, option_type) → str
    get_option_contract(expiry, strike, option_type) → Dict
    batch_get_instrument_tokens(contracts) → Dict
    get_available_strikes_for_expiry(expiry) → List[int]
    has_instrument_tokens() → bool
```

---

## Part 4: Standard Types (Broker-Agnostic)

### Enums

```python
class Exchange(Enum):
    NSE = "NSE"
    NFO = "NFO"
    BSE = "BSE"
    MCX = "MCX"

class TransactionType(Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "SL"
    SL_M = "SL_M"

class ProductType(Enum):
    INTRADAY = "INTRADAY"
    DELIVERY = "DELIVERY"
    CARRYFORWARD = "CARRYFORWARD"

class OrderStatus(Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    COMPLETE = "COMPLETE"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
```

### Dataclasses

```python
@dataclass
class OrderRequest:
    underlying: str           # "NIFTY"
    option_type: str          # "CE" / "PE"
    strike: int               # 23000
    expiry: str               # "2026-01-23"
    exchange: Exchange
    transaction_type: TransactionType
    order_type: OrderType
    quantity: int
    price: Optional[float]
    trigger_price: Optional[float]
    product_type: ProductType

@dataclass
class OrderResponse:
    success: bool
    order_id: str
    status: OrderStatus
    message: str
    filled_quantity: int
    average_price: float

@dataclass
class Quote:
    ltp: float
    open: float
    high: float
    low: float
    close: float
    volume: int
    oi: int
    bid: float
    ask: float

@dataclass
class Position:
    underlying: str
    option_type: str
    strike: int
    expiry: str
    quantity: int
    avg_price: float
    ltp: float
    pnl: float

@dataclass
class Funds:
    available_cash: float
    used_margin: float
    available_margin: float
```

---

## Part 5: Broker-Specific Mappings

### Zerodha Adapter Mappings

```python
ORDER_TYPE_MAP = {
    OrderType.MARKET: "MARKET",
    OrderType.LIMIT: "LIMIT",
    OrderType.SL: "SL",
    OrderType.SL_M: "SL-M"
}

PRODUCT_MAP = {
    ProductType.INTRADAY: "MIS",
    ProductType.DELIVERY: "CNC",
    ProductType.CARRYFORWARD: "NRML"
}
```

### AngelOne Adapter Mappings

```python
ORDER_TYPE_MAP = {
    OrderType.MARKET: "MARKET",
    OrderType.LIMIT: "LIMIT",
    OrderType.SL: "STOPLOSS_LIMIT",
    OrderType.SL_M: "STOPLOSS_MARKET"
}

PRODUCT_MAP = {
    ProductType.INTRADAY: "INTRADAY",
    ProductType.DELIVERY: "DELIVERY",
    ProductType.CARRYFORWARD: "CARRYFORWARD"
}
```

---

## Part 6: How Token Resolution Works

### Before (Symbol Construction - Error Prone)

```python
# Old way - had to construct broker-specific symbols
def build_zerodha_symbol(underlying, strike, opt_type, expiry):
    # Complex logic to format: NIFTY2612323000CE
    expiry_code = ...  # Parse date, format as YYMDD
    return f"{underlying}{expiry_code}{strike}{opt_type}"

def build_angelone_symbol(underlying, strike, opt_type, expiry):
    # Different format for AngelOne
    return f"{underlying}..."
```

### After (Token Lookup - Reliable)

```python
# New way - adapter uses ContractManager
class ZerodhaAdapter(BrokerAdapter):
    def get_ltp(self, underlying, opt_type, strike, expiry):
        # Get contract from ContractManager
        contract = self._resolve_instrument(underlying, opt_type, strike, expiry)
        # contract = {'token': '123456', 'symbol': 'NIFTY2612323000CE'}

        # Use token for API call (most reliable)
        token = contract['token']
        return self._kite.quote([f"NFO:{token}"])[f"NFO:{token}"]['last_price']
```

### Resolution Chain

```
Strategy calls:
  adapter.get_ltp("NIFTY", "CE", 23000, "2026-01-23")
       │
       ▼
Adapter calls:
  self._resolve_instrument("NIFTY", "CE", 23000, "2026-01-23")
       │
       ▼
ContractManager looks up:
  self.options_instruments["2026-01-23"]["23000"]["CE"]
       │
       ▼
Returns:
  {"token": "123456", "symbol": "NIFTY2612323000CE"}
       │
       ▼
Adapter uses token for API call:
  self._kite.quote([123456])
```

---

## Part 7: Usage Examples

### Running Paper Trading

```bash
# Refresh cache first (to get tokens)
python refresh_contracts.py --broker zerodha

# Run paper trading (uses adapter)
python paper_trading/runner.py --broker zerodha
```

### Strategy Using Adapter

```python
class IntradayMomentumOIPaper:
    def __init__(self, config, broker, oi_analyzer, state_manager, contract_manager, adapter):
        self.adapter = adapter
        self.contract_manager = contract_manager

    def get_instrument_token(self, strike, option_type, expiry=None):
        """Get token for contract (uses ContractManager)"""
        if expiry is None:
            expiry = self.daily_expiry

        if self.contract_manager:
            return self.contract_manager.get_instrument_token(expiry, strike, option_type)

        if self.adapter:
            contract = self.adapter._resolve_instrument("NIFTY", option_type, strike, expiry)
            return contract.get('token') if contract else ""

        return ""
```

### Adding a New Broker

```python
# 1. Create paper_trading/brokers/adapter/plugins/newbroker.py
class NewBrokerAdapter(BrokerAdapter):
    broker_name = "newbroker"

    ORDER_TYPE_MAP = {
        OrderType.MARKET: "MKT",
        OrderType.LIMIT: "LMT",
        # ...
    }

    def connect(self) -> bool:
        # Connect to NewBroker API
        ...

    def get_ltp(self, underlying, opt_type, strike, expiry) -> float:
        contract = self._resolve_instrument(underlying, opt_type, strike, expiry)
        # Use NewBroker's API with token
        ...

    # Implement all abstract methods...

# 2. Register in factory.py
BROKER_REGISTRY['newbroker'] = NewBrokerAdapter

# 3. Use it
adapter = create_adapter(credentials, broker='newbroker')
```

---

## Part 8: Files Changed Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `refresh_contracts.py` | Modified | Added instrument token extraction for options |
| `paper_trading/core/contract_manager.py` | Modified | Added token lookup methods |
| `paper_trading/brokers/adapter/__init__.py` | Created | Package exports |
| `paper_trading/brokers/adapter/types.py` | Created | Standard enums & dataclasses |
| `paper_trading/brokers/adapter/base.py` | Created | BrokerAdapter abstract base class |
| `paper_trading/brokers/adapter/factory.py` | Created | create_adapter() factory |
| `paper_trading/brokers/adapter/plugins/__init__.py` | Created | Plugin exports |
| `paper_trading/brokers/adapter/plugins/zerodha.py` | Created | Zerodha adapter |
| `paper_trading/brokers/adapter/plugins/angelone.py` | Created | AngelOne adapter |
| `paper_trading/brokers/adapter/plugins/paper.py` | Created | Paper trading adapter |
| `paper_trading/core/strategy.py` | Modified | Added adapter param & helper methods |
| `paper_trading/runner.py` | Modified | Fully migrated to use adapter |

---

## Part 9: Deprecated Files

These files are **NO LONGER USED** but kept for reference:

| File | Status | Replacement |
|------|--------|-------------|
| `paper_trading/brokers/base.py` | Deprecated | `brokers/adapter/base.py` |
| `paper_trading/brokers/zerodha.py` | Deprecated | `brokers/adapter/plugins/zerodha.py` |
| `paper_trading/brokers/angelone.py` | Deprecated | `brokers/adapter/plugins/angelone.py` |
| `paper_trading/utils/factory.py` | Deprecated | `brokers/adapter/factory.py` |

---

## Part 10: Benefits Achieved

1. **Strategy is Broker-Agnostic** - Same code works with any broker
2. **No Symbol Construction** - Tokens are universal identifiers
3. **Easy to Add Brokers** - Just implement adapter plugin
4. **Centralized Broker Logic** - All mappings in one place per broker
5. **Testable** - Can mock adapter for unit tests
6. **Type Safety** - Standard enums and dataclasses
7. **Better Error Handling** - Consistent response formats
