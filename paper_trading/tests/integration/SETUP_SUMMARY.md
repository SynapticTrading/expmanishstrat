# Integration Tests - Setup Summary

**Created:** 2026-01-27
**Location:** `/Users/Algo_Trading/manishsir_options/paper_trading/tests/integration/`

---

## 📝 What Was Created

### 1. **requirements.txt** (95 lines)
Complete dependency list for integration tests including:
- Testing framework (pytest)
- Broker APIs (kiteconnect, smartapi-python)
- Authentication (pyotp)
- Data handling (pandas, numpy)
- Configuration (PyYAML)
- Utilities (requests, websocket-client, pytz, logzero)

### 2. **INSTALL.md** (266 lines)
Step-by-step installation and setup guide covering:
- Quick start instructions
- Dependency installation
- Credential setup (both Zerodha and AngelOne)
- How to get broker API credentials
- Verification steps
- Common issues and troubleshooting

### 3. **Existing: README.md** (29KB)
Comprehensive test documentation (already existed)

---

## 🚀 Quick Setup (TL;DR)

```bash
# 1. Navigate to integration tests directory
cd /Users/Algo_Trading/manishsir_options/paper_trading/tests/integration

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up credentials
cp test_credentials.yaml.template test_credentials.yaml
# Edit test_credentials.yaml with your broker credentials

# 4. Run tests
pytest test_angelone_integration.py::TestAngelOneConnection -v
```

---

## 📦 Dependencies Included

| Package | Version | Purpose |
|---------|---------|---------|
| **pytest** | ≥7.4.0 | Test framework |
| **kiteconnect** | ≥4.1.0 | Zerodha API |
| **smartapi-python** | ≥1.3.0 | AngelOne API |
| **pyotp** | ≥2.8.0 | 2FA authentication |
| **pandas** | ≥2.0.3 | Data manipulation |
| **numpy** | ≥1.24.3 | Numerical operations |
| **PyYAML** | ≥6.0.1 | Config files |
| **requests** | ≥2.31.0 | HTTP requests |
| **websocket-client** | ≥1.6.0 | WebSocket feeds |
| **pytz** | ≥2023.3 | Timezone support |
| **logzero** | ≥1.7.0 | Enhanced logging |
| **python-dateutil** | ≥2.8.2 | Date utilities |

---

## 📂 File Structure

```
integration/
├── requirements.txt              ✅ NEW - Install this first
├── INSTALL.md                    ✅ NEW - Setup guide
├── SETUP_SUMMARY.md              ✅ NEW - This file
├── README.md                     📖 Existing - Full documentation
│
├── conftest.py                   🔧 Test fixtures
├── test_credentials.yaml         🔐 Your credentials (create from template)
├── test_credentials.yaml.template 📋 Template
│
├── test_angelone_integration.py  🧪 14 AngelOne tests
├── test_zerodha_integration.py   🧪 14 Zerodha tests
├── test_angelone_amo_limit.py    🧪 3 AMO tests
├── test_angelone_cancel_amo.py   🧪 3 cancellation tests
└── test_cancel_pending_orders.py 🧹 Cleanup utility
```

---

## ✅ Installation Verification

After installing, verify everything works:

```bash
# 1. Check all dependencies installed
python3 -c "import pytest, kiteconnect, SmartApi, pyotp, pandas, yaml; print('✓ All dependencies OK')"

# 2. Verify credentials file
python3 -c "import yaml; yaml.safe_load(open('test_credentials.yaml')); print('✓ Credentials file OK')"

# 3. Test connection
pytest test_angelone_integration.py::TestAngelOneConnection::test_conn_01_connection_success -v -s
```

---

## 🎯 Test Categories

### **Connection Tests** (Safe - Always run first)
```bash
pytest test_angelone_integration.py::TestAngelOneConnection -v
pytest test_zerodha_integration.py::TestZerodhaConnection -v
```

### **Market Data Tests** (Safe - Read-only)
```bash
pytest test_angelone_integration.py::TestAngelOneMarketData -v
pytest test_zerodha_integration.py::TestZerodhaMarketData -v
```

### **Position & Account Tests** (Safe - Read-only)
```bash
pytest test_angelone_integration.py::TestAngelOnePositions -v
pytest test_zerodha_integration.py::TestZerodhaPositions -v
```

### **Order Tests** (⚠️ Caution - Places real AMO orders)
```bash
# Review test code first!
pytest test_angelone_integration.py::TestAngelOneOrders -v
pytest test_angelone_amo_limit.py -v
```

---

## 🔒 Security Notes

1. **Never commit credentials:**
   ```bash
   # test_credentials.yaml is already in .gitignore
   git status  # Should NOT show test_credentials.yaml
   ```

2. **Secure the credentials file:**
   ```bash
   chmod 600 test_credentials.yaml
   ```

3. **Use MPIN for AngelOne:**
   - Use your 4-6 digit MPIN, NOT your trading password

4. **Rate limiting:**
   - Tests use session-scoped fixtures (one connection per test session)
   - Wait 60 seconds if you hit rate limits
   - Don't run multiple test sessions in parallel

---

## 🆘 Common Issues

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: No module named 'SmartApi'` | `pip install smartapi-python` |
| `ModuleNotFoundError: No module named 'kiteconnect'` | `pip install kiteconnect` |
| `Connection timeout` | Wait 60 seconds, tests use session scope |
| `TOTP validation failed` | Check TOTP secret, sync system time |
| `Invalid MPIN` (AngelOne) | Use MPIN (4-6 digits), not trading password |
| `Module not found: paper_trading` | `pip install -e .` from project root |

---

## 📊 What Tests Check

### ✅ **Connection Tests**
- Authenticate with broker API
- Verify session creation
- Check connection status

### ✅ **Market Data Tests**
- Get spot price (LTP)
- Fetch full quotes (LTP, OI, volume)
- Get option chains (5-min candles)
- Historical data retrieval

### ✅ **Position & Account Tests**
- Get open positions
- Fetch holdings
- Check account funds/margin

### ✅ **Order Tests** (⚠️)
- Place AMO orders (safe, after market hours)
- Modify orders
- Cancel orders
- Get order status

---

## 📚 Read Next

1. **INSTALL.md** - Detailed installation guide
2. **README.md** - Complete test documentation
3. **test_credentials.yaml.template** - Credential template

---

## 🎉 You're Ready!

After setup:
1. ✅ Dependencies installed → `pip install -r requirements.txt`
2. ✅ Credentials configured → `test_credentials.yaml`
3. ✅ Connection verified → Run connection test
4. 🚀 **Start testing!** → Begin with market data tests

---

**Questions?** Check **INSTALL.md** for detailed setup or **README.md** for test documentation.

**Last Updated:** 2026-01-27
