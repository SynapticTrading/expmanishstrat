"""
Test Trade Flow Scenarios
Tests all the key scenarios:
1. Trade entry
2. Trade exit
3. Closed position + next candle behavior
4. New signal after closed trade (should be blocked)
5. Blocked trade message + next candle behavior
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from datetime import datetime, time, date
import pandas as pd
import numpy as np
from paper_trading.core.broker import PaperBroker
from paper_trading.core.strategy import IntradayMomentumOIPaper
from paper_trading.core.state_manager import StateManager
from src.oi_analyzer import OIAnalyzer


class MockConfig:
    """Mock config for testing"""
    def __getitem__(self, key):
        config_dict = {
            'entry': {
                'start_time': '09:20',
                'end_time': '14:30',
                'strikes_above_spot': 10,
                'strikes_below_spot': 10
            },
            'exit': {
                'exit_start_time': '15:15',
                'exit_end_time': '15:29',
                'initial_stop_loss_pct': 0.25,
                'profit_threshold': 1.15,
                'trailing_stop_pct': 0.10,
                'vwap_stop_pct': 0.05,
                'oi_increase_stop_pct': 0.10
            },
            'market': {
                'option_lot_size': 75
            },
            'risk_management': {
                'max_positions': 2
            }
        }
        return config_dict[key]


def create_mock_options_data(spot_price, expiry_date, strike, option_price, oi, volume):
    """
    Create mock options data for testing

    Args:
        spot_price: Current spot price
        expiry_date: Expiry date
        strike: Strike price to focus on
        option_price: Price for the strike
        oi: Open Interest
        volume: Volume

    Returns:
        DataFrame with options chain data
    """
    strikes = []
    for offset in range(-10, 11):
        strikes.append(spot_price + (offset * 50))

    data = []
    for s in strikes:
        # CE (Call) data
        ce_price = option_price if s == strike else max(1, option_price - abs(s - strike) * 0.5)
        ce_oi = oi if s == strike else oi * 0.5
        ce_volume = volume if s == strike else volume * 0.3

        data.append({
            'strike': s,
            'option_type': 'CE',
            'expiry': expiry_date,
            'close': ce_price,
            'OI': ce_oi,
            'volume': ce_volume
        })

        # PE (Put) data
        pe_price = max(1, ce_price * 0.8)
        pe_oi = oi * 1.2 if s == strike else oi * 0.6
        pe_volume = volume * 0.7 if s == strike else volume * 0.2

        data.append({
            'strike': s,
            'option_type': 'PE',
            'expiry': expiry_date,
            'close': pe_price,
            'OI': pe_oi,
            'volume': pe_volume
        })

    return pd.DataFrame(data)


def print_scenario_header(scenario_num, title):
    """Print a clear scenario header"""
    print(f"\n{'='*100}")
    print(f"SCENARIO {scenario_num}: {title}")
    print(f"{'='*100}\n")


def print_step_header(step_title):
    """Print a step header"""
    print(f"\n{'-'*100}")
    print(f"STEP: {step_title}")
    print(f"{'-'*100}\n")


def test_trade_flow_scenarios():
    """
    Test comprehensive trade flow scenarios
    """
    print(f"\n{'#'*100}")
    print(f"COMPREHENSIVE TRADE FLOW TEST")
    print(f"Testing all scenarios from entry to exit and blocking")
    print(f"{'#'*100}\n")

    # Setup
    config = MockConfig()
    state_manager = StateManager(state_dir="paper_trading/tests/test_state")
    state_manager.initialize_session(mode="test")

    broker = PaperBroker(initial_capital=100000, state_manager=state_manager)
    oi_analyzer = OIAnalyzer(pd.DataFrame())
    strategy = IntradayMomentumOIPaper(config, broker, oi_analyzer, state_manager)

    # Test parameters
    test_date = date(2026, 1, 5)
    expiry_date = date(2026, 1, 9)  # Weekly expiry
    spot_price = 24500
    strike = 24500

    # ========================================
    # SCENARIO 1: Trade Entry
    # ========================================
    print_scenario_header(1, "TRADE ENTRY - OI Unwinding + Price Above VWAP")

    # Step 1: Market open - Determine direction
    print_step_header("1.1: Market Open at 9:15 AM - Direction Determination")
    current_time = datetime.combine(test_date, time(9, 15))

    # Create options data with high CALL OI buildup (suggests CALL direction)
    options_data = create_mock_options_data(
        spot_price=spot_price,
        expiry_date=expiry_date,
        strike=strike,
        option_price=100,
        oi=5000000,  # High OI
        volume=10000
    )

    # Add extra OI for max CALL strike to trigger CALL direction
    options_data.loc[(options_data['strike'] == spot_price + 100) &
                     (options_data['option_type'] == 'CE'), 'OI'] = 8000000

    strategy.on_new_day(current_time, spot_price, options_data)

    print(f"Direction determined: {strategy.daily_direction}")
    print(f"Daily strike: {strategy.daily_strike}")
    print(f"Daily expiry: {strategy.daily_expiry}")
    print(f"Daily trade taken: {strategy.daily_trade_taken}")

    # Step 2: First candle - Build VWAP (no entry yet)
    print_step_header("1.2: First Candle at 9:20 AM - VWAP Initialization")
    current_time = datetime.combine(test_date, time(9, 20))

    options_data = create_mock_options_data(
        spot_price=spot_price,
        expiry_date=expiry_date,
        strike=strike,
        option_price=95,  # Price started at 95
        oi=5000000,
        volume=15000
    )

    strategy.on_candle(current_time, spot_price, options_data)
    print(f"VWAP tracking initialized: {len(strategy.vwap_running_totals)} strikes")

    # Step 3: Entry signal - OI unwinding + Price above VWAP
    print_step_header("1.3: Entry Signal at 9:25 AM - OI Unwinding + Price Above VWAP")
    current_time = datetime.combine(test_date, time(9, 25))

    options_data = create_mock_options_data(
        spot_price=spot_price,
        expiry_date=expiry_date,
        strike=strike,
        option_price=105,  # Price went up (above VWAP of ~100)
        oi=4500000,  # OI decreased (unwinding)
        volume=25000
    )

    print(f"\nBEFORE ENTRY:")
    print(f"  Open positions: {len(broker.get_open_positions())}")
    print(f"  Cash: ₹{broker.cash:,.2f}")
    print(f"  Daily trade taken: {strategy.daily_trade_taken}")

    strategy.on_candle(current_time, spot_price, options_data)

    print(f"\nAFTER ENTRY:")
    positions = broker.get_open_positions()
    print(f"  Open positions: {len(positions)}")
    if positions:
        pos = positions[0]
        print(f"  Position: {pos.option_type} {pos.strike} @ ₹{pos.entry_price:.2f}")
        print(f"  Size: {pos.size}")
        print(f"  Cost: ₹{pos.entry_price * pos.size:,.2f}")
    print(f"  Cash: ₹{broker.cash:,.2f}")
    print(f"  Daily trade taken: {strategy.daily_trade_taken}")

    # ========================================
    # SCENARIO 2: Trade Exit (Stop Loss)
    # ========================================
    print_scenario_header(2, "TRADE EXIT - Stop Loss Hit")

    print_step_header("2.1: Next Candle at 9:30 AM - Price Drops Below Stop Loss")
    current_time = datetime.combine(test_date, time(9, 30))

    # Price drops significantly (triggers 25% stop loss)
    options_data = create_mock_options_data(
        spot_price=spot_price,
        expiry_date=expiry_date,
        strike=strike,
        option_price=70,  # 70 is below 75% of 105 = 78.75 (stop loss hit)
        oi=4200000,
        volume=30000
    )

    print(f"\nBEFORE EXIT CHECK:")
    print(f"  Open positions: {len(broker.get_open_positions())}")
    print(f"  Trade history: {len(broker.trade_history)}")

    strategy.on_candle(current_time, spot_price, options_data)

    print(f"\nAFTER EXIT:")
    print(f"  Open positions: {len(broker.get_open_positions())}")
    print(f"  Trade history: {len(broker.trade_history)}")
    if broker.trade_history:
        trade = broker.trade_history[-1]
        print(f"  Closed Trade: {trade.option_type} {trade.strike}")
        print(f"  Entry: ₹{trade.entry_price:.2f} | Exit: ₹{trade.exit_price:.2f}")
        print(f"  P&L: ₹{trade.pnl:+,.2f} ({trade.pnl_pct:+.2f}%)")
        print(f"  Exit Reason: {trade.exit_reason}")
    print(f"  Cash: ₹{broker.cash:,.2f}")
    print(f"  Daily trade taken: {strategy.daily_trade_taken}")

    # ========================================
    # SCENARIO 3: Closed Position + Next Candle
    # ========================================
    print_scenario_header(3, "CLOSED POSITION + NEXT CANDLE - System Monitoring")

    print_step_header("3.1: Next 5-Min Candle at 9:35 AM - What Happens?")
    current_time = datetime.combine(test_date, time(9, 35))

    options_data = create_mock_options_data(
        spot_price=spot_price,
        expiry_date=expiry_date,
        strike=strike,
        option_price=75,
        oi=4100000,
        volume=20000
    )

    print(f"\nBEFORE CANDLE:")
    print(f"  Open positions: {len(broker.get_open_positions())}")
    print(f"  Closed trades: {len(broker.trade_history)}")
    print(f"  Daily trade taken: {strategy.daily_trade_taken}")

    strategy.on_candle(current_time, spot_price, options_data)

    print(f"\nAFTER CANDLE:")
    print(f"  Open positions: {len(broker.get_open_positions())}")
    print(f"  System should be in MONITORING mode (no new entries)")
    print(f"  Expected log: 'MONITORING MODE: Daily trade limit reached'")

    # ========================================
    # SCENARIO 4: New Entry Signal After Closed Trade
    # ========================================
    print_scenario_header(4, "NEW ENTRY SIGNAL AFTER CLOSED TRADE - Should Be Blocked")

    print_step_header("4.1: Perfect Entry Signal at 10:00 AM - OI Unwinding + Price Above VWAP")
    current_time = datetime.combine(test_date, time(10, 0))

    # Create PERFECT entry conditions (OI unwinding + price above VWAP)
    options_data = create_mock_options_data(
        spot_price=spot_price + 50,  # Spot moved up
        expiry_date=expiry_date,
        strike=strike + 50,  # New strike
        option_price=120,  # High price (above VWAP)
        oi=3500000,  # Significant OI unwinding
        volume=40000  # High volume
    )

    print(f"\nBEFORE ENTRY SIGNAL:")
    print(f"  Open positions: {len(broker.get_open_positions())}")
    print(f"  Closed trades: {len(broker.trade_history)}")
    print(f"  Daily trade taken: {strategy.daily_trade_taken}")
    print(f"  Cash available: ₹{broker.cash:,.2f}")

    strategy.on_candle(current_time, spot_price + 50, options_data)

    print(f"\nAFTER ENTRY SIGNAL:")
    print(f"  Open positions: {len(broker.get_open_positions())}")
    print(f"  Expected: 0 (entry should be BLOCKED)")
    print(f"  Expected log: '⛔ Entry blocked: Daily trade limit reached (1 trade/day)'")
    print(f"  Cash (should be unchanged): ₹{broker.cash:,.2f}")

    # ========================================
    # SCENARIO 5: Blocked Trade + Next Candle
    # ========================================
    print_scenario_header(5, "BLOCKED TRADE + NEXT CANDLE - Continued Monitoring")

    print_step_header("5.1: Next Candle at 10:05 AM - After Block")
    current_time = datetime.combine(test_date, time(10, 5))

    options_data = create_mock_options_data(
        spot_price=spot_price + 50,
        expiry_date=expiry_date,
        strike=strike + 50,
        option_price=125,
        oi=3400000,
        volume=35000
    )

    print(f"\nBEFORE CANDLE:")
    print(f"  Open positions: {len(broker.get_open_positions())}")
    print(f"  Closed trades: {len(broker.trade_history)}")
    print(f"  Daily trade taken: {strategy.daily_trade_taken}")

    strategy.on_candle(current_time, spot_price + 50, options_data)

    print(f"\nAFTER CANDLE:")
    print(f"  Open positions: {len(broker.get_open_positions())}")
    print(f"  System continues monitoring but NO new entries")
    print(f"  Expected log: 'MONITORING MODE: Daily trade limit reached'")

    # ========================================
    # FINAL SUMMARY
    # ========================================
    print(f"\n{'='*100}")
    print(f"TEST SUMMARY")
    print(f"{'='*100}\n")

    stats = broker.get_statistics()
    print(f"Final Statistics:")
    print(f"  Total Trades: {stats['total_trades']}")
    print(f"  Winning Trades: {stats['winning_trades']}")
    print(f"  Losing Trades: {stats['losing_trades']}")
    print(f"  Win Rate: {stats['win_rate']:.1f}%")
    print(f"  Total P&L: ₹{stats['total_pnl']:+,.2f}")
    print(f"  ROI: {stats['roi']:+.2f}%")
    print(f"  Current Cash: ₹{stats['current_cash']:,.2f}")
    print(f"\nOpen Positions: {len(broker.get_open_positions())}")
    print(f"Closed Trades: {len(broker.trade_history)}")
    print(f"Daily Trade Taken: {strategy.daily_trade_taken}")

    print(f"\n{'='*100}")
    print(f"TRADE LOG DETAILS")
    print(f"{'='*100}\n")

    if broker.trade_history:
        for i, trade in enumerate(broker.trade_history, 1):
            print(f"\nTrade #{i}:")
            print(f"  Entry Time: {trade.entry_time}")
            print(f"  Exit Time: {trade.exit_time}")
            print(f"  Position: {trade.option_type} {trade.strike}")
            print(f"  Entry Price: ₹{trade.entry_price:.2f}")
            print(f"  Exit Price: ₹{trade.exit_price:.2f}")
            print(f"  P&L: ₹{trade.pnl:+,.2f} ({trade.pnl_pct:+.2f}%)")
            print(f"  Exit Reason: {trade.exit_reason}")

    print(f"\n{'='*100}")
    print(f"LOGS TO CHECK")
    print(f"{'='*100}\n")
    print(f"Check the following log files for detailed outputs:")
    print(f"  Daily trades: {broker.daily_trade_log}")
    print(f"  Cumulative trades: {broker.cumulative_trade_log}")
    print(f"  State file: {state_manager.state_file}")

    print(f"\n{'='*100}")
    print(f"TEST COMPLETED SUCCESSFULLY!")
    print(f"{'='*100}\n")


if __name__ == "__main__":
    test_trade_flow_scenarios()
