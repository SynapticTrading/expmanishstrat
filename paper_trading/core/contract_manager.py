"""
Contract Manager for Paper Trading (Read-Only from Universal Cache)

Reads NIFTY options contract data from the universal cache file at:
/Users/Algo_Trading/manishsir_options/contracts_cache.json

This cache is maintained by the root-level refresh_contracts.py script.
The contract manager only reads the options data (current_week, next_week, etc.)
and ignores futures data.

Options: current_week, next_week, current_month, next_month

Usage:
    manager = ContractManager()

    # Get options expiry dates
    current_week_expiry = manager.get_options_expiry('current_week')

    # Check if rollover needed
    if manager.should_rollover_options('current_week', days_threshold=2):
        next_expiry = manager.get_options_expiry('next_week')

    # Auto-reload when cache is updated by refresh_contracts.py
    manager.check_and_reload_if_updated()
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ContractManager:
    """
    Manages NIFTY options contracts with automatic expiry-based mapping.

    Reads from universal cache file maintained by refresh_contracts.py.
    Only extracts and uses options data (ignores futures).

    Attributes:
        cache_file: Path to universal contracts cache JSON file
        symbol: Underlying symbol (NIFTY)

        Options:
            options_expiry_dates: List of available options expiry dates
            options_expiry_mapping: Dict mapping expiry types to dates
            options_strikes: Dict with min, max, step for strikes
    """

    def __init__(self, broker_api=None, cache_file=None, symbol='NIFTY'):
        """
        Initialize the ContractManager.

        Args:
            broker_api: Not used - kept for compatibility
            cache_file: Path to cache file (defaults to root contracts_cache.json)
            symbol: Underlying symbol (default: 'NIFTY')
        """
        self.broker_api = broker_api
        self.symbol = symbol

        # Setup cache file path - use universal cache at root level
        if cache_file is None:
            # Point to root-level universal cache
            root_dir = Path(__file__).parent.parent.parent
            self.cache_file = root_dir / "contracts_cache.json"
        else:
            self.cache_file = Path(cache_file)

        # Options data
        self.options_expiry_dates = []
        self.options_expiry_mapping = {}
        self.options_strikes = {'min': 0, 'max': 0, 'step': 50}
        self.options_lot_size = 65  # Default NIFTY options lot size (1 lot = 65 units)

        # Track cache file modification time for auto-reload
        self.cache_mtime = None

        # Load from cache
        cache_loaded = self._load_from_cache()

        if cache_loaded:
            logger.info(f"✓ Loaded contracts from universal cache: {self.cache_file}")
            # Store initial modification time
            if self.cache_file.exists():
                self.cache_mtime = self.cache_file.stat().st_mtime
        else:
            logger.warning(f"⚠️  Could not load cache from {self.cache_file}")
            logger.warning(f"Please run: python refresh_contracts.py")

    def _create_options_mapping(self):
        """Create mapping of options expiry types to dates."""
        self.options_expiry_mapping = {}

        if not self.options_expiry_dates:
            return

        today = datetime.now().date()

        # Find current week expiry (Thursday of current week or next available)
        current_week_expiry = None
        for expiry_str in self.options_expiry_dates:
            expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
            if expiry_date >= today:
                # Check if it's within 7 days (current week)
                days_away = (expiry_date - today).days
                if days_away <= 7:
                    current_week_expiry = expiry_str
                    break

        # Find next week expiry
        next_week_expiry = None
        if current_week_expiry:
            current_week_date = datetime.strptime(current_week_expiry, '%Y-%m-%d').date()
            for expiry_str in self.options_expiry_dates:
                expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
                if expiry_date > current_week_date:
                    next_week_expiry = expiry_str
                    break

        # Find current month expiry (monthly expiry - last Thursday)
        current_month_expiry = None
        next_month_expiry = None

        for expiry_str in self.options_expiry_dates:
            expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
            if expiry_date >= today:
                # Monthly expiry typically has more days (> 20 days from start of month)
                if expiry_date.day >= 24:  # Last Thursday typically falls after 24th
                    if not current_month_expiry:
                        current_month_expiry = expiry_str
                    elif not next_month_expiry and expiry_date.month != datetime.strptime(current_month_expiry, '%Y-%m-%d').date().month:
                        next_month_expiry = expiry_str

        # Set mappings
        if current_week_expiry:
            self.options_expiry_mapping['current_week'] = current_week_expiry
        elif self.options_expiry_dates:
            self.options_expiry_mapping['current_week'] = self.options_expiry_dates[0]

        if next_week_expiry:
            self.options_expiry_mapping['next_week'] = next_week_expiry
        elif len(self.options_expiry_dates) > 1:
            self.options_expiry_mapping['next_week'] = self.options_expiry_dates[1]

        if current_month_expiry:
            self.options_expiry_mapping['current_month'] = current_month_expiry

        if next_month_expiry:
            self.options_expiry_mapping['next_month'] = next_month_expiry

    def _calculate_days_to_expiry(self, expiry_date_str: str) -> int:
        """
        Calculate days remaining until expiry.

        Args:
            expiry_date_str: Expiry date as string (YYYY-MM-DD)

        Returns:
            int: Days until expiry
        """
        expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d').date()
        today = datetime.now().date()
        return (expiry_date - today).days

    def _is_cache_stale(self, max_age_hours=24) -> bool:
        """
        Check if cache is older than max_age_hours.

        Args:
            max_age_hours: Maximum cache age in hours (default: 24)

        Returns:
            bool: True if cache is stale
        """
        if not self.cache_file.exists():
            return True

        try:
            with open(self.cache_file, 'r') as f:
                data = json.load(f)

            cache_time = datetime.fromisoformat(data.get('timestamp', '2000-01-01T00:00:00'))
            age = datetime.now() - cache_time

            return age.total_seconds() > (max_age_hours * 3600)

        except Exception as e:
            logger.warning(f"Error checking cache age: {e}")
            return True

    def _load_from_cache(self) -> bool:
        """
        Load contracts from cache file.

        Returns:
            bool: True if successfully loaded from cache
        """
        if not self.cache_file.exists():
            logger.info("No cache file found")
            return False

        try:
            with open(self.cache_file, 'r') as f:
                data = json.load(f)

            # Load options data
            options_data = data.get('options', {})
            self.options_expiry_dates = options_data.get('expiry_dates', [])
            self.options_strikes = options_data.get('strikes', {'min': 0, 'max': 0, 'step': 50})
            self.options_lot_size = options_data.get('lot_size', 65)  # Default to 65 if not in cache

            self._create_options_mapping()

            cache_time = data.get('timestamp', 'unknown')
            logger.info(f"Loaded {len(self.options_expiry_dates)} options expiries from cache (cached at: {cache_time})")
            logger.info(f"Options lot size: {self.options_lot_size} units per lot")

            return True

        except Exception as e:
            logger.error(f"Error loading from cache: {e}")
            return False


    def check_and_reload_if_updated(self) -> bool:
        """
        Check if cache file has been updated externally (e.g., by cronjob) and reload if needed.

        Returns:
            bool: True if cache was reloaded, False otherwise
        """
        try:
            if not self.cache_file.exists():
                logger.warning("Cache file no longer exists")
                return False

            # Get current modification time
            current_mtime = self.cache_file.stat().st_mtime

            # Check if file was modified since we last loaded it
            if self.cache_mtime is None or current_mtime > self.cache_mtime:
                logger.info("=" * 70)
                logger.info("CACHE FILE UPDATED - RELOADING CONTRACTS")
                logger.info("=" * 70)
                logger.info(f"Previous mtime: {self.cache_mtime}")
                logger.info(f"Current mtime:  {current_mtime}")

                # Reload from cache
                cache_loaded = self._load_from_cache()

                if cache_loaded:
                    # Update modification time
                    self.cache_mtime = current_mtime

                    logger.info("✓ Contracts reloaded successfully")
                    logger.info(f"  Options: {len(self.options_expiry_dates)} expiry dates")

                    # Log active expiry
                    current_week = self.get_options_expiry('current_week')
                    if current_week:
                        days = self._calculate_days_to_expiry(current_week)
                        logger.info(f"  Active Options: {current_week} ({days} days)")

                    logger.info("=" * 70)
                    return True
                else:
                    logger.error("Failed to reload cache")
                    return False

            return False

        except Exception as e:
            logger.error(f"Error checking cache update: {e}")
            return False

    # ===== OPTIONS METHODS =====

    def get_options_expiry(self, expiry_type: str) -> Optional[str]:
        """
        Get options expiry date by type.

        Args:
            expiry_type: One of 'current_week', 'next_week', 'current_month', 'next_month'

        Returns:
            str: Expiry date (YYYY-MM-DD) or None if not available
        """
        valid_types = ['current_week', 'next_week', 'current_month', 'next_month']

        if expiry_type not in valid_types:
            raise ValueError(f"Invalid expiry_type: {expiry_type}. Must be one of {valid_types}")

        return self.options_expiry_mapping.get(expiry_type)

    def get_all_options_expiry_dates(self) -> List[str]:
        """
        Get all available options expiry dates.

        Returns:
            list: List of expiry dates (YYYY-MM-DD) sorted by date
        """
        return self.options_expiry_dates

    def get_options_lot_size(self) -> int:
        """
        Get NIFTY options lot size.

        Returns:
            int: Lot size (number of units per lot)
        """
        return self.options_lot_size

    def get_atm_strike(self, spot_price: float, round_to: int = None) -> int:
        """
        Get ATM (At The Money) strike price closest to spot price.

        Args:
            spot_price: Current spot price
            round_to: Strike interval to round to (default: use strike step from data)

        Returns:
            int: ATM strike price
        """
        if round_to is None:
            round_to = self.options_strikes.get('step', 50)

        return int(round(spot_price / round_to) * round_to)

    def get_strike_range(self, center_strike: int, num_strikes: int = 5) -> List[int]:
        """
        Get a range of strike prices around a center strike.

        Args:
            center_strike: Center strike price
            num_strikes: Number of strikes on each side (default: 5)

        Returns:
            list: List of strike prices
        """
        step = self.options_strikes.get('step', 50)
        strikes = []

        for i in range(-num_strikes, num_strikes + 1):
            strike = center_strike + (i * step)
            if self.options_strikes['min'] <= strike <= self.options_strikes['max']:
                strikes.append(strike)

        return strikes

    # ===== ROLLOVER METHODS =====

    def should_rollover_options(self, expiry_type: str, days_threshold: int = 2) -> bool:
        """
        Check if options should be rolled over to next expiry.

        Args:
            expiry_type: Options expiry type to check ('current_week', 'current_month', etc.)
            days_threshold: Rollover when days to expiry <= this value

        Returns:
            bool: True if rollover is needed
        """
        expiry = self.get_options_expiry(expiry_type)

        if not expiry:
            logger.warning(f"Options expiry type '{expiry_type}' not available")
            return False

        days_left = self._calculate_days_to_expiry(expiry)

        if days_left <= days_threshold:
            logger.warning(f"⚠️ Options rollover recommended for {expiry_type}: {days_left} days until expiry (threshold: {days_threshold})")
            return True

        return False

    def get_options_rollover_target(self, current_expiry_type: str) -> Optional[str]:
        """
        Get the target options expiry for rollover.

        Args:
            current_expiry_type: Current options expiry type

        Returns:
            str: Target expiry date (YYYY-MM-DD) or None
        """
        if current_expiry_type == 'current_week':
            return self.get_options_expiry('next_week')
        elif current_expiry_type == 'current_month':
            return self.get_options_expiry('next_month')
        else:
            logger.warning(f"No rollover target defined for {current_expiry_type}")
            return None

    def _print_mapping(self):
        """Print current contract mapping for options."""
        print("\n" + "=" * 70)
        print("OPTIONS EXPIRY MAPPING")
        print("=" * 70)

        for expiry_type in ['current_week', 'next_week', 'current_month', 'next_month']:
            expiry = self.options_expiry_mapping.get(expiry_type)
            if expiry:
                days = self._calculate_days_to_expiry(expiry)
                print(f"\n{expiry_type.upper().replace('_', ' ')}:")
                print(f"  Expiry Date:      {expiry}")
                print(f"  Days to Expiry:   {days} days")
            else:
                print(f"\n{expiry_type.upper().replace('_', ' ')}: Not Available")

        if self.options_strikes['max'] > 0:
            print(f"\nOPTIONS STRIKE RANGE:")
            print(f"  Min Strike:       {self.options_strikes['min']}")
            print(f"  Max Strike:       {self.options_strikes['max']}")
            print(f"  Strike Step:      {self.options_strikes['step']}")

        print("\n" + "=" * 70 + "\n")

    def get_contract_summary(self) -> str:
        """
        Get a summary string of all options contracts.

        Returns:
            str: Summary of contracts
        """
        summary = []

        # Options summary
        summary.append(f"\n{self.symbol} Options Expiry Dates:")
        for i, expiry in enumerate(self.options_expiry_dates[:5]):
            days = self._calculate_days_to_expiry(expiry)
            expiry_type = ''
            for etype, edate in self.options_expiry_mapping.items():
                if edate == expiry:
                    expiry_type = f" [{etype}]"
                    break
            summary.append(f"  {expiry}{expiry_type} ({days} days)")

        if self.options_strikes['max'] > 0:
            summary.append(f"\nOptions Strikes: {self.options_strikes['min']} - {self.options_strikes['max']} (step: {self.options_strikes['step']})")

        return '\n'.join(summary)
