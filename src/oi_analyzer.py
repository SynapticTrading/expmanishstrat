"""
Open Interest (OI) Analyzer Module
Analyzes OI changes to identify short covering and long unwinding
"""

import pandas as pd
import numpy as np


class OIAnalyzer:
    """Analyze Open Interest changes for options"""

    def __init__(self, options_df):
        self.options_df = options_df  # Full dataset (11M rows)
        self.working_df = None  # Cached subset for performance (set via set_working_data)
        self.oi_history = {}

    def set_working_data(self, cached_df):
        """
        Set a cached subset of data for performance optimization.
        When set, all queries will use this cached data instead of full dataset.
        Strategy should call this once per day with ~10K rows instead of 11M.
        """
        self.working_df = cached_df

    def clear_working_data(self):
        """Clear cached working data and revert to full dataset"""
        self.working_df = None

    def _get_active_df(self):
        """Get the dataframe to query - cached subset if available, else full dataset"""
        return self.working_df if self.working_df is not None else self.options_df

    def get_strikes_near_spot(self, spot_price, timestamp, expiry_date, num_strikes_above=5, num_strikes_below=5):
        """Get strikes near spot price for given timestamp and expiry"""
        # Convert to pandas Timestamp if needed (timezone-naive)
        if not isinstance(timestamp, pd.Timestamp):
            timestamp = pd.Timestamp(timestamp)

        # Remove timezone if present
        if hasattr(timestamp, 'tz') and timestamp.tz is not None:
            timestamp = timestamp.tz_localize(None)

        # Use cached working data if available, else full dataset
        active_df = self._get_active_df()

        # Filter options for this timestamp and expiry - find nearest timestamp (within same minute)
        mask = (
            (active_df['expiry'] == expiry_date) &
            (active_df['datetime'] <= timestamp) &
            (active_df['datetime'] >= timestamp - pd.Timedelta(minutes=1))
        )
        options_at_time = active_df[mask].copy()

        # DEBUG: Print filtering details if no data found
        if len(options_at_time) == 0:
            print(f"DEBUG get_strikes_near_spot:")
            print(f"  Looking for expiry: {expiry_date} (type: {type(expiry_date)})")
            print(f"  Timestamp: {timestamp}")
            print(f"  Unique expiries in data: {active_df['expiry'].unique()[:5]}")
            expiry_matches = active_df[active_df['expiry'] == expiry_date]
            print(f"  Rows matching expiry: {len(expiry_matches)}")
            if len(expiry_matches) > 0:
                print(f"  Datetime range for this expiry: {expiry_matches['datetime'].min()} to {expiry_matches['datetime'].max()}")
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
    
    def calculate_max_oi_buildup(self, options_df, spot_price, debug=False):
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

        # Drop rows with NaN OI values before finding max
        calls_valid = calls.dropna(subset=['OI'])
        puts_valid = puts.dropna(subset=['OI'])

        if len(calls_valid) == 0 or len(puts_valid) == 0:
            return None, None, None, None

        # DEBUG: Print all OI values
        if debug:
            print(f"\n{'='*80}")
            print(f"OI DISTRIBUTION DEBUG (Spot: {spot_price:.2f})")
            print(f"{'='*80}")

            # Sort by strike for readability
            calls_sorted = calls_valid.sort_values('strike')
            puts_sorted = puts_valid.sort_values('strike')

            print(f"\nCALL OI by Strike:")
            print(f"{'Strike':<10} {'OI':>15} {'Distance from Spot':>20}")
            print(f"{'-'*50}")
            for _, row in calls_sorted.iterrows():
                distance = row['strike'] - spot_price
                marker = " 👈 MAX" if row['OI'] == calls_valid['OI'].max() else ""
                print(f"{row['strike']:<10.1f} {row['OI']:>15,.0f} {distance:>18.2f}{marker}")

            print(f"\nPUT OI by Strike:")
            print(f"{'Strike':<10} {'OI':>15} {'Distance from Spot':>20}")
            print(f"{'-'*50}")
            for _, row in puts_sorted.iterrows():
                distance = spot_price - row['strike']
                marker = " 👈 MAX" if row['OI'] == puts_valid['OI'].max() else ""
                print(f"{row['strike']:<10.1f} {row['OI']:>15,.0f} {distance:>18.2f}{marker}")
            print(f"{'='*80}\n")

        # Find strike with maximum OI for calls and puts
        max_call_oi_idx = calls_valid['OI'].idxmax()
        max_put_oi_idx = puts_valid['OI'].idxmax()

        max_call_strike = calls_valid.loc[max_call_oi_idx, 'strike']
        max_put_strike = puts_valid.loc[max_put_oi_idx, 'strike']

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

        # Use cached working data if available, else full dataset
        active_df = self._get_active_df()

        # Get current OI - find nearest timestamp (within same minute)
        mask = (
            (active_df['strike'] == strike) &
            (active_df['option_type'] == option_type) &
            (active_df['expiry'] == expiry_date) &
            (active_df['datetime'] <= timestamp) &
            (active_df['datetime'] >= timestamp - pd.Timedelta(minutes=1))
        )

        current_data = active_df[mask]
        
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

        # Use cached working data if available, else full dataset
        active_df = self._get_active_df()

        # Find nearest timestamp (within last 6 minutes to handle 5-min data)
        mask = (
            (active_df['strike'] == strike) &
            (active_df['option_type'] == option_type) &
            (active_df['expiry'] == expiry_date) &
            (active_df['datetime'] <= timestamp) &
            (active_df['datetime'] >= timestamp - pd.Timedelta(minutes=6))
        )

        option_data = active_df[mask]
        
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

        # Get the date part only (ignore time) for comparison
        # This ensures same-day expiries are included even if timestamp is 9:15am
        timestamp_date = pd.Timestamp(timestamp.date())

        # Get expiries on or after today's date (>= instead of >)
        future_expiries = self.options_df[self.options_df['expiry'] >= timestamp_date]['expiry'].unique()

        if len(future_expiries) == 0:
            return None

        # Get the nearest expiry
        expiry_dates = sorted(future_expiries)
        return expiry_dates[0]

