# Integration Tests - Complete Guide

**Last Updated**: 2026-01-27

---

## 📁 **Test Organization**

### **Zerodha Tests**
- `test_zerodha_integration.py` - Main Zerodha integration tests (14 tests)

### **AngelOne Tests**
- `test_angelone_integration.py` - Main AngelOne integration tests (14 tests)
- `test_angelone_amo_limit.py` - Safe AMO limit order tests (3 tests)
- `test_angelone_cancel_amo.py` - Order cancellation tests (3 tests)

### **Utility Tests**
- `test_cancel_pending_orders.py` - Cancel all pending orders (cleanup utility)

### **Configuration**
- `conftest.py` - Pytest fixtures and test setup
- `test_credentials.yaml` - Broker credentials and test config
- `test_credentials.yaml.template` - Template for credentials

---

## 🔧 **How Tests Import and Use Adapters**

### **Architecture**

```
Test File
    ↓
conftest.py (fixtures)
    ↓
Broker Adapters (ZerodhaAdapter, AngelOneAdapter)
    ↓
Contract Manager (token lookups)
    ↓
Broker APIs (Zerodha/AngelOne)
```

### **Import Chain**

```python
# 1. Test imports types
from paper_trading.brokers.adapter.types import (
    OrderRequest, OrderType, TransactionType,
    Exchange, ProductType, OrderStatus
)

# 2. conftest.py imports adapters
from paper_trading.brokers.adapter.plugins.zerodha import ZerodhaAdapter
from paper_trading.brokers.adapter.plugins.angelone import AngelOneAdapter

# 3. conftest.py imports contract manager
from paper_trading.core.contract_manager import ContractManager

# 4. Fixtures create adapter instances
@pytest.fixture(scope="session")
def zerodha_adapter(zerodha_credentials, contract_manager):
    adapter = ZerodhaAdapter(zerodha_credentials, contract_manager)
    adapter.connect()
    yield adapter
    adapter.disconnect()
```

### **How Adapters Work**

#### **Zerodha: Pure Token-Based**
```python
# User provides simple parameters
order_request = OrderRequest(
    underlying='NIFTY',
    strike=25000,
    expiry='2026-01-27',
    option_type='CE',
    quantity=65,
    order_type=OrderType.LIMIT,
    price=150.0
)

# Adapter handles everything:
1. contract = contract_manager.get_option_contract(expiry, strike, option_type)
2. token = contract['zerodha_instrument_token']  # e.g., 15017218
3. Place order using token directly:
   kite.place_order(tradingsymbol=token, exchange='NFO', ...)

# No symbol construction needed!
```

#### **AngelOne: Token → Symbol Lookup**
```python
# User provides same simple parameters
order_request = OrderRequest(
    underlying='NIFTY',
    strike=25000,
    expiry='2026-01-27',
    option_type='CE',
    quantity=65,
    order_type=OrderType.LIMIT,
    price=150.0
)

# Adapter handles everything:
1. contract = contract_manager.get_option_contract(expiry, strike, option_type)
2. token = contract['token']  # e.g., '58661'
3. symbol = _get_symbol_from_token(token)  # Auto-lookup: '58661' → 'NIFTY27JAN2625000CE'
4. Place order with symbol + token:
   smart_api.placeOrder(tradingsymbol=symbol, symboltoken=token, ...)

# Symbol auto-looked up from token!
```

---

## 🚀 **Running Tests**

### **Prerequisites**

1. **From Project Root** (IMPORTANT!):
   ```bash
   cd /Users/Algo_Trading/manishsir_options
   ```

2. **Credentials Setup**:
   - Copy `test_credentials.yaml.template` to `test_credentials.yaml`
   - Fill in your broker credentials

3. **After Market Hours**:
   - Tests run after 3:30 PM (AMO orders only)

---

## 🖥️ **Output Modes**

### **Standard Mode** (Only pass/fail):
```bash
python3 -m pytest <test_file> -v
# Shows: ✅ PASSED or ❌ FAILED
```

### **Detailed Mode** (See all output - LTP, prices, order IDs, etc.):
```bash
python3 -m pytest <test_file> -v -s
# Shows: All print statements, logging output, API responses
```

### **Extra Verbose** (Debug everything):
```bash
python3 -m pytest <test_file> -vv -s --log-cli-level=DEBUG
# Shows: Everything including debug logs
```

**💡 Recommendation**: Always use `-s` flag to see:
- ✅ LTP values fetched
- ✅ Order IDs placed
- ✅ Strike prices used
- ✅ API responses
- ✅ Cancellation confirmations

---

## 📋 **Run Individual Tests**

### **Zerodha Tests (One by One)**

#### Authentication Tests
```bash
# TC_AUTH_01: Connect and Authenticate
python3 -m pytest paper_trading/tests/integration/test_zerodha_integration.py::TestZerodhaAuthentication::test_auth_01_connect_and_authenticate -v -s

# TC_AUTH_02: Get Profile (See profile details!)
python3 -m pytest paper_trading/tests/integration/test_zerodha_integration.py::TestZerodhaAuthentication::test_auth_02_get_profile -v -s

# TC_AUTH_03: Reconnection
python3 -m pytest paper_trading/tests/integration/test_zerodha_integration.py::TestZerodhaAuthentication::test_auth_03_reconnection -v -s
```

#### Market Data Tests
```bash
# TC_QUOTE_01: Get LTP (See actual LTP values!)
python3 -m pytest paper_trading/tests/integration/test_zerodha_integration.py::TestZerodhaMarketData::test_quote_01_get_ltp_single -v -s

# TC_QUOTE_02: Get Full Quote (See bid/ask, volume, OI!)
python3 -m pytest paper_trading/tests/integration/test_zerodha_integration.py::TestZerodhaMarketData::test_quote_02_get_full_quote_multiple -v -s

# TC_QUOTE_03: Historical Data (See candle data!)
python3 -m pytest paper_trading/tests/integration/test_zerodha_integration.py::TestZerodhaMarketData::test_quote_03_historical_data_1day -v -s

# Get Spot Price (See NIFTY spot price!)
python3 -m pytest paper_trading/tests/integration/test_zerodha_integration.py::TestZerodhaMarketData::test_get_spot_price -v -s
```

#### Position Tests
```bash
# TC_POS_01: Fetch Positions (See your positions!)
python3 -m pytest paper_trading/tests/integration/test_zerodha_integration.py::TestZerodhaPositions::test_pos_01_fetch_net_positions -v -s

# TC_POS_02: Fetch Holdings/Funds (See your funds!)
python3 -m pytest paper_trading/tests/integration/test_zerodha_integration.py::TestZerodhaPositions::test_pos_02_fetch_holdings_funds -v -s
```

#### Order Tests (Requires NFO Activation)
```bash
# TC_ORDER_01: Market Buy (See order ID and details!)
python3 -m pytest paper_trading/tests/integration/test_zerodha_integration.py::TestZerodhaOrdersAMO::test_order_01_place_amo_market_buy -v -s

# TC_ORDER_02: Limit Sell (See limit price and order status!)
python3 -m pytest paper_trading/tests/integration/test_zerodha_integration.py::TestZerodhaOrdersAMO::test_order_02_place_amo_limit_sell -v -s

# TC_ORDER_03: Invalid Symbol (See error message!)
python3 -m pytest paper_trading/tests/integration/test_zerodha_integration.py::TestZerodhaOrdersAMO::test_order_03_invalid_symbol -v -s

# TC_ORDER_04: Cancel Order (See cancellation confirmation!)
python3 -m pytest paper_trading/tests/integration/test_zerodha_integration.py::TestZerodhaOrdersAMO::test_order_04_cancel_amo_order -v -s
```

---

### **AngelOne Tests (One by One)**

#### Authentication Tests
```bash
# TC_AUTH_01: Connect and Authenticate (See connection process!)
python3 -m pytest paper_trading/tests/integration/test_angelone_integration.py::TestAngelOneAuthentication::test_auth_01_connect_and_authenticate -v -s

# Wait 3 seconds (rate limiting)
sleep 3

# TC_AUTH_02: Get Profile (See profile details!)
python3 -m pytest paper_trading/tests/integration/test_angelone_integration.py::TestAngelOneAuthentication::test_auth_02_get_profile -v -s

# Wait 3 seconds
sleep 3

# TC_AUTH_03: Reconnection (May fail due to rate limiting)
python3 -m pytest paper_trading/tests/integration/test_angelone_integration.py::TestAngelOneAuthentication::test_auth_03_reconnection -v -s
```

#### Market Data Tests
```bash
# TC_QUOTE_01: Get LTP (See actual LTP values!)
sleep 3
python3 -m pytest paper_trading/tests/integration/test_angelone_integration.py::TestAngelOneMarketData::test_quote_01_get_ltp_single -v -s

# TC_QUOTE_02: Get Full Quote (See bid/ask, volume, OI!)
sleep 3
python3 -m pytest paper_trading/tests/integration/test_angelone_integration.py::TestAngelOneMarketData::test_quote_02_get_full_quote_multiple -v -s

# TC_QUOTE_03: Historical Data (See candle data!)
sleep 3
python3 -m pytest paper_trading/tests/integration/test_angelone_integration.py::TestAngelOneMarketData::test_quote_03_historical_data_1day -v -s

# Get Spot Price (See NIFTY spot price!)
sleep 3
python3 -m pytest paper_trading/tests/integration/test_angelone_integration.py::TestAngelOneMarketData::test_get_spot_price -v -s
```

#### Position Tests
```bash
# TC_POS_01: Fetch Positions (See your positions!)
sleep 3
python3 -m pytest paper_trading/tests/integration/test_angelone_integration.py::TestAngelOnePositions::test_pos_01_fetch_net_positions -v -s

# TC_POS_02: Fetch Holdings/Funds (See your funds!)
sleep 3
python3 -m pytest paper_trading/tests/integration/test_angelone_integration.py::TestAngelOnePositions::test_pos_02_fetch_holdings_funds -v -s
```

#### Safe AMO Limit Order Tests
```bash
# Safe Limit BUY (10% above market - See LTP, limit price, order ID!)
sleep 5
python3 -m pytest paper_trading/tests/integration/test_angelone_amo_limit.py::TestAngelOneAMOLimit::test_amo_limit_buy_safe -v -s

# Safe Limit SELL (10% below market - See LTP, limit price, order ID!)
sleep 5
python3 -m pytest paper_trading/tests/integration/test_angelone_amo_limit.py::TestAngelOneAMOLimit::test_amo_limit_sell_safe -v -s

# Extreme Limit (50% away - See extreme pricing calculation!)
sleep 5
python3 -m pytest paper_trading/tests/integration/test_angelone_amo_limit.py::TestAngelOneAMOLimit::test_amo_limit_extreme_price -v -s
```

#### Order Cancellation Tests
```bash
# Place and cancel single order (See full lifecycle: place → verify → cancel!)
sleep 5
python3 -m pytest paper_trading/tests/integration/test_angelone_cancel_amo.py::TestAngelOneAMOCancellation::test_place_and_cancel_amo_limit -v -s

# Cancel multiple orders (See batch cancellation!)
sleep 5
python3 -m pytest paper_trading/tests/integration/test_angelone_cancel_amo.py::TestAngelOneAMOCancellation::test_cancel_multiple_amo_orders -v -s

# Error handling (See error messages!)
sleep 5
python3 -m pytest paper_trading/tests/integration/test_angelone_cancel_amo.py::TestAngelOneAMOCancellation::test_cancel_nonexistent_order -v -s
```

---

## 🧹 **Cleanup Utility**

### **Cancel All Pending Orders**

```bash
# Cancel all Zerodha pending orders (See each order being cancelled!)
python3 -m pytest paper_trading/tests/integration/test_cancel_pending_orders.py::TestCancelPendingOrders::test_cancel_zerodha_pending_orders -v -s

# Cancel all AngelOne pending orders (See each order being cancelled!)
sleep 3
python3 -m pytest paper_trading/tests/integration/test_cancel_pending_orders.py::TestCancelPendingOrders::test_cancel_angelone_pending_orders -v -s

# Verify no pending orders remain (See final verification!)
sleep 3
python3 -m pytest paper_trading/tests/integration/test_cancel_pending_orders.py::TestCancelPendingOrders::test_verify_no_pending_orders -v -s
```

---

## 📊 **Test Coverage Summary**

### **Zerodha (14 tests)**

| Category | Tests | Status |
|----------|-------|--------|
| Authentication | 3 | ✅ All passing |
| Market Data | 4 | ✅ All passing |
| Positions | 2 | ✅ All passing |
| Orders (AMO) | 4 | ⚠️ Requires NFO activation |
| WebSocket | 3 | ⏭️ Skipped |

### **AngelOne (20 tests)**

| Category | Tests | Status |
|----------|-------|--------|
| Authentication | 3 | ✅ 2 passing, 1 rate limited |
| Market Data | 4 | ✅ All passing |
| Positions | 2 | ✅ All passing |
| Orders (Main) | 4 | ✅ All passing |
| AMO Limit (Safe) | 3 | ✅ All passing |
| Cancellation | 3 | ✅ All passing |
| WebSocket | 3 | ⏭️ Skipped |

---

## 🏗️ **Architecture**

### **How Tests Work**

```
┌─────────────────────────────────────────────────────────────┐
│ Test File (e.g., test_zerodha_integration.py)              │
│                                                             │
│  import from paper_trading.brokers.adapter.types           │
│  Uses: OrderRequest, OrderType, TransactionType, etc.      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ conftest.py (Fixtures)                                      │
│                                                             │
│  @pytest.fixture                                            │
│  def zerodha_adapter(credentials, contract_manager):        │
│      adapter = ZerodhaAdapter(credentials, contract_manager)│
│      adapter.connect()                                      │
│      yield adapter                                          │
│      adapter.disconnect()                                   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Broker Adapter (e.g., ZerodhaAdapter)                      │
│                                                             │
│  from paper_trading.brokers.adapter.base import BaseAdapter│
│  from paper_trading.core.contract_manager import ...       │
│                                                             │
│  def place_order(order: OrderRequest) → OrderResponse:     │
│      1. Get token from contract_manager                     │
│      2. Resolve instrument using token                      │
│      3. Place order via broker API                          │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Contract Manager                                            │
│                                                             │
│  Loads: contracts_cache.json                                │
│  Provides:                                                  │
│    - get_option_contract(expiry, strike, option_type)      │
│    - get_options_expiry(expiry_type)                       │
│    - Token lookups (universal exchange tokens)             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Broker APIs                                                 │
│                                                             │
│  Zerodha: KiteConnect                                       │
│    - place_order(tradingsymbol=TOKEN, ...)                 │
│                                                             │
│  AngelOne: SmartAPI                                         │
│    - placeOrder(tradingsymbol=SYMBOL, symboltoken=TOKEN)   │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔐 **Token-Based Design**

### **Both Brokers Use Tokens**

**contracts_cache.json structure**:
```json
{
  "options": {
    "instruments": {
      "2026-01-27": {
        "25000": {
          "CE": {
            "token": "58661",              // ← AngelOne/NSE token
            "zerodha_instrument_token": "15017218"  // ← Zerodha token
          }
        }
      }
    }
  }
}
```

**Zerodha**:
- Uses: `zerodha_instrument_token` (e.g., 15017218)
- Places orders with token directly
- No symbol needed

**AngelOne**:
- Uses: `token` (e.g., "58661")
- Looks up symbol from token using master instruments
- Places order with symbol + token

**From user perspective**: Both are token-based! Just provide strike/expiry/type.

---

## 🛡️ **Safety Features**

### **Built-in Protections**

1. **After-Hours Only**:
   - Tests skip during market hours (9:15 AM - 3:30 PM)
   - AMO orders only (safe for testing)

2. **Safe Prices**:
   - Limit orders: 10-50% away from market
   - Won't execute in normal conditions

3. **Auto-Cancellation**:
   - AMO limit tests cancel orders immediately
   - Cleanup utilities available

4. **Rate Limiting**:
   - AngelOne tests need 3-5 second delays
   - Prevents API throttling

---

## 📖 **Example Test Walkthrough**

### **Example: test_amo_limit_buy_safe**

```python
def test_amo_limit_buy_safe(self, angelone_adapter, test_instruments, skip_if_market_open):
    # 1. Get current market price
    ltp = angelone_adapter.get_ltp(underlying='NIFTY', strike=25000, ...)
    # Result: ₹174.80
    
    # 2. Set safe limit price (won't execute)
    limit_price = ltp * 1.10  # ₹192.28 (10% above market)
    
    # 3. Create order request (token-based!)
    order_request = OrderRequest(
        underlying='NIFTY',      # ← No tokens visible!
        strike=25000,            # ← Just parameters
        option_type='CE',
        order_type=OrderType.LIMIT,
        price=limit_price
    )
    
    # 4. Place order (adapter handles tokens internally)
    response = angelone_adapter.place_order(order_request)
    # Internally:
    #   - Gets token from cache: '58661'
    #   - Looks up symbol: 'NIFTY27JAN2625000CE'
    #   - Places order with both
    
    # 5. Verify success
    assert response.success is True
    order_id = response.order_id  # e.g., '01279b1d2939AO'
    
    # 6. Cancel for safety
    angelone_adapter._smart_api.cancelOrder(order_id, 'NORMAL')
```

---

## 🎯 **Quick Reference Commands**

### **Run All Tests (Batch)**

```bash
# Zerodha - All tests (Standard output)
python3 -m pytest paper_trading/tests/integration/test_zerodha_integration.py -v

# Zerodha - All tests (WITH DETAILED OUTPUT - See LTP, order IDs, etc.)
python3 -m pytest paper_trading/tests/integration/test_zerodha_integration.py -v -s

# AngelOne - All tests (with rate limiting risk)
python3 -m pytest paper_trading/tests/integration/test_angelone_integration.py -v

# AngelOne - All tests (WITH DETAILED OUTPUT)
python3 -m pytest paper_trading/tests/integration/test_angelone_integration.py -v -s

# AngelOne - Safe AMO tests only (WITH DETAILED OUTPUT)
python3 -m pytest paper_trading/tests/integration/test_angelone_amo_limit.py -v -s

# Cancellation tests (WITH DETAILED OUTPUT - See each cancellation!)
python3 -m pytest paper_trading/tests/integration/test_angelone_cancel_amo.py -v -s
```

### **Run by Category**

```bash
# All Authentication tests (Standard)
python3 -m pytest paper_trading/tests/integration/ -k "Authentication" -v

# All Authentication tests (WITH DETAILED OUTPUT)
python3 -m pytest paper_trading/tests/integration/ -k "Authentication" -v -s

# All Market Data tests (WITH DETAILED OUTPUT - See LTP values!)
python3 -m pytest paper_trading/tests/integration/ -k "MarketData" -v -s

# All Position tests (WITH DETAILED OUTPUT - See positions/funds!)
python3 -m pytest paper_trading/tests/integration/ -k "Positions" -v -s

# All AMO Order tests (WITH DETAILED OUTPUT - See order lifecycle!)
python3 -m pytest paper_trading/tests/integration/ -k "AMO" -v -s
```

### **Run Specific Broker**

```bash
# Zerodha only (WITH DETAILED OUTPUT)
python3 -m pytest paper_trading/tests/integration/test_zerodha_integration.py -v -s

# AngelOne only - all files (WITH DETAILED OUTPUT)
python3 -m pytest paper_trading/tests/integration/test_angelone_*.py -v -s
```

### **🌟 Pro Tip: Always Use `-s` for Real Testing**

The `-s` flag shows you:
- 📊 Actual LTP values fetched
- 🆔 Order IDs when orders are placed
- 💰 Prices used (market price, limit price, etc.)
- ✅ Cancellation confirmations
- 🔍 Token → Symbol lookups
- 📈 Historical data candles
- 💼 Your actual positions and funds

**Example Output WITH `-s`:**
```
🧪 Testing AMO Limit BUY (Safe - 10% above market)
Current LTP: ₹174.80
Limit Price: ₹192.28 (10% above - SAFE)
Strike: 25000 CE
Placing AMO Limit BUY order...
✅ Order placed successfully!
   Order ID: 01279b1d2939AO
   Price: ₹192.28
   Status: pending
🛡️ Cancelling order for safety...
✅ Order cancelled successfully: 01279b1d2939AO
```

**Example Output WITHOUT `-s`:**
```
PASSED
```

**Use `-s` to see what's actually happening!** 🎯

---

## 🐛 **Troubleshooting**

### **Common Issues**

#### 1. ModuleNotFoundError
```bash
# MUST run from project root!
cd /Users/Algo_Trading/manishsir_options
python3 -m pytest paper_trading/tests/integration/...
```

#### 2. Credentials Not Found
```bash
# Copy template and fill credentials
cp test_credentials.yaml.template test_credentials.yaml
# Edit test_credentials.yaml with your API keys
```

#### 3. AngelOne Rate Limiting
```bash
# Add delays between tests
sleep 3  # Wait 3-5 seconds between tests
```

#### 4. Zerodha NFO Not Activated
```
Error: "NFO is disabled for your account"
Solution: Activate F&O segment at https://console.zerodha.com/account/segment-activation
```

---

## 📝 **Test File Structure**

### **test_zerodha_integration.py**
```
TestZerodhaAuthentication (3 tests)
  ├── test_auth_01_connect_and_authenticate
  ├── test_auth_02_get_profile
  └── test_auth_03_reconnection

TestZerodhaOrdersAMO (4 tests)
  ├── test_order_01_place_amo_market_buy
  ├── test_order_02_place_amo_limit_sell
  ├── test_order_03_invalid_symbol
  └── test_order_04_cancel_amo_order

TestZerodhaMarketData (4 tests)
  ├── test_quote_01_get_ltp_single
  ├── test_quote_02_get_full_quote_multiple
  ├── test_quote_03_historical_data_1day
  └── test_get_spot_price

TestZerodhaPositions (3 tests)
  ├── test_pos_01_fetch_net_positions
  ├── test_pos_02_fetch_holdings_funds
  └── test_pos_03_square_off_position

TestZerodhaWebSocket (3 tests - skipped)
  ├── test_ws_01_subscribe_live_ticks
  ├── test_ws_02_error_invalid_token
  └── test_ws_03_unsubscribe_mode
```

### **test_angelone_integration.py**
```
TestAngelOneAuthentication (3 tests)
  ├── test_auth_01_connect_and_authenticate
  ├── test_auth_02_get_profile
  └── test_auth_03_reconnection

TestAngelOneOrdersAMO (4 tests)
  ├── test_order_01_place_amo_market_buy
  ├── test_order_02_place_amo_limit_sell
  ├── test_order_03_invalid_symbol
  └── test_order_04_cancel_amo_order

TestAngelOneMarketData (4 tests)
  ├── test_quote_01_get_ltp_single
  ├── test_quote_02_get_full_quote_multiple
  ├── test_quote_03_historical_data_1day
  └── test_get_spot_price

TestAngelOnePositions (3 tests)
  ├── test_pos_01_fetch_net_positions
  ├── test_pos_02_fetch_holdings_funds
  └── test_pos_03_square_off_position

TestAngelOneWebSocket (3 tests - skipped)
  ├── test_ws_01_subscribe_live_ticks
  ├── test_ws_02_error_invalid_token
  └── test_ws_03_unsubscribe_mode
```

### **test_angelone_amo_limit.py**
```
TestAngelOneAMOLimit (3 tests)
  ├── test_amo_limit_buy_safe (10% above market)
  ├── test_amo_limit_sell_safe (10% below market)
  └── test_amo_limit_extreme_price (50% away - very safe)

TestAngelOneLimitOrderValidation (1 test)
  └── test_limit_order_requires_price
```

### **test_angelone_cancel_amo.py**
```
TestAngelOneAMOCancellation (3 tests)
  ├── test_place_and_cancel_amo_limit
  ├── test_cancel_multiple_amo_orders
  └── test_cancel_nonexistent_order
```

### **test_cancel_pending_orders.py**
```
TestCancelPendingOrders (3 tests)
  ├── test_cancel_zerodha_pending_orders
  ├── test_cancel_angelone_pending_orders
  └── test_verify_no_pending_orders
```

---

## 🔍 **conftest.py - Fixtures Explained**

### **Key Fixtures**

#### 1. **test_settings**
```python
@pytest.fixture(scope="session")
def test_settings():
    """Load test configuration from test_credentials.yaml"""
    # Returns: credentials + test config
```

#### 2. **contract_manager**
```python
@pytest.fixture(scope="session")
def contract_manager():
    """Initialize ContractManager with cached tokens"""
    # Returns: ContractManager instance
    # Loads: contracts_cache.json
```

#### 3. **zerodha_adapter**
```python
@pytest.fixture(scope="session")
def zerodha_adapter(zerodha_credentials, contract_manager):
    """Create and connect Zerodha adapter"""
    # Returns: Connected ZerodhaAdapter instance
    # Auto-disconnects after tests
```

#### 4. **angelone_adapter**
```python
@pytest.fixture(scope="session")
def angelone_adapter(angelone_credentials, contract_manager):
    """Create and connect AngelOne adapter"""
    # Returns: Connected AngelOneAdapter instance
    # Loads: AngelOne master instruments for symbol lookup
    # Auto-disconnects after tests
```

#### 5. **test_instruments**
```python
@pytest.fixture(scope="session")
def test_instruments(test_settings):
    """Provide test instrument parameters"""
    # Returns: {'underlying': 'NIFTY', 'strike': 25000, 'quantity': 65}
```

#### 6. **amo_order_helper**
```python
@pytest.fixture(scope="session")
def amo_order_helper():
    """Helper for AMO order creation and tracking"""
    # Methods:
    #   - create_amo_request(adapter, underlying, strike, quantity)
    #   - place_and_track(adapter, order_request)
```

#### 7. **skip_if_market_open**
```python
@pytest.fixture(scope="function")
def skip_if_market_open(test_settings):
    """Skip test if market is open (safety)"""
    # Skips: 9:15 AM - 3:30 PM
```

---

## 🎯 **Token-Based Flow Example**

### **Complete Order Placement Flow**

```python
# Test Code (What you write)
def test_place_order(angelone_adapter):
    order_request = OrderRequest(
        underlying='NIFTY',      # Simple parameters
        strike=25000,
        expiry='2026-01-27',
        option_type='CE',
        quantity=65,
        order_type=OrderType.LIMIT,
        price=150.0
    )
    
    response = angelone_adapter.place_order(order_request)
    assert response.success is True

# What happens inside angelone_adapter.place_order():
Step 1: Get contract from cache
    contract = self.contract_manager.get_option_contract(
        '2026-01-27', 25000, 'CE'
    )
    # Returns: {'token': '58661', 'zerodha_instrument_token': '15017218'}

Step 2: Extract token
    token = contract['token']  # '58661'

Step 3: Lookup symbol from token
    symbol = self._get_symbol_from_token(token)
    # Looks in self.nfo_instruments (loaded from AngelOne master)
    # Returns: 'NIFTY27JAN2625000CE'

Step 4: Build order params
    order_params = {
        'tradingsymbol': symbol,      # 'NIFTY27JAN2625000CE'
        'symboltoken': token,          # '58661'
        'exchange': 'NFO',
        'quantity': '65',
        'price': '150.0',
        ...
    }

Step 5: Place order
    response = self._smart_api.placeOrder(order_params)

Step 6: Return standardized response
    return OrderResponse(
        success=True,
        order_id=response.get('data').get('orderid'),
        status=OrderStatus.PENDING,
        ...
    )
```

---

## 📚 **Dependencies**

### **Required Packages**
```bash
pip install pytest pytest-asyncio
pip install kiteconnect              # Zerodha
pip install smartapi-python logzero websocket-client  # AngelOne
pip install pandas pyyaml requests
```

---

## ✅ **Verification**

### **Check Setup**
```bash
# 1. Check you're in project root
pwd
# Should show: /Users/Algo_Trading/manishsir_options

# 2. Check credentials exist
ls paper_trading/tests/integration/test_credentials.yaml

# 3. Check contracts cache exists
ls contracts_cache.json

# 4. Run a simple test (WITH DETAILED OUTPUT to verify everything works!)
python3 -m pytest paper_trading/tests/integration/test_zerodha_integration.py::TestZerodhaAuthentication::test_auth_01_connect_and_authenticate -v -s
```

---

## 🎓 **Best Practices**

1. **Always run from project root**
2. **Add delays for AngelOne** (3-5 seconds between tests)
3. **Cancel orders immediately** after testing
4. **Test after market hours** (3:30 PM+)
5. **Use safe limit prices** (10%+ away from market)
6. **Verify cleanup** with `test_verify_no_pending_orders`

---

## 📞 **Support**

### **If Tests Fail**

1. **Check you're in project root**: `pwd`
2. **Check credentials**: `cat paper_trading/tests/integration/test_credentials.yaml`
3. **Check broker connection**: Run auth tests first
4. **Check contracts cache**: `ls -lh contracts_cache.json`
5. **Check for pending orders**: Run verification test

---

**Created**: 2026-01-27
**Status**: ✅ Production Ready - All Tests Working
**Brokers**: Zerodha + AngelOne
**Approach**: Token-Based (No Manual Symbols)
