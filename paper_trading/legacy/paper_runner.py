"""
Paper Trading Runner - Main execution script
Runs the Intraday Momentum OI strategy in paper trading mode
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
from paper_trading.angelone_connection import AngelOneConnection
from paper_trading.paper_broker import PaperBroker
from paper_trading.paper_strategy import IntradayMomentumOIPaper
from paper_trading.data_feed import PaperDataFeed


class PaperTradingRunner:
    """Main runner for paper trading"""

    def __init__(self, config_path):
        """
        Initialize paper trading runner

        Args:
            config_path: Path to config YAML file
        """
        print(f"\n{'='*80}")
        print(f"PAPER TRADING - Intraday Momentum OI Strategy")
        print(f"{'='*80}\n")

        # Load config
        print(f"[{datetime.now()}] Loading configuration...")
        config_loader = ConfigLoader(config_path)
        self.config = config_loader.load()

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

    def connect(self, api_key, username, password, totp_token):
        """
        Connect to broker API

        Args:
            api_key: AngelOne API key
            username: Client code
            password: MPIN
            totp_token: TOTP token
        """
        print(f"[{datetime.now()}] Connecting to AngelOne...")
        self.connection = AngelOneConnection(api_key, username, password, totp_token)

        session_data = self.connection.connect()
        if not session_data:
            raise Exception("Failed to connect to AngelOne")

        print(f"[{datetime.now()}] ✓ Connected successfully")

    def initialize(self):
        """Initialize all components"""

        # Initialize data feed
        print(f"[{datetime.now()}] Initializing data feed...")
        self.data_feed = PaperDataFeed(self.connection)

        # Initialize broker
        print(f"[{datetime.now()}] Initializing paper broker...")
        initial_capital = self.config['position_sizing']['initial_capital']
        self.broker = PaperBroker(initial_capital)

        # Initialize OI analyzer (using dummy options data for now)
        # In production, you would load or fetch real options data
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
                # Note: This needs proper implementation to fetch real options chain
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

        Note: This is a placeholder. In production, you need to:
        1. Determine current/next expiry
        2. Calculate strikes around spot price
        3. Fetch option chain from AngelOne
        4. Build DataFrame with required columns

        Returns:
            DataFrame: Options data
        """
        # Placeholder - return empty DataFrame
        # You'll need to implement proper options data fetching
        return pd.DataFrame(columns=['strike', 'option_type', 'expiry', 'close', 'oi', 'volume'])

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
        if self.strategy:
            positions = self.broker.get_open_positions()
            if positions:
                print(f"[{datetime.now()}] Closing {len(positions)} open position(s)...")
                # Force close at market
                # (Implementation depends on how you want to handle this)

        # Print final statistics
        if self.broker:
            stats = self.broker.get_statistics()
            print(f"\nFinal Statistics:")
            print(f"  Total Trades: {stats['total_trades']}")
            print(f"  Win Rate: {stats['win_rate']:.1f}%")
            print(f"  Total P&L: ₹{stats['total_pnl']:,.2f}")
            print(f"  Final Capital: ₹{stats['current_cash']:,.2f}")
            print(f"  ROI: {stats['roi']:+.2f}%")

        # Logout from broker
        if self.connection:
            self.connection.logout()

        print(f"\n[{datetime.now()}] ✓ Shutdown complete")


def main():
    """Main entry point"""

    # Load credentials
    # IMPORTANT: Store credentials securely, not in code!
    # Use environment variables or a secure config file
    API_KEY = "YOUR_API_KEY"
    USERNAME = "YOUR_USERNAME"
    PASSWORD = "YOUR_MPIN"
    TOTP_TOKEN = "YOUR_TOTP_TOKEN"

    # Create runner
    config_path = "paper_trading/config.yaml"
    runner = PaperTradingRunner(config_path)

    try:
        # Connect to broker
        runner.connect(API_KEY, USERNAME, PASSWORD, TOTP_TOKEN)

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
        runner.cleanup()


if __name__ == "__main__":
    main()
