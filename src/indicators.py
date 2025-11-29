"""
Custom Indicators for Backtrader
Includes VWAP (anchored to market open)
"""

import backtrader as bt
import pandas as pd
from datetime import time


class VWAP(bt.Indicator):
    """
    VWAP (Volume Weighted Average Price)
    Anchored to market opening (9:15 AM IST)
    Resets every trading day
    """
    lines = ('vwap',)
    
    params = (
        ('period', 1),  # Not used, but kept for compatibility
    )
    
    def __init__(self):
        self.cumulative_tpv = 0.0  # Cumulative Typical Price * Volume
        self.cumulative_volume = 0.0
        self.current_date = None
    
    def next(self):
        # Get current date
        current_dt = self.data.datetime.datetime(0)
        current_date = current_dt.date()
        
        # Reset at start of new day
        if self.current_date is None or current_date != self.current_date:
            self.cumulative_tpv = 0.0
            self.cumulative_volume = 0.0
            self.current_date = current_date
        
        # Calculate typical price
        typical_price = (self.data.high[0] + self.data.low[0] + self.data.close[0]) / 3.0
        
        # Update cumulative values
        volume = self.data.volume[0] if self.data.volume[0] > 0 else 1.0  # Avoid division by zero
        self.cumulative_tpv += typical_price * volume
        self.cumulative_volume += volume
        
        # Calculate VWAP
        if self.cumulative_volume > 0:
            self.lines.vwap[0] = self.cumulative_tpv / self.cumulative_volume
        else:
            self.lines.vwap[0] = typical_price


class OptionVWAP(bt.Indicator):
    """
    VWAP specifically for Options data
    Can handle options data structure
    """
    lines = ('vwap',)
    
    def __init__(self):
        self.cumulative_tpv = 0.0
        self.cumulative_volume = 0.0
        self.current_date = None
        self.first_price = None
    
    def next(self):
        # Get current date
        current_dt = self.data.datetime.datetime(0)
        current_date = current_dt.date()
        
        # Reset at start of new day or at first bar
        if self.current_date is None or current_date != self.current_date:
            self.cumulative_tpv = 0.0
            self.cumulative_volume = 0.0
            self.current_date = current_date
            self.first_price = None
        
        # Store first price of the day as reference
        if self.first_price is None:
            self.first_price = self.data.close[0]
        
        # Calculate typical price
        typical_price = (self.data.high[0] + self.data.low[0] + self.data.close[0]) / 3.0
        
        # Update cumulative values
        # For options, volume might be sporadic, so use 1 as default
        volume = self.data.volume[0] if hasattr(self.data, 'volume') and self.data.volume[0] > 0 else 1.0
        
        self.cumulative_tpv += typical_price * volume
        self.cumulative_volume += volume
        
        # Calculate VWAP
        if self.cumulative_volume > 0:
            self.lines.vwap[0] = self.cumulative_tpv / self.cumulative_volume
        else:
            self.lines.vwap[0] = typical_price


def calculate_vwap_for_option(option_df):
    """
    Calculate VWAP for option price data
    Helper function for non-backtrader usage
    """
    if len(option_df) == 0:
        return None
    
    # Group by date to reset VWAP daily
    option_df = option_df.copy()
    option_df['date'] = option_df['datetime'].dt.date
    
    vwap_values = []
    
    for date, group in option_df.groupby('date'):
        group = group.sort_values('datetime')
        
        # Calculate typical price
        group['typical_price'] = (group['high'] + group['low'] + group['close']) / 3.0
        
        # Calculate cumulative TPV and volume
        group['volume_filled'] = group['volume'].replace(0, 1)  # Handle zero volume
        group['tpv'] = group['typical_price'] * group['volume_filled']
        
        group['cumulative_tpv'] = group['tpv'].cumsum()
        group['cumulative_volume'] = group['volume_filled'].cumsum()
        
        # Calculate VWAP
        group['vwap'] = group['cumulative_tpv'] / group['cumulative_volume']
        
        vwap_values.extend(group['vwap'].tolist())
    
    return vwap_values

