"""
Integration Test: Runner Strike Update

This test verifies the exact flow of how strikes are updated in the runner's
_get_options_for_entry method when spot price changes.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

import unittest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime
import pandas as pd
import pytz
import tempfile
import yaml

from paper_trading.runner import UniversalPaperTrader


class TestRunnerStrikeUpdate(unittest.TestCase):
    """Test strike updates in the actual runner code"""

    def setUp(self):
        """Set up test fixtures with temporary config files"""

        # Create temporary config file
        self.config_data = {
            'strategy': {'name': 'Test', 'type': 'Test'},
            'data': {'timeframe': 5, 'timezone': 'Asia/Kolkata'},
            'market': {
                'instrument': 'NIFTY',
                'expiry_type': 'weekly',
                'option_lot_size': 65,
                'trading_hours': {'start': '09:15', 'end': '15:30'}
            },
            'entry': {
                'start_time': '09:30',
                'end_time': '15:30',
                'strikes_above_spot': 5,
                'strikes_below_spot': 5
            },
            'exit': {
                'exit_start_time': '15:29',
                'exit_end_time': '15:30',
                'initial_stop_loss_pct': 0.25,
                'profit_threshold': 1.10,
                'trailing_stop_pct': 0.10,
                'vwap_stop_pct': 0.05,
                'oi_increase_stop_pct': 0.10
            },
            'position_sizing': {'initial_capital': 100000},
            'risk_management': {'max_positions': 2, 'avoid_monday_tuesday': False},
            'broker': {'name': 'zerodha'},
            'trading_mode': {
                'mode': 'paper',
                'live_settings': {'product_type': 'INTRADAY', 'order_type': 'MARKET'}
            },
            'logging': {'log_dir': 'paper_trading/logs', 'log_level': 'INFO'},
            'backtest': {'commission': 0.0005, 'slippage': 0.0}
        }

        # Create temp config file
        self.config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        yaml.dump(self.config_data, self.config_file)
        self.config_file.close()

        # Create temp credentials file
        self.creds_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
        self.creds_file.write("api_key:test_key\napi_secret:test_secret\n")
        self.creds_file.close()

    def tearDown(self):
        """Clean up temp files"""
        import os
        os.unlink(self.config_file.name)
        os.unlink(self.creds_file.name)

    def test_strike_updates_call_direction(self):
        """Test CALL direction strike updates as spot moves"""

        print("\n" + "="*80)
        print("TEST: CALL Direction Strike Updates")
        print("="*80)

        # Create mocks
        with patch('paper_trading.runner.create_adapter') as mock_create_adapter, \
             patch('paper_trading.runner.PaperBroker') as MockBroker, \
             patch('paper_trading.runner.IntradayMomentumOIPaper') as MockStrategy, \
             patch('paper_trading.runner.StateManager') as MockStateManager, \
             patch('paper_trading.runner.ContractManager') as MockContractManager:

            # Mock adapter
            mock_adapter = Mock()
            mock_adapter.broker_name = 'zerodha'
            mock_adapter.get_next_expiry.return_value = '2026-02-03'
            mock_create_adapter.return_value = mock_adapter

            # Mock broker
            mock_broker = Mock()
            mock_broker.get_open_positions.return_value = []
            MockBroker.return_value = mock_broker

            # Mock strategy
            mock_strategy = Mock()
            mock_strategy.oi_analyzer = Mock()
            mock_strategy.daily_direction = 'CALL'
            mock_strategy.daily_strike = 24900  # Initial strike
            mock_strategy.daily_expiry = '2026-02-03'
            MockStrategy.return_value = mock_strategy

            # Mock contract manager
            mock_contract_manager = Mock()
            mock_contract_manager.get_options_expiry.return_value = '2026-02-03'
            MockContractManager.return_value = mock_contract_manager

            # Create runner
            runner = UniversalPaperTrader(
                config_path=self.config_file.name,
                credentials_path=self.creds_file.name,
                trading_mode='paper'
            )

            # Mock _get_ltp_for_entry to track what strike is requested
            ltp_calls = []
            def mock_get_ltp(current_time, strike, option_type, expiry):
                ltp_calls.append({
                    'strike': strike,
                    'option_type': option_type,
                    'spot_at_call': runner.strategy.daily_strike
                })
                return pd.DataFrame([{
                    'strike': strike,
                    'option_type': option_type,
                    'expiry': expiry,
                    'close': 100.0,
                    'OI': 1000000,
                    'volume': 500000
                }])

            runner._get_ltp_for_entry = Mock(side_effect=mock_get_ltp)

            # Test scenarios
            test_cases = [
                {'spot': 24875.0, 'expected_strike': 24900, 'description': 'Initial - spot at 24875'},
                {'spot': 24920.0, 'expected_strike': 24950, 'description': 'Spot moves to 24920'},
                {'spot': 24880.0, 'expected_strike': 24900, 'description': 'Spot drops to 24880'},
                {'spot': 24960.0, 'expected_strike': 25000, 'description': 'Spot jumps to 24960'},
                {'spot': 25025.0, 'expected_strike': 25050, 'description': 'Spot rises to 25025'},
            ]

            current_time = datetime.now(pytz.timezone('Asia/Kolkata'))

            print("\nRunning strike update simulation:\n")

            for i, test_case in enumerate(test_cases):
                spot = test_case['spot']
                expected = test_case['expected_strike']
                desc = test_case['description']

                # Mock get_nearest_strike to return correct strike
                base = round(spot / 50) * 50
                available = [base + (j * 50) for j in range(-5, 6)]
                upper_strikes = [s for s in available if s >= spot]
                calculated_strike = min(upper_strikes) if upper_strikes else None

                runner.strategy.oi_analyzer.get_nearest_strike.return_value = calculated_strike

                # Call the method
                print(f"Candle {i+1}: {desc}")
                print(f"  Spot Price: {spot:.2f}")

                old_strike = runner.strategy.daily_strike

                options_df = runner._get_options_for_entry(current_time, spot)

                new_strike = runner.strategy.daily_strike

                # Verify
                self.assertEqual(new_strike, expected,
                    f"Strike should be {expected} for spot {spot}, got {new_strike}")

                if old_strike != new_strike:
                    print(f"  📍 STRIKE UPDATED: {old_strike} → {new_strike}")
                else:
                    print(f"  Strike unchanged: {new_strike}")

                # Verify LTP was fetched for the correct strike
                last_call = ltp_calls[-1]
                self.assertEqual(last_call['strike'], expected,
                    f"LTP should be fetched for strike {expected}, got {last_call['strike']}")

                print(f"  ✓ LTP fetched for strike: {last_call['strike']}")
                print()

            print("="*80)
            print(f"✅ All {len(test_cases)} scenarios passed!")
            print("="*80)

            # Summary
            print("\nStrike Update Summary:")
            print(f"  Total candles processed: {len(test_cases)}")
            print(f"  Total LTP calls made: {len(ltp_calls)}")
            print(f"  Strikes used: {sorted(set(call['strike'] for call in ltp_calls))}")

    def test_strike_updates_put_direction(self):
        """Test PUT direction strike updates as spot moves"""

        print("\n" + "="*80)
        print("TEST: PUT Direction Strike Updates")
        print("="*80)

        # Create mocks
        with patch('paper_trading.runner.create_adapter') as mock_create_adapter, \
             patch('paper_trading.runner.PaperBroker') as MockBroker, \
             patch('paper_trading.runner.IntradayMomentumOIPaper') as MockStrategy, \
             patch('paper_trading.runner.StateManager') as MockStateManager, \
             patch('paper_trading.runner.ContractManager') as MockContractManager:

            # Mock adapter
            mock_adapter = Mock()
            mock_adapter.broker_name = 'zerodha'
            mock_adapter.get_next_expiry.return_value = '2026-02-03'
            mock_create_adapter.return_value = mock_adapter

            # Mock broker
            mock_broker = Mock()
            mock_broker.get_open_positions.return_value = []
            MockBroker.return_value = mock_broker

            # Mock strategy
            mock_strategy = Mock()
            mock_strategy.oi_analyzer = Mock()
            mock_strategy.daily_direction = 'PUT'
            mock_strategy.daily_strike = 25000  # Initial strike
            mock_strategy.daily_expiry = '2026-02-03'
            MockStrategy.return_value = mock_strategy

            # Mock contract manager
            mock_contract_manager = Mock()
            mock_contract_manager.get_options_expiry.return_value = '2026-02-03'
            MockContractManager.return_value = mock_contract_manager

            # Create runner
            runner = UniversalPaperTrader(
                config_path=self.config_file.name,
                credentials_path=self.creds_file.name,
                trading_mode='paper'
            )

            # Mock _get_ltp_for_entry to track what strike is requested
            ltp_calls = []
            def mock_get_ltp(current_time, strike, option_type, expiry):
                ltp_calls.append({
                    'strike': strike,
                    'option_type': option_type
                })
                return pd.DataFrame([{
                    'strike': strike,
                    'option_type': option_type,
                    'expiry': expiry,
                    'close': 100.0,
                    'OI': 1000000,
                    'volume': 500000
                }])

            runner._get_ltp_for_entry = Mock(side_effect=mock_get_ltp)

            # Test scenarios
            test_cases = [
                {'spot': 25025.0, 'expected_strike': 25000, 'description': 'Initial - spot at 25025'},
                {'spot': 24980.0, 'expected_strike': 24950, 'description': 'Spot drops to 24980'},
                {'spot': 25010.0, 'expected_strike': 25000, 'description': 'Spot rises to 25010'},
                {'spot': 24720.0, 'expected_strike': 24700, 'description': 'Spot falls to 24720'},
                {'spot': 24875.0, 'expected_strike': 24850, 'description': 'Spot moves to 24875'},
            ]

            current_time = datetime.now(pytz.timezone('Asia/Kolkata'))

            print("\nRunning strike update simulation:\n")

            for i, test_case in enumerate(test_cases):
                spot = test_case['spot']
                expected = test_case['expected_strike']
                desc = test_case['description']

                # Mock get_nearest_strike to return correct strike
                base = round(spot / 50) * 50
                available = [base + (j * 50) for j in range(-5, 6)]
                lower_strikes = [s for s in available if s < spot]
                calculated_strike = max(lower_strikes) if lower_strikes else None

                runner.strategy.oi_analyzer.get_nearest_strike.return_value = calculated_strike

                # Call the method
                print(f"Candle {i+1}: {desc}")
                print(f"  Spot Price: {spot:.2f}")

                old_strike = runner.strategy.daily_strike

                options_df = runner._get_options_for_entry(current_time, spot)

                new_strike = runner.strategy.daily_strike

                # Verify
                self.assertEqual(new_strike, expected,
                    f"Strike should be {expected} for spot {spot}, got {new_strike}")

                if old_strike != new_strike:
                    print(f"  📍 STRIKE UPDATED: {old_strike} → {new_strike}")
                else:
                    print(f"  Strike unchanged: {new_strike}")

                # Verify LTP was fetched for the correct strike
                last_call = ltp_calls[-1]
                self.assertEqual(last_call['strike'], expected,
                    f"LTP should be fetched for strike {expected}, got {last_call['strike']}")

                print(f"  ✓ LTP fetched for strike: {last_call['strike']}")
                print()

            print("="*80)
            print(f"✅ All {len(test_cases)} scenarios passed!")
            print("="*80)


    def test_real_log_scenario_reproduction(self):
        """Reproduce exact scenario from user's logs where strike was stuck"""

        print("\n" + "="*80)
        print("TEST: Real Log Scenario - Strike Was Stuck at 24950")
        print("="*80)

        # Create mocks
        with patch('paper_trading.runner.create_adapter') as mock_create_adapter, \
             patch('paper_trading.runner.PaperBroker') as MockBroker, \
             patch('paper_trading.runner.IntradayMomentumOIPaper') as MockStrategy, \
             patch('paper_trading.runner.StateManager') as MockStateManager, \
             patch('paper_trading.runner.ContractManager') as MockContractManager:

            # Setup mocks
            mock_adapter = Mock()
            mock_adapter.broker_name = 'zerodha'
            mock_adapter.get_next_expiry.return_value = '2026-02-03'
            mock_create_adapter.return_value = mock_adapter

            mock_broker = Mock()
            mock_broker.get_open_positions.return_value = []
            MockBroker.return_value = mock_broker

            mock_strategy = Mock()
            mock_strategy.oi_analyzer = Mock()
            mock_strategy.daily_direction = 'CALL'
            mock_strategy.daily_strike = 24950  # STUCK at this value in the bug
            mock_strategy.daily_expiry = '2026-02-03'
            MockStrategy.return_value = mock_strategy

            mock_contract_manager = Mock()
            mock_contract_manager.get_options_expiry.return_value = '2026-02-03'
            MockContractManager.return_value = mock_contract_manager

            # Create runner
            runner = UniversalPaperTrader(
                config_path=self.config_file.name,
                credentials_path=self.creds_file.name,
                trading_mode='paper'
            )

            # Track LTP calls
            ltp_calls = []
            def mock_get_ltp(current_time, strike, option_type, expiry):
                ltp_calls.append(strike)
                return pd.DataFrame([{
                    'strike': strike,
                    'option_type': option_type,
                    'expiry': expiry,
                    'close': 100.0,
                    'OI': 1000000,
                    'volume': 500000
                }])

            runner._get_ltp_for_entry = Mock(side_effect=mock_get_ltp)

            # Real data from user's logs
            real_log_data = [
                ('10:00', 24863.30),
                ('10:05', 24816.65),
                ('11:00', 24773.00),
                ('11:25', 24686.75),  # Lowest
                ('12:00', 24874.05),
                ('12:35', 24878.25),
                ('13:00', 24938.55),
                ('13:10', 24959.55),
                ('14:50', 24993.95),
                ('14:55', 25019.30),  # Highest
            ]

            current_time = datetime.now(pytz.timezone('Asia/Kolkata'))

            print("\nBEFORE FIX: Strike would be stuck at 24950")
            print("AFTER FIX: Strike should update dynamically\n")

            strikes_used = set()

            for time_str, spot in real_log_data:
                # Calculate what strike should be
                base = round(spot / 50) * 50
                available = [base + (j * 50) for j in range(-5, 6)]
                upper_strikes = [s for s in available if s >= spot]
                expected_strike = min(upper_strikes) if upper_strikes else None

                runner.strategy.oi_analyzer.get_nearest_strike.return_value = expected_strike

                old_strike = runner.strategy.daily_strike
                options_df = runner._get_options_for_entry(current_time, spot)
                new_strike = runner.strategy.daily_strike

                strikes_used.add(new_strike)

                if old_strike != new_strike:
                    print(f"[{time_str}] Spot: {spot:7.2f} → 📍 STRIKE UPDATED: {old_strike} → {new_strike}")
                else:
                    print(f"[{time_str}] Spot: {spot:7.2f} → Strike: {new_strike}")

            print("\n" + "="*80)
            print(f"Strikes used: {sorted(strikes_used)}")
            print(f"Total unique strikes: {len(strikes_used)}")
            print("="*80)

            # Verify we're not stuck at one strike
            self.assertGreater(len(strikes_used), 1,
                "Strike should change as spot moves, not stay stuck at one value")

            # Verify we used appropriate strikes for extreme prices
            self.assertIn(24700, strikes_used, "Should use 24700 CE when spot is 24686")
            self.assertIn(25050, strikes_used, "Should use 25050 CE when spot is 25019")

            print("\n✅ TEST PASSED: Strikes update dynamically (not stuck at 24950!)")


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
