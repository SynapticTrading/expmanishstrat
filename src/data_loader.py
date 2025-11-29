"""
Data Loader Module
Handles loading and preprocessing of spot price and options data
Ensures proper IST timezone handling
"""

import pandas as pd
import numpy as np
from datetime import datetime, time
import pytz
from pathlib import Path


class DataLoader:
    """Load and preprocess market data for backtesting"""
    
    def __init__(self, config):
        self.config = config
        self.timezone = pytz.timezone(config['data']['timezone'])
        
    def load_spot_data(self):
        """Load spot price data with proper timezone handling"""
        print("Loading spot price data...")
        
        spot_file = self.config['data']['spot_price_file']
        df = pd.read_csv(spot_file)
        
        # Parse datetime with timezone
        df['datetime'] = pd.to_datetime(df['date'])
        
        # Ensure timezone is set to IST
        if df['datetime'].dt.tz is None:
            df['datetime'] = df['datetime'].dt.tz_localize(self.timezone)
        else:
            df['datetime'] = df['datetime'].dt.tz_convert(self.timezone)
        
        # Set as index
        df.set_index('datetime', inplace=True)
        df.drop('date', axis=1, errors='ignore', inplace=True)
        
        # Filter by date range
        start_date = pd.to_datetime(self.config['data']['start_date']).tz_localize(self.timezone)
        end_date = pd.to_datetime(self.config['data']['end_date']).tz_localize(self.timezone)
        df = df.loc[start_date:end_date]
        
        # Remove timezone for Backtrader compatibility (preserve IST wall-clock time)
        # Convert to string and back to remove timezone while keeping time values
        df.index = pd.to_datetime(df.index.strftime('%Y-%m-%d %H:%M:%S'))
        
        print(f"Loaded {len(df)} spot price records from {df.index[0]} to {df.index[-1]}")
        return df
    
    def load_options_data(self):
        """Load options data with OI information"""
        print("Loading options data (this may take a while for large files)...")
        
        options_file = self.config['data']['options_file']
        
        # Read in chunks to handle large file
        chunk_size = 1000000
        chunks = []
        
        for chunk in pd.read_csv(options_file, chunksize=chunk_size, low_memory=False):
            # Strip timezone info from timestamp strings and parse all as naive
            # This treats all timestamps as IST (both with and without +05:30)
            chunk['timestamp_clean'] = chunk['timestamp'].str.replace(r'\+05:30$', '', regex=True)
            chunk['datetime'] = pd.to_datetime(chunk['timestamp_clean'])
            chunk['datetime'] = chunk['datetime'].dt.tz_localize(self.timezone)
            chunk.drop('timestamp_clean', axis=1, inplace=True)

            # Same for expiry
            chunk['expiry_clean'] = chunk['expiry'].str.replace(r'\+05:30$', '', regex=True)
            chunk['expiry'] = pd.to_datetime(chunk['expiry_clean'])
            chunk['expiry'] = chunk['expiry'].dt.tz_localize(self.timezone)
            chunk.drop('expiry_clean', axis=1, inplace=True)
            
            # Filter by date range
            start_date = pd.to_datetime(self.config['data']['start_date']).tz_localize(self.timezone)
            end_date = pd.to_datetime(self.config['data']['end_date']).tz_localize(self.timezone)
            chunk = chunk[(chunk['datetime'] >= start_date) & (chunk['datetime'] <= end_date)]
            
            if len(chunk) > 0:
                chunks.append(chunk)
        
        df = pd.concat(chunks, ignore_index=True)
        df.drop('timestamp', axis=1, errors='ignore', inplace=True)

        # Remove timezone from options data to match spot data (both in IST market time)
        # Use replace(tzinfo=None) to preserve wall-clock time and just remove timezone metadata
        df['datetime'] = pd.to_datetime(df['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S'))

        # Normalize expiry to date only (remove time component for consistent comparison)
        # Convert to date string and back to midnight timestamp
        df['expiry'] = pd.to_datetime(df['expiry'].dt.strftime('%Y-%m-%d'))

        print(f"Loaded {len(df)} options records")
        return df
    
    def get_weekly_expiry_options(self, options_df):
        """Filter for weekly expiry options only"""
        # Calculate days to expiry (both are now timezone-naive)
        options_df['days_to_expiry'] = (options_df['expiry'] - options_df['datetime']).dt.total_seconds() / (24 * 3600)
        
        # Weekly options typically expire within 7 days
        # Keep options that are closest to expiry (weekly)
        weekly_options = options_df[options_df['days_to_expiry'] <= 7].copy()
        
        print(f"Filtered to {len(weekly_options)} weekly expiry option records")
        return weekly_options
    
    def resample_to_timeframe(self, df, timeframe_minutes):
        """Resample data to specified timeframe (in minutes)"""
        if timeframe_minutes == 1:
            return df  # Already 1-minute data
        
        # Resample to desired timeframe
        resampled = df.resample(f'{timeframe_minutes}T').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        
        return resampled
    
    def filter_trading_hours(self, df):
        """Filter data to keep only trading hours (9:15 AM - 3:30 PM IST)"""
        # Note: Data is now timezone-naive but in IST market time
        market_open = time(9, 15)
        market_close = time(15, 30)
        
        df_filtered = df.between_time(market_open, market_close)
        return df_filtered
    
    def prepare_data(self):
        """Main method to prepare all data for backtesting"""
        # Load spot data
        spot_df = self.load_spot_data()
        spot_df = self.filter_trading_hours(spot_df)
        
        # Resample if needed
        timeframe = self.config['data']['timeframe']
        if timeframe > 1:
            spot_df = self.resample_to_timeframe(spot_df, timeframe)
        
        # Load options data
        options_df = self.load_options_data()
        options_df = self.get_weekly_expiry_options(options_df)
        
        return spot_df, options_df

