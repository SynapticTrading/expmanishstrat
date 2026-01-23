#!/usr/bin/env python3
"""
Test the fixed boundary calculation
"""
from datetime import datetime, timedelta

def test_boundary(test_time_str):
    """Test boundary calculation for a given time"""
    # Parse test time
    test_time = datetime.strptime(test_time_str, "%H:%M:%S")
    test_time = test_time.replace(year=2026, month=1, day=23)

    # Calculate boundary (same logic as code)
    current_minute = test_time.minute
    boundary_minute = (current_minute // 5) * 5
    last_complete_boundary = test_time.replace(minute=boundary_minute, second=0, microsecond=0)

    # Calculate fetch window
    to_date = last_complete_boundary
    from_date = last_complete_boundary - timedelta(minutes=5)

    print(f"At {test_time_str}:")
    print(f"  Fetch: {from_date.strftime('%H:%M')} to {to_date.strftime('%H:%M')}")
    print()

print("="*60)
print("BOUNDARY CALCULATION TEST (FIXED)")
print("="*60)
print()

test_boundary("12:30:00")  # Should fetch 12:25-12:30? No! 12:30-12:35 candle just started, so last complete is 12:25-12:30
test_boundary("12:35:00")  # Should fetch 12:30-12:35 (just completed)
test_boundary("12:35:10")  # Should fetch 12:30-12:35
test_boundary("12:37:23")  # Should fetch 12:30-12:35
test_boundary("12:39:59")  # Should fetch 12:30-12:35
test_boundary("12:40:00")  # Should fetch 12:35-12:40 (just completed)
test_boundary("12:42:15")  # Should fetch 12:35-12:40

print("="*60)
print("EXPECTED: Each time gets the LAST COMPLETE candle!")
print("="*60)
