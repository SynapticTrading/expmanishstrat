"""
Backtrader Strategy Wrapper for Intraday Momentum OI Strategy

This wraps the core strategy logic to work with Backtrader framework
"""

import backtrader as bt
import pandas as pd
import numpy as np
from datetime import datetime, time
import logging

from strategies.intraday_momentum_oi import IntradayMomentumOIStrategy
from utils.config_loader import get_config

logger = logging.getLogger(__name__)


class IntradayMomentumOIBacktrader(bt.Strategy):
    """
    Backtrader wrapper for Intraday Momentum OI Strategy

    This strategy handles the backtesting integration with Backtrader
    while delegating core strategy logic to IntradayMomentumOIStrategy
    """

    params = (
        ('config', None),
        ('options_data', None),
        ('spot_data', None),
        ('vix_data', None),
        ('expiry_type', 'weekly'),
    )

    def __init__(self):
        """Initialize Backtrader strategy"""
        # Load config
        if self.params.config is None:
            self.config = get_config()
        else:
            self.config = self.params.config

        # Initialize core strategy
        self.strategy = IntradayMomentumOIStrategy(self.config)

        # Data references
        self.options_data = self.params.options_data
        self.spot_data = self.params.spot_data
        self.vix_data = self.params.vix_data
        self.expiry_type = self.params.expiry_type

        # Trade tracking
        self.trades = []
        self.daily_trades = 0
        self.current_date = None

        # Option history for VWAP calculation
        self.option_history_buffer = {}

        logger.info("Backtrader strategy initialized")

    def next(self):
        """
        Called on each bar/candle

        This is the main loop that gets called by Backtrader
        """
        # Get current datetime
        current_dt = self.datas[0].datetime.datetime(0)
        current_date = current_dt.date()

        # Check if new day - reset daily counters
        if self.current_date != current_date:
            self.current_date = current_date
            self.daily_trades = 0
            self.strategy.reset_daily()
            self.option_history_buffer = {}
            logger.info(f"New trading day: {current_date}")

        # Get current spot price
        spot_price = self.get_spot_price(current_dt)
        if spot_price is None:
            logger.warning(f"No spot price for {current_dt}")
            return

        # Get current expiry
        expiry_date = self.get_current_expiry(current_dt)
        if expiry_date is None:
            logger.warning(f"No expiry found for {current_dt}")
            return

        # Get options data for current timestamp
        current_options = self.get_options_data(current_dt, expiry_date)
        if current_options is None or len(current_options) == 0:
            logger.debug(f"No options data for {current_dt}")
            return

        # Get previous options data for OI comparison
        if self.strategy.previous_options_data is None:
            # First iteration - just store and continue
            self.strategy.update_previous_data(current_options)
            return

        previous_options = self.strategy.previous_options_data

        # Check if we should exit current position
        if self.strategy.current_position is not None:
            should_exit, exit_reason, exit_price = self.strategy.check_exit_conditions(
                current_options, current_dt
            )

            if should_exit:
                # Exit position
                exit_record = self.strategy.exit_position(
                    exit_price, exit_reason, current_dt
                )
                self.trades.append(exit_record)

                # Close Backtrader position if any
                if self.position:
                    self.close()

        # Check for entry if no position
        if self.strategy.current_position is None:
            # Check max trades per day
            max_trades = self.config.get('max_positions_per_day', 5)
            if self.daily_trades >= max_trades:
                logger.debug(f"Max trades per day ({max_trades}) reached")
                self.strategy.update_previous_data(current_options)
                return

            # Get option history for VWAP (build buffer)
            # This is a simplified approach - in production, maintain proper history
            option_history = self.build_option_history(
                current_options, current_dt, expiry_date
            )

            # Check entry conditions
            should_enter, entry_signal = self.strategy.check_entry_conditions(
                current_options,
                previous_options,
                spot_price,
                current_dt,
                option_history
            )

            if should_enter:
                # Enter position
                self.strategy.enter_position(entry_signal)
                self.daily_trades += 1

                # For Backtrader, we don't actually place trades on options
                # We just track the P&L through our strategy class
                # But we could use a dummy data feed if needed

        # Update previous data for next iteration
        self.strategy.update_previous_data(current_options)

    def get_spot_price(self, timestamp: datetime) -> float:
        """Get spot price for timestamp"""
        if self.spot_data is None:
            return None

        spot_row = self.spot_data[self.spot_data['date'] == timestamp]
        if len(spot_row) > 0:
            return spot_row.iloc[0]['close']

        return None

    def get_current_expiry(self, current_dt: datetime) -> datetime:
        """Get current expiry based on expiry type"""
        data = self.options_data

        # Get unique expiries after current date
        future_expiries = data[data['expiry'] >= current_dt]['expiry'].unique()

        if len(future_expiries) == 0:
            return None

        # Return the closest one
        return pd.to_datetime(sorted(future_expiries)[0])

    def get_options_data(self, timestamp: datetime, expiry: datetime) -> pd.DataFrame:
        """Get options data for timestamp and expiry"""
        if self.options_data is None:
            return None

        filtered = self.options_data[
            (self.options_data['timestamp'] == timestamp) &
            (self.options_data['expiry'] == expiry)
        ].copy()

        return filtered

    def build_option_history(
        self,
        current_data: pd.DataFrame,
        current_time: datetime,
        expiry: datetime
    ) -> pd.DataFrame:
        """
        Build historical data for option (for VWAP calculation)

        This is simplified - maintains a buffer of recent data
        """
        # In a real implementation, we would maintain proper historical data
        # For now, we'll create a simple buffer

        # Get lookback period
        lookback = self.config.get('vwap_lookback_periods', 20)

        # Filter historical data from options_data
        # Get data from current_time - lookback periods to current_time
        end_time = current_time
        start_time = current_time - pd.Timedelta(minutes=lookback * 5)  # Assuming 5 min candles

        history = self.options_data[
            (self.options_data['timestamp'] >= start_time) &
            (self.options_data['timestamp'] <= end_time) &
            (self.options_data['expiry'] == expiry)
        ].copy()

        return history

    def stop(self):
        """Called when backtesting ends"""
        logger.info(f"Backtest completed. Total trades: {len(self.trades)}")

        # Calculate final statistics
        if len(self.trades) > 0:
            total_pnl = sum(t['pnl'] for t in self.trades)
            win_trades = [t for t in self.trades if t['pnl'] > 0]
            loss_trades = [t for t in self.trades if t['pnl'] <= 0]

            win_rate = len(win_trades) / len(self.trades) * 100

            logger.info(f"Total P&L: {total_pnl:.2f}")
            logger.info(f"Win Rate: {win_rate:.2f}%")
            logger.info(f"Winning Trades: {len(win_trades)}")
            logger.info(f"Losing Trades: {len(loss_trades)}")

    def get_trades(self):
        """Get all trades executed"""
        return self.trades
