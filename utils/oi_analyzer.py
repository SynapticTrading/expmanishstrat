"""
Open Interest Analyzer Module
Analyzes OI changes to identify max buildup strikes and unwinding
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class OIAnalyzer:
    """Analyze Open Interest changes for option strikes"""

    def __init__(self, config):
        """
        Initialize OI Analyzer

        Args:
            config: ConfigLoader instance
        """
        self.config = config
        self.num_strikes = config.get('num_strikes_to_analyze', 10)
        self.strikes_below = config.get('strikes_below_spot', 5)
        self.strikes_above = config.get('strikes_above_spot', 5)

    def get_strikes_around_spot(
        self,
        spot_price: float,
        available_strikes: np.ndarray,
        option_type: str = 'CE'
    ) -> np.ndarray:
        """
        Get strikes around spot price (5 below, 5 above)

        Args:
            spot_price: Current spot price
            available_strikes: Array of available strikes
            option_type: 'CE' or 'PE'

        Returns:
            Array of selected strikes
        """
        available_strikes = np.array(sorted(available_strikes))

        # Find strikes below and above spot
        below_strikes = available_strikes[available_strikes < spot_price]
        above_strikes = available_strikes[available_strikes >= spot_price]

        # Get 5 closest below spot
        strikes_below = below_strikes[-self.strikes_below:] if len(below_strikes) >= self.strikes_below else below_strikes

        # Get 5 closest above spot
        strikes_above = above_strikes[:self.strikes_above] if len(above_strikes) >= self.strikes_above else above_strikes

        # Combine
        selected_strikes = np.concatenate([strikes_below, strikes_above])

        logger.debug(f"Selected {len(selected_strikes)} strikes around spot {spot_price}: {selected_strikes}")

        return selected_strikes

    def calculate_oi_buildup(
        self,
        current_data: pd.DataFrame,
        previous_data: pd.DataFrame,
        strikes: np.ndarray,
        option_type: str
    ) -> Dict[float, float]:
        """
        Calculate OI buildup (change) for given strikes

        Args:
            current_data: Current timestamp options data
            previous_data: Previous timestamp options data
            strikes: Array of strikes to analyze
            option_type: 'CE' or 'PE'

        Returns:
            Dict mapping strike to OI change
        """
        oi_changes = {}

        for strike in strikes:
            # Get current OI
            current_oi = self._get_oi_for_strike(current_data, strike, option_type)

            # Get previous OI
            previous_oi = self._get_oi_for_strike(previous_data, strike, option_type)

            # Calculate change
            if current_oi is not None and previous_oi is not None:
                oi_change = current_oi - previous_oi
                oi_changes[strike] = oi_change
            else:
                oi_changes[strike] = 0.0

        return oi_changes

    def _get_oi_for_strike(
        self,
        data: pd.DataFrame,
        strike: float,
        option_type: str
    ) -> Optional[float]:
        """
        Get OI for a specific strike and option type

        Args:
            data: Options data
            strike: Strike price
            option_type: 'CE' or 'PE'

        Returns:
            OI value or None if not found
        """
        filtered = data[
            (data['strike'] == strike) &
            (data['option_type'] == option_type)
        ]

        if len(filtered) > 0:
            return filtered.iloc[0]['OI']

        return None

    def find_max_buildup_strikes(
        self,
        oi_changes: Dict[float, float],
        option_type: str
    ) -> Tuple[float, float]:
        """
        Find strike with maximum OI buildup (increase)

        Args:
            oi_changes: Dict mapping strike to OI change
            option_type: 'CE' or 'PE'

        Returns:
            Tuple of (max_buildup_strike, oi_change_value)
        """
        if not oi_changes:
            return None, 0.0

        # Find strike with maximum positive change (buildup)
        max_strike = max(oi_changes.items(), key=lambda x: x[1])

        logger.debug(f"Max {option_type} buildup at strike {max_strike[0]}: {max_strike[1]}")

        return max_strike[0], max_strike[1]

    def analyze_oi_for_entry(
        self,
        current_data: pd.DataFrame,
        previous_data: pd.DataFrame,
        spot_price: float
    ) -> Dict[str, any]:
        """
        Analyze OI to determine entry direction (Call or Put)

        This implements the core logic from the strategy document:
        1. Identify 10 strikes (5 below, 5 above spot)
        2. Calculate max Call buildup strike
        3. Calculate max Put buildup strike
        4. Calculate distances from spot
        5. Determine Call or Put based on closer distance

        Args:
            current_data: Current timestamp options data
            previous_data: Previous timestamp options data
            spot_price: Current spot price

        Returns:
            Dict with analysis results including:
            - call_or_put: 'CALL' or 'PUT'
            - max_call_strike: Strike with max call buildup
            - max_put_strike: Strike with max put buildup
            - call_distance: Distance from spot to call strike
            - put_distance: Distance from spot to put strike
            - selected_strike: Strike to trade
        """
        # Get available strikes
        all_strikes = current_data['strike'].unique()

        # Get strikes around spot
        strikes = self.get_strikes_around_spot(spot_price, all_strikes)

        # Calculate Call OI changes
        call_oi_changes = self.calculate_oi_buildup(
            current_data, previous_data, strikes, 'CE'
        )

        # Calculate Put OI changes
        put_oi_changes = self.calculate_oi_buildup(
            current_data, previous_data, strikes, 'PE'
        )

        # Find max Call buildup strike
        max_call_strike, max_call_change = self.find_max_buildup_strikes(call_oi_changes, 'CE')

        # Find max Put buildup strike
        max_put_strike, max_put_change = self.find_max_buildup_strikes(put_oi_changes, 'PE')

        # Calculate distances from spot
        call_distance = abs(max_call_strike - spot_price) if max_call_strike else float('inf')
        put_distance = abs(spot_price - max_put_strike) if max_put_strike else float('inf')

        # Determine Call or Put
        # Call if CallStrikeDistance < PutStrikeDistance else Put
        if call_distance < put_distance:
            call_or_put = 'CALL'
            selected_strike_type = 'CE'
            # Choose CallStrike as nearest to Nifty Spot on the upper side
            selected_strike = self._get_nearest_strike_above_spot(spot_price, all_strikes)
        else:
            call_or_put = 'PUT'
            selected_strike_type = 'PE'
            # Choose PutStrike as nearest to Nifty Spot on the lower side
            selected_strike = self._get_nearest_strike_below_spot(spot_price, all_strikes)

        analysis = {
            'call_or_put': call_or_put,
            'selected_option_type': selected_strike_type,
            'max_call_strike': max_call_strike,
            'max_put_strike': max_put_strike,
            'max_call_change': max_call_change,
            'max_put_change': max_put_change,
            'call_distance': call_distance,
            'put_distance': put_distance,
            'selected_strike': selected_strike,
            'spot_price': spot_price
        }

        logger.info(f"OI Analysis: {call_or_put} selected, Strike: {selected_strike}, "
                   f"Call Distance: {call_distance:.2f}, Put Distance: {put_distance:.2f}")

        return analysis

    def _get_nearest_strike_above_spot(
        self,
        spot_price: float,
        available_strikes: np.ndarray
    ) -> float:
        """
        Get nearest strike above (or equal to) spot price

        Args:
            spot_price: Current spot price
            available_strikes: Available strikes

        Returns:
            Nearest strike above spot
        """
        above_strikes = available_strikes[available_strikes >= spot_price]

        if len(above_strikes) == 0:
            return max(available_strikes)

        return min(above_strikes)

    def _get_nearest_strike_below_spot(
        self,
        spot_price: float,
        available_strikes: np.ndarray
    ) -> float:
        """
        Get nearest strike below spot price

        Args:
            spot_price: Current spot price
            available_strikes: Available strikes

        Returns:
            Nearest strike below spot
        """
        below_strikes = available_strikes[available_strikes < spot_price]

        if len(below_strikes) == 0:
            return min(available_strikes)

        return max(below_strikes)

    def check_oi_unwinding(
        self,
        current_data: pd.DataFrame,
        previous_data: pd.DataFrame,
        strike: float,
        option_type: str
    ) -> Tuple[bool, float]:
        """
        Check if OI is unwinding at given strike

        OI unwinding = decrease in OI (negative change)

        Args:
            current_data: Current timestamp data
            previous_data: Previous timestamp data
            strike: Strike to check
            option_type: 'CE' or 'PE'

        Returns:
            Tuple of (is_unwinding, oi_change)
        """
        current_oi = self._get_oi_for_strike(current_data, strike, option_type)
        previous_oi = self._get_oi_for_strike(previous_data, strike, option_type)

        if current_oi is None or previous_oi is None:
            return False, 0.0

        oi_change = current_oi - previous_oi

        # Unwinding means OI is decreasing (negative change)
        is_unwinding = oi_change < 0

        logger.debug(f"OI check for {option_type} {strike}: "
                    f"Previous: {previous_oi}, Current: {current_oi}, "
                    f"Change: {oi_change}, Unwinding: {is_unwinding}")

        return is_unwinding, oi_change
