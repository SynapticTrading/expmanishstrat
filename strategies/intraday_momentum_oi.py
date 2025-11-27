"""
Intraday Momentum OI Unwinding Strategy

Strategy Logic:
1. Identify 10 strikes (5 below, 5 above spot)
2. Calculate max Call and Put buildup strikes
3. Determine direction based on distance from spot
4. Monitor for OI unwinding at selected strike
5. Enter when OI unwinding + price > VWAP
6. Manage with 25% stop loss initially, then 10% trailing after 10% profit
7. Exit by 2:50-3:00 PM or on trailing stop
"""

import pandas as pd
from datetime import datetime, time
from typing import Dict, Optional, Tuple
import logging

from utils.config_loader import ConfigLoader
from utils.oi_analyzer import OIAnalyzer
from utils.indicators import VWAPCalculator

logger = logging.getLogger(__name__)


class IntradayMomentumOIStrategy:
    """
    Core strategy implementation for Intraday Momentum OI Unwinding

    This class implements the exact logic from the strategy document
    """

    def __init__(self, config: ConfigLoader):
        """
        Initialize strategy

        Args:
            config: Configuration loader instance
        """
        self.config = config
        self.oi_analyzer = OIAnalyzer(config)
        self.vwap_calculator = VWAPCalculator(
            lookback_periods=config.get('vwap_lookback_periods', 20)
        )

        # Strategy parameters from config
        self.entry_start_time = self._parse_time(config.get('entry_start_time', '09:30'))
        self.entry_end_time = self._parse_time(config.get('entry_end_time', '14:30'))
        self.exit_start_time = self._parse_time(config.get('exit_start_time', '14:50'))
        self.exit_end_time = self._parse_time(config.get('exit_end_time', '15:00'))

        # Stop loss and target parameters
        self.initial_stop_loss_pct = config.get('initial_stop_loss_percent', 25) / 100
        self.profit_threshold = config.get('profit_threshold_for_trailing', 1.1)
        self.trailing_stop_pct = config.get('trailing_stop_percent', 10) / 100

        # Position sizing
        self.risk_per_trade = config.get('risk_per_trade_percent', 1.0) / 100
        self.initial_capital = config.get('initial_capital', 1000000)

        # Current position tracking
        self.current_position = None
        self.position_entry_price = None
        self.position_entry_time = None
        self.position_strike = None
        self.position_option_type = None
        self.position_qty = 0
        self.highest_price_since_entry = 0
        self.stop_loss_price = 0

        # Previous data for OI comparison
        self.previous_options_data = None

        # OI analysis result (cached for the day)
        self.oi_analysis = None
        self.oi_analysis_timestamp = None

    def _parse_time(self, time_str: str) -> time:
        """Parse time string to time object"""
        return datetime.strptime(time_str, "%H:%M").time()

    def analyze_oi_setup(
        self,
        current_data: pd.DataFrame,
        previous_data: pd.DataFrame,
        spot_price: float,
        current_time: datetime
    ) -> Dict:
        """
        Analyze OI to determine setup (Call or Put direction)

        This is done once and cached until we find an entry or reset

        Args:
            current_data: Current options data
            previous_data: Previous options data
            spot_price: Current spot price
            current_time: Current timestamp

        Returns:
            OI analysis dict
        """
        # Perform OI analysis
        analysis = self.oi_analyzer.analyze_oi_for_entry(
            current_data, previous_data, spot_price
        )

        self.oi_analysis = analysis
        self.oi_analysis_timestamp = current_time

        logger.info(f"OI Analysis at {current_time}: Direction={analysis['call_or_put']}, "
                   f"Strike={analysis['selected_strike']}")

        return analysis

    def check_entry_conditions(
        self,
        current_data: pd.DataFrame,
        previous_data: pd.DataFrame,
        spot_price: float,
        current_time: datetime,
        option_history: pd.DataFrame
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Check if entry conditions are met

        Entry Logic:
        1. Must be within entry timeframe (9:30 to 14:30)
        2. OI must be unwinding at selected strike
        3. Option price must be > VWAP

        Args:
            current_data: Current options data
            previous_data: Previous options data
            spot_price: Current spot price
            current_time: Current timestamp
            option_history: Historical data for selected option (for VWAP)

        Returns:
            Tuple of (should_enter, entry_signal_dict)
        """
        # Check if within entry timeframe
        current_t = current_time.time()
        if not (self.entry_start_time <= current_t <= self.entry_end_time):
            return False, None

        # Check if we already have a position
        if self.current_position is not None:
            return False, None

        # Perform OI analysis if not done yet or if we need to update
        if self.oi_analysis is None:
            self.analyze_oi_setup(current_data, previous_data, spot_price, current_time)

        # Get selected strike and option type from analysis
        selected_strike = self.oi_analysis['selected_strike']
        option_type = self.oi_analysis['selected_option_type']

        # Update selected strike to nearest to current spot
        # (Keep updating till entry is found - as per strategy doc)
        if option_type == 'CE':
            selected_strike = self.oi_analyzer._get_nearest_strike_above_spot(
                spot_price, current_data['strike'].unique()
            )
        else:
            selected_strike = self.oi_analyzer._get_nearest_strike_below_spot(
                spot_price, current_data['strike'].unique()
            )

        logger.debug(f"Checking entry for {option_type} {selected_strike}")

        # Check if OI is unwinding at selected strike
        is_unwinding, oi_change = self.oi_analyzer.check_oi_unwinding(
            current_data, previous_data, selected_strike, option_type
        )

        if not is_unwinding:
            logger.debug(f"OI not unwinding at {option_type} {selected_strike}")
            return False, None

        # Get current option price
        option_row = current_data[
            (current_data['strike'] == selected_strike) &
            (current_data['option_type'] == option_type)
        ]

        if len(option_row) == 0:
            logger.warning(f"No data found for {option_type} {selected_strike}")
            return False, None

        current_price = option_row.iloc[0]['close']

        # Calculate VWAP for this specific option (not all strikes!)
        # Filter option_history to only this strike and option type
        specific_option_history = option_history[
            (option_history['strike'] == selected_strike) &
            (option_history['option_type'] == option_type)
        ].copy()

        if len(specific_option_history) < 2:
            logger.debug(f"Insufficient history for VWAP calculation (only {len(specific_option_history)} candles)")
            return False, None

        vwap = self.vwap_calculator.calculate_vwap_for_option(specific_option_history)

        if pd.isna(vwap.iloc[-1]):
            logger.debug("VWAP is NaN")
            return False, None

        current_vwap = vwap.iloc[-1]

        # Check if price > VWAP
        is_above_vwap = self.vwap_calculator.is_price_above_vwap(current_price, current_vwap)

        if not is_above_vwap:
            logger.debug(f"Price {current_price} not above VWAP {current_vwap}")
            return False, None

        # All conditions met - generate entry signal
        entry_signal = {
            'timestamp': current_time,
            'strike': selected_strike,
            'option_type': option_type,
            'entry_price': current_price,
            'spot_price': spot_price,
            'vwap': current_vwap,
            'oi_change': oi_change,
            'direction': self.oi_analysis['call_or_put']
        }

        logger.info(f"ENTRY SIGNAL: {option_type} {selected_strike} at {current_price}, "
                   f"VWAP={current_vwap:.2f}, OI Change={oi_change}")

        return True, entry_signal

    def enter_position(self, entry_signal: Dict):
        """
        Enter a position based on entry signal

        Implements position sizing based on risk management

        Args:
            entry_signal: Entry signal dict from check_entry_conditions
        """
        entry_price = entry_signal['entry_price']

        # Calculate position size based on stop loss and risk
        # Risk amount = initial_capital * risk_per_trade
        risk_amount = self.initial_capital * self.risk_per_trade

        # Stop loss amount per unit = entry_price * initial_stop_loss_pct
        stop_loss_per_unit = entry_price * self.initial_stop_loss_pct

        # Position size = risk_amount / stop_loss_per_unit
        # For options, this gives us the number of lots
        if stop_loss_per_unit > 0:
            position_qty = int(risk_amount / stop_loss_per_unit)
        else:
            position_qty = 1

        # Set stop loss price
        stop_loss_price = entry_price * (1 - self.initial_stop_loss_pct)

        # Record position
        self.current_position = entry_signal
        self.position_entry_price = entry_price
        self.position_entry_time = entry_signal['timestamp']
        self.position_strike = entry_signal['strike']
        self.position_option_type = entry_signal['option_type']
        self.position_qty = position_qty
        self.highest_price_since_entry = entry_price
        self.stop_loss_price = stop_loss_price

        logger.info(f"ENTERED POSITION: {self.position_option_type} {self.position_strike}, "
                   f"Price={entry_price}, Qty={position_qty}, SL={stop_loss_price:.2f}")

    def check_exit_conditions(
        self,
        current_data: pd.DataFrame,
        current_time: datetime
    ) -> Tuple[bool, Optional[str], Optional[float]]:
        """
        Check if exit conditions are met

        Exit Logic:
        1. Time-based: Exit between 14:50 and 15:00
        2. Stop loss: Exit if price hits stop loss
        3. Trailing stop: After 10% profit, trail by 10%

        Args:
            current_data: Current options data
            current_time: Current timestamp

        Returns:
            Tuple of (should_exit, exit_reason, exit_price)
        """
        if self.current_position is None:
            return False, None, None

        current_t = current_time.time()

        # Get current price for position
        option_row = current_data[
            (current_data['strike'] == self.position_strike) &
            (current_data['option_type'] == self.position_option_type)
        ]

        if len(option_row) == 0:
            logger.warning(f"No data for position {self.position_option_type} {self.position_strike}")
            return False, None, None

        current_price = option_row.iloc[0]['close']

        # Update highest price
        if current_price > self.highest_price_since_entry:
            self.highest_price_since_entry = current_price

        # Check time-based exit
        if self.exit_start_time <= current_t <= self.exit_end_time:
            logger.info(f"TIME-BASED EXIT at {current_time}")
            return True, "TIME_EXIT", current_price

        # Check if profit threshold reached for trailing stop
        if current_price >= self.position_entry_price * self.profit_threshold:
            # Activate trailing stop
            # Trail by 10% from highest price
            trailing_stop_price = self.highest_price_since_entry * (1 - self.trailing_stop_pct)

            if current_price <= trailing_stop_price:
                logger.info(f"TRAILING STOP HIT: Price={current_price}, "
                           f"Trailing SL={trailing_stop_price:.2f}")
                return True, "TRAILING_STOP", current_price

        else:
            # Before profit threshold, use initial stop loss
            if current_price <= self.stop_loss_price:
                logger.info(f"STOP LOSS HIT: Price={current_price}, SL={self.stop_loss_price:.2f}")
                return True, "STOP_LOSS", current_price

        return False, None, None

    def exit_position(self, exit_price: float, exit_reason: str, exit_time: datetime):
        """
        Exit current position

        Args:
            exit_price: Exit price
            exit_reason: Reason for exit
            exit_time: Exit timestamp
        """
        if self.current_position is None:
            return

        entry_price = self.position_entry_price
        pnl = (exit_price - entry_price) * self.position_qty
        pnl_pct = (exit_price - entry_price) / entry_price * 100

        logger.info(f"EXITED POSITION: {self.position_option_type} {self.position_strike}, "
                   f"Entry={entry_price:.2f}, Exit={exit_price:.2f}, "
                   f"PnL={pnl:.2f} ({pnl_pct:.2f}%), Reason={exit_reason}")

        # Record exit
        exit_record = {
            'entry_time': self.position_entry_time,
            'exit_time': exit_time,
            'strike': self.position_strike,
            'option_type': self.position_option_type,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'qty': self.position_qty,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'exit_reason': exit_reason,
            'highest_price': self.highest_price_since_entry
        }

        # Reset position
        self.current_position = None
        self.position_entry_price = None
        self.position_entry_time = None
        self.position_strike = None
        self.position_option_type = None
        self.position_qty = 0
        self.highest_price_since_entry = 0
        self.stop_loss_price = 0

        return exit_record

    def reset_daily(self):
        """Reset strategy state for new trading day"""
        self.current_position = None
        self.position_entry_price = None
        self.position_entry_time = None
        self.position_strike = None
        self.position_option_type = None
        self.position_qty = 0
        self.highest_price_since_entry = 0
        self.stop_loss_price = 0
        self.previous_options_data = None
        self.oi_analysis = None
        self.oi_analysis_timestamp = None

        logger.info("Strategy reset for new trading day")

    def update_previous_data(self, current_data: pd.DataFrame):
        """Update previous data for OI comparison"""
        self.previous_options_data = current_data.copy()
