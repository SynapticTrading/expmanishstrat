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
# Generic credential loader - works for both Zerodha and AngelOne
from paper_trading.legacy.zerodha_connection import load_credentials_from_file
from paper_trading.utils.factory import create_broker
from paper_trading.core.broker import PaperBroker
from paper_trading.core.strategy import IntradayMomentumOIPaper
from paper_trading.core.state_manager import StateManager
from paper_trading.core.contract_manager import ContractManager
import pandas as pd
import signal
import threading
import time as time_module
import logging
import os


def setup_logging():
    """
    Setup logging to both console and timestamped file
    Returns the path to the log file
    """
    # Get the paper_trading directory (where runner.py is located)
    paper_trading_dir = Path(__file__).parent

    # Create necessary directories
    logs_dir = paper_trading_dir / "logs"
    state_dir = paper_trading_dir / "state"
    logs_dir.mkdir(exist_ok=True)
    state_dir.mkdir(exist_ok=True)

    # Generate timestamped log filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = logs_dir / f"session_log_{timestamp}.txt"

    # Setup logging with both console and file handlers
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Remove any existing handlers
    logger.handlers = []

    # Save original stdout/stderr
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    # Console handler (uses original stdout)
    console_handler = logging.StreamHandler(original_stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler with immediate flushing
    # Open file with line buffering (mode 1) for immediate writes
    file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Redirect print statements to logger
    class LoggerWriter:
        def __init__(self, level, handlers):
            self.level = level
            self.handlers = handlers

        def write(self, message):
            if message.strip():  # Only log non-empty messages
                self.level(message.rstrip())
                # Flush all handlers immediately
                for handler in self.handlers:
                    handler.flush()

        def flush(self):
            # Flush all handlers
            for handler in self.handlers:
                handler.flush()

    # Redirect stdout and stderr to logger
    sys.stdout = LoggerWriter(logger.info, logger.handlers)
    sys.stderr = LoggerWriter(logger.error, logger.handlers)

    return log_file


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

        # State management (pass broker name for separate state files)
        # Use absolute path to ensure consistent location
        paper_trading_dir = Path(__file__).parent
        state_dir = paper_trading_dir / "state"
        self.state_manager = StateManager(state_dir=str(state_dir), broker_name=self.broker_api.name)
        self.ist = pytz.timezone('Asia/Kolkata')

        # Contract management for automatic expiry selection
        self.contract_manager = None  # Initialized after broker connection
        self.use_contract_manager = True  # Enable automatic contract management
        self.contract_monitor_interval = 300  # Check for contract updates every 5 minutes

        # Threading
        self.running = False
        self.exit_monitor_thread = None
        self.contract_monitor_thread = None
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

        # Initialize contract manager for automatic expiry selection
        # Reads from universal cache: /Users/Algo_Trading/manishsir_options/contracts_cache.json
        if self.use_contract_manager:
            print(f"[{self._get_ist_now()}] Initializing contract manager (reading from universal cache)...")
            try:
                self.contract_manager = ContractManager()
                print(f"[{self._get_ist_now()}] ✓ Contract manager initialized")

                # Show active expiry
                current_week = self.contract_manager.get_options_expiry('current_week')
                if current_week:
                    days = self.contract_manager._calculate_days_to_expiry(current_week)
                    print(f"[{self._get_ist_now()}] Active Weekly Expiry: {current_week} ({days} days)")

                    # Check rollover warning
                    if self.contract_manager.should_rollover_options('current_week', days_threshold=2):
                        next_week = self.contract_manager.get_options_expiry('next_week')
                        print(f"[{self._get_ist_now()}] ⚠️  ROLLOVER WARNING: Consider rolling to {next_week}")

            except Exception as e:
                print(f"[{self._get_ist_now()}] ⚠️  Contract manager initialization failed: {e}")
                print(f"[{self._get_ist_now()}] Falling back to broker's expiry detection...")
                self.contract_manager = None

        # Initialize paper broker
        print(f"[{self._get_ist_now()}] Initializing paper broker...")
        # Use absolute path for logs directory
        paper_trading_dir = Path(__file__).parent
        logs_dir = paper_trading_dir / "logs"
        self.paper_broker = PaperBroker(
            initial_capital,
            state_manager=self.state_manager,
            logs_dir=str(logs_dir),
            broker_name=self.broker_api.name  # Pass broker name for tracking
        )

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
            state_manager=self.state_manager,
            contract_manager=self.contract_manager
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
        if self.use_contract_manager and self.contract_manager:
            print(f"  Loop 3: Contract Monitor Loop - Every {self.contract_monitor_interval}s (Cache updates)")
        if self.recovery_mode:
            print(f"  MODE: RECOVERY (resumed from crash)")
        print(f"{'='*80}\n")

        # Start contract monitor thread BEFORE market open
        # This ensures cache updates are detected even when market is closed
        # (e.g., cronjob runs at 8:30 AM, before market open at 9:15 AM)
        if self.use_contract_manager and self.contract_manager:
            self.contract_monitor_thread = threading.Thread(
                target=self._contract_monitor_loop,
                name="ContractMonitor",
                daemon=True
            )
            self.contract_monitor_thread.start()
            print(f"[{self._get_ist_now()}] ✓ Contract monitor loop started (checks every {self.contract_monitor_interval}s)")

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

    def _contract_monitor_loop(self):
        """
        Contract monitor loop - runs every 5 minutes to check for contract cache updates.
        Automatically reloads contracts when cache is updated by cronjob.
        """
        print(f"[{self._get_ist_now()}] ✓ Contract monitor loop started (checks every {self.contract_monitor_interval}s)")

        while self.running:
            try:
                time_module.sleep(self.contract_monitor_interval)

                if not self.contract_manager:
                    continue

                # Check if cache file was updated externally (e.g., by cronjob)
                print(f"[{self._get_ist_now()}] 🔄 Contract monitor: Checking for cache updates...")
                cache_updated = self.contract_manager.check_and_reload_if_updated()

                if cache_updated:
                    print(f"[{self._get_ist_now()}] ✓ Contracts reloaded from cronjob update")

                    # Log updated expiry
                    current_week = self.contract_manager.get_options_expiry('current_week')
                    if current_week:
                        days = self.contract_manager._calculate_days_to_expiry(current_week)
                        print(f"[{self._get_ist_now()}] Active Weekly Expiry: {current_week} ({days} days)")

                        # Check rollover warning
                        if self.contract_manager.should_rollover_options('current_week', days_threshold=2):
                            next_week = self.contract_manager.get_options_expiry('next_week')
                            print(f"[{self._get_ist_now()}] ⚠️  ROLLOVER WARNING: Consider rolling to {next_week}")

                    # Update state with contract info
                    if current_week:
                        self.state_manager.state['strategy_state']['active_expiry'] = current_week
                        self.state_manager.save()
                else:
                    # Log that check completed (no updates)
                    current_week = self.contract_manager.get_options_expiry('current_week')
                    if current_week:
                        days = self.contract_manager._calculate_days_to_expiry(current_week)
                        print(f"[{self._get_ist_now()}] ✓ Contract check complete - No updates (Active: {current_week}, {days} days)")

            except Exception as e:
                print(f"[{self._get_ist_now()}] ✗ Error in contract monitor loop: {e}")
                import traceback
                traceback.print_exc()

    def _get_options_data(self, current_time, spot_price):
        """Get options chain data"""
        # Get next expiry - use contract manager if available
        if self.contract_manager:
            expiry = self.contract_manager.get_options_expiry('current_week')
            if not expiry:
                print(f"[{current_time}] ⚠️ Contract manager: No current week expiry, falling back to broker")
                expiry = self.broker_api.get_next_expiry()
        else:
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


def print_session_summary(log_file, start_time, trader=None):
    """Print end-of-session summary with file locations"""
    print("\n")
    print("=" * 80)
    print("Paper trading stopped")
    print("")
    print(f"Session log: {log_file}")
    print("")
    print("View files:")
    print(f"  Session log:  cat {log_file}")

    # Find latest trade log
    logs_dir = Path(log_file).parent
    trade_logs = sorted(logs_dir.glob("trades_*.csv"))
    if trade_logs:
        latest_trade_log = trade_logs[-1]
        print(f"  Trade log:    cat {latest_trade_log}")

    # Find latest state file
    state_dir = logs_dir.parent / "state"
    state_files = sorted(state_dir.glob("trading_state_*.json"))
    if state_files:
        latest_state = state_files[-1]
        print(f"  State (JSON): cat {latest_state} | jq .")

    print("")
    print("All paper trading files are in: paper_trading/")
    print("  - paper_trading/logs/       (session logs & trade CSVs)")
    print("  - paper_trading/state/      (state JSON files)")
    print("=" * 80)
    print("")


def main():
    """Main entry point"""
    # Setup logging first (creates directories and log file)
    log_file = setup_logging()
    start_time = datetime.now()

    # Print startup banner
    print("=" * 80)
    print("   PAPER TRADING LAUNCHER")
    print("=" * 80)
    print("")

    # Determine the paper_trading directory (where runner.py is located)
    paper_trading_dir = Path(__file__).parent

    parser = argparse.ArgumentParser(description='Universal Paper Trading System')
    parser.add_argument('--broker', choices=['zerodha', 'angelone'], help='Broker to use (auto-detected if not specified)')
    parser.add_argument('--config', help='Config file path')
    parser.add_argument('--credentials', help='Credentials file path (auto-selected if not specified)')

    args = parser.parse_args()

    # Set default config path relative to runner.py location
    if not args.config:
        args.config = str(paper_trading_dir / 'config' / 'config.yaml')

    # Auto-select credentials file based on broker
    if not args.credentials:
        if args.broker == 'zerodha':
            args.credentials = str(paper_trading_dir / 'config' / 'credentials_zerodha.txt')
        elif args.broker == 'angelone':
            args.credentials = str(paper_trading_dir / 'config' / 'credentials_angelone.txt')
        else:
            # Try Zerodha first
            zerodha_creds = paper_trading_dir / 'config' / 'credentials_zerodha.txt'
            angelone_creds = paper_trading_dir / 'config' / 'credentials_angelone.txt'

            if zerodha_creds.exists():
                args.credentials = str(zerodha_creds)
            elif angelone_creds.exists():
                args.credentials = str(angelone_creds)
            else:
                print("Error: No credentials file found!")
                print(f"Create either:")
                print(f"  - {zerodha_creds}")
                print(f"  - {angelone_creds}")
                return

    print("Starting paper trading...")
    print(f"Broker: {args.broker if args.broker else 'Auto-detect'}")
    print(f"Log file: {log_file}")
    print("")
    print("Press Ctrl+C to stop")
    print("=" * 80)
    print("")

    trader = None
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

    except KeyboardInterrupt:
        print("\n\nReceived interrupt signal, shutting down...")
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Print session summary
        print_session_summary(log_file, start_time, trader)


if __name__ == "__main__":
    main()
