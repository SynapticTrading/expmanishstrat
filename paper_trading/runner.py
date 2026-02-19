"""
Universal Paper Trading Runner
Supports multiple brokers (Zerodha, AngelOne) with automatic state recovery

FULLY MIGRATED: Uses BrokerAdapter for ALL broker operations.
The old broker_api (BrokerInterface) is no longer used.
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
from paper_trading.core.broker import PaperBroker
from paper_trading.core.strategy import IntradayMomentumOIPaper
from paper_trading.core.state_manager import StateManager
from paper_trading.core.contract_manager import ContractManager
# Broker adapter for unified interface - FULLY MIGRATED
from paper_trading.brokers.adapter import create_adapter
from paper_trading.data_store.data_recorder import DataRecorder
import datetime as _dt
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

    def __init__(self, config_path, credentials_path, broker_type=None, trading_mode=None):
        """
        Initialize paper trader

        Args:
            config_path: Path to config YAML
            credentials_path: Path to credentials file
            broker_type: 'zerodha' or 'angelone' (auto-detected if None)
            trading_mode: 'paper' or 'live' (from command-line, overrides config)
        """
        print(f"\n{'='*80}")
        print(f"UNIVERSAL TRADING SYSTEM (Adapter-Based)")
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

        # Store broker type and trading mode for later adapter creation
        self.broker_type = broker_type
        self.trading_mode_override = trading_mode  # Command-line override

        # Determine broker name for state management (auto-detect if not specified)
        if broker_type:
            broker_name = broker_type
        else:
            # Auto-detect from credentials
            if 'api_secret' in self.credentials:
                broker_name = 'zerodha'
            elif 'username' in self.credentials and 'api_key' in self.credentials:
                broker_name = 'angelone'
            else:
                broker_name = 'paper'
        print(f"✓ Broker: {broker_name}")

        # Components
        self.paper_broker = None
        self.strategy = None
        self.oi_analyzer = None
        self.recorder = None  # DataRecorder for persistent market data + VWAP storage

        # Contract management for automatic expiry selection
        self.contract_manager = None  # Initialized before adapter connection
        self.use_contract_manager = True  # Enable automatic contract management
        self.contract_monitor_interval = 300  # Check for contract updates every 5 minutes

        # Broker adapter - FULLY MIGRATED: this is the ONLY broker interface
        self.adapter = None  # Initialized in connect()

        # State management - initialized early for crash recovery
        paper_trading_dir = Path(__file__).parent
        state_dir = paper_trading_dir / "state"
        self.state_manager = StateManager(state_dir=str(state_dir), broker_name=broker_name)
        self.ist = pytz.timezone('Asia/Kolkata')

        # Threading
        self.running = False
        self.exit_monitor_thread = None
        self.contract_monitor_thread = None
        # THREAD SAFETY: Lock to prevent concurrent exit checks causing duplicate sells
        self.exit_monitor_lock = threading.Lock()
        # Track last 5-min boundary where VWAP was updated in the exit monitor loop
        self.last_vwap_boundary = None

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

    def _confirm_live_trading(self):
        """Require user confirmation before live trading"""
        if not self.config['trading_mode']['live_settings'].get('require_confirmation', True):
            print(f"\n⚠️  Live trading confirmation DISABLED in config ⚠️")
            return True

        print("\n" + "="*80)
        print("⚠️  LIVE TRADING MODE ACTIVATED ⚠️")
        print("="*80)
        print("\nThis will place REAL orders with REAL money!")
        print(f"Broker: {self.adapter.broker_name}")
        print(f"Product Type: {self.config['trading_mode']['live_settings']['product_type']}")
        print(f"Order Type: {self.config['trading_mode']['live_settings']['order_type']}")

        # Display safety limits (if configured)
        max_order_value = self.config['trading_mode']['live_settings'].get('max_order_value')
        max_daily_loss = self.config['trading_mode']['live_settings'].get('max_daily_loss')

        if max_order_value:
            print(f"Max Order Value: ₹{max_order_value:,.2f}")
        else:
            print(f"Max Order Value: No limit (relying on strategy stop losses)")

        if max_daily_loss:
            print(f"Max Daily Loss: ₹{max_daily_loss:,.2f}")
        else:
            print(f"Max Daily Loss: No limit (relying on strategy stop losses)")

        # Get account info
        try:
            funds = self.adapter.get_funds()
            if funds:
                print(f"\nAccount Balance: ₹{funds.available_cash:,.2f}")
        except Exception as e:
            print(f"\n⚠️  Could not fetch account balance: {e}")

        print("\n" + "="*80)
        response = input("\nType 'CONFIRM LIVE TRADING' to proceed: ")

        return response == 'CONFIRM LIVE TRADING'

    def _check_global_trades_today(self):
        """
        Check cumulative CSV for any trades today (from ANY broker AND any mode).
        This ensures 1 trade/day limit works globally, not per broker or mode.

        Returns:
            int: Number of trades today across all brokers and modes
        """
        try:
            logs_dir = Path(__file__).parent / "logs"
            today = self._get_ist_now().date()
            total_trades_today = 0

            import pandas as pd

            # Check BOTH paper and live cumulative CSVs
            csv_files = [
                logs_dir / "trades_cumulative.csv",        # Paper trades
                logs_dir / "live_trades_cumulative.csv"    # Live trades
            ]

            for cumulative_csv in csv_files:
                if not cumulative_csv.exists():
                    continue

                try:
                    df = pd.read_csv(cumulative_csv)
                    if df.empty:
                        continue

                    # Parse entry_time and count trades from today
                    df['entry_date'] = pd.to_datetime(df['entry_time']).dt.date
                    trades = len(df[df['entry_date'] == today])
                    total_trades_today += trades

                    if trades > 0:
                        mode = "live" if "live_trades" in str(cumulative_csv) else "paper"
                        print(f"[{self._get_ist_now()}] 📊 GLOBAL TRADE CHECK: Found {trades} {mode} trade(s) today in {cumulative_csv.name}")

                except Exception as e:
                    print(f"[{self._get_ist_now()}] ⚠️  Error reading {cumulative_csv.name}: {e}")
                    continue

            return total_trades_today
        except Exception as e:
            print(f"[{self._get_ist_now()}] ⚠️  Error checking global trades: {e}")
            return 0

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

        # CRITICAL: Set mode BEFORE trying to load state
        # Otherwise load() won't find the correct paper/live state file
        trading_mode = self.config['trading_mode']['mode']
        if self.trading_mode_override:
            trading_mode = self.trading_mode_override

        self.state_manager.mode = trading_mode
        print(f"[{self._get_ist_now()}] Looking for {trading_mode.upper()} mode state file...")

        # Try to load today's state (will use mode from state_manager.mode)
        loaded_state = self.state_manager.load()

        if not loaded_state:
            print(f"[{self._get_ist_now()}] No previous {trading_mode.upper()} state found - starting fresh")
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
        else:
            # No open positions but has previous session data
            print(f"✓ AUTOMATIC RECOVERY: Previous session detected")
            print(f"Automatically resuming from crash...\n")

        # Always automatically recover - no user input required
        self.recovery_mode = True
        self.state_manager.resume_session()
        return True

    def connect(self):
        """Connect to broker via adapter"""
        # Initialize contract manager FIRST (before adapter needs it)
        # ContractManager uses UNIVERSAL exchange tokens (same for all brokers)
        if self.use_contract_manager:
            print(f"[{self._get_ist_now()}] Initializing contract manager (reading from universal cache)...")
            try:
                self.contract_manager = ContractManager()
                print(f"[{self._get_ist_now()}] ✓ Contract manager initialized (using universal exchange tokens)")

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

        # Create adapter with contract_manager for token-based lookups
        print(f"[{self._get_ist_now()}] Creating broker adapter...")
        self.adapter = create_adapter(
            self.credentials,
            broker=self.broker_type,
            contract_manager=self.contract_manager
        )
        print(f"[{self._get_ist_now()}] ✓ Adapter created: {self.adapter.broker_name}")

        # Connect adapter
        print(f"[{self._get_ist_now()}] Connecting to {self.adapter.broker_name}...")
        if not self.adapter.connect():
            raise Exception(f"Failed to connect to {self.adapter.broker_name}")

        print(f"[{self._get_ist_now()}] ✓ Connected to {self.adapter.broker_name}")

    def initialize(self):
        """Initialize components"""

        # Determine trading mode (command-line overrides config)
        trading_mode = self.config['trading_mode']['mode']
        if self.trading_mode_override:
            trading_mode = self.trading_mode_override
            self.config['trading_mode']['mode'] = trading_mode
            print(f"\n[{self._get_ist_now()}] Trading mode overridden to: {trading_mode}")

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
            self.state_manager.initialize_session(mode=trading_mode)
        else:
            print(f"\n[{self._get_ist_now()}] Resuming from previous session...")
            initial_capital = self.recovery_info['portfolio'].get('current_cash', 100000)

        # Update system health
        self.state_manager.update_system_health(
            broker_connected=True,
            data_feed_status="INITIALIZING"
        )

        # Load instruments via adapter
        print(f"[{self._get_ist_now()}] Loading instruments...")
        if not self.adapter.load_instruments():
            print(f"[{self._get_ist_now()}] ⚠ Could not load instruments (may not affect operation)")

        # Log adapter status
        if self.contract_manager and self.contract_manager.has_instrument_tokens():
            print(f"[{self._get_ist_now()}] ✓ Adapter ready with token-based lookups")
        else:
            print(f"[{self._get_ist_now()}] ✓ Adapter ready (symbol-based fallback)")

        # Initialize broker based on mode
        paper_trading_dir = Path(__file__).parent
        logs_dir = paper_trading_dir / "logs"

        if trading_mode == 'live':
            # Require confirmation
            if not self._confirm_live_trading():
                print("\n⛔ Live trading cancelled by user")
                sys.exit(0)

            print(f"\n🔴 INITIALIZING LIVE BROKER 🔴")
            from paper_trading.core.live_broker import LiveBroker

            self.broker = LiveBroker(
                adapter=self.adapter,
                config=self.config,
                state_manager=self.state_manager,
                logs_dir=str(logs_dir)
            )
            print(f"✓ Live broker initialized - REAL MONEY MODE")

        else:  # paper mode
            print(f"\n📄 INITIALIZING PAPER BROKER 📄")
            self.broker = PaperBroker(
                initial_capital,
                state_manager=self.state_manager,
                logs_dir=str(logs_dir),
                broker_name=self.adapter.broker_name  # Pass broker name for tracking
            )
            print(f"✓ Paper broker initialized - SIMULATION MODE")

        # Keep paper_broker alias for compatibility
        self.paper_broker = self.broker

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

        # Initialize persistent data recorder (one DB file per trading day)
        data_store_dir = str(Path(__file__).parent / 'data_store')
        self.recorder = DataRecorder(date=_dt.date.today(), base_dir=data_store_dir)

        # Initialize strategy
        print(f"[{self._get_ist_now()}] Initializing strategy...")
        self.strategy = IntradayMomentumOIPaper(
            config=self.config,
            broker=self.broker,  # Works with both PaperBroker and LiveBroker
            oi_analyzer=self.oi_analyzer,
            state_manager=self.state_manager,
            contract_manager=self.contract_manager,
            adapter=self.adapter,  # New: pass adapter for token-based lookups
            recorder=self.recorder  # Persistent data store
        )

        # GLOBAL TRADE CHECK: Check if ANY broker took a trade today
        # This must happen BEFORE strategy state restoration
        global_trades_today = self._check_global_trades_today()
        if global_trades_today > 0:
            self.strategy.daily_trade_taken = True
            print(f"[{self._get_ist_now()}] 📊 GLOBAL TRADE LIMIT: {global_trades_today} trade(s) already taken today (any broker)")
            print(f"[{self._get_ist_now()}] Setting daily_trade_taken = True")

        # Restore strategy state ONLY if there are active or closed positions
        # If flat (no trades), start fresh and re-determine direction from current OI
        if self.recovery_mode and self.recovery_info:
            has_active = self.recovery_info.get('active_positions_count', 0) > 0
            has_closed = len(self.recovery_info.get('closed_positions', [])) > 0

            if has_active or has_closed:
                print(f"[{self._get_ist_now()}] Restoring strategy state (has positions/trades)...")
                self._restore_strategy_state(self.recovery_info['strategy_state'])
            else:
                print(f"[{self._get_ist_now()}] No positions/trades - starting fresh to re-determine direction")

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

        # Restore expiry - try strategy_state first (for flat days with no trades)
        expiry_restored = False

        # Try strategy_state first (most reliable - always saved)
        if strategy_state.get('trading_expiry'):
            self.strategy.daily_expiry = strategy_state.get('trading_expiry')
            expiry_restored = True
            print(f"  Restored expiry from strategy_state: {self.strategy.daily_expiry}")

        # Fallback: Try active positions
        if not expiry_restored and self.recovery_info.get('active_positions'):
            active_positions_dict = self.recovery_info.get('active_positions', {})
            if active_positions_dict:
                first_position = list(active_positions_dict.values())[0]
                self.strategy.daily_expiry = first_position.get('expiry')
                expiry_restored = True
                print(f"  Restored expiry from active position: {self.strategy.daily_expiry}")

        # Fallback: Try closed positions
        if not expiry_restored and self.recovery_info.get('closed_positions'):
            closed_positions = self.recovery_info.get('closed_positions', [])
            if closed_positions:
                first_closed = closed_positions[0]
                self.strategy.daily_expiry = first_closed.get('expiry')
                expiry_restored = True
                print(f"  Restored expiry from closed position: {self.strategy.daily_expiry}")

        # Restore daily_trade_taken flag - check GLOBAL trades (across all brokers)
        # This ensures 1 trade/day limit works regardless of which broker was used
        has_open_positions = self.recovery_info.get('active_positions_count', 0) > 0
        has_closed_trades = len(self.recovery_info.get('closed_positions', [])) > 0
        trades_today = self.recovery_info.get('daily_stats', {}).get('trades_today', 0)
        
        # GLOBAL CHECK: Check cumulative CSV for any trade today (any broker)
        global_trades_today = self._check_global_trades_today()

        if has_open_positions or has_closed_trades or trades_today > 0 or global_trades_today > 0:
            self.strategy.daily_trade_taken = True
            reason = []
            if has_open_positions:
                reason.append("has open positions")
            if has_closed_trades:
                reason.append("has closed trades")
            if trades_today > 0:
                reason.append(f"trades_today={trades_today}")
            if global_trades_today > 0:
                reason.append(f"global_trades_today={global_trades_today}")
            print(f"  Restored daily_trade_taken: True ({', '.join(reason)})")

        # Restore VWAP tracking
        # Note: This is simplified - you may need to reconstruct full VWAP state

        print(f"  Restored direction: {self.strategy.daily_direction}")
        print(f"  Restored strike: {self.strategy.daily_strike}")
        print(f"  Restored expiry: {self.strategy.daily_expiry}")

    def run(self):
        """Main trading loop"""
        self.running = True

        # Determine trading mode display
        trading_mode = self.config['trading_mode']['mode']
        mode_display = '🔴 LIVE TRADING 🔴' if trading_mode == 'live' else '📄 PAPER TRADING 📄'

        print(f"\n{'='*80}")
        print(f"[{self._get_ist_now()}] Starting DUAL-LOOP trading...")
        print(f"  MODE: {mode_display}")
        print(f"  Broker: {self.adapter.broker_name}")
        print(f"  Loop 1: Strategy Loop - Every 5 minutes (Entry decisions)")
        print(f"  Loop 2: Exit Monitor Loop - Every 1 minute (LTP-based exits)")
        if self.use_contract_manager and self.contract_manager:
            print(f"  Loop 3: Contract Monitor Loop - Every {self.contract_monitor_interval}s (Cache updates)")
        if self.recovery_mode:
            print(f"  RECOVERY: Resumed from crash")
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
        while self.running and not self.adapter.is_market_open():
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
                if not self.adapter.is_market_open():
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

                # Get spot price via adapter
                spot_price = self.adapter.get_spot_price()
                if not spot_price:
                    print(f"[{current_time}] ✗ Failed to get spot price, skipping...")
                    self.adapter.wait_for_next_candle()
                    continue

                print(f"[{current_time}] Nifty Spot: {spot_price:.2f}")

                # Check if we have open positions - skip entry logic
                open_positions = self.paper_broker.get_open_positions()

                if len(open_positions) > 0:
                    print(f"[{current_time}] 📊 POSITION ACTIVE: Exit monitoring handled by 1-min LTP loop")
                    print(f"[{current_time}] Skipping option chain fetch (not needed for exits)")
                    self.adapter.wait_for_next_candle()
                    continue

                # Check if in monitoring-only mode (trade already taken but position closed)
                if self.strategy.daily_trade_taken:
                    print(f"[{current_time}] 📊 MONITORING MODE: Daily trade limit reached (1/1 trades taken)")
                    print(f"[{current_time}] System will continue monitoring but will NOT enter new trades")

                # Get options data for ENTRY decisions only (no open positions)
                options_data = self._get_options_data(current_time, spot_price)

                # Check if direction is determined
                direction_determined = (
                    hasattr(self.strategy, 'daily_direction') and
                    self.strategy.daily_direction is not None and
                    hasattr(self.strategy, 'daily_strike') and
                    self.strategy.daily_strike is not None
                )

                # Skip only if empty AND direction not determined (true error)
                # If direction IS determined, empty DataFrame is OK (optimized path)
                if options_data.empty and not direction_determined:
                    print(f"[{current_time}] ✗ No options data for direction determination, skipping...")
                    self.adapter.wait_for_next_candle()
                    continue

                # Update shared data
                with self.exit_monitor_lock:
                    self.current_spot_price = spot_price
                    self.current_options_data = options_data

                # Process candle for ENTRY signals (with thread lock for exit checks)
                # THREAD SAFETY: on_candle calls _check_exits internally
                with self.exit_monitor_lock:
                    self.strategy.on_candle(current_time, spot_price, options_data)
                    # Mark this 5-min boundary as VWAP-updated so the exit monitor
                    # doesn't refetch the same candle seconds later and double-count it
                    bm = (current_time.minute // 5) * 5
                    self.last_vwap_boundary = current_time.replace(minute=bm, second=0, microsecond=0)

                # Update state
                self.state_manager.update_api_stats('5min')
                self.state_manager.save()

                # Print status
                self._print_status()

                # Wait for next candle via adapter
                self.adapter.wait_for_next_candle()

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
                if not self.adapter.is_market_open():
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

                # Fetch spot price via adapter
                spot_price = self.adapter.get_spot_price()
                if not spot_price:
                    print(f"[{current_time}] ⚠️ Exit Monitor: Could not get spot price, skipping...")
                    time_module.sleep(60)
                    continue

                # Fetch LTP-only data for exit monitoring (fast!)
                options_data = self._get_ltp_for_positions(current_time, positions)
                if options_data is None or options_data.empty:
                    print(f"[{current_time}] ⚠️ Exit Monitor: Could not get LTP data, skipping...")
                    time_module.sleep(60)
                    continue

                # Calculate current 5-min candle boundary
                bm = (current_time.minute // 5) * 5
                current_boundary = current_time.replace(minute=bm, second=0, microsecond=0)

                with self.exit_monitor_lock:
                    # Update VWAP once per 5-min candle boundary (not every minute)
                    if current_boundary != self.last_vwap_boundary:
                        self.strategy._update_vwap_for_positions(current_time)
                        self.last_vwap_boundary = current_boundary

                    # Check exits with real-time LTP + updated VWAP from cache
                    self.strategy._check_exits(current_time, options_data, use_ltp_only=True)

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
        """
        Get options data for entry decisions - optimized to fetch only what's needed.

        OPTIMIZATION:
        - First candle of day: Fetch full option chain (22 strikes) to determine direction
        - After direction determined: Fetch LTP only for specific strike (1 API call, fast!)
        """
        # Get next expiry - use contract manager if available
        if self.contract_manager:
            expiry = self.contract_manager.get_options_expiry('current_week')
            if not expiry:
                print(f"[{current_time}] ⚠️ Contract manager: No current week expiry, falling back to adapter")
                expiry = self.adapter.get_next_expiry()
        else:
            expiry = self.adapter.get_next_expiry()

        if not expiry:
            return pd.DataFrame()

        # Check if direction is already determined
        direction_determined = (
            hasattr(self.strategy, 'daily_direction') and
            self.strategy.daily_direction is not None and
            hasattr(self.strategy, 'daily_strike') and
            self.strategy.daily_strike is not None
        )

        if direction_determined:
            # OPTIMIZED PATH: No API call needed! Strategy fetches its own candles.
            # We just provide the strike range metadata for strike update logic.

            # Calculate current ATM strike based on spot price
            strike_interval = 50
            base_strike = round(spot_price / strike_interval) * strike_interval

            # Get available strikes around current spot (for strike update logic in strategy)
            strikes_range = 5  # Check strikes within +/- 5 strikes
            available_strikes = [base_strike + (i * strike_interval) for i in range(-strikes_range, strikes_range + 1)]

            # Calculate what the strike should be for current direction
            # Use strategy's oi_analyzer if available, otherwise create a new one
            oi_analyzer = self.strategy.oi_analyzer if hasattr(self.strategy, 'oi_analyzer') else OIAnalyzer()
            current_strike = oi_analyzer.get_nearest_strike(
                spot_price, self.strategy.daily_direction, available_strikes
            )

            if current_strike is not None:
                current_strike = int(current_strike)
            else:
                # Fallback to current strike if calculation fails
                print(f"[{current_time}] ⚠️  Strike calculation returned None (spot: {spot_price:.2f}, direction: {self.strategy.daily_direction})")
                print(f"[{current_time}]    Using existing strike: {self.strategy.daily_strike}")
                current_strike = self.strategy.daily_strike

            print(f"[{current_time}] 🚀 OPTIMIZED PATH: Direction determined ({self.strategy.daily_direction} @ {current_strike})")
            print(f"[{current_time}] ✓ No quote fetch needed - strategy will fetch candle data with OI included")

            # Create a minimal DataFrame with just metadata (no API call!)
            # Strategy doesn't use this data - it fetches its own candles
            # We just provide available_strikes for strike update logic
            options_df = pd.DataFrame()
            options_df.attrs['available_strikes'] = available_strikes

            return options_df
        else:
            # FIRST CANDLE: Fetch full option chain to determine direction
            print(f"[{current_time}] 📊 FULL FETCH: Direction not determined, fetching all strikes to find max OI")

            # Calculate strikes
            strikes_above = self.config['entry']['strikes_above_spot']
            strikes_below = self.config['entry']['strikes_below_spot']

            strike_interval = 50
            base_strike = round(spot_price / strike_interval) * strike_interval

            strikes = []
            for i in range(-strikes_below, strikes_above + 1):
                strikes.append(base_strike + (i * strike_interval))

            # Fetch full options chain (22 strikes, one-time cost for direction determination)
            options_df = self.adapter.get_options_chain(expiry, strikes)

            # Record full chain snapshot to persistent store
            if self.recorder and options_df is not None and not options_df.empty:
                self.recorder.record_option_chain(
                    spot_price=spot_price,
                    direction=None,  # Direction not yet determined at this point
                    chain_df=options_df
                )

            return options_df if options_df is not None else pd.DataFrame()

    def _get_ltp_for_entry(self, current_time, strike, option_type, expiry):
        """
        Get LTP-only data for specific strike (fast, for entry monitoring after direction determined).

        Fetches only quote data (LTP + OI + Volume) for the specific strike being monitored,
        NOT candle data for the entire option chain.

        Args:
            current_time: Current timestamp
            strike: Strike price to monitor
            option_type: 'CALL' or 'PUT' (strategy format)
            expiry: Expiry date string (YYYY-MM-DD)

        Returns:
            DataFrame with columns: strike, option_type, expiry, close (LTP), OI, volume
        """
        import pandas as pd

        # Convert option_type format: CALL→CE, PUT→PE (for adapter compatibility)
        adapter_option_type = 'CE' if option_type == 'CALL' else 'PE'

        # Ensure strike is integer
        strike = int(strike)

        # Convert expiry to string format if needed
        if hasattr(expiry, 'strftime'):
            expiry_str = expiry.strftime('%Y-%m-%d')
        else:
            expiry_str = str(expiry)

        try:
            # Get quote (LTP + OI + Volume) for this specific strike
            quote = self.adapter.get_quote(
                underlying='NIFTY',
                option_type=adapter_option_type,
                strike=strike,
                expiry=expiry_str
            )

            if quote:
                print(f"[{current_time}] ✓ Quote fetched: {strike} {adapter_option_type} → LTP=₹{quote.ltp:.2f}, OI={quote.oi:,.0f}, Vol={quote.volume:,.0f}")

                # Return as DataFrame matching option chain format
                return pd.DataFrame([{
                    'strike': strike,
                    'option_type': adapter_option_type,  # Use adapter format (PE/CE)
                    'expiry': expiry_str,
                    'close': quote.ltp,      # Use LTP as close (for price checks)
                    'OI': quote.oi,          # Current open interest
                    'volume': quote.volume   # Cumulative volume (market open to now)
                }])
            else:
                print(f"[{current_time}] ⚠️ Could not get quote for {strike} {adapter_option_type} (returned None)")
                return pd.DataFrame()

        except Exception as e:
            print(f"[{current_time}] ✗ Error fetching quote for {strike} {adapter_option_type}: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()

    def _get_ltp_for_positions(self, current_time, positions):
        """
        Get LTP-only data for open positions (fast, for exit monitoring).

        Fetches only quote data (LTP + OI) for the specific positions held,
        NOT candle data for the entire option chain.

        Args:
            current_time: Current timestamp
            positions: List of open positions

        Returns:
            DataFrame with columns: strike, option_type, expiry, close (LTP), OI, volume
        """
        import pandas as pd

        if not positions:
            return pd.DataFrame()

        result_data = []

        for position in positions:
            try:
                # Convert option_type format: PUT→PE, CALL→CE (for adapter compatibility)
                adapter_option_type = 'PE' if position.option_type == 'PUT' else 'CE'

                # Ensure strike is integer (pandas can return floats)
                strike = int(position.strike)

                # Convert expiry to string format if needed
                if hasattr(position.expiry, 'strftime'):
                    expiry_str = position.expiry.strftime('%Y-%m-%d')
                else:
                    expiry_str = str(position.expiry)

                # Debug logging
                print(f"[{current_time}] 🔍 Fetching LTP: strike={strike}, type={adapter_option_type}, expiry={expiry_str}")

                # Get quote (LTP + OI) for this specific position
                quote = self.adapter.get_quote(
                    underlying='NIFTY',
                    option_type=adapter_option_type,
                    strike=strike,
                    expiry=expiry_str
                )

                if quote:
                    result_data.append({
                        'strike': strike,  # Use integer strike
                        'option_type': adapter_option_type,  # Use adapter format (PE/CE) for consistency
                        'expiry': expiry_str,
                        'close': quote.ltp,  # Use LTP as close for exit monitoring
                        'OI': quote.oi,
                        'volume': quote.volume
                    })
                    print(f"[{current_time}] ✓ LTP fetched: ₹{quote.ltp:.2f}")
                else:
                    print(f"[{current_time}] ⚠️ Could not get LTP for {strike} {adapter_option_type} (quote returned None)")

            except Exception as e:
                strike = int(position.strike) if hasattr(position, 'strike') else 'unknown'
                option_type = 'PE' if position.option_type == 'PUT' else 'CE'
                print(f"[{current_time}] ✗ Error fetching LTP for {strike} {option_type}: {e}")
                import traceback
                traceback.print_exc()
                continue

        return pd.DataFrame(result_data)

    def _print_status(self):
        """Print current status"""
        status = self.strategy.get_status()
        stats = status['statistics']

        print(f"\n{'-'*80}")
        print(f"STATUS UPDATE")
        print(f"{'-'*80}")
        print(f"Date: {status['current_date']}")
        print(f"Broker: {self.adapter.broker_name}")
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

        # Logout via adapter
        if self.adapter:
            self.adapter.logout()

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
    parser.add_argument('--mode', choices=['paper', 'live'], help='Trading mode (overrides config)')

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

    # Determine mode display
    mode = args.mode if args.mode else 'Config default'
    mode_emoji = '🔴 LIVE' if args.mode == 'live' else '📄 PAPER' if args.mode == 'paper' else '📋 Config'

    print("Starting trading system...")
    print(f"Mode: {mode_emoji} {mode}")
    print(f"Broker: {args.broker if args.broker else 'Auto-detect'}")
    print(f"Log file: {log_file}")
    print("")
    print("Press Ctrl+C to stop")
    print("=" * 80)
    print("")

    trader = None
    try:
        # Create trader
        trader = UniversalPaperTrader(args.config, args.credentials, args.broker, args.mode)

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
        # Close persistent data recorder
        if trader and trader.recorder:
            trader.recorder.close()
        # Print session summary
        print_session_summary(log_file, start_time, trader)


if __name__ == "__main__":
    main()
