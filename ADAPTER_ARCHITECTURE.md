# Adapter Architecture: Token-Based, Broker-Agnostic Trading System

## System Overview

The paper trading system uses a **token-based, broker-agnostic architecture** that allows trading strategies to work seamlessly across multiple brokers (Zerodha, AngelOne, etc.) without modification.

## Core Principles

### 1. Token-Based Instrument Identification
- NSE/NFO assigns each instrument a unique **exchange token**
- Cache stores **dual token formats** to support different broker APIs:
  - **AngelOne**: Uses NSE/NFO exchange tokens directly (e.g., "47603")
  - **Zerodha**: Uses Zerodha's internal instrument tokens (e.g., "12186370")
- Both token formats reference the same instrument but in broker-specific representations
- Stored centrally in `contracts_cache.json` at the repository root
- Eliminates runtime symbol construction and broker-specific naming inconsistencies

### 2. Broker Abstraction
- Strategies interact through **BrokerAdapter interface** - never directly with broker APIs
- Each broker has its own adapter plugin that translates standard calls to broker-specific formats
- Automatic broker detection from credentials or explicit selection

## Architecture Components

### ContractManager
**Purpose**: Central token registry and contract metadata provider

**Key Methods**:
- `get_options_expiry()` - Returns expiry dates mapped by type (current_week, next_week, etc.)
- `get_option_contract()` - Resolves (expiry, strike, option_type) to {token, symbol}
- `check_and_reload_if_updated()` - Auto-detects cache updates from refresh cronjob
- `should_rollover_options()` - Expiry proximity warnings

**Data Source**: Reads from universal `contracts_cache.json` maintained by `refresh_contracts.py`

### BrokerAdapter (Base Class)
**Purpose**: Abstract interface defining all trading operations

**Core Methods**:
- **Market Data**: `get_ltp()`, `get_quote()`, `get_option_chain()`, `get_spot_price()`
- **Orders**: `place_order()`, `modify_order()`, `cancel_order()`, `get_orders()`
- **Positions**: `get_positions()`, `get_holdings()`, `get_funds()`
- **Market Status**: `is_market_open()`, `get_next_expiry()`
- **Connection**: `connect()`, `disconnect()`, `logout()`

**Standard Parameters**: All methods use platform-agnostic params (underlying, option_type, strike, expiry) - NO broker-specific symbols

### Adapter Factory
**Purpose**: Automatic adapter creation and broker detection

**Capabilities**:
- Auto-detects broker type from credential structure (api_secret → Zerodha, username → AngelOne)
- Registry pattern for extensibility - new brokers can be registered dynamically
- Single entry point via `create_adapter()` function

### Broker Plugins (ZerodhaAdapter, AngelOneAdapter)
**Purpose**: Broker-specific implementations

**Responsibilities**:
- Translate standard adapter calls to broker API format
- Map order types, product types, and statuses between universal and broker-specific enums
- Handle broker authentication and connection lifecycle
- Use ContractManager tokens for 100% token-based API calls (no symbol fallback)

### Type Definitions
**Purpose**: Standardized data contracts

**Key Types**:
- `OrderRequest` / `OrderResponse` - Unified order structures
- `Quote`, `Position`, `Funds` - Market data and account information
- Enums: `OrderType`, `ProductType`, `OrderStatus`, `TransactionType` - Cross-broker constants

## Broker-Specific Token Mappings

The cache maintains **dual token formats** to support different broker APIs:

### AngelOne Token Format
- Uses **exchange tokens** directly from NSE/NFO
- Cache field: `"token": "47603"` (5-digit exchange token)
- API call: `getMarketData(exchangeTokens={"NFO": [token]})`
- Direct mapping - no conversion required

### Zerodha Token Format
- Uses **instrument tokens** (Zerodha's internal format)
- Cache field: `"zerodha_instrument_token": "12186370"` (8-digit instrument token)
- API call: `ltp([f"NFO:{instrument_token}"])`
- Zerodha-specific mapping maintained in cache

### Cache Structure Example
```
"25600": {
  "CE": {
    "token": "47603",                      # AngelOne uses this
    "zerodha_instrument_token": "12186370" # Zerodha uses this
  }
}
```

**Key Insight**: Both tokens represent the same instrument but in broker-specific formats. The cache stores both, enabling each adapter to retrieve its required format without runtime conversion.

## Token Resolution Flow

1. **Strategy Request**: Requests data using standard params (e.g., "NIFTY", "CE", 23000, "2026-01-20")
2. **Adapter Resolution**: Calls `_resolve_instrument()` internally
3. **ContractManager Lookup**: Returns contract dict with both token formats
4. **Broker-Specific Selection**:
   - AngelOneAdapter extracts `contract['token']`
   - ZerodhaAdapter extracts `contract['zerodha_instrument_token']`
5. **Broker API Call**: Adapter uses appropriate token format (no conversion needed)
6. **Response Translation**: Adapter translates broker response to standard format
7. **Strategy Receives**: Gets normalized data - broker token formats hidden

## Broker Agnostic Verification

**Evidence of Broker Independence**:
- Strategies import only `BrokerAdapter` - never broker-specific classes
- Zero broker-specific code in strategy files (runner.py, strategy.py)
- Credential-based auto-detection enables switch via config file change
- Same `contracts_cache.json` used across all brokers - single source of truth
- Adapter plugins isolated in `/adapter/plugins/` directory

**Switching Brokers**: Change credentials file or pass `--broker` flag - no code modification required

## Token-Based System Verification

**Confirmed Token-Only Operations**:
- ContractManager reads universal exchange tokens from cache JSON
- Adapters resolve instruments to tokens before API calls
- No runtime symbol construction - all symbols pre-cached
- Token mismatches would break the system - forces cache maintenance discipline

**Cache Structure**:
- `timestamp` - Cache generation time
- `source_broker` - Broker used for token refresh
- `options.strikes` - Full strike-token mappings for all expiries
- `options.mapping` - Dynamic expiry mappings (current_week, next_week, etc.)
- `options.instruments` - Nested dict: {expiry: {strike: {CE/PE: {token, zerodha_instrument_token}}}}
  - `token` field: NSE/NFO exchange token (used by AngelOne)
  - `zerodha_instrument_token` field: Zerodha's internal token format (used by Zerodha)

## Key Integration Points

**In UniversalPaperTrader (runner.py)**:
1. Initialize ContractManager with universal cache
2. Create adapter via factory with ContractManager injection
3. Connect adapter to broker
4. Pass adapter to strategy for all market operations
5. Contract monitor thread auto-reloads cache when updated

**State Persistence**:
- Trading state includes broker name for multi-broker tracking
- Crash recovery system restores positions and strategy state
- Global trade limit enforced across all brokers via cumulative CSV

## Benefits

**For Strategies**: Write once, run on any broker - complete portability
**For Maintenance**: Single cache file update affects all brokers simultaneously
**For Reliability**: Token-based lookups eliminate symbol string parsing errors
**For Extensibility**: Add new brokers by implementing adapter interface - no strategy changes needed
