# Adapter Test Suite

Comprehensive test suite for the broker adapter abstraction layer.

## Overview

This test suite validates the complete adapter system including:
- **Token-based contract resolution** from `contracts_cache.json`
- **Factory pattern** for adapter creation and broker auto-detection
- **Base adapter** functionality and abstract interface
- **Plugin implementations** for AngelOne and Zerodha
- **Order lifecycle** management
- **Market data** fetching using tokens (no symbols required)

## Test Structure

```
test_adapter/
├── __init__.py                   # Package initialization
├── conftest.py                   # Pytest fixtures and shared utilities
├── test_types.py                 # Tests for types and enums
├── test_base.py                  # Tests for base adapter class
├── test_factory.py               # Tests for factory pattern
├── test_integration.py           # End-to-end integration tests
├── plugins/
│   ├── __init__.py
│   ├── test_zerodha.py          # Zerodha adapter tests
│   └── test_angelone.py         # AngelOne adapter tests
└── README.md                     # This file
```

## Running Tests

### Run All Tests
```bash
pytest paper_trading/test_adapter/ -v
```

### Run Specific Test File
```bash
pytest paper_trading/test_adapter/test_types.py -v
```

### Run Tests by Category
```bash
# Base adapter tests
pytest paper_trading/test_adapter/test_base.py -v

# Factory tests
pytest paper_trading/test_adapter/test_factory.py -v

# Plugin tests
pytest paper_trading/test_adapter/plugins/ -v

# Integration tests
pytest paper_trading/test_adapter/test_integration.py -v
```

### Run with Coverage
```bash
pytest paper_trading/test_adapter/ --cov=paper_trading.brokers.adapter --cov-report=html
```

## Test Categories

### 1. Type Tests (`test_types.py`)
Tests for standard broker-agnostic types:
- ✅ Enum definitions (Exchange, OrderType, ProductType, etc.)
- ✅ OrderRequest creation and validation
- ✅ OrderResponse handling
- ✅ Quote, Position, Funds dataclasses
- ✅ InstrumentInfo structure

### 2. Base Adapter Tests (`test_base.py`)
Tests for base adapter functionality:
- ✅ Adapter initialization with/without ContractManager
- ✅ Connection lifecycle (connect, disconnect, is_connected)
- ✅ Instrument resolution using ContractManager
- ✅ Token-based lookups from cache
- ✅ Expiry date retrieval
- ✅ Utility methods (wait_for_next_candle)

### 3. Factory Tests (`test_factory.py`)
Tests for adapter factory pattern:
- ✅ Adapter creation with explicit broker name
- ✅ Auto-detection of broker from credentials
- ✅ Case-insensitive broker names
- ✅ Custom adapter registration
- ✅ Error handling for unknown brokers
- ✅ Registry management

### 4. Zerodha Plugin Tests (`plugins/test_zerodha.py`)
Tests for Zerodha adapter:
- ✅ Connection management
- ✅ Token-based LTP fetching using `zerodha_instrument_token`
- ✅ Quote fetching with tokens (no symbols)
- ✅ Order placement (MARKET, LIMIT, SL, SL_M)
- ✅ Product type mapping (INTRADAY→MIS, CARRYFORWARD→NRML)
- ✅ Order modification and cancellation
- ✅ Position and fund management
- ✅ Market status checks

### 5. AngelOne Plugin Tests (`plugins/test_angelone.py`)
Tests for AngelOne adapter:
- ✅ Connection management
- ✅ Token-only API calls (no symbols required)
- ✅ LTP and quote fetching using tokens
- ✅ Batch market data fetching
- ✅ Order placement with AngelOne-specific params
- ✅ Product type mapping (INTRADAY→INTRADAY, CARRYFORWARD→CARRYFORWARD)
- ✅ Stop-loss order types (STOPLOSS_LIMIT, STOPLOSS_MARKET)
- ✅ Market hours validation
- ✅ Error handling

### 6. Integration Tests (`test_integration.py`)
End-to-end workflow tests:
- ✅ Factory → Adapter → ContractManager → cache.json flow
- ✅ Complete order lifecycle (LTP check → place → check → cancel)
- ✅ Multi-broker scenarios
- ✅ Cache query mechanism without symbols
- ✅ All order types across brokers

## Key Test Features

### Token-Based Approach Testing

The tests validate that the system:
1. **Never constructs symbols manually** - all lookups use ContractManager
2. **Uses cached tokens** - `zerodha_instrument_token` for Zerodha, `token` for AngelOne
3. **Queries cache.json** - no runtime symbol generation
4. **Fails gracefully** - returns None when token missing, logs appropriate warnings

Example test:
```python
def test_get_ltp_uses_token_from_cache(self, adapter, mock_contract_manager):
    """LTP fetch uses zerodha_instrument_token from cache."""
    contract = {'zerodha_instrument_token': 12345678, 'strike': 25000}
    mock_contract_manager.get_option_contract.return_value = contract

    ltp = adapter.get_ltp('NIFTY', 'CE', 25000, '2026-02-26')

    # Verify token-based API call
    assert ltp == 150.50
    mock_kite_api.ltp.assert_called_with(['NFO:12345678'])
```

### Order Type Coverage

Tests validate all order types:
- **MARKET** - Immediate execution at market price
- **LIMIT** - Execution at specified price
- **SL** (Stop-Loss Limit) - Trigger + limit price
- **SL_M** (Stop-Loss Market) - Trigger only

For each type, tests verify:
- Correct broker-specific mapping
- Required parameters included
- Optional parameters handled properly

### Product Type Mapping

Tests verify broker-specific mappings:

| Standard Type   | Zerodha | AngelOne      |
|----------------|---------|---------------|
| INTRADAY       | MIS     | INTRADAY      |
| DELIVERY       | CNC     | DELIVERY      |
| CARRYFORWARD   | NRML    | CARRYFORWARD  |

### Error Handling

Tests cover:
- Missing contracts in cache
- Missing tokens in cache
- API connection failures
- Invalid broker names
- Missing credentials
- Market closed scenarios

## Fixtures

### `contracts_cache`
Loads real `contracts_cache.json` for testing with actual data structure.

### `mock_contract_manager`
Provides a mock ContractManager with realistic behavior:
- Returns contracts from cache
- Handles CE/PE lookups
- Provides expiry dates

### `mock_kite_api`
Mock Zerodha Kite API with realistic responses for:
- LTP, quotes, option chains
- Order placement, modification, cancellation
- Positions, margins, funds

### `mock_angelone_api`
Mock AngelOne SmartAPI with realistic responses for:
- Market data (LTP/FULL modes)
- Order management
- Position and fund queries

### `sample_option_contract`
Sample option contract from cache with all required fields.

### `sample_order_request`
Pre-configured OrderRequest for testing.

## Dependencies

Required packages:
```bash
pip install pytest pytest-cov pytest-mock
```

## Coverage Goals

Target coverage: **>90%**

Current coverage areas:
- ✅ Base adapter interface
- ✅ Factory pattern
- ✅ Type definitions
- ✅ Zerodha plugin
- ✅ AngelOne plugin
- ✅ Integration flows

## Writing New Tests

### Adding Tests for New Broker

1. Create `plugins/test_newbroker.py`
2. Test connection management
3. Test token-based lookups
4. Test order placement variations
5. Test broker-specific mappings
6. Add integration tests

### Test Template
```python
import pytest
from unittest.mock import Mock, patch

class TestNewBrokerAdapter:
    """Tests for NewBroker adapter."""

    @patch('path.to.BrokerConnection')
    def test_connect_success(self, mock_conn, credentials, mock_api):
        """Test successful connection."""
        # Setup mocks
        # Create adapter
        # Connect and verify
        pass

    def test_token_based_ltp(self, adapter, mock_cm, contract):
        """Test LTP uses token from cache."""
        # Setup contract with token
        # Fetch LTP
        # Verify token-based API call
        pass
```

## Best Practices

1. **Use fixtures** - Leverage conftest.py for common setup
2. **Mock external APIs** - Never call real broker APIs in tests
3. **Test token flow** - Always verify token-based lookups
4. **Test error paths** - Cover missing data, connection failures
5. **Descriptive names** - Test names should explain what's being tested
6. **Isolated tests** - Each test should be independent

## Troubleshooting

### `contracts_cache.json not found`
Run `python refresh_contracts.py --broker zerodha` to generate cache.

### Import errors
Ensure you're running from project root and PYTHONPATH is set.

### Mock issues
Check that mock return values match actual API response structure.

## Contributing

When adding new functionality:
1. Write tests first (TDD)
2. Ensure token-based approach is followed
3. Add integration tests for new workflows
4. Update this README with new test categories
5. Run full test suite before committing

## License

Same as parent project.
