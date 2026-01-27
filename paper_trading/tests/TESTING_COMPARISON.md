# Testing Strategy: Mock vs Integration Tests

## Overview

You now have **TWO complete test suites**:

1. **Mock Tests** (`tests/adapter/`) - Unit tests with mocked connections
2. **Integration Tests** (`tests/integration/`) - Real broker API tests with AMO orders

## 📊 Quick Comparison

| Aspect | Mock Tests | Integration Tests |
|--------|------------|-------------------|
| **Location** | `tests/adapter/` | `tests/integration/` |
| **Files** | 7 files | 10 files |
| **Test Count** | 64 tests | 28 tests |
| **Speed** | Fast (~3 sec) | Slower (~15-30 sec) |
| **Broker Connection** | ❌ Mocked | ✅ Real API |
| **Market Data** | ❌ Fake | ✅ Live data |
| **Order Placement** | ❌ Simulated | ✅ AMO (safe) |
| **Credentials Required** | ❌ No | ✅ Yes |
| **Network Required** | ❌ No | ✅ Yes |
| **Safety** | 100% safe | Safe (AMO + auto-cancel) |
| **Best For** | Development, CI/CD | Pre-production validation |

## 🎯 When to Use Each

### Use Mock Tests When:
- ✅ Developing new features
- ✅ Running tests in CI/CD pipeline
- ✅ Testing code logic and error handling
- ✅ Quick feedback loop needed
- ✅ No network connection available
- ✅ Testing edge cases and error scenarios

### Use Integration Tests When:
- ✅ Validating actual broker integration
- ✅ Testing before deployment
- ✅ Verifying live market data handling
- ✅ End-to-end workflow validation
- ✅ After major changes to broker code
- ✅ Weekly/monthly regression testing

## 📁 File Structure

```
paper_trading/tests/
│
├── adapter/                          # MOCK TESTS
│   ├── conftest.py                  # Mock fixtures
│   ├── test_base_adapter.py         # 17 tests
│   ├── test_zerodha_adapter.py      # 21 tests
│   ├── test_angelone_adapter.py     # 26 tests
│   ├── README.md                    # Mock test docs
│   ├── QUICK_START.md
│   └── TEST_SUMMARY.md
│
└── integration/                      # INTEGRATION TESTS
    ├── conftest.py                  # Real broker fixtures
    ├── test_zerodha_integration.py  # 14 tests
    ├── test_angelone_integration.py # 14 tests
    ├── test_credentials.yaml.template
    ├── run_tests.sh                 # Test runner
    ├── README.md                    # Integration docs
    ├── QUICK_START.md
    ├── COVERAGE_REPORT.md
    └── IMPLEMENTATION_SUMMARY.md
```

## 🚀 How to Run

### Mock Tests (Fast)

```bash
# All mock tests
pytest paper_trading/tests/adapter/ -v

# Specific broker
pytest paper_trading/tests/adapter/test_zerodha_adapter.py -v
pytest paper_trading/tests/adapter/test_angelone_adapter.py -v

# Specific category
pytest paper_trading/tests/adapter/ -v -k "auth"
pytest paper_trading/tests/adapter/ -v -k "order"

# With coverage
pytest paper_trading/tests/adapter/ \
  --cov=paper_trading/brokers/adapter \
  --cov-report=html -v
```

### Integration Tests (Real Broker)

```bash
# Setup first time only
cd paper_trading/tests/integration
cp test_credentials.yaml.template test_credentials.yaml
# Edit test_credentials.yaml with your credentials

# Run tests
./run_tests.sh all               # All tests
./run_tests.sh zerodha           # Zerodha only
./run_tests.sh auth              # Auth tests
./run_tests.sh quick             # Smoke test

# Or with pytest directly
pytest paper_trading/tests/integration/ -v
```

## 🎨 What Each Tests

### Mock Tests Coverage

```
✅ Base Adapter (17 tests)
   - Abstract interface compliance
   - Type validation
   - Error handling

✅ Zerodha Adapter (21 tests)
   - Authentication (4)
   - Order placement (4)
   - Market data (4)
   - Positions (3)
   - Integration (2)
   - Parametrized (4)

✅ AngelOne Adapter (26 tests)
   - Authentication (4)
   - Order placement (4)
   - Market data (4)
   - Positions (3)
   - Integration (3)
   - Parametrized (8)

Total: 64 mock tests
```

### Integration Tests Coverage

```
✅ Zerodha Real Tests (14 tests)
   - Authentication (3)
   - Orders - AMO (4)
   - Market Data (4)
   - Positions (3)

✅ AngelOne Real Tests (14 tests)
   - Authentication (3)
   - Orders - AMO (4)
   - Market Data (4)
   - Positions (3)

🚧 WebSocket Tests (6 tests)
   - Zerodha (3) - Skipped
   - AngelOne (3) - Skipped

Total: 28 integration tests (6 skipped)
```

## ✅ Test Matrix

| Test Category | Mock | Integration | Total |
|---------------|------|-------------|-------|
| Authentication | 8 | 6 | 14 |
| Order Placement | 8 | 8 | 16 |
| Market Data | 8 | 8 | 16 |
| Positions | 6 | 6 | 12 |
| Base/Abstract | 17 | - | 17 |
| Integration | 5 | - | 5 |
| Parametrized | 12 | - | 12 |
| WebSocket | - | 6 (skip) | 6 |
| **Total** | **64** | **28+6** | **98** |

## 🔒 Safety Comparison

### Mock Tests Safety
- ✅ **100% safe** - No real connections
- ✅ No credentials needed
- ✅ No network calls
- ✅ No real orders
- ✅ Can run anytime, anywhere

### Integration Tests Safety
- ✅ **Safe with precautions**
- ✅ Real connection but **AMO orders only**
- ✅ All orders **auto-cancelled**
- ✅ **Market hours check** prevents live orders
- ✅ Requires real credentials (protected)
- ⚠️ Network required
- ⚠️ Broker API must be accessible

## 📈 CI/CD Strategy

### Recommended Approach

```yaml
# .github/workflows/tests.yml

# Run on every commit
on: [push, pull_request]

jobs:
  # Fast mock tests
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run mock tests
        run: pytest paper_trading/tests/adapter/ -v
      # Fast feedback: ~1 minute
  
  # Integration tests (scheduled)
  integration-tests:
    runs-on: ubuntu-latest
    # Only run after market hours
    schedule:
      - cron: '0 18 * * *'  # 6 PM daily
    steps:
      - uses: actions/checkout@v2
      - name: Setup credentials
        run: |
          echo "${{ secrets.TEST_CREDENTIALS }}" > \
            paper_trading/tests/integration/test_credentials.yaml
      - name: Run integration tests
        run: |
          cd paper_trading/tests/integration
          ./run_tests.sh all
      # Slower: ~5-10 minutes
```

## 🎯 Development Workflow

### Daily Development
```bash
# 1. Make changes to code
vim paper_trading/brokers/adapter/plugins/zerodha.py

# 2. Run fast mock tests
pytest paper_trading/tests/adapter/test_zerodha_adapter.py -v

# 3. Fix any failures
# Repeat until all pass

# 4. Commit
git add .
git commit -m "Fix: Updated Zerodha adapter"
```

### Before Deployment
```bash
# 1. Run all mock tests
pytest paper_trading/tests/adapter/ -v

# 2. Run integration tests (after market hours)
cd paper_trading/tests/integration
./run_tests.sh all

# 3. Review results
# - All mock tests pass: ✅
# - All integration tests pass: ✅

# 4. Deploy with confidence
```

## 📊 Expected Results

### Mock Tests Output
```
tests/adapter/test_base_adapter.py::TestBaseAdapter::test_is_abstract PASSED
tests/adapter/test_zerodha_adapter.py::TestZerodhaAuthentication::test_auth_01 PASSED
tests/adapter/test_zerodha_adapter.py::TestZerodhaAuthentication::test_auth_02 PASSED
...

======================== 64 passed in 3.21s ========================
```

### Integration Tests Output
```
tests/integration/test_zerodha_integration.py::TestZerodhaAuthentication::test_auth_01 PASSED
✓ TC_AUTH_01: Successfully authenticated with Zerodha

tests/integration/test_zerodha_integration.py::TestZerodhaOrdersAMO::test_order_01 PASSED
✓ TC_ORDER_01: AMO Market Buy order placed - ID: 240127000001234
✓ Cleaning up 1 AMO orders...
✓ Cancelled order: 240127000001234
...

==================== 28 passed, 6 skipped in 18.45s ====================
```

## 🎓 Summary

| Question | Mock Tests | Integration Tests |
|----------|------------|-------------------|
| **What do they test?** | Code logic | Real API integration |
| **How fast?** | Very fast | Slower |
| **Safe?** | 100% safe | Safe with AMO |
| **When to run?** | Always | Before deployment |
| **Who should run?** | Developers | QA & DevOps |
| **Frequency?** | Every commit | Daily/weekly |
| **CI/CD?** | Yes, always | Yes, scheduled |

## 🏆 Best Practice

**Use BOTH suites in combination:**

1. **During Development**
   - Run mock tests frequently
   - Fast feedback on code changes
   - Catch logic errors early

2. **Before Commits**
   - Run full mock suite
   - Ensure no regressions
   - Verify type safety

3. **Before Deployment**
   - Run integration tests
   - Validate real broker behavior
   - Confirm end-to-end workflow

4. **Production Monitoring**
   - Weekly integration test runs
   - Alert on failures
   - Track API changes

---

## 🎉 Final Summary

You now have:

✅ **64 mock tests** - Fast, safe, comprehensive unit testing  
✅ **28 integration tests** - Real broker validation with AMO safety  
✅ **Comprehensive documentation** - Easy to understand and use  
✅ **Safety features** - Multiple layers of protection  
✅ **Easy execution** - Simple scripts and commands  
✅ **Production-ready** - Battle-tested approaches  

**Total: 92 automated tests covering your entire broker adapter system!** 🚀

---

**Remember**: 
- Mock tests for **speed** ⚡
- Integration tests for **confidence** 🔒
- Use **both** for best results! 🎯
