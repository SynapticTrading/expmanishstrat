"""
Open Interest (OI) Analyzer Module
Analyzes OI changes to identify short covering and long unwinding
"""

import pandas as pd
import numpy as np


class OIAnalyzer:
    """Analyze Open Interest changes for options"""
    
    def __init__(self, options_df):
        self.options_df = options_df
        self.oi_history = {}
        
    def get_strikes_near_spot(self, spot_price, timestamp, expiry_date, num_strikes_above=5, num_strikes_below=5):
        """Get strikes near spot price for given timestamp and expiry"""
        # Convert to pandas Timestamp if needed (timezone-naive)
        if not isinstance(timestamp, pd.Timestamp):
            timestamp = pd.Timestamp(timestamp)
        
        # Remove timezone if present
        if hasattr(timestamp, 'tz') and timestamp.tz is not None:
            timestamp = timestamp.tz_localize(None)
        
        # Filter options for this timestamp and expiry - find nearest timestamp (within same minute)
        mask = (
            (self.options_df['expiry'] == expiry_date) &
            (self.options_df['datetime'] <= timestamp) &
            (self.options_df['datetime'] >= timestamp - pd.Timedelta(minutes=1))
        )
        options_at_time = self.options_df[mask].copy()
        
        if len(options_at_time) == 0:
            return None, None
        
        # Get the most recent timestamp
        latest_time = options_at_time['datetime'].max()
        options_at_time = options_at_time[options_at_time['datetime'] == latest_time]
        
        # Get unique strikes
        strikes = sorted(options_at_time['strike'].unique())
        
        # Find strikes around spot
        strikes_below = [s for s in strikes if s < spot_price][-num_strikes_below:]
        strikes_above = [s for s in strikes if s >= spot_price][:num_strikes_above]
        
        selected_strikes = strikes_below + strikes_above
        
        # Filter to selected strikes
        options_filtered = options_at_time[options_at_time['strike'].isin(selected_strikes)]
        
        return options_filtered, selected_strikes
    
    def calculate_max_oi_buildup(self, options_df, spot_price):
        """
        Calculate strike with maximum Call and Put OI buildup
        Returns: (max_call_strike, max_put_strike, call_distance, put_distance)
        """
        if options_df is None or len(options_df) == 0:
            return None, None, None, None
        
        # Separate calls and puts
        calls = options_df[options_df['option_type'] == 'CE'].copy()
        puts = options_df[options_df['option_type'] == 'PE'].copy()
        
        if len(calls) == 0 or len(puts) == 0:
            return None, None, None, None
        
        # Find strike with maximum OI for calls and puts
        max_call_oi_idx = calls['OI'].idxmax()
        max_put_oi_idx = puts['OI'].idxmax()
        
        max_call_strike = calls.loc[max_call_oi_idx, 'strike']
        max_put_strike = puts.loc[max_put_oi_idx, 'strike']
        
        # Calculate distances
        call_distance = max_call_strike - spot_price
        put_distance = spot_price - max_put_strike
        
        return max_call_strike, max_put_strike, call_distance, put_distance
    
    def determine_direction(self, call_distance, put_distance):
        """
        Determine if we should look for Call or Put based on OI buildup
        Returns: 'CALL' or 'PUT'
        """
        if call_distance is None or put_distance is None:
            return None
        
        # If Call buildup is closer to spot, look for Call unwinding
        if call_distance < put_distance:
            return 'CALL'
        else:
            return 'PUT'
    
    def get_nearest_strike(self, spot_price, option_type, available_strikes):
        """
        Get nearest strike to spot price
        For CALL: nearest strike on upper side
        For PUT: nearest strike on lower side
        """
        if option_type == 'CALL':
            # Nearest strike >= spot
            upper_strikes = [s for s in available_strikes if s >= spot_price]
            if upper_strikes:
                return min(upper_strikes)
        else:  # PUT
            # Nearest strike < spot
            lower_strikes = [s for s in available_strikes if s < spot_price]
            if lower_strikes:
                return max(lower_strikes)
        
        return None
    
    def calculate_oi_change(self, strike, option_type, timestamp, expiry_date):
        """
        Calculate OI change for a specific strike and option type
        Returns: (current_oi, oi_change, oi_change_pct)
        """
        # Convert to pandas Timestamp if needed (timezone-naive)
        if not isinstance(timestamp, pd.Timestamp):
            timestamp = pd.Timestamp(timestamp)
        
        # Remove timezone if present
        if hasattr(timestamp, 'tz') and timestamp.tz is not None:
            timestamp = timestamp.tz_localize(None)
        
        # Get current OI - find nearest timestamp (within same minute)
        mask = (
            (self.options_df['strike'] == strike) &
            (self.options_df['option_type'] == option_type) &
            (self.options_df['expiry'] == expiry_date) &
            (self.options_df['datetime'] <= timestamp) &
            (self.options_df['datetime'] >= timestamp - pd.Timedelta(minutes=1))
        )
        
        current_data = self.options_df[mask]
        
        if len(current_data) == 0:
            return None, None, None
        
        # Get the most recent data point
        current_data = current_data.sort_values('datetime').iloc[-1]
        current_oi = current_data['OI']
        
        # Create key for history
        key = f"{strike}_{option_type}_{expiry_date}"
        
        # Get previous OI from history
        if key in self.oi_history:
            prev_oi = self.oi_history[key]
            oi_change = current_oi - prev_oi
            oi_change_pct = (oi_change / prev_oi * 100) if prev_oi > 0 else 0
        else:
            oi_change = 0
            oi_change_pct = 0
        
        # Update history
        self.oi_history[key] = current_oi
        
        return current_oi, oi_change, oi_change_pct
    
    def is_unwinding(self, oi_change):
        """Check if OI is unwinding (decreasing)"""
        if oi_change is None:
            return False
        return oi_change < 0
    
    def get_option_price_data(self, strike, option_type, timestamp, expiry_date):
        """Get option price data for a specific strike and time"""
        # Convert to pandas Timestamp if needed (timezone-naive)
        if not isinstance(timestamp, pd.Timestamp):
            timestamp = pd.Timestamp(timestamp)
        
        # Remove timezone if present
        if hasattr(timestamp, 'tz') and timestamp.tz is not None:
            timestamp = timestamp.tz_localize(None)
        
        # Find nearest timestamp (within same minute)
        mask = (
            (self.options_df['strike'] == strike) &
            (self.options_df['option_type'] == option_type) &
            (self.options_df['expiry'] == expiry_date) &
            (self.options_df['datetime'] <= timestamp) &
            (self.options_df['datetime'] >= timestamp - pd.Timedelta(minutes=1))
        )
        
        option_data = self.options_df[mask]
        
        if len(option_data) == 0:
            return None
        
        # Get the most recent data point
        return option_data.sort_values('datetime').iloc[-1]
    
    def get_closest_expiry(self, timestamp):
        """Get the closest (weekly) expiry date for given timestamp"""
        # Convert to pandas Timestamp if needed (timezone-naive)
        if not isinstance(timestamp, pd.Timestamp):
            timestamp = pd.Timestamp(timestamp)
        
        # Remove timezone if present (we work with naive datetimes now)
        if hasattr(timestamp, 'tz') and timestamp.tz is not None:
            timestamp = timestamp.tz_localize(None)
        
        future_expiries = self.options_df[self.options_df['expiry'] > timestamp]['expiry'].unique()
        
        if len(future_expiries) == 0:
            return None
        
        # Get the nearest expiry
        expiry_dates = sorted(future_expiries)
        return expiry_dates[0]

