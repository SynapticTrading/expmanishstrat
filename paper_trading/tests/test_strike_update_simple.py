"""
Simple Strike Update Test

Tests the strike update logic in isolation by directly testing
the _get_options_for_entry method behavior.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

import unittest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
import pandas as pd
import pytz

from src.oi_analyzer import OIAnalyzer


class TestStrikeUpdateLogic(unittest.TestCase):
    """Test strike calculation logic"""

    def setUp(self):
        """Set up test fixtures"""
        # OIAnalyzer requires options_df but get_nearest_strike doesn't use it
        # Pass empty DataFrame for testing
        self.oi_analyzer = OIAnalyzer(pd.DataFrame())

    def test_call_strike_selection(self):
        """Test CALL strike selection for different spot prices"""

        spot_tests = [
            # (spot, expected_strike)
            (24875.0, 24900),  # Nearest >= 24875
            (24900.0, 24900),  # Exact match
            (24901.0, 24950),  # Just above 24900
            (24920.0, 24950),  # Mid-range
            (24950.0, 24950),  # Exact match
            (24975.0, 25000),  # Between strikes
            (25000.0, 25000),  # Exact match
            (25025.0, 25050),  # Above 25000
        ]

        for spot, expected_strike in spot_tests:
            # Available strikes around spot
            base = round(spot / 50) * 50
            available_strikes = [base + (i * 50) for i in range(-5, 6)]

            result_strike = self.oi_analyzer.get_nearest_strike(
                spot, 'CALL', available_strikes
            )

            self.assertEqual(int(result_strike), expected_strike,
                           f"CALL: Spot={spot}, Expected={expected_strike}, Got={result_strike}")
            print(f"✓ CALL: Spot {spot:.2f} -> Strike {int(result_strike)}")

    def test_put_strike_selection(self):
        """Test PUT strike selection for different spot prices"""

        spot_tests = [
            # (spot, expected_strike)
            (25025.0, 25000),  # Nearest < 25025
            (25000.0, 24950),  # Just at 25000, nearest below
            (24980.0, 24950),  # Mid-range
            (24950.0, 24900),  # Just at 24950, nearest below
            (24920.0, 24900),  # Between strikes
            (24900.0, 24850),  # Just at 24900, nearest below
            (24875.0, 24850),  # Mid-range
            (24850.0, 24800),  # Just at 24850, nearest below
        ]

        for spot, expected_strike in spot_tests:
            # Available strikes around spot
            base = round(spot / 50) * 50
            available_strikes = [base + (i * 50) for i in range(-5, 6)]

            result_strike = self.oi_analyzer.get_nearest_strike(
                spot, 'PUT', available_strikes
            )

            self.assertEqual(int(result_strike), expected_strike,
                           f"PUT: Spot={spot}, Expected={expected_strike}, Got={result_strike}")
            print(f"✓ PUT: Spot {spot:.2f} -> Strike {int(result_strike)}")

    def test_strike_changes_with_spot_movement(self):
        """Test that strike updates correctly as spot moves through day"""

        # Simulate CALL direction throughout a day
        print("\n" + "="*60)
        print("CALL Direction - Strike Updates Throughout Day")
        print("="*60)

        strike = 24900
        direction = 'CALL'

        spot_timeline = [
            (datetime(2026, 2, 2, 9, 30), 24875.0),   # Morning low
            (datetime(2026, 2, 2, 10, 0), 24863.0),   # Drops further
            (datetime(2026, 2, 2, 11, 0), 24773.0),   # Big drop
            (datetime(2026, 2, 2, 12, 0), 24874.0),   # Recovery
            (datetime(2026, 2, 2, 13, 0), 24938.0),   # Moving up
            (datetime(2026, 2, 2, 14, 0), 24948.0),   # Near 24950
            (datetime(2026, 2, 2, 15, 0), 25019.0),   # Big rally
        ]

        strike_updates = []

        for time_point, spot in spot_timeline:
            # Calculate available strikes
            base = round(spot / 50) * 50
            available_strikes = [base + (i * 50) for i in range(-10, 11)]

            # Get new strike
            new_strike = int(self.oi_analyzer.get_nearest_strike(
                spot, direction, available_strikes
            ))

            if new_strike != strike:
                strike_updates.append((time_point, spot, strike, new_strike))
                print(f"{time_point.strftime('%H:%M')} - Spot: {spot:7.2f} - "
                      f"Strike UPDATE: {strike} → {new_strike}")
                strike = new_strike
            else:
                print(f"{time_point.strftime('%H:%M')} - Spot: {spot:7.2f} - "
                      f"Strike UNCHANGED: {strike}")

        # Verify we had some strikes updates
        self.assertGreater(len(strike_updates), 0,
                          "Strike should update at least once as spot moves significantly")

        print(f"\n✓ Total strike updates: {len(strike_updates)}")

    def test_strike_stability_in_small_moves(self):
        """Test that strike doesn't change on small spot movements"""

        direction = 'CALL'
        initial_strike = 24900

        # Spot moves slightly around 24875-24890 (should stay at 24900 CALL)
        spot_prices = [24875.0, 24878.0, 24880.0, 24885.0, 24890.0, 24888.0, 24882.0]

        print("\n" + "="*60)
        print("Testing Strike Stability on Small Spot Movements")
        print("="*60)

        for spot in spot_prices:
            base = round(spot / 50) * 50
            available_strikes = [base + (i * 50) for i in range(-5, 6)]

            strike = int(self.oi_analyzer.get_nearest_strike(
                spot, direction, available_strikes
            ))

            self.assertEqual(strike, initial_strike,
                           f"Strike should stay at {initial_strike} for spot {spot}")
            print(f"Spot {spot:.2f} -> Strike {strike} ✓")

        print(f"\n✓ Strike remained stable at {initial_strike} throughout small movements")


class TestIntegrationScenario(unittest.TestCase):
    """Integration test simulating real scenario from logs"""

    def test_real_scenario_from_logs(self):
        """Test the exact scenario from the user's log where strike was stuck at 24950"""

        # OIAnalyzer requires options_df but get_nearest_strike doesn't use it
        oi_analyzer = OIAnalyzer(pd.DataFrame())
        direction = 'CALL'

        # Real data from logs - spot varied wildly but strike was stuck at 24950
        log_data = [
            ("10:00", 24863.30),
            ("10:05", 24816.65),
            ("10:10", 24810.55),
            ("11:00", 24773.00),
            ("11:25", 24686.75),  # Lowest point
            ("12:00", 24874.05),
            ("12:35", 24878.25),
            ("13:00", 24938.55),
            ("13:10", 24959.55),
            ("14:50", 24993.95),
            ("14:55", 25019.30),  # Highest point
        ]

        print("\n" + "="*60)
        print("Real Scenario Test - Strike Should Update (Was Stuck at 24950)")
        print("="*60)

        strikes_used = set()
        current_strike = None

        for time_str, spot in log_data:
            # Calculate available strikes
            base = round(spot / 50) * 50
            available_strikes = [base + (i * 50) for i in range(-10, 11)]

            # Get strike for this spot
            strike = int(oi_analyzer.get_nearest_strike(
                spot, direction, available_strikes
            ))

            strikes_used.add(strike)

            if strike != current_strike:
                print(f"[{time_str}] Spot: {spot:7.2f} -> Strike UPDATED: "
                      f"{current_strike or '----'} → {strike}")
                current_strike = strike
            else:
                print(f"[{time_str}] Spot: {spot:7.2f} -> Strike: {strike}")

        print(f"\n{'='*60}")
        print(f"All strikes used: {sorted(strikes_used)}")
        print(f"Total unique strikes: {len(strikes_used)}")
        print(f"{'='*60}")

        # Verify strike changed as spot moved
        self.assertGreater(len(strikes_used), 1,
                          "Strike should change as spot moves from 24686 to 25019")

        # Verify we're not stuck at 24950 throughout
        # At lowest spot (24686), CALL should be around 24700
        # At highest spot (25019), CALL should be around 25050
        self.assertIn(24700, strikes_used, "Should trade 24700 CE when spot is 24686")
        self.assertIn(25050, strikes_used, "Should trade 25050 CE when spot is 25019")

        print("\n✓ Test passed: Strikes update correctly with spot price movement")


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
