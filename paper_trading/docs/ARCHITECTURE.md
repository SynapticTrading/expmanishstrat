# Paper Trading System - Clean Architecture

## Overview

The paper trading system has been reorganized into a clean, modular architecture with clear separation of concerns.

---

## Directory Structure

```
paper_trading/
│
├── runner.py                    # Main entry point (was: paper_trader.py)
├── README.md                    # Complete usage guide
├── ARCHITECTURE.md              # This file - architecture documentation
├── requirements.txt             # Python dependencies
├── .gitignore                  # Git ignore rules
│
├── brokers/                    # Broker implementations (abstraction layer)
│   ├── __init__.py             # Package initializer
│   ├── base.py                 # BrokerInterface (abstract base class)
│   ├── zerodha.py              # Zerodha Kite Connect implementation
│   └── angelone.py             # AngelOne SmartAPI implementation
│
├── core/                       # Core business logic
│   ├── __init__.py             # Package initializer
│   ├── broker.py               # PaperBroker - Order simulation (was: paper_broker.py)
│   ├── strategy.py             # Trading strategy (was: paper_strategy.py)
│   └── state_manager.py        # State persistence & crash recovery
│
├── utils/                      # Utility functions
│   ├── __init__.py             # Package initializer
│   └── factory.py              # BrokerFactory - Auto-detection (was: broker_factory.py)
│
├── config/                     # Configuration & credentials
│   ├── config.yaml             # Strategy configuration
│   ├── credentials_zerodha.txt           # Zerodha credentials (gitignored)
│   ├── credentials_angelone.txt          # AngelOne credentials (gitignored)
│   ├── credentials.template.txt          # Generic template
│   └── credentials_angelone.template.txt # AngelOne template
│
├── tests/                      # Test suite
│   ├── test_zerodha_connection.py  # Zerodha connection test
│   ├── test_connection.py          # AngelOne connection test
│   └── simple_test.py              # Simple end-to-end test
│
├── legacy/                     # Deprecated/old code (kept for reference)
│   ├── dual_loop_runner.py         # Old Zerodha-specific runner
│   ├── paper_runner.py             # Old simple runner
│   ├── zerodha_paper_runner.py     # Old Zerodha runner
│   ├── zerodha_connection.py       # Zerodha connection wrapper
│   ├── zerodha_data_feed.py        # Zerodha data fetcher
│   ├── angelone_connection.py      # AngelOne connection wrapper
│   ├── data_feed.py                # Old data feed
│   └── data_fetch_examples.py      # Data fetch examples
│
├── docs/                       # Documentation
│   ├── BROKER_SELECTION_AND_RECOVERY.md  # Broker & recovery guide
│   ├── DUAL_LOOP_EXPLAINED.md            # Why two loops
│   ├── FIXED_IMPLEMENTATION.md           # What was fixed
│   ├── IMPLEMENTATION_COMPLETE.md        # Implementation checklist
│   ├── IMPLEMENTATION_SUMMARY.md         # Summary
│   ├── QUICK_START.md                    # Quick start
│   ├── SETUP_GUIDE.md                    # Setup instructions
│   └── ZERODHA_SETUP.md                  # Zerodha setup
│
├── logs/                       # Trade logs (auto-created, gitignored)
│   └── trades_YYYYMMDD_HHMMSS.csv
│
└── state/                      # State persistence (auto-created, gitignored)
    └── trading_state_YYYYMMDD.json
```

---

## Module Responsibilities

### `runner.py` (Main Entry Point)
- **Purpose**: Universal paper trading runner
- **Responsibilities**:
  - Command-line argument parsing
  - Broker auto-detection and selection
  - Credentials loading
  - Component initialization
  - Crash recovery workflow
  - Main trading loop orchestration
- **Key Classes**: `UniversalPaperTrader`
- **Imports**:
  - `brokers` → via `utils.factory.create_broker()`
  - `core.broker` → `PaperBroker`
  - `core.strategy` → `IntradayMomentumOIPaper`
  - `core.state_manager` → `StateManager`

### `brokers/` (Broker Abstraction Layer)

#### `base.py`
- **Purpose**: Abstract base class for broker implementations
- **Key Classes**: `BrokerInterface` (ABC)
- **Methods**:
  - `connect()` - Connect to broker API
  - `get_spot_price()` - Get Nifty spot price
  - `get_ltp()` - Get Last Traded Price
  - `get_quote()` - Get full quote
  - `get_historical_data()` - Get candle data
  - `get_options_chain()` - Get options chain
  - `get_next_expiry()` - Get next expiry date
  - `is_market_open()` - Check market hours
  - `wait_for_next_candle()` - Wait for next candle
  - `logout()` - Disconnect from broker

#### `zerodha.py`
- **Purpose**: Zerodha Kite Connect implementation
- **Status**: ✅ Fully implemented
- **Key Classes**: `ZerodhaBroker(BrokerInterface)`
- **Dependencies**:
  - `legacy.zerodha_connection.ZerodhaConnection`
  - `legacy.zerodha_data_feed.ZerodhaDataFeed`
- **Features**: All features working (spot, LTP, historical, options chain, etc.)

#### `angelone.py`
- **Purpose**: AngelOne SmartAPI implementation
- **Status**: ⚠️ Partially implemented
- **Key Classes**: `AngelOneBroker(BrokerInterface)`
- **Dependencies**:
  - `legacy.angelone_connection.AngelOneConnection`
- **Features**: Core features work, options chain needs completion

### `core/` (Business Logic)

#### `broker.py`
- **Purpose**: Paper trading broker (order simulation)
- **Key Classes**: `PaperBroker`, `PaperPosition`
- **Responsibilities**:
  - Simulate order execution (no real money)
  - Track positions (entry, exit, P&L)
  - Calculate statistics (win rate, total P&L, ROI)
  - Provide position queries
- **Note**: This is NOT a real broker, it simulates trading in memory

#### `strategy.py`
- **Purpose**: Trading strategy implementation
- **Key Classes**: `IntradayMomentumOIPaper`
- **Strategy**: Same logic as backtest (`strategies/intraday_momentum_oi.py`)
- **Entry Logic**:
  - OI unwinding (option OI decreasing)
  - Price > VWAP
  - Strike based on max OI
  - 1 trade per day limit
- **Exit Logic** (4 stop losses):
  1. 25% initial stop loss
  2. 5% VWAP stop
  3. 10% OI reversal stop
  4. 10% trailing stop (after 10% profit)
  5. Mandatory EOD exit (2:50 PM)
- **Dependencies**: `core.broker.PaperBroker`, `src.oi_analyzer.OIAnalyzer`

#### `state_manager.py`
- **Purpose**: State persistence and crash recovery
- **Key Classes**: `StateManager`
- **Features**:
  - JSON state files (one per day)
  - IST timestamps (pytz)
  - Automatic saves (after every change)
  - Crash detection (`can_recover()`)
  - Recovery info (`get_recovery_info()`)
  - Session resumption (`resume_session()`)
- **State Format**: Matches `TRADING_SYSTEM_QUICK_GUIDE.md` exactly
- **File Location**: `state/trading_state_YYYYMMDD.json`

### `utils/` (Utilities)

#### `factory.py`
- **Purpose**: Broker factory with auto-detection
- **Key Classes**: `BrokerFactory`
- **Key Functions**: `create_broker(credentials, broker_type=None)`
- **Features**:
  - Auto-detect broker from credentials format
  - Create appropriate broker instance
  - Validate credentials
- **Detection Logic**:
  - Zerodha: Has `api_secret` and `user_id`
  - AngelOne: Has `username` (not `user_id`)

### `config/` (Configuration)

- **config.yaml**: Strategy parameters
  - Position sizing (initial capital, lot size)
  - Entry conditions (strikes, VWAP)
  - Stop losses (percentages, trailing)
  - Timing (market hours, EOD window)

- **credentials_zerodha.txt**: Zerodha credentials
  ```
  api_key = ...
  api_secret = ...
  user_id = ...
  user_password = ...
  totp_key = ...
  ```

- **credentials_angelone.txt**: AngelOne credentials
  ```
  api_key = ...
  username = ...
  password = ...
  totp_token = ...
  ```

### `tests/` (Testing)

- **test_zerodha_connection.py**: Test Zerodha connection
- **test_connection.py**: Test AngelOne connection
- **simple_test.py**: Simple end-to-end test

### `legacy/` (Deprecated Code)

Old implementations kept for reference:
- `dual_loop_runner.py` - Old Zerodha-specific runner (replaced by `runner.py`)
- `paper_runner.py` - Old simple runner
- `zerodha_connection.py` - Still used by `brokers/zerodha.py`
- `zerodha_data_feed.py` - Still used by `brokers/zerodha.py`
- `angelone_connection.py` - Still used by `brokers/angelone.py`
- Other old files

### `docs/` (Documentation)

Complete documentation suite - see individual files for details.

---

## Import Structure

### Top-Level Imports (runner.py)
```python
from paper_trading.utils.factory import create_broker
from paper_trading.core.broker import PaperBroker
from paper_trading.core.strategy import IntradayMomentumOIPaper
from paper_trading.core.state_manager import StateManager
from paper_trading.legacy.zerodha_connection import load_credentials_from_file
```

### Broker Factory (utils/factory.py)
```python
from paper_trading.brokers.zerodha import ZerodhaBroker
from paper_trading.brokers.angelone import AngelOneBroker
```

### Broker Implementations (brokers/zerodha.py, brokers/angelone.py)
```python
from paper_trading.brokers.base import BrokerInterface
from paper_trading.legacy.zerodha_connection import ZerodhaConnection
from paper_trading.legacy.zerodha_data_feed import ZerodhaDataFeed
# (or angelone_connection for AngelOne)
```

### Strategy (core/strategy.py)
```python
from paper_trading.core.broker import PaperBroker
from src.oi_analyzer import OIAnalyzer
```

---

## Data Flow

### Startup Flow
1. **runner.py**: Parse args, load credentials
2. **utils/factory.py**: Auto-detect broker type, create broker instance
3. **brokers/zerodha.py** (or angelone.py): Connect to broker API
4. **core/state_manager.py**: Check for crash recovery
5. **core/broker.py**: Initialize paper broker (simulated orders)
6. **core/strategy.py**: Initialize strategy
7. **runner.py**: Start dual-loop trading

### Trading Flow (Normal Operation)

#### Loop 1: Strategy Loop (5-min)
1. **runner.py**: Wait for next 5-min candle
2. **brokers/zerodha.py**: Fetch spot price, options chain
3. **core/strategy.py**: Analyze OI + VWAP, make entry decision
4. **core/broker.py**: Execute simulated order (if entry signal)
5. **core/state_manager.py**: Save state to JSON

#### Loop 2: Exit Monitor Loop (1-min)
1. **runner.py**: Every 1 minute, check open positions
2. **brokers/zerodha.py**: Fetch current LTP for positions
3. **core/strategy.py**: Check 4 stop losses + EOD
4. **core/broker.py**: Execute simulated exit (if stop loss hit)
5. **core/state_manager.py**: Save state to JSON

### Crash Recovery Flow
1. **runner.py**: On startup, call `state_manager.can_recover()`
2. **core/state_manager.py**: Load today's state JSON
3. **core/state_manager.py**: Check for active positions
4. **runner.py**: Prompt user to resume or start fresh
5. If resume:
   - **core/state_manager.py**: Return recovery info (crash time, downtime, positions)
   - **runner.py**: Restore all components
   - **core/strategy.py**: Restore strategy state (direction, strike, VWAP)
   - **core/broker.py**: Restore positions (entry, stops, peak prices)
   - **runner.py**: Resume dual-loop from where it left off

---

## Design Principles

### 1. Separation of Concerns
- **Brokers**: Handle API communication (isolated per broker)
- **Core**: Business logic (broker-agnostic)
- **Utils**: Helper functions
- **Config**: All configuration centralized

### 2. Interface-Based Design
- `BrokerInterface` defines contract
- Each broker implements the interface
- Easy to add new brokers (just implement interface)

### 3. Dependency Inversion
- High-level modules (runner, strategy) depend on abstractions (BrokerInterface)
- Low-level modules (zerodha, angelone) implement abstractions
- Decoupling allows easy broker switching

### 4. Single Responsibility
- Each module has one clear purpose
- `broker.py` = order simulation
- `strategy.py` = trading logic
- `state_manager.py` = persistence
- `factory.py` = broker creation

### 5. State Persistence
- Single source of truth (state JSON)
- IST timestamps throughout
- Crash-safe writes (atomic operations)
- Human-readable format

### 6. Legacy Preservation
- Old code kept in `legacy/` for reference
- Still used by new implementations (zerodha_connection, etc.)
- Can be phased out gradually

---

## Key Features

### ✅ Multi-Broker Support
- Same command works for any broker
- Auto-detection from credentials
- Easy to switch (just change credentials file)

### ✅ Crash Recovery
- Auto-detection on restart
- User confirmation prompt
- Full state restoration (positions, stops, P&L)
- Downtime tracking

### ✅ State Persistence
- JSON format (human-readable)
- IST timestamps (pytz)
- Per-day files
- Crash-safe

### ✅ Dual-Loop Architecture
- Loop 1: 5-min strategy (entry decisions)
- Loop 2: 1-min LTP (exit monitoring)
- Threading for parallel execution

### ✅ Clean Architecture
- Modular design
- Clear separation
- Easy to extend
- Well-documented

---

## Usage

### Basic
```bash
python runner.py
```

### With Broker Selection
```bash
python runner.py --broker zerodha
python runner.py --broker angelone
```

### With Custom Config
```bash
python runner.py --config config/config.yaml --credentials config/credentials_zerodha.txt
```

---

## Testing

```bash
# Test Zerodha connection
python tests/test_zerodha_connection.py

# Test AngelOne connection
python tests/test_connection.py

# Simple end-to-end test
python tests/simple_test.py
```

---

## Future Enhancements

### Short-term
1. Complete AngelOne options chain implementation
2. Add more comprehensive tests
3. Add logging configuration
4. Add performance monitoring

### Long-term
1. Add more brokers (ICICI, Upstox, etc.)
2. Web dashboard for monitoring
3. Backtesting integration
4. Alert system (Telegram, email)
5. Multi-strategy support

---

## Migration Notes

### From Old Structure to New

**Old File** → **New File**
- `paper_trader.py` → `runner.py`
- `broker_interface.py` → `brokers/base.py`
- `zerodha_broker.py` → `brokers/zerodha.py`
- `angelone_broker.py` → `brokers/angelone.py`
- `paper_broker.py` → `core/broker.py`
- `paper_strategy.py` → `core/strategy.py`
- `state_manager.py` → `core/state_manager.py`
- `broker_factory.py` → `utils/factory.py`
- `config.yaml` → `config/config.yaml`
- `credentials_*.txt` → `config/credentials_*.txt`
- `*.md` → `docs/*.md`
- Old runners → `legacy/`

### Import Changes
All imports updated to reflect new structure. See "Import Structure" section above.

---

## Summary

✅ **Clean Architecture**: Proper folder structure with clear separation
✅ **Multi-Broker**: Zerodha (full), AngelOne (partial)
✅ **Crash Recovery**: Automatic detection and resumption
✅ **State Persistence**: JSON format, IST timestamps
✅ **Dual-Loop**: 5-min strategy + 1-min LTP monitoring
✅ **Well-Documented**: Complete docs in `docs/`
✅ **Easy to Use**: Single command to run
✅ **Easy to Extend**: Interface-based design

---

**Built**: 2025-12-26
**Status**: Production-ready for Zerodha, Partial for AngelOne
**Maintained**: Active development
