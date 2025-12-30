#!/usr/bin/env python3
"""
Standalone Test: Real-time LTP Monitoring
Tests that the exit monitor fetches REAL-TIME LTP every minute, not stale data

This simulates what the exit monitor does and verifies:
1. LTP is fetched every minute
2. LTP values CHANGE (not stuck/cached)
3. API calls are working
"""

import sys
from pathlib import Path
# Add project root to path (go up two levels from paper_trading/tests/)
sys.path.append(str(Path(__file__).parent.parent.parent))

from datetime import datetime, timedelta
import time
from paper_trading.legacy.zerodha_connection import load_credentials_from_file
from paper_trading.utils.factory import create_broker
import pandas as pd

class LTPMonitorTest:
    def __init__(self):
        print("\n" + "="*80)
        print("REAL-TIME LTP MONITORING TEST")
        print("="*80)
        print("\nThis test will:")
        print("1. Connect to Zerodha")
        print("2. Fetch LTP for a specific option EVERY MINUTE")
        print("3. Log the values to verify they're changing")
        print("4. Prove we're getting real-time data, not cached")
        print("\n" + "="*80 + "\n")

        # Load credentials
        credentials = load_credentials_from_file('paper_trading/config/credentials_zerodha.txt')
        if not credentials:
            raise Exception("Failed to load credentials!")

        # Create broker
        print("Connecting to Zerodha...")
        self.broker_api = create_broker(credentials, 'zerodha')
        if not self.broker_api.connect():
            raise Exception("Failed to connect to Zerodha")

        print("✓ Connected to Zerodha\n")

        # Load instruments
        print("Loading instruments...")
        if not self.broker_api.load_instruments():
            raise Exception("Failed to load instruments")
        print("✓ Instruments loaded\n")

        # Get test option
        self.test_strike = None
        self.test_expiry = None
        self.ltp_history = []

    def get_test_option(self):
        """Get a test option to monitor"""
        # Get spot price
        spot_price = self.broker_api.get_spot_price()
        print(f"Current Nifty Spot: {spot_price:.2f}")

        # Get next expiry
        expiry = self.broker_api.get_next_expiry()
        print(f"Next Expiry: {expiry}")

        # Round to nearest 50
        strike = round(spot_price / 50) * 50

        self.test_strike = strike
        self.test_expiry = expiry

        print(f"\n✓ Will monitor: PUT {strike} (Expiry: {expiry})")
        print(f"  This is an ATM option, should have good liquidity\n")

    def fetch_ltp_once(self):
        """Fetch LTP for the test option"""
        # Get options chain
        strikes = [self.test_strike]
        options_data = self.broker_api.get_options_chain(self.test_expiry, strikes)

        if options_data is None or options_data.empty:
            return None, None

        # Find the PUT option (option_type is 'PE' for PUT)
        put_option = options_data[
            (options_data['strike'] == self.test_strike) &
            (options_data['option_type'] == 'PE')
        ]

        if put_option.empty:
            return None, None

        ltp = put_option.iloc[0]['close']
        oi = put_option.iloc[0]['OI']

        return ltp, oi

    def run_test(self, duration_minutes=5, interval_seconds=60):
        """
        Run the LTP monitoring test

        Args:
            duration_minutes: How long to run the test
            interval_seconds: How often to check LTP (default: 60 = 1 minute)
        """
        self.get_test_option()

        print("="*80)
        print(f"STARTING {duration_minutes}-MINUTE LTP MONITORING TEST")
        print(f"Checking every {interval_seconds} seconds")
        print("="*80)
        print(f"\nTest Option: PUT {self.test_strike} (Expiry: {self.test_expiry})")
        print(f"Start Time: {datetime.now().strftime('%H:%M:%S')}")
        print(f"Expected End: {(datetime.now() + timedelta(minutes=duration_minutes)).strftime('%H:%M:%S')}")
        print("\nPress Ctrl+C to stop early\n")
        print("-"*80)

        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=duration_minutes)
        check_count = 0

        try:
            while datetime.now() < end_time:
                check_count += 1
                current_time = datetime.now()

                # Fetch LTP
                print(f"\n[Check #{check_count}] {current_time.strftime('%H:%M:%S')} - Fetching LTP...")
                ltp, oi = self.fetch_ltp_once()

                if ltp is None:
                    print("  ✗ Failed to fetch LTP")
                    time.sleep(interval_seconds)
                    continue

                # Store in history
                self.ltp_history.append({
                    'time': current_time,
                    'ltp': ltp,
                    'oi': oi
                })

                # Calculate change from previous
                if len(self.ltp_history) > 1:
                    prev_ltp = self.ltp_history[-2]['ltp']
                    change = ltp - prev_ltp
                    change_pct = (change / prev_ltp * 100) if prev_ltp > 0 else 0

                    change_indicator = "📈" if change > 0 else "📉" if change < 0 else "➡️"

                    print(f"  ✓ LTP: ₹{ltp:.2f} | OI: {oi:,.0f}")
                    print(f"    {change_indicator} Change: ₹{change:+.2f} ({change_pct:+.2f}%) from previous")
                else:
                    print(f"  ✓ LTP: ₹{ltp:.2f} | OI: {oi:,.0f}")
                    print(f"    (First reading - no comparison)")

                # Wait for next check
                if datetime.now() < end_time:
                    wait_seconds = min(interval_seconds, (end_time - datetime.now()).total_seconds())
                    if wait_seconds > 0:
                        print(f"\n  Waiting {int(wait_seconds)}s for next check...")
                        time.sleep(wait_seconds)

        except KeyboardInterrupt:
            print("\n\n✗ Test interrupted by user")

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)

        if not self.ltp_history:
            print("✗ No LTP data collected")
            return

        print(f"\nTotal LTP Checks: {len(self.ltp_history)}")
        print(f"Option: PUT {self.test_strike} (Expiry: {self.test_expiry})")
        print(f"\nLTP History:")
        print("-"*80)

        # Show all readings
        for i, reading in enumerate(self.ltp_history, 1):
            time_str = reading['time'].strftime('%H:%M:%S')
            ltp = reading['ltp']
            oi = reading['oi']

            if i > 1:
                prev_ltp = self.ltp_history[i-2]['ltp']
                change = ltp - prev_ltp
                change_pct = (change / prev_ltp * 100) if prev_ltp > 0 else 0
                change_str = f"({change:+.2f}, {change_pct:+.2f}%)"
            else:
                change_str = "(baseline)"

            print(f"  {i}. [{time_str}] ₹{ltp:.2f} | OI: {oi:,.0f} {change_str}")

        # Analysis
        print("\n" + "-"*80)
        print("ANALYSIS:")

        ltps = [r['ltp'] for r in self.ltp_history]
        unique_ltps = len(set(ltps))

        print(f"  Unique LTP values: {unique_ltps} out of {len(ltps)} readings")

        if unique_ltps == 1:
            print(f"  ❌ FAIL: LTP stuck at ₹{ltps[0]:.2f} (using STALE DATA!)")
        elif unique_ltps < len(ltps) * 0.3:
            print(f"  ⚠️  WARNING: Only {unique_ltps} unique values - may be using cached data")
        else:
            print(f"  ✅ PASS: LTP values changing (using REAL-TIME data!)")

        # Price range
        min_ltp = min(ltps)
        max_ltp = max(ltps)
        ltp_range = max_ltp - min_ltp
        avg_ltp = sum(ltps) / len(ltps)

        print(f"\n  Price Range: ₹{min_ltp:.2f} - ₹{max_ltp:.2f} (Range: ₹{ltp_range:.2f})")
        print(f"  Average LTP: ₹{avg_ltp:.2f}")

        # OI analysis
        ois = [r['oi'] for r in self.ltp_history]
        if len(set(ois)) > 1:
            print(f"  OI also changing: {min(ois):,.0f} - {max(ois):,.0f}")

        print("\n" + "="*80)

        # Verdict
        if unique_ltps > len(ltps) * 0.5:
            print("\n✅ VERDICT: Exit monitor is using REAL-TIME LTP data!")
        elif unique_ltps > 1:
            print("\n⚠️  VERDICT: Exit monitor is getting some data, but may be partially cached")
        else:
            print("\n❌ VERDICT: Exit monitor is using STALE/CACHED data!")

        print("="*80 + "\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Test real-time LTP monitoring')
    parser.add_argument('--duration', type=int, default=5, help='Test duration in minutes (default: 5)')
    parser.add_argument('--interval', type=int, default=60, help='Check interval in seconds (default: 60)')

    args = parser.parse_args()

    try:
        test = LTPMonitorTest()
        test.run_test(duration_minutes=args.duration, interval_seconds=args.interval)

    except KeyboardInterrupt:
        print("\n\n✗ Test interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
