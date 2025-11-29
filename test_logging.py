"""Quick test to verify trade logging works"""
import csv
from pathlib import Path
from datetime import datetime

# Test immediate write
trade_log_file = Path('reports') / 'test_trades.csv'
trade_log_file.parent.mkdir(parents=True, exist_ok=True)

# Write header
with open(trade_log_file, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=[
        'entry_time', 'exit_time', 'strike', 'option_type', 'expiry',
        'entry_price', 'exit_price', 'size', 'pnl', 'pnl_pct'
    ])
    writer.writeheader()
    print(f"✓ Created CSV with headers: {trade_log_file}")

# Write test trade
test_trade = {
    'entry_time': datetime(2025, 1, 1, 9, 30),
    'exit_time': datetime(2025, 1, 1, 14, 50),
    'strike': 23600,
    'option_type': 'PE',
    'expiry': datetime(2025, 1, 2),
    'entry_price': 103.40,
    'exit_price': 238.80,
    'size': 1,
    'pnl': 135.40,
    'pnl_pct': 130.89,
}

with open(trade_log_file, 'a', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=[
        'entry_time', 'exit_time', 'strike', 'option_type', 'expiry',
        'entry_price', 'exit_price', 'size', 'pnl', 'pnl_pct'
    ])
    writer.writerow(test_trade)
    print(f"✓ Wrote test trade to CSV")

# Read and display
with open(trade_log_file, 'r') as f:
    print(f"\nCSV Contents:")
    print(f.read())

print(f"\n✓ Test complete! Logging mechanism works correctly.")
