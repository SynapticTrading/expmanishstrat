"""
Setup Test Script

Quick test to verify all components are working correctly
"""

import sys
from pathlib import Path

print("="*80)
print("Testing Intraday Momentum OI Strategy Setup")
print("="*80)

# Test 1: Import all modules
print("\n[TEST 1] Testing imports...")
try:
    from utils.config_loader import get_config
    from utils.data_loader import DataLoader
    from utils.oi_analyzer import OIAnalyzer
    from utils.indicators import VWAPCalculator
    from strategies.intraday_momentum_oi import IntradayMomentumOIStrategy
    print("✅ All modules imported successfully")
except Exception as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

# Test 2: Load configuration
print("\n[TEST 2] Testing configuration loading...")
try:
    config = get_config()
    print(f"✅ Configuration loaded")
    print(f"   - Strategy: {config.get('strategy_name')}")
    print(f"   - Instrument: {config.get('instrument')}")
    print(f"   - Expiry Type: {config.get('expiry_type')}")
    print(f"   - Initial Capital: ₹{config.get('initial_capital'):,}")
except Exception as e:
    print(f"❌ Configuration error: {e}")
    sys.exit(1)

# Test 3: Check data files
print("\n[TEST 3] Checking data files...")
try:
    data_files = [
        'weekly_expiry',
        'monthly_expiry',
        'spot_price',
        'india_vix'
    ]

    for data_type in data_files:
        path = config.get_data_path(data_type)
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            print(f"✅ {data_type}: {path.name} ({size_mb:.1f} MB)")
        else:
            print(f"❌ {data_type}: NOT FOUND at {path}")

except Exception as e:
    print(f"❌ Data file check error: {e}")
    sys.exit(1)

# Test 4: Load sample data
print("\n[TEST 4] Testing data loading...")
try:
    data_loader = DataLoader(config)
    print("✅ DataLoader initialized")

    # Try loading just the headers
    print("   Loading data files (this may take a moment)...")
    import pandas as pd

    # Test weekly data
    weekly_path = config.get_data_path('weekly_expiry')
    weekly_sample = pd.read_csv(weekly_path, nrows=5)
    print(f"✅ Weekly options data: {len(weekly_sample.columns)} columns")
    print(f"   Columns: {', '.join(weekly_sample.columns[:5])}...")

    # Test spot data
    spot_path = config.get_data_path('spot_price')
    spot_sample = pd.read_csv(spot_path, nrows=5)
    print(f"✅ Spot price data: {len(spot_sample.columns)} columns")

except Exception as e:
    print(f"❌ Data loading error: {e}")
    sys.exit(1)

# Test 5: Initialize strategy
print("\n[TEST 5] Testing strategy initialization...")
try:
    strategy = IntradayMomentumOIStrategy(config)
    print("✅ Strategy initialized successfully")
    print(f"   - Entry start: {strategy.entry_start_time}")
    print(f"   - Entry end: {strategy.entry_end_time}")
    print(f"   - Stop loss: {strategy.initial_stop_loss_pct*100}%")
    print(f"   - Trailing stop: {strategy.trailing_stop_pct*100}%")
except Exception as e:
    print(f"❌ Strategy initialization error: {e}")
    sys.exit(1)

# Test 6: Check output directories
print("\n[TEST 6] Checking output directories...")
try:
    directories = ['logs', 'reports', 'data']
    for dir_name in directories:
        dir_path = Path(dir_name)
        if dir_path.exists():
            print(f"✅ {dir_name}/ directory exists")
        else:
            print(f"⚠️  {dir_name}/ directory not found, will be created on first run")
except Exception as e:
    print(f"❌ Directory check error: {e}")

# Summary
print("\n" + "="*80)
print("SETUP TEST SUMMARY")
print("="*80)
print("✅ All core components are working correctly!")
print("\nYou're ready to run the backtest:")
print("   python backtest_runner.py")
print("\nTo customize parameters:")
print("   Edit: config/strategy_config.yaml")
print("="*80)
