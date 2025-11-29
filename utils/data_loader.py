"""
Data Loader Module
Handles loading and preprocessing of options, spot, and VIX data
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Tuple, Optional
from datetime import datetime, time
import logging

logger = logging.getLogger(__name__)


class DataLoader:
    """Load and preprocess all required data for backtesting"""

    def __init__(self, config):
        """
        Initialize data loader

        Args:
            config: ConfigLoader instance
        """
        self.config = config
        self.weekly_data = None
        self.monthly_data = None
        self.spot_data = None
        self.vix_data = None

    def load_all_data(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Load all required datasets

        Returns:
            Tuple of (weekly_options, monthly_options, spot_price, india_vix)
        """
        logger.info("Loading all data files...")

        # Load weekly options data
        logger.info("Loading weekly options data...")
        self.weekly_data = self._load_options_data('weekly_expiry')

        # Load monthly options data (optional - only if file exists)
        logger.info("Loading monthly options data...")
        try:
            self.monthly_data = self._load_options_data('monthly_expiry')
        except FileNotFoundError:
            logger.warning("Monthly expiry file not found. Skipping monthly data (not required for weekly strategy).")
            self.monthly_data = pd.DataFrame()  # Empty dataframe

        # Load spot price data
        logger.info("Loading spot price data...")
        self.spot_data = self._load_spot_data()

        # Load India VIX data (optional - not used in current strategy)
        logger.info("Loading India VIX data...")
        try:
            self.vix_data = self._load_vix_data()
        except FileNotFoundError:
            logger.warning("India VIX file not found. Skipping VIX data (not required for current strategy).")
            self.vix_data = pd.DataFrame()  # Empty dataframe

        logger.info("All data loaded successfully")

        return self.weekly_data, self.monthly_data, self.spot_data, self.vix_data

    def _load_options_data(self, data_type: str) -> pd.DataFrame:
        """
        Load options data (weekly or monthly)

        Args:
            data_type: 'weekly_expiry' or 'monthly_expiry'

        Returns:
            DataFrame with options data
        """
        file_path = self.config.get_data_path(data_type)

        # Read CSV
        df = pd.read_csv(file_path)

        # Parse timestamp
        if data_type == 'weekly_expiry':
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        else:
            df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Parse expiry date
        df['expiry'] = pd.to_datetime(df['expiry'])

        # Sort by timestamp
        df = df.sort_values('timestamp').reset_index(drop=True)

        # Add additional computed columns
        df['date'] = df['timestamp'].dt.date
        df['time'] = df['timestamp'].dt.time

        logger.info(f"Loaded {len(df)} rows from {data_type}")

        return df

    def _load_spot_data(self) -> pd.DataFrame:
        """
        Load spot price data

        Returns:
            DataFrame with spot price data
        """
        file_path = self.config.get_data_path('spot_price')

        # Read CSV
        df = pd.read_csv(file_path)

        # Parse date column
        df['date'] = pd.to_datetime(df['date'])

        # Sort by date
        df = df.sort_values('date').reset_index(drop=True)

        # Rename for consistency
        df = df.rename(columns={'close': 'spot_price'})

        logger.info(f"Loaded {len(df)} rows of spot price data")

        return df

    def _load_vix_data(self) -> pd.DataFrame:
        """
        Load India VIX data

        Returns:
            DataFrame with VIX data
        """
        file_path = self.config.get_data_path('india_vix')

        # Read CSV
        df = pd.read_csv(file_path)

        # Parse datetime
        df['datetime'] = pd.to_datetime(df['datetime'])

        # Sort by datetime
        df = df.sort_values('datetime').reset_index(drop=True)

        logger.info(f"Loaded {len(df)} rows of VIX data")

        return df

    def get_options_for_date_and_expiry(
        self,
        date: datetime,
        expiry_date: datetime,
        expiry_type: str = 'weekly'
    ) -> pd.DataFrame:
        """
        Get options data for specific date and expiry

        Args:
            date: Trading date
            expiry_date: Expiry date to filter
            expiry_type: 'weekly' or 'monthly'

        Returns:
            Filtered options DataFrame
        """
        data = self.weekly_data if expiry_type == 'weekly' else self.monthly_data

        # Filter by date and expiry
        filtered = data[
            (data['timestamp'].dt.date == date.date()) &
            (data['expiry'].dt.date == expiry_date.date())
        ].copy()

        return filtered

    def get_spot_price_for_timestamp(self, timestamp: datetime) -> Optional[float]:
        """
        Get spot price for a given timestamp

        Args:
            timestamp: Timestamp to lookup

        Returns:
            Spot price or None if not found
        """
        if self.spot_data is None:
            return None

        # Find closest timestamp
        spot_row = self.spot_data[self.spot_data['date'] == timestamp]

        if len(spot_row) > 0:
            return spot_row.iloc[0]['spot_price']

        return None

    def get_vix_for_timestamp(self, timestamp: datetime) -> Optional[float]:
        """
        Get VIX value for a given timestamp

        Args:
            timestamp: Timestamp to lookup

        Returns:
            VIX value or None if not found
        """
        if self.vix_data is None:
            return None

        # Find closest timestamp
        vix_row = self.vix_data[self.vix_data['datetime'] == timestamp]

        if len(vix_row) > 0:
            return vix_row.iloc[0]['vix']

        return None

    def get_closest_expiry(
        self,
        current_date: datetime,
        expiry_type: str = 'weekly',
        skip_mon_tue: bool = False
    ) -> Optional[datetime]:
        """
        Get closest expiry date from current date

        Args:
            current_date: Current trading date
            expiry_type: 'weekly' or 'monthly'
            skip_mon_tue: If True, skip Monday/Tuesday expiries (for testing)
                         Note from PDF: "Might need to be revisited for Monday
                         and Tuesday based on the test results"

        Returns:
            Closest expiry datetime or None
        """
        data = self.weekly_data if expiry_type == 'weekly' else self.monthly_data
        
        # Handle timezone mismatch - remove timezone from current_date if expiry column is timezone-naive
        if hasattr(current_date, 'tz') and current_date.tz is not None:
            if data['expiry'].dt.tz is None:
                current_date = current_date.tz_localize(None)

        # Get unique expiries after current date
        future_expiries = data[data['expiry'] >= current_date]['expiry'].unique()

        if len(future_expiries) == 0:
            return None

        # Sort expiries
        sorted_expiries = sorted(future_expiries)

        # If skip_mon_tue is enabled, filter out Monday/Tuesday expiries
        if skip_mon_tue:
            filtered_expiries = []
            for expiry in sorted_expiries:
                expiry_dt = pd.to_datetime(expiry)
                # 0=Monday, 1=Tuesday, 2=Wednesday, etc.
                if expiry_dt.weekday() not in [0, 1]:
                    filtered_expiries.append(expiry)

            if len(filtered_expiries) > 0:
                return pd.to_datetime(filtered_expiries[0])

            logger.warning("No non-Monday/Tuesday expiries found, using closest")

        # Return the closest one
        return pd.to_datetime(sorted_expiries[0])

    def filter_trading_hours(
        self,
        df: pd.DataFrame,
        start_time: str = "09:15",
        end_time: str = "15:30"
    ) -> pd.DataFrame:
        """
        Filter data to trading hours only

        Args:
            df: DataFrame with timestamp column
            start_time: Start time (HH:MM format)
            end_time: End time (HH:MM format)

        Returns:
            Filtered DataFrame
        """
        start_t = datetime.strptime(start_time, "%H:%M").time()
        end_t = datetime.strptime(end_time, "%H:%M").time()

        # Filter by time
        filtered = df[
            (df['timestamp'].dt.time >= start_t) &
            (df['timestamp'].dt.time <= end_t)
        ].copy()

        return filtered
