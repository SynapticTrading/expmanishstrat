"""
Test script to verify stop loss logic is working correctly
"""
import pandas as pd
from src.oi_analyzer import OIAnalyzer

# Load options data
print("Loading options data...")
df_options = pd.read_csv('DataDump/all_options_5min_2025_with_delta.csv')
df_options['timestamp'] = pd.to_datetime(df_options['timestamp'])
df_options['expiry'] = pd.to_datetime(df_options['expiry'])

# Rename timestamp to datetime to match expected format
df_options['datetime'] = df_options['timestamp']

print(f"Loaded {len(df_options)} option records\n")

# Initialize OI Analyzer
oi_analyzer = OIAnalyzer(df_options)

# Test case: The worst trade that lost -865%
print("=" * 70)
print("TEST CASE: Worst trade (Apr 17, strike 23450 CE)")
print("=" * 70)

entry_time = pd.Timestamp('2025-04-17 10:50:00')
strike = 23450
opt_type = 'CE'
expiry = pd.Timestamp('2025-04-17')
entry_price = 41.85
stop_loss = entry_price * 1.25

print(f"Entry: {entry_time} at ₹{entry_price}")
print(f"Stop loss: ₹{stop_loss:.2f}")
print(f"Expiry: {expiry.date()}\n")

# Test data retrieval at multiple timestamps
test_times = [
    entry_time + pd.Timedelta(minutes=5),   # 10:55
    entry_time + pd.Timedelta(minutes=10),  # 11:00
    entry_time + pd.Timedelta(minutes=15),  # 11:05
    entry_time + pd.Timedelta(minutes=20),  # 11:10
]

for check_time in test_times:
    option_data = oi_analyzer.get_option_price_data(
        strike=strike,
        option_type=opt_type,
        timestamp=check_time,
        expiry_date=expiry
    )

    if option_data is not None:
        price = option_data['close']
        data_time = option_data['datetime']
        should_stop = price >= stop_loss
        status = "🛑 STOP!" if should_stop else "✓ OK"
        print(f"{str(check_time)[11:16]}: Found data from {str(data_time)[11:16]}, price=₹{price:7.2f} {status}")
    else:
        print(f"{str(check_time)[11:16]}: ❌ NO DATA FOUND - THIS IS THE BUG!")

print("\n" + "=" * 70)
print("EXPECTED BEHAVIOR:")
print("=" * 70)
print("- Should find data at all timestamps")
print("- Should trigger stop at 11:05 when price reaches ₹55.20")
print("- If NO DATA FOUND appears, that's why stop loss didn't work!")
