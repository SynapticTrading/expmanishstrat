"""
Paper Trading Runner - DUAL LOOP ARCHITECTURE
Implements proper separation:
- Strategy Loop (5-min): Entry decisions based on candles
- Exit Monitor Loop (Continuous): Exit decisions based on real-time LTP
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from datetime import datetime, time
import threading
import signal
import pandas as pd
import pytz
from src.config_loader import ConfigLoader
from src.oi_analyzer import OIAnalyzer
from paper_trading.legacy.zerodha_connection import ZerodhaConnection, load_credentials_from_file
from paper_trading.paper_broker import PaperBroker
from paper_trading.paper_strategy import IntradayMomentumOIPaper
from paper_trading.zerodha_data_feed import ZerodhaDataFeed
from paper_trading.state_manager import StateManager
import time as time_module


class DualLoopPaperTrader:
    """
    Dual-loop paper trading system:
    - Main thread: 5-min strategy loop (entry decisions)
    - Exit thread: Continuous LTP monitoring (exit decisions)
    """

    def __init__(self, config_path, credentials_path="paper_trading/credentials.txt"):
        """Initialize paper trading runner"""

        print(f"\n{'='*80}")
        print(f"DUAL-LOOP PAPER TRADING - Intraday Momentum OI Strategy")
        print(f"{'='*80}\n")

        # Load config
        print(f"[{datetime.now()}] Loading configuration...")
        config_loader = ConfigLoader(config_path)
        self.config = config_loader.load()

        # Load credentials
        print(f"[{datetime.now()}] Loading credentials...")
        self.credentials = load_credentials_from_file(credentials_path)
        if not self.credentials:
            raise Exception("Failed to load credentials!")

        # Components
        self.connection = None
        self.data_feed = None
        self.broker = None
        self.strategy = None
        self.oi_analyzer = None

        # State management
        self.state_manager = StateManager()
        self.ist = pytz.timezone('Asia/Kolkata')

        # Threading control
        self.running = False
        self.exit_monitor_thread = None
        self.exit_monitor_lock = threading.Lock()

        # Current market data (shared between threads)
        self.current_spot_price = None
        self.current_options_data = None

        # Position tracking (order_id -> position mapping)
        self.position_order_ids = {}

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _get_ist_now(self):
        """Get current time in IST"""
        return datetime.now(self.ist)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\n[{self._get_ist_now()}] Received shutdown signal, exiting gracefully...")
        self.running = False

    def connect(self):
        """Connect to Zerodha API"""
        print(f"[{datetime.now()}] Connecting to Zerodha...")

        self.connection = ZerodhaConnection(
            api_key=self.credentials['api_key'],
            api_secret=self.credentials['api_secret'],
            user_id=self.credentials['user_id'],
            user_password=self.credentials['user_password'],
            totp_key=self.credentials['totp_key']
        )

        kite = self.connection.connect()
        if not kite:
            raise Exception("Failed to connect to Zerodha")

        print(f"[{datetime.now()}] ✓ Connected successfully")

    def initialize(self):
        """Initialize all components"""

        # Initialize state session
        print(f"[{self._get_ist_now()}] Initializing state session...")
        self.state_manager.initialize_session(mode="paper")
        self.state_manager.update_system_health(broker_connected=True, data_feed_status="INITIALIZING")

        # Initialize data feed
        print(f"[{self._get_ist_now()}] Initializing data feed...")
        self.data_feed = ZerodhaDataFeed(self.connection)

        # Load instruments
        print(f"[{self._get_ist_now()}] Loading instruments...")
        if not self.data_feed.load_instruments():
            raise Exception("Failed to load instruments")

        # Initialize broker
        print(f"[{self._get_ist_now()}] Initializing paper broker...")
        initial_capital = self.config['position_sizing']['initial_capital']
        self.broker = PaperBroker(initial_capital)

        # Initialize portfolio state
        self.state_manager.state["portfolio"]["initial_capital"] = initial_capital
        self.state_manager.state["portfolio"]["current_cash"] = initial_capital
        self.state_manager.state["daily_stats"]["max_trades_allowed"] = self.config['risk_management']['max_positions']
        self.state_manager.save()

        # Initialize OI analyzer
        print(f"[{self._get_ist_now()}] Initializing OI analyzer...")
        dummy_options_df = pd.DataFrame()
        self.oi_analyzer = OIAnalyzer(dummy_options_df)

        # Initialize strategy
        print(f"[{self._get_ist_now()}] Initializing strategy...")
        self.strategy = IntradayMomentumOIPaper(
            config=self.config,
            broker=self.broker,
            oi_analyzer=self.oi_analyzer
        )

        # Update system health
        self.state_manager.update_system_health(data_feed_status="ACTIVE")
        self.state_manager.save()

        print(f"[{self._get_ist_now()}] ✓ All components initialized")

    def run(self):
        """Main orchestrator - starts both loops"""

        self.running = True

        print(f"\n{'='*80}")
        print(f"[{datetime.now()}] Starting DUAL-LOOP paper trading...")
        print(f"  Loop 1: Strategy Loop - Every 5 minutes (Entry decisions)")
        print(f"  Loop 2: Exit Monitor Loop - Every 1 minute (LTP-based exits)")
        print(f"{'='*80}\n")

        # Wait for market to open
        while self.running and not self.data_feed.is_market_open():
            print(f"[{datetime.now()}] Market is closed, waiting...")
            time_module.sleep(60)

        # Start exit monitor thread
        self.exit_monitor_thread = threading.Thread(
            target=self._exit_monitor_loop,
            name="ExitMonitor",
            daemon=True
        )
        self.exit_monitor_thread.start()
        print(f"[{datetime.now()}] ✓ Exit monitor loop started")

        # Run strategy loop (main thread)
        self._strategy_loop()

        # Cleanup
        self.cleanup()

    def _strategy_loop(self):
        """
        Strategy Loop - Runs every 5 minutes
        Handles:
        - Entry decisions based on 5-min candles
        - Daily direction determination
        - VWAP calculation
        """

        print(f"[{datetime.now()}] ✓ Strategy loop started")

        while self.running:
            try:
                current_time = datetime.now()

                # Check if market is still open
                if not self.data_feed.is_market_open():
                    print(f"[{datetime.now()}] Market closed, stopping strategy loop...")
                    break

                print(f"\n{'='*80}")
                print(f"[{current_time}] STRATEGY LOOP - Processing 5-min candle...")
                print(f"{'='*80}\n")

                # Get spot price
                spot_price = self.data_feed.get_spot_price()
                if not spot_price:
                    print(f"[{current_time}] ✗ Failed to get spot price, skipping...")
                    self.data_feed.wait_for_next_candle()
                    continue

                print(f"[{current_time}] Nifty Spot: {spot_price:.2f}")

                # Get options data (5-min aggregated)
                options_data = self._get_options_data(current_time, spot_price)

                if options_data.empty:
                    print(f"[{current_time}] ✗ No options data available, skipping...")
                    self.data_feed.wait_for_next_candle()
                    continue

                # Update shared data for exit monitor
                with self.exit_monitor_lock:
                    self.current_spot_price = spot_price
                    self.current_options_data = options_data

                # Process candle with strategy (ENTRY decisions only)
                self.strategy.on_candle(current_time, spot_price, options_data)

                # Print status
                self._print_status()

                # Wait for next 5-min candle
                self.data_feed.wait_for_next_candle()

            except Exception as e:
                print(f"[{datetime.now()}] ✗ Error in strategy loop: {e}")
                import traceback
                traceback.print_exc()
                time_module.sleep(60)

    def _exit_monitor_loop(self):
        """
        Exit Monitor Loop - Runs every 1 MINUTE
        Handles:
        - LTP monitoring (every 1 minute)
        - Stop loss checks
        - Trailing stop updates
        - Immediate exit execution
        """

        print(f"[{datetime.now()}] ✓ Exit monitor loop started (1-min LTP checks)")

        while self.running:
            try:
                # Only monitor if we have open positions
                positions = self.broker.get_open_positions()

                if not positions:
                    # No positions, sleep for 1 minute
                    time_module.sleep(60)
                    continue

                # We have open positions - check LTP
                for position in positions.copy():
                    try:
                        # Get LTP for this option
                        ltp = self._get_option_ltp(position)

                        if ltp is None:
                            continue

                        # Get current OI (for OI stop check)
                        current_oi = self._get_option_oi(position)

                        # Check exit conditions
                        exit_reason = self._check_exit_conditions_ltp(
                            position, ltp, current_oi
                        )

                        if exit_reason:
                            print(f"\n[{datetime.now()}] EXIT MONITOR (1-min LTP): {exit_reason}")

                            # Get VWAP from current options data
                            vwap = self._get_current_vwap(position)

                            # Execute exit
                            with self.exit_monitor_lock:
                                self.broker.sell(
                                    position,
                                    ltp,
                                    vwap,
                                    current_oi if current_oi else 0,
                                    exit_reason
                                )

                    except Exception as e:
                        print(f"[{datetime.now()}] ✗ Error monitoring position: {e}")
                        continue

                # Sleep for 1 MINUTE before next check
                time_module.sleep(60)

            except Exception as e:
                print(f"[{datetime.now()}] ✗ Error in exit monitor loop: {e}")
                import traceback
                traceback.print_exc()
                time_module.sleep(60)

    def _get_option_ltp(self, position):
        """Get real-time LTP for option position"""
        try:
            # Build tradingsymbol from position
            # Find instrument in cached data
            with self.exit_monitor_lock:
                if self.current_options_data is None or self.current_options_data.empty:
                    return None

                # Find matching option
                mask = (
                    (self.current_options_data['strike'] == position.strike) &
                    (self.current_options_data['option_type'] == position.option_type) &
                    (self.current_options_data['expiry'] == position.expiry)
                )

                matching = self.current_options_data[mask]

                if matching.empty:
                    return None

                tradingsymbol = matching.iloc[0]['tradingsymbol']

            # Get LTP from Zerodha
            ltp = self.connection.get_ltp(f"NFO:{tradingsymbol}")

            return ltp

        except Exception as e:
            print(f"[{datetime.now()}] ✗ Error getting LTP: {e}")
            return None

    def _get_option_oi(self, position):
        """Get current OI for option position"""
        try:
            with self.exit_monitor_lock:
                if self.current_options_data is None or self.current_options_data.empty:
                    return None

                mask = (
                    (self.current_options_data['strike'] == position.strike) &
                    (self.current_options_data['option_type'] == position.option_type) &
                    (self.current_options_data['expiry'] == position.expiry)
                )

                matching = self.current_options_data[mask]

                if matching.empty:
                    return None

                return matching.iloc[0]['oi']

        except Exception as e:
            return None

    def _get_current_vwap(self, position):
        """Get current VWAP for option position"""
        try:
            # Use strategy's VWAP calculation
            key = (position.strike, position.option_type, position.expiry)
            if key in self.strategy.vwap_running_totals:
                totals = self.strategy.vwap_running_totals[key]
                if totals['volume'] > 0:
                    return totals['tpv'] / totals['volume']

            return position.entry_price  # Fallback

        except Exception as e:
            return position.entry_price

    def _check_exit_conditions_ltp(self, position, current_price, current_oi):
        """
        Check exit conditions using real-time LTP
        Returns exit reason string or None
        """

        # Calculate P&L
        pnl_pct = (current_price / position.entry_price - 1)

        # Update peak for trailing stop
        if current_price > position.peak_price:
            position.peak_price = current_price
            print(f"[{datetime.now()}] New peak: ₹{current_price:.2f} (position peak updated)")

        # Check if profit threshold reached for trailing stop
        profit_threshold = self.config['exit']['profit_threshold']
        if current_price >= position.entry_price * profit_threshold:
            if not position.trailing_stop_active:
                position.trailing_stop_active = True
                print(f"[{datetime.now()}] Trailing stop activated (10% profit reached)")

        # 1. Initial stop loss (25%)
        stop_loss_pct = self.config['exit']['initial_stop_loss_pct']
        stop_loss_price = position.entry_price * (1 - stop_loss_pct)
        if current_price <= stop_loss_price:
            return f"Stop Loss ({stop_loss_pct*100:.0f}%)"

        # 2. VWAP stop (only in loss)
        vwap_stop_pct = self.config['exit']['vwap_stop_pct']
        if pnl_pct < 0:
            vwap = self._get_current_vwap(position)
            vwap_stop_price = vwap * (1 - vwap_stop_pct)
            if current_price <= vwap_stop_price:
                return f"VWAP Stop (>{vwap_stop_pct*100:.0f}% below VWAP)"

        # 3. OI increase stop (only in loss)
        oi_stop_pct = self.config['exit']['oi_increase_stop_pct']
        if pnl_pct < 0 and current_oi:
            oi_change_pct = (current_oi / position.oi_at_entry - 1)
            if oi_change_pct > oi_stop_pct:
                return f"OI Increase Stop ({oi_change_pct*100:+.1f}%)"

        # 4. Trailing stop (only if activated)
        if position.trailing_stop_active:
            trailing_pct = self.config['exit']['trailing_stop_pct']
            trailing_stop_price = position.peak_price * (1 - trailing_pct)
            if current_price <= trailing_stop_price:
                return f"Trailing Stop ({trailing_pct*100:.0f}%)"

        # 5. EOD exit check
        current_time = datetime.now().time()
        exit_start = self._parse_time(self.config['exit']['exit_start_time'])
        exit_end = self._parse_time(self.config['exit']['exit_end_time'])
        if exit_start <= current_time <= exit_end:
            return "EOD Exit"

        return None

    def _parse_time(self, time_str):
        """Parse time string to time object"""
        h, m = map(int, time_str.split(':'))
        return time(h, m)

    def _get_options_data(self, current_time, spot_price):
        """Get options chain data (5-min aggregated)"""
        try:
            # Get next expiry
            expiry = self.data_feed.get_next_expiry()
            if not expiry:
                print(f"[{current_time}] ✗ Could not determine next expiry")
                return pd.DataFrame()

            # Calculate strikes
            strikes_above = self.config['entry']['strikes_above_spot']
            strikes_below = self.config['entry']['strikes_below_spot']

            strike_interval = 50
            base_strike = round(spot_price / strike_interval) * strike_interval

            strikes = []
            for i in range(-strikes_below, strikes_above + 1):
                strikes.append(base_strike + (i * strike_interval))

            print(f"[{current_time}] Fetching options for expiry: {expiry}")
            print(f"  Strikes: {min(strikes)} - {max(strikes)} ({len(strikes)} strikes)")

            # Fetch options chain
            options_df = self.data_feed.get_options_chain(expiry, strikes)

            return options_df

        except Exception as e:
            print(f"[{current_time}] ✗ Error getting options data: {e}")
            return pd.DataFrame()

    def _print_status(self):
        """Print current status"""
        status = self.strategy.get_status()
        stats = status['statistics']

        print(f"\n{'-'*80}")
        print(f"STATUS UPDATE")
        print(f"{'-'*80}")
        print(f"Date: {status['current_date']}")
        print(f"Daily Direction: {status['daily_direction']} @ {status['daily_strike']}")
        print(f"Trade Taken Today: {status['daily_trade_taken']}")
        print(f"Open Positions: {status['open_positions']}")
        print(f"\nStatistics:")
        print(f"  Total Trades: {stats['total_trades']}")
        print(f"  Win Rate: {stats['win_rate']:.1f}%")
        print(f"  Total P&L: ₹{stats['total_pnl']:,.2f}")
        print(f"  Current Cash: ₹{stats['current_cash']:,.2f}")
        print(f"  ROI: {stats['roi']:+.2f}%")
        print(f"{'-'*80}\n")

    def cleanup(self):
        """Cleanup and shutdown"""
        print(f"\n{'='*80}")
        print(f"[{datetime.now()}] Shutting down...")
        print(f"{'='*80}\n")

        # Stop exit monitor thread
        self.running = False
        if self.exit_monitor_thread and self.exit_monitor_thread.is_alive():
            print(f"[{datetime.now()}] Stopping exit monitor thread...")
            self.exit_monitor_thread.join(timeout=5)

        # Print final statistics
        if self.broker:
            stats = self.broker.get_statistics()
            print(f"\nFinal Statistics:")
            print(f"  Total Trades: {stats['total_trades']}")
            print(f"  Winning Trades: {stats['winning_trades']}")
            print(f"  Losing Trades: {stats['losing_trades']}")
            print(f"  Win Rate: {stats['win_rate']:.1f}%")
            print(f"  Total P&L: ₹{stats['total_pnl']:,.2f}")
            print(f"  Average P&L: ₹{stats['avg_pnl']:,.2f}")
            print(f"  Max Win: ₹{stats['max_win']:,.2f}")
            print(f"  Max Loss: ₹{stats['max_loss']:,.2f}")
            print(f"  Final Capital: ₹{stats['current_cash']:,.2f}")
            print(f"  ROI: {stats['roi']:+.2f}%")

        # Logout
        if self.connection:
            self.connection.logout()

        print(f"\n[{datetime.now()}] ✓ Shutdown complete")


def main():
    """Main entry point"""

    config_path = "paper_trading/config.yaml"

    # Create runner
    runner = DualLoopPaperTrader(config_path)

    try:
        # Connect
        runner.connect()

        # Initialize
        runner.initialize()

        # Run (starts both loops)
        runner.run()

    except Exception as e:
        print(f"\n[{datetime.now()}] ✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if hasattr(runner, 'cleanup'):
            runner.cleanup()


if __name__ == "__main__":
    main()
