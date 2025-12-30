"""
Paper Trading Runner - Zerodha Version
Runs the Intraday Momentum OI strategy in paper trading mode using Zerodha Kite Connect
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from datetime import datetime, time
import yaml
import signal
import pandas as pd
from src.config_loader import ConfigLoader
from src.oi_analyzer import OIAnalyzer
from paper_trading.legacy.zerodha_connection import ZerodhaConnection, load_credentials_from_file
from paper_trading.paper_broker import PaperBroker
from paper_trading.paper_strategy import IntradayMomentumOIPaper
from paper_trading.zerodha_data_feed import ZerodhaDataFeed


class PaperTradingRunner:
    """Main runner for paper trading with Zerodha"""

    def __init__(self, config_path, credentials_path="paper_trading/credentials.txt"):
        """
        Initialize paper trading runner

        Args:
            config_path: Path to config YAML file
            credentials_path: Path to credentials file
        """
        print(f"\n{'='*80}")
        print(f"PAPER TRADING - Intraday Momentum OI Strategy (Zerodha)")
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

        # Initialize components
        self.connection = None
        self.data_feed = None
        self.broker = None
        self.strategy = None
        self.oi_analyzer = None

        # State
        self.running = False

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\n[{datetime.now()}] Received shutdown signal, exiting gracefully...")
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

        # Initialize data feed
        print(f"[{datetime.now()}] Initializing data feed...")
        self.data_feed = ZerodhaDataFeed(self.connection)

        # Load instruments
        print(f"[{datetime.now()}] Loading instruments...")
        if not self.data_feed.load_instruments():
            raise Exception("Failed to load instruments")

        # Initialize broker
        print(f"[{datetime.now()}] Initializing paper broker...")
        initial_capital = self.config['position_sizing']['initial_capital']
        self.broker = PaperBroker(initial_capital)

        # Initialize OI analyzer (using dummy options data for now)
        # In production, options data will be fetched in real-time
        print(f"[{datetime.now()}] Initializing OI analyzer...")
        dummy_options_df = pd.DataFrame()  # Placeholder
        self.oi_analyzer = OIAnalyzer(dummy_options_df)

        # Initialize strategy
        print(f"[{datetime.now()}] Initializing strategy...")
        self.strategy = IntradayMomentumOIPaper(
            config=self.config,
            broker=self.broker,
            oi_analyzer=self.oi_analyzer
        )

        print(f"[{datetime.now()}] ✓ All components initialized")

    def run(self):
        """Main trading loop"""

        self.running = True

        print(f"\n{'='*80}")
        print(f"[{datetime.now()}] Starting paper trading loop...")
        print(f"{'='*80}\n")

        # Wait for market to open if not already open
        while self.running and not self.data_feed.is_market_open():
            print(f"[{datetime.now()}] Market is closed, waiting...")
            import time
            time.sleep(60)  # Check every minute

        # Main loop - run every 5 minutes
        while self.running:
            try:
                current_time = datetime.now()

                # Check if market is still open
                if not self.data_feed.is_market_open():
                    print(f"[{datetime.now()}] Market closed, stopping...")
                    break

                print(f"\n{'='*80}")
                print(f"[{current_time}] Processing 5-min candle...")
                print(f"{'='*80}\n")

                # Get spot price
                spot_price = self.data_feed.get_spot_price()
                if not spot_price:
                    print(f"[{current_time}] ✗ Failed to get spot price, skipping...")
                    self.data_feed.wait_for_next_candle()
                    continue

                print(f"[{current_time}] Nifty Spot: {spot_price:.2f}")

                # Get options data
                options_data = self._get_options_data(current_time, spot_price)

                if options_data.empty:
                    print(f"[{current_time}] ✗ No options data available, skipping...")
                    self.data_feed.wait_for_next_candle()
                    continue

                # Process candle with strategy
                self.strategy.on_candle(current_time, spot_price, options_data)

                # Print status
                self._print_status()

                # Wait for next candle
                self.data_feed.wait_for_next_candle()

            except Exception as e:
                print(f"[{datetime.now()}] ✗ Error in trading loop: {e}")
                import traceback
                traceback.print_exc()

                # Wait a bit before retrying
                import time
                time.sleep(60)

        # Cleanup
        self.cleanup()

    def _get_options_data(self, current_time, spot_price):
        """
        Get options chain data

        Args:
            current_time: Current datetime
            spot_price: Current Nifty spot price

        Returns:
            DataFrame: Options data
        """
        try:
            # Get next expiry
            expiry = self.data_feed.get_next_expiry()
            if not expiry:
                print(f"[{current_time}] ✗ Could not determine next expiry")
                return pd.DataFrame()

            # Calculate strikes around spot price
            strikes_above = self.config['entry']['strikes_above_spot']
            strikes_below = self.config['entry']['strikes_below_spot']

            # Round spot to nearest 50 (Nifty strike interval)
            strike_interval = 50
            base_strike = round(spot_price / strike_interval) * strike_interval

            # Build strike list
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
            import traceback
            traceback.print_exc()
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

        # Close any open positions (EOD)
        if self.strategy and self.broker:
            positions = self.broker.get_open_positions()
            if positions:
                print(f"[{datetime.now()}] Warning: {len(positions)} position(s) still open")
                # Note: In a real implementation, you might want to force close these

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

        # Logout from broker
        if self.connection:
            self.connection.logout()

        print(f"\n[{datetime.now()}] ✓ Shutdown complete")


def main():
    """Main entry point"""

    # Config path
    config_path = "paper_trading/config.yaml"

    # Create runner
    runner = PaperTradingRunner(config_path)

    try:
        # Connect to broker
        runner.connect()

        # Initialize components
        runner.initialize()

        # Run trading loop
        runner.run()

    except Exception as e:
        print(f"\n[{datetime.now()}] ✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        if hasattr(runner, 'cleanup'):
            runner.cleanup()


if __name__ == "__main__":
    main()
