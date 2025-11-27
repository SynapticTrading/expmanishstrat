"""
Backtest Runner - Main Entry Point

This is the main script to run backtests for the Intraday Momentum OI Strategy
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, time
import logging

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from utils.config_loader import get_config
from utils.data_loader import DataLoader
from utils.logger import setup_logger
from utils.reporter import BacktestReporter
from strategies.intraday_momentum_oi import IntradayMomentumOIStrategy


class BacktestRunner:
    """
    Main backtest runner for Intraday Momentum OI Strategy

    This runner handles the entire backtest workflow:
    1. Load configuration
    2. Load data
    3. Initialize strategy
    4. Run backtest loop
    5. Generate reports
    """

    def __init__(self, config_path: str = None):
        """
        Initialize backtest runner

        Args:
            config_path: Path to configuration file (optional)
        """
        # Load configuration
        self.config = get_config(config_path)

        # Setup logging
        self.logger = setup_logger(
            name='IntradayMomentumOI',
            log_level=self.config.get('logging.level', 'INFO'),
            log_dir='logs',
            console_output=True
        )

        self.logger.info("="*80)
        self.logger.info("Backtest Runner Initialized")
        self.logger.info("="*80)

        # Initialize data loader
        self.data_loader = DataLoader(self.config)

        # Initialize strategy
        self.strategy = IntradayMomentumOIStrategy(self.config)

        # Initialize reporter
        self.reporter = BacktestReporter(self.config, output_dir='reports')

        # Trade history
        self.trades = []

        # Data containers
        self.weekly_data = None
        self.monthly_data = None
        self.spot_data = None
        self.vix_data = None

    def load_data(self):
        """Load all required data"""
        self.logger.info("Loading data...")

        try:
            self.weekly_data, self.monthly_data, self.spot_data, self.vix_data = \
                self.data_loader.load_all_data()

            self.logger.info(f"Weekly options data: {len(self.weekly_data)} rows")
            self.logger.info(f"Monthly options data: {len(self.monthly_data)} rows")
            self.logger.info(f"Spot price data: {len(self.spot_data)} rows")
            self.logger.info(f"VIX data: {len(self.vix_data)} rows")

        except Exception as e:
            self.logger.error(f"Error loading data: {str(e)}")
            raise

    def run_backtest(self):
        """
        Run the backtest

        Main backtest loop that processes data chronologically
        """
        self.logger.info("="*80)
        self.logger.info("Starting Backtest")
        self.logger.info("="*80)

        # Determine which expiry data to use
        expiry_type = self.config.get('expiry_type', 'weekly')
        options_data = self.weekly_data if expiry_type == 'weekly' else self.monthly_data

        self.logger.info(f"Using {expiry_type} expiry options")

        # Get backtest date range
        start_date = pd.to_datetime(self.config.get('backtest.start_date', '2025-01-01'))
        end_date = pd.to_datetime(self.config.get('backtest.end_date', '2025-12-31'))

        self.logger.info(f"Backtest period: {start_date.date()} to {end_date.date()}")

        # Filter data to backtest period
        options_data = options_data[
            (options_data['timestamp'] >= start_date) &
            (options_data['timestamp'] <= end_date)
        ]

        # Get unique trading days
        trading_days = sorted(options_data['timestamp'].dt.date.unique())

        self.logger.info(f"Total trading days: {len(trading_days)}")

        # Process each trading day
        for day_idx, trading_day in enumerate(trading_days):
            self.logger.info(f"\n--- Trading Day {day_idx + 1}/{len(trading_days)}: {trading_day} ---")

            # Reset strategy for new day
            self.strategy.reset_daily()

            # Get data for this day
            day_data = options_data[options_data['timestamp'].dt.date == trading_day]

            # Get unique timestamps for this day
            timestamps = sorted(day_data['timestamp'].unique())

            self.logger.info(f"Processing {len(timestamps)} timestamps")

            # Process each timestamp (candle)
            previous_data = None

            for ts_idx, timestamp in enumerate(timestamps):
                # Get current timestamp data
                current_data = day_data[day_data['timestamp'] == timestamp].copy()

                # Skip if no data
                if len(current_data) == 0:
                    continue

                # Skip first timestamp (need previous for OI comparison)
                if previous_data is None:
                    previous_data = current_data
                    continue

                # Get spot price
                spot_price = self._get_spot_price(timestamp)
                if spot_price is None:
                    self.logger.debug(f"No spot price for {timestamp}")
                    previous_data = current_data
                    continue

                # Get current expiry
                skip_mon_tue = self.config.get('skip_monday_tuesday_expiry', False)
                expiry = self.data_loader.get_closest_expiry(
                    timestamp, expiry_type, skip_mon_tue=skip_mon_tue
                )
                if expiry is None:
                    self.logger.debug(f"No expiry found for {timestamp}")
                    previous_data = current_data
                    continue

                # Filter to current expiry
                current_expiry_data = current_data[current_data['expiry'] == expiry]
                previous_expiry_data = previous_data[previous_data['expiry'] == expiry]

                if len(current_expiry_data) == 0:
                    previous_data = current_data
                    continue

                # Check for exit if we have a position
                if self.strategy.current_position is not None:
                    should_exit, exit_reason, exit_price = self.strategy.check_exit_conditions(
                        current_expiry_data, timestamp
                    )

                    if should_exit:
                        exit_record = self.strategy.exit_position(
                            exit_price, exit_reason, timestamp
                        )
                        if exit_record:
                            self.trades.append(exit_record)

                # Check for entry if no position
                if self.strategy.current_position is None:
                    # Check max trades per day
                    max_trades = self.config.get('max_positions_per_day', 5)
                    day_trades_count = sum(
                        1 for t in self.trades
                        if pd.to_datetime(t['entry_time']).date() == trading_day
                    )

                    if day_trades_count >= max_trades:
                        previous_data = current_data
                        continue

                    # Build option history for VWAP
                    option_history = self._build_option_history(
                        day_data, timestamp, expiry
                    )

                    # Check entry conditions
                    should_enter, entry_signal = self.strategy.check_entry_conditions(
                        current_expiry_data,
                        previous_expiry_data,
                        spot_price,
                        timestamp,
                        option_history
                    )

                    if should_enter:
                        self.strategy.enter_position(entry_signal)

                # Update previous data
                previous_data = current_data

            # End of day - force exit if position is still open
            if self.strategy.current_position is not None:
                self.logger.warning(f"Forcing exit at EOD for open position")
                # Get last price
                last_data = day_data[day_data['timestamp'] == timestamps[-1]]
                exit_price = self._get_position_price(
                    last_data,
                    self.strategy.position_strike,
                    self.strategy.position_option_type
                )
                if exit_price:
                    exit_record = self.strategy.exit_position(
                        exit_price, 'EOD_FORCED', timestamps[-1]
                    )
                    if exit_record:
                        self.trades.append(exit_record)

        self.logger.info("="*80)
        self.logger.info("Backtest Completed")
        self.logger.info(f"Total Trades: {len(self.trades)}")
        self.logger.info("="*80)

    def _get_spot_price(self, timestamp: pd.Timestamp) -> float:
        """Get spot price for timestamp"""
        spot_row = self.spot_data[self.spot_data['date'] == timestamp]
        if len(spot_row) > 0:
            return spot_row.iloc[0]['close']
        return None

    def _get_position_price(
        self,
        data: pd.DataFrame,
        strike: float,
        option_type: str
    ) -> float:
        """Get option price for position"""
        option_row = data[
            (data['strike'] == strike) &
            (data['option_type'] == option_type)
        ]
        if len(option_row) > 0:
            return option_row.iloc[0]['close']
        return None

    def _build_option_history(
        self,
        day_data: pd.DataFrame,
        current_timestamp: pd.Timestamp,
        expiry: pd.Timestamp
    ) -> pd.DataFrame:
        """Build historical data for option (for VWAP)"""
        lookback = self.config.get('vwap_lookback_periods', 20)
        candle_minutes = self.config.get('candle_timeframe', 5)

        # Get data up to current timestamp
        history = day_data[
            (day_data['timestamp'] <= current_timestamp) &
            (day_data['expiry'] == expiry)
        ].copy()

        # Sort by timestamp
        history = history.sort_values('timestamp')

        # Take last N periods
        return history.tail(lookback)

    def generate_reports(self):
        """Generate backtest reports"""
        self.logger.info("Generating reports...")

        if len(self.trades) == 0:
            self.logger.warning("No trades to report!")
            return

        initial_capital = self.config.get('initial_capital', 1000000)

        self.reporter.generate_report(
            trades=self.trades,
            initial_capital=initial_capital,
            strategy_name=self.config.get('strategy_name', 'Intraday_Momentum_OI')
        )

    def run(self):
        """Run complete backtest workflow"""
        try:
            # Load data
            self.load_data()

            # Run backtest
            self.run_backtest()

            # Generate reports
            self.generate_reports()

            self.logger.info("Backtest workflow completed successfully!")

        except Exception as e:
            self.logger.error(f"Error in backtest: {str(e)}", exc_info=True)
            raise


def main():
    """Main entry point"""
    print("\n" + "="*80)
    print("Intraday Momentum OI Strategy - Backtest Runner")
    print("="*80 + "\n")

    # Create and run backtest
    runner = BacktestRunner()
    runner.run()


if __name__ == '__main__':
    main()
