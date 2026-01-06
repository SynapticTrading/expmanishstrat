"""
Universal Paper Trading Runner
Supports multiple brokers (Zerodha, AngelOne) with automatic state recovery
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from datetime import datetime
import argparse
import pytz
from src.config_loader import ConfigLoader
from src.oi_analyzer import OIAnalyzer
from paper_trading.legacy.zerodha_connection import load_credentials_from_file
from paper_trading.utils.factory import create_broker
from paper_trading.core.broker import PaperBroker
from paper_trading.core.strategy import IntradayMomentumOIPaper
from paper_trading.core.state_manager import StateManager
import pandas as pd
import signal
import threading
import time as time_module


class UniversalPaperTrader:
    """Universal paper trader supporting multiple brokers"""

    def __init__(self, config_path, credentials_path, broker_type=None):
        """
        Initialize paper trader

        Args:
            config_path: Path to config YAML
            credentials_path: Path to credentials file
            broker_type: 'zerodha' or 'angelone' (auto-detected if None)
        """
        print(f"\n{'='*80}")
        print(f"UNIVERSAL PAPER TRADING SYSTEM")
        print(f"{'='*80}\n")

        # Load config
        print(f"Loading configuration...")
        config_loader = ConfigLoader(config_path)
        self.config = config_loader.load()

        # Load credentials
        print(f"Loading credentials from: {credentials_path}")
        self.credentials = load_credentials_from_file(credentials_path)
        if not self.credentials:
            raise Exception("Failed to load credentials!")

        # Create broker
        print(f"Creating broker instance...")
        self.broker_api = create_broker(self.credentials, broker_type)
        print(f"✓ Broker: {self.broker_api.name}")

        # Components
        self.paper_broker = None
        self.strategy = None
        self.oi_analyzer = None

        # State management
        self.state_manager = StateManager()
        self.ist = pytz.timezone('Asia/Kolkata')

        # Threading
        self.running = False
        self.exit_monitor_thread = None
        self.exit_monitor_lock = threading.Lock()

        # Shared data
        self.current_spot_price = None
        self.current_options_data = None
        self.position_order_ids = {}

        # Recovery mode flag
        self.recovery_mode = False
        self.recovery_info = None

        # Signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _get_ist_now(self):
        """Get current IST time"""
        return datetime.now(self.ist)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\n[{self._get_ist_now()}] Shutting down gracefully...")
        self.running = False

    def try_recover_state(self):
        """
        Try to recover from previous session

        Returns:
            bool: True if recovery successful
        """
        print(f"\n[{self._get_ist_now()}] Checking for previous session...")

        # Try to load today's state
        loaded_state = self.state_manager.load()

        if not loaded_state:
            print(f"[{self._get_ist_now()}] No previous state found - starting fresh")
            return False

        # Check if can recover
        if not self.state_manager.can_recover():
            print(f"[{self._get_ist_now()}] Previous state found but nothing to recover - starting fresh")
            return False

        # Get recovery info
        self.recovery_info = self.state_manager.get_recovery_info()

        print(f"\n{'='*80}")
        print(f"CRASH RECOVERY DETECTED")
        print(f"{'='*80}")
        print(f"Last Activity: {self.recovery_info['crash_time']}")
        print(f"Downtime: ~{self.recovery_info['downtime_minutes']} minutes")
        print(f"Active Positions: {self.recovery_info['active_positions_count']}")
        print(f"Daily P&L: ₹{self.recovery_info['daily_stats'].get('total_pnl_today', 0):,.2f}")
        print(f"{'='*80}\n")

        # Check for open positions
        has_open_positions = self.recovery_info.get('active_positions_count', 0) > 0

        if has_open_positions:
            # FORCE recovery - cannot abandon positions
            print(f"⚠️  CRITICAL: {self.recovery_info['active_positions_count']} open position(s) detected!")
            print(f"Cannot start fresh session with active positions.")
            print(f"Automatically resuming from crash...\n")

            self.recovery_mode = True
            self.state_manager.resume_session()
            return True
        else:
            # No positions - safe to ask user
            response = input("Resume from crash? (y/n): ").strip().lower()

            if response == 'y':
                print(f"\n[{self._get_ist_now()}] Resuming session...")
                self.recovery_mode = True
                self.state_manager.resume_session()
                return True
            else:
                print(f"\n[{self._get_ist_now()}] Starting fresh session...")
                return False

    def connect(self):
        """Connect to broker"""
        print(f"\n[{self._get_ist_now()}] Connecting to {self.broker_api.name}...")

        if not self.broker_api.connect():
            raise Exception(f"Failed to connect to {self.broker_api.name}")

        print(f"[{self._get_ist_now()}] ✓ Connected to {self.broker_api.name}")

    def initialize(self):
        """Initialize components"""

        # Initialize or resume state
        if not self.recovery_mode:
            print(f"\n[{self._get_ist_now()}] Initializing new session...")

            # IMPORTANT: Check for previous portfolio BEFORE creating today's state file
            previous_portfolio = self.state_manager.get_latest_portfolio()

            if previous_portfolio:
                # Carry forward portfolio from previous day
                initial_capital = previous_portfolio['current_cash']
                print(f"[{self._get_ist_now()}] 📊 PORTFOLIO CARRYOVER")
                print(f"  Previous Date: {previous_portfolio['previous_date']}")
                print(f"  Starting Capital: ₹{initial_capital:,.2f}")
                print(f"  Previous P&L: ₹{previous_portfolio['total_pnl']:+,.2f}")
                print(f"  Previous Trades: {previous_portfolio['trades_count']}")
                print(f"  Previous Win Rate: {previous_portfolio['win_rate']:.1f}%")
            else:
                # First time running - use config
                initial_capital = self.config['position_sizing']['initial_capital']
                print(f"[{self._get_ist_now()}] 🆕 First session - Starting with ₹{initial_capital:,.2f}")

            # Now create today's state file
            self.state_manager.initialize_session(mode="paper")
        else:
            print(f"\n[{self._get_ist_now()}] Resuming from previous session...")
            initial_capital = self.recovery_info['portfolio'].get('current_cash', 100000)

        # Update system health
        self.state_manager.update_system_health(
            broker_connected=True,
            data_feed_status="INITIALIZING"
        )

        # Load instruments
        print(f"[{self._get_ist_now()}] Loading instruments...")
        if not self.broker_api.load_instruments():
            print(f"[{self._get_ist_now()}] ⚠ Could not load instruments (may not affect operation)")

        # Initialize paper broker
        print(f"[{self._get_ist_now()}] Initializing paper broker...")
        self.paper_broker = PaperBroker(initial_capital, state_manager=self.state_manager)

        # Restore positions if recovering from crash
        if self.recovery_mode and self.recovery_info:
            saved_positions_dict = self.recovery_info.get('active_positions', {})
            if saved_positions_dict:
                # Convert dict to list of position objects
                saved_positions = list(saved_positions_dict.values())
                self.paper_broker.restore_positions(saved_positions)

            # Restore closed trades (trade history)
            closed_positions = self.recovery_info.get('closed_positions', [])
            if closed_positions:
                self.paper_broker.restore_trade_history(closed_positions)

        # Update portfolio state
        if not self.recovery_mode:
            self.state_manager.state["portfolio"]["initial_capital"] = initial_capital
            self.state_manager.state["portfolio"]["current_cash"] = initial_capital

        # Initialize OI analyzer
        print(f"[{self._get_ist_now()}] Initializing OI analyzer...")
        dummy_options_df = pd.DataFrame()
        self.oi_analyzer = OIAnalyzer(dummy_options_df)

        # Initialize strategy
        print(f"[{self._get_ist_now()}] Initializing strategy...")
        self.strategy = IntradayMomentumOIPaper(
            config=self.config,
            broker=self.paper_broker,
            oi_analyzer=self.oi_analyzer,
            state_manager=self.state_manager
        )

        # Restore strategy state if recovering
        if self.recovery_mode and self.recovery_info:
            print(f"[{self._get_ist_now()}] Restoring strategy state...")
            self._restore_strategy_state(self.recovery_info['strategy_state'])

        # Update system health
        self.state_manager.update_system_health(data_feed_status="ACTIVE")
        self.state_manager.save()

        print(f"[{self._get_ist_now()}] ✓ All components initialized")

    def _restore_strategy_state(self, strategy_state):
        """Restore strategy state from saved data"""
        self.strategy.daily_direction = strategy_state.get('direction')
        self.strategy.daily_strike = strategy_state.get('trading_strike')

        # Restore current_date to prevent on_new_day() from resetting flags
        if self.state_manager.state and 'date' in self.state_manager.state:
            from datetime import datetime
            date_str = self.state_manager.state['date']
            self.strategy.current_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            print(f"  Restored current_date: {self.strategy.current_date}")

        # Restore expiry from positions (active or closed)
        expiry_restored = False

        # Try active positions first
        if self.recovery_info.get('active_positions'):
            active_positions_dict = self.recovery_info.get('active_positions', {})
            if active_positions_dict:
                first_position = list(active_positions_dict.values())[0]
                self.strategy.daily_expiry = first_position.get('expiry')
                expiry_restored = True

        # If no active positions, try closed positions
        if not expiry_restored and self.recovery_info.get('closed_positions'):
            closed_positions = self.recovery_info.get('closed_positions', [])
            if closed_positions:
                first_closed = closed_positions[0]
                self.strategy.daily_expiry = first_closed.get('expiry')
                expiry_restored = True
                print(f"  Restored expiry from closed position: {self.strategy.daily_expiry}")

        # Restore daily_trade_taken flag - if there are open positions OR closed trades, trade was taken
        has_open_positions = self.recovery_info.get('active_positions_count', 0) > 0
        has_closed_trades = len(self.recovery_info.get('closed_positions', [])) > 0
        trades_today = self.recovery_info.get('daily_stats', {}).get('trades_today', 0)

        if has_open_positions or has_closed_trades or trades_today > 0:
            self.strategy.daily_trade_taken = True
            reason = []
            if has_open_positions:
                reason.append("has open positions")
            if has_closed_trades:
                reason.append("has closed trades")
            if trades_today > 0:
                reason.append(f"trades_today={trades_today}")
            print(f"  Restored daily_trade_taken: True ({', '.join(reason)})")

        # Restore VWAP tracking
        # Note: This is simplified - you may need to reconstruct full VWAP state

        print(f"  Restored direction: {self.strategy.daily_direction}")
        print(f"  Restored strike: {self.strategy.daily_strike}")
        print(f"  Restored expiry: {self.strategy.daily_expiry}")

    def run(self):
        """Main trading loop"""
        self.running = True

        print(f"\n{'='*80}")
        print(f"[{self._get_ist_now()}] Starting DUAL-LOOP paper trading...")
        print(f"  Broker: {self.broker_api.name}")
        print(f"  Loop 1: Strategy Loop - Every 5 minutes (Entry decisions)")
        print(f"  Loop 2: Exit Monitor Loop - Every 1 minute (LTP-based exits)")
        if self.recovery_mode:
            print(f"  MODE: RECOVERY (resumed from crash)")
        print(f"{'='*80}\n")

        # Wait for market open
        while self.running and not self.broker_api.is_market_open():
            print(f"[{self._get_ist_now()}] Market closed, waiting...")
            time_module.sleep(60)

        # Start exit monitor thread
        self.exit_monitor_thread = threading.Thread(
            target=self._exit_monitor_loop,
            name="ExitMonitor",
            daemon=True
        )
        self.exit_monitor_thread.start()
        print(f"[{self._get_ist_now()}] ✓ Exit monitor loop started")

        # Update system health
        self.state_manager.update_system_health(
            ltp_loop_running=True,
            strategy_loop_running=True
        )
        self.state_manager.save()

        # Run strategy loop
        self._strategy_loop()

        # Cleanup
        self.cleanup()

    def _strategy_loop(self):
        """Strategy loop - runs every 5 minutes"""
        print(f"[{self._get_ist_now()}] ✓ Strategy loop started")

        while self.running:
            try:
                current_time = self._get_ist_now()

                # Check market open
                if not self.broker_api.is_market_open():
                    print(f"[{current_time}] Market closed, stopping...")
                    break

                # Check if past EOD exit time
                current_time_only = current_time.time()
                exit_end = self.strategy.exit_end_time
                if current_time_only > exit_end:
                    print(f"[{current_time}] Past EOD exit time ({exit_end}), stopping...")
                    break

                print(f"\n{'='*80}")
                print(f"[{current_time}] STRATEGY LOOP - Processing 5-min candle...")
                print(f"{'='*80}\n")

                # Get spot price
                spot_price = self.broker_api.get_spot_price()
                if not spot_price:
                    print(f"[{current_time}] ✗ Failed to get spot price, skipping...")
                    self.broker_api.wait_for_next_candle()
                    continue

                print(f"[{current_time}] Nifty Spot: {spot_price:.2f}")

                # Check if in monitoring-only mode (trade already taken)
                if self.strategy.daily_trade_taken and len(self.paper_broker.get_open_positions()) == 0:
                    print(f"[{current_time}] 📊 MONITORING MODE: Daily trade limit reached (1/1 trades taken)")
                    print(f"[{current_time}] System will continue monitoring but will NOT enter new trades")

                # Get options data
                options_data = self._get_options_data(current_time, spot_price)

                if options_data.empty:
                    print(f"[{current_time}] ✗ No options data, skipping...")
                    self.broker_api.wait_for_next_candle()
                    continue

                # Update shared data
                with self.exit_monitor_lock:
                    self.current_spot_price = spot_price
                    self.current_options_data = options_data

                # Process candle
                self.strategy.on_candle(current_time, spot_price, options_data)

                # Update state
                self.state_manager.update_api_stats('5min')
                self.state_manager.save()

                # Print status
                self._print_status()

                # Wait for next candle
                self.broker_api.wait_for_next_candle()

            except Exception as e:
                print(f"[{self._get_ist_now()}] ✗ Error in strategy loop: {e}")
                import traceback
                traceback.print_exc()
                time_module.sleep(60)

    def _exit_monitor_loop(self):
        """Exit monitor loop - runs every 1 minute to monitor exits with real-time LTP"""
        print(f"[{self._get_ist_now()}] ✓ Exit monitor loop started (1-min LTP)")

        while self.running:
            try:
                # Only check if market is open
                if not self.broker_api.is_market_open():
                    time_module.sleep(60)
                    continue

                # Get current time
                current_time = self._get_ist_now()

                # Check if past EOD exit time
                current_time_only = current_time.time()
                exit_end = self.strategy.exit_end_time
                if current_time_only > exit_end:
                    print(f"[{current_time}] Exit Monitor: Past EOD exit time ({exit_end}), stopping...")
                    break

                positions = self.paper_broker.get_open_positions()

                if not positions:
                    # No positions to monitor, just wait
                    time_module.sleep(60)
                    continue

                # Fetch FRESH real-time LTP data (not 5-min cached data)
                spot_price = self.broker_api.get_spot_price()
                if not spot_price:
                    print(f"[{current_time}] ⚠️ Exit Monitor: Could not get spot price, skipping...")
                    time_module.sleep(60)
                    continue

                # Fetch fresh options chain with real-time LTP
                print(f"[{current_time}] 🔍 Exit Monitor: Fetching real-time LTP for {len(positions)} position(s)...")
                options_data = self._get_options_data(current_time, spot_price)
                if options_data is None or options_data.empty:
                    print(f"[{current_time}] ⚠️ Exit Monitor: Could not get options data, skipping...")
                    time_module.sleep(60)
                    continue

                # Check exits using strategy logic with REAL-TIME LTP
                self.strategy._check_exits(current_time, options_data)

                # Update state
                self.state_manager.update_api_stats('1min')
                self.state_manager.save()

                time_module.sleep(60)

            except Exception as e:
                print(f"[{self._get_ist_now()}] ✗ Error in exit monitor loop: {e}")
                import traceback
                traceback.print_exc()
                time_module.sleep(60)

    def _get_options_data(self, current_time, spot_price):
        """Get options chain data"""
        # Get next expiry
        expiry = self.broker_api.get_next_expiry()
        if not expiry:
            return pd.DataFrame()

        # Calculate strikes
        strikes_above = self.config['entry']['strikes_above_spot']
        strikes_below = self.config['entry']['strikes_below_spot']

        strike_interval = 50
        base_strike = round(spot_price / strike_interval) * strike_interval

        strikes = []
        for i in range(-strikes_below, strikes_above + 1):
            strikes.append(base_strike + (i * strike_interval))

        # Fetch options chain
        options_df = self.broker_api.get_options_chain(expiry, strikes)
        return options_df if options_df is not None else pd.DataFrame()

    def _print_status(self):
        """Print current status"""
        status = self.strategy.get_status()
        stats = status['statistics']

        print(f"\n{'-'*80}")
        print(f"STATUS UPDATE")
        print(f"{'-'*80}")
        print(f"Date: {status['current_date']}")
        print(f"Broker: {self.broker_api.name}")
        print(f"Daily Direction: {status['daily_direction']} @ {status['daily_strike']}")
        print(f"Open Positions: {status['open_positions']}")
        print(f"Total P&L: ₹{stats['total_pnl']:,.2f}")
        print(f"ROI: {stats['roi']:+.2f}%")
        print(f"{'-'*80}\n")

    def cleanup(self):
        """Cleanup and shutdown"""
        print(f"\n{'='*80}")
        print(f"[{self._get_ist_now()}] Shutting down...")
        print(f"{'='*80}\n")

        self.running = False

        # Stop exit monitor
        if self.exit_monitor_thread and self.exit_monitor_thread.is_alive():
            self.exit_monitor_thread.join(timeout=5)

        # Update system health
        self.state_manager.update_system_health(
            ltp_loop_running=False,
            strategy_loop_running=False
        )
        self.state_manager.save()

        # Print final stats
        if self.paper_broker:
            stats = self.paper_broker.get_statistics()
            print(f"Final Statistics:")
            print(f"  Total Trades: {stats['total_trades']}")
            print(f"  Win Rate: {stats['win_rate']:.1f}%")
            print(f"  Total P&L: ₹{stats['total_pnl']:,.2f}")
            print(f"  ROI: {stats['roi']:+.2f}%")

        # Logout
        if self.broker_api:
            self.broker_api.logout()

        print(f"\n[{self._get_ist_now()}] ✓ Shutdown complete")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Universal Paper Trading System')
    parser.add_argument('--broker', choices=['zerodha', 'angelone'], help='Broker to use (auto-detected if not specified)')
    parser.add_argument('--config', default='paper_trading/config/config.yaml', help='Config file path')
    parser.add_argument('--credentials', help='Credentials file path (auto-selected if not specified)')

    args = parser.parse_args()

    # Auto-select credentials file based on broker
    if not args.credentials:
        if args.broker == 'zerodha':
            args.credentials = 'paper_trading/config/credentials_zerodha.txt'
        elif args.broker == 'angelone':
            args.credentials = 'paper_trading/config/credentials_angelone.txt'
        else:
            # Try Zerodha first
            if Path('paper_trading/config/credentials_zerodha.txt').exists():
                args.credentials = 'paper_trading/config/credentials_zerodha.txt'
            elif Path('paper_trading/config/credentials_angelone.txt').exists():
                args.credentials = 'paper_trading/config/credentials_angelone.txt'
            else:
                print("Error: No credentials file found!")
                print("Create either config/credentials_zerodha.txt or config/credentials_angelone.txt")
                return

    try:
        # Create trader
        trader = UniversalPaperTrader(args.config, args.credentials, args.broker)

        # Try to recover from crash
        trader.try_recover_state()

        # Connect
        trader.connect()

        # Initialize
        trader.initialize()

        # Run
        trader.run()

    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
