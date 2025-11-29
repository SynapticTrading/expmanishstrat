"""
Technical Indicators Module
Implements VWAP and other technical indicators for options trading
"""

import pandas as pd
import numpy as np
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class VWAPCalculator:
    """Calculate VWAP (Volume Weighted Average Price) for options"""

    def __init__(self, lookback_periods: int = 20, anchored: bool = True):
        """
        Initialize VWAP calculator

        Args:
            lookback_periods: Number of periods to use for rolling VWAP (ignored if anchored=True)
            anchored: If True, VWAP is anchored to opening (9:15 AM). If False, uses rolling window.
        """
        self.lookback_periods = int(lookback_periods)  # Ensure it's an integer
        self.anchored = anchored

    def calculate_vwap(
        self,
        prices: pd.Series,
        volumes: pd.Series,
        highs: Optional[pd.Series] = None,
        lows: Optional[pd.Series] = None,
        closes: Optional[pd.Series] = None
    ) -> pd.Series:
        """
        Calculate VWAP for a price series

        VWAP = Sum(Price * Volume) / Sum(Volume)

        For options, we use typical price = (High + Low + Close) / 3

        Args:
            prices: Price series (can be close prices)
            volumes: Volume series
            highs: High prices (optional)
            lows: Low prices (optional)
            closes: Close prices (optional)

        Returns:
            VWAP series
        """
        # Calculate typical price if high, low, close are provided
        if highs is not None and lows is not None and closes is not None:
            typical_price = (highs + lows + closes) / 3
        else:
            typical_price = prices

        # Calculate VWAP
        pv = typical_price * volumes
        vwap = pv.rolling(window=self.lookback_periods).sum() / \
               volumes.rolling(window=self.lookback_periods).sum()

        return vwap

    def calculate_anchored_vwap(
        self,
        prices: pd.Series,
        volumes: pd.Series,
        highs: Optional[pd.Series] = None,
        lows: Optional[pd.Series] = None,
        closes: Optional[pd.Series] = None
    ) -> pd.Series:
        """
        Calculate anchored VWAP (from opening to current time)
        
        Anchored VWAP = Cumulative(Price * Volume) / Cumulative(Volume)
        
        Args:
            prices: Price series (can be close prices)
            volumes: Volume series
            highs: High prices (optional)
            lows: Low prices (optional)
            closes: Close prices (optional)
            
        Returns:
            Anchored VWAP series
        """
        # Calculate typical price if high, low, close are provided
        if highs is not None and lows is not None and closes is not None:
            typical_price = (highs + lows + closes) / 3
        else:
            typical_price = prices
        
        # Calculate cumulative VWAP (anchored to start)
        pv = typical_price * volumes
        cumulative_pv = pv.cumsum()
        cumulative_volume = volumes.cumsum()
        
        # Avoid division by zero
        vwap = cumulative_pv / cumulative_volume
        vwap = vwap.replace([np.inf, -np.inf], np.nan)
        
        return vwap

    def calculate_vwap_for_option(
        self,
        option_data: pd.DataFrame,
        lookback: Optional[int] = None
    ) -> pd.Series:
        """
        Calculate VWAP for option data DataFrame
        
        Uses anchored VWAP (from 9:15 AM) if self.anchored=True,
        otherwise uses rolling VWAP with lookback periods.

        Args:
            option_data: DataFrame with columns: high, low, close, volume
            lookback: Lookback periods (only used if anchored=False)

        Returns:
            VWAP series
        """
        # Check if required columns exist
        required_cols = ['high', 'low', 'close', 'volume']
        missing_cols = [col for col in required_cols if col not in option_data.columns]
        
        if missing_cols:
            logger.warning(f"Missing columns {missing_cols} for VWAP calculation, using close price only")
            if self.anchored:
                return self.calculate_anchored_vwap(
                    option_data['close'],
                    option_data['volume']
                )
            else:
                return self.calculate_vwap(
                    option_data['close'],
                    option_data['volume']
                )
        
        # Use anchored or rolling VWAP based on configuration
        if self.anchored:
            return self.calculate_anchored_vwap(
                option_data['close'],
                option_data['volume'],
                option_data['high'],
                option_data['low'],
                option_data['close']
            )
        else:
            periods = lookback if lookback is not None else self.lookback_periods
            return self.calculate_vwap(
                option_data['close'],
                option_data['volume'],
                option_data['high'],
                option_data['low'],
                option_data['close']
            )

    def is_price_above_vwap(
        self,
        current_price: float,
        vwap_value: float
    ) -> bool:
        """
        Check if current price is above VWAP

        Args:
            current_price: Current option price
            vwap_value: Current VWAP value

        Returns:
            True if price > VWAP, False otherwise
        """
        if pd.isna(vwap_value):
            logger.warning("VWAP value is NaN, returning False")
            return False

        return current_price > vwap_value


# NOTE: The following classes/functions are NOT used in the current strategy
# They are kept for potential future enhancements
# The PDF strategy only requires VWAP calculation

# Uncomment if needed for future strategies:

# class IndicatorCalculator:
#     """Calculate various technical indicators (NOT USED IN CURRENT STRATEGY)"""
#     @staticmethod
#     def calculate_ema(data: pd.Series, period: int) -> pd.Series:
#         return data.ewm(span=period, adjust=False).mean()
#
#     @staticmethod
#     def calculate_sma(data: pd.Series, period: int) -> pd.Series:
#         return data.rolling(window=period).mean()
#
#     @staticmethod
#     def calculate_rsi(data: pd.Series, period: int = 14) -> pd.Series:
#         delta = data.diff()
#         gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
#         loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
#         rs = gain / loss
#         return 100 - (100 / (1 + rs))
#
#     @staticmethod
#     def calculate_atr(high, low, close, period=14):
#         tr1 = high - low
#         tr2 = abs(high - close.shift())
#         tr3 = abs(low - close.shift())
#         tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
#         return tr.rolling(window=period).mean()
#
#     @staticmethod
#     def calculate_bollinger_bands(data, period=20, num_std=2.0):
#         middle_band = data.rolling(window=period).mean()
#         std = data.rolling(window=period).std()
#         upper_band = middle_band + (std * num_std)
#         lower_band = middle_band - (std * num_std)
#         return upper_band, middle_band, lower_band

# def calculate_option_greeks_simple(spot, strike, option_price, option_type):
#     """NOT USED - Greeks are already in the data (IV, delta)"""
#     if option_type == 'CE':
#         itm_amount = max(0, spot - strike)
#     else:
#         itm_amount = max(0, strike - spot)
#     intrinsic_value = itm_amount
#     time_value = max(0, option_price - intrinsic_value)
#     return {
#         'intrinsic_value': intrinsic_value,
#         'time_value': time_value,
#         'itm_amount': itm_amount
#     }
