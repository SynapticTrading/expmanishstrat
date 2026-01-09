#!/usr/bin/env python
"""
Daily Contract Refresh Script (Futures + Options)

This script refreshes the contracts cache by downloading the latest
futures and options contract information from broker (Zerodha/AngelOne).
Intended to be run daily at 8:30 AM before market open.

Usage:
    python refresh_contracts.py --broker zerodha
    python refresh_contracts.py --broker angelone
    python refresh_contracts.py  (defaults to zerodha)

Cron Schedule (8:30 AM daily):
    30 8 * * * cd /Users/Algo_Trading/manishsir_options && python refresh_contracts.py --broker zerodha >> logs/refresh.log 2>&1
"""

import sys
import logging
import argparse
from datetime import datetime
from pathlib import Path

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent))


def setup_logging():
    """Setup logging for the refresh script."""
    log_dir = Path(__file__).parent / 'logs'
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / 'refresh_contracts.log'

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    return logging.getLogger(__name__)


def _create_cache_from_zerodha(kite):
    """
    Create cache file from Zerodha broker data.
    Fetches BOTH futures AND options.

    Args:
        kite: KiteConnect instance with API access

    Returns:
        Mock manager object with the expiry data
    """
    import json
    from datetime import datetime

    logger = logging.getLogger(__name__)

    # Fetch instruments from Zerodha
    logger.info("Fetching instruments from Zerodha...")
    try:
        instruments = kite.instruments('NFO')
    except Exception as e:
        logger.error(f"Failed to fetch instruments: {e}")
        return None

    logger.info(f"Fetched {len(instruments)} NFO instruments")

    # === PROCESS FUTURES ===
    logger.info("Processing NIFTY futures...")
    futures = [
        inst for inst in instruments
        if inst.get('name') == 'NIFTY'
        and inst.get('instrument_type') == 'FUT'
    ]

    # Sort by expiry date
    futures.sort(key=lambda x: x['expiry'])

    today = datetime.now().date()

    # Build futures contracts list
    futures_contracts = []
    for fut in futures:
        expiry_date = fut['expiry']
        days_to_expiry = (expiry_date - today).days

        # Skip expired contracts
        if days_to_expiry < 0:
            continue

        futures_contracts.append({
            'symbol': fut['tradingsymbol'],
            'exchange': fut['exchange'],
            'instrument_token': fut['instrument_token'],
            'expiry': expiry_date.strftime('%Y-%m-%d'),
            'lot_size': int(fut.get('lot_size', 25)),
            'tick_size': float(fut.get('tick_size', 0.05)),
            'name': 'NIFTY',
            'days_to_expiry': days_to_expiry
        })

    logger.info(f"Found {len(futures_contracts)} NIFTY futures contracts")

    # Create futures mapping
    futures_mapping = {}
    if len(futures_contracts) >= 1:
        futures_mapping['current_month'] = futures_contracts[0]
    if len(futures_contracts) >= 2:
        futures_mapping['next_month'] = futures_contracts[1]
    if len(futures_contracts) >= 3:
        futures_mapping['far_next_month'] = futures_contracts[2]

    # === PROCESS OPTIONS ===
    logger.info("Processing NIFTY options...")
    options = [
        inst for inst in instruments
        if inst.get('name') == 'NIFTY'
        and inst.get('instrument_type') in ['CE', 'PE']
    ]

    logger.info(f"Found {len(options)} NIFTY options contracts")

    # Get unique expiry dates
    expiry_dates = sorted(list(set([
        opt['expiry'].strftime('%Y-%m-%d')
        for opt in options
    ])))

    logger.info(f"Found {len(expiry_dates)} unique options expiry dates")

    # Get strike range
    strikes = sorted(list(set([opt.get('strike', 0) for opt in options if opt.get('strike')])))
    strikes_info = {
        'min': strikes[0] if strikes else 0,
        'max': strikes[-1] if strikes else 0,
        'step': strikes[1] - strikes[0] if len(strikes) > 1 else 50
    }

    # Get lot size (same for all NIFTY options typically)
    lot_sizes = [opt.get('lot_size', 0) for opt in options if opt.get('lot_size')]
    lot_size = lot_sizes[0] if lot_sizes else 65  # Default to 65
    logger.info(f"Options lot size: {lot_size} units per lot")

    # Create options expiry mapping
    options_mapping = {}

    # Find current week expiry
    current_week_expiry = None
    for expiry_str in expiry_dates:
        expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
        if expiry_date >= today:
            days_away = (expiry_date - today).days
            if days_away <= 7:
                current_week_expiry = expiry_str
                break

    # Find next week expiry
    next_week_expiry = None
    if current_week_expiry:
        current_week_date = datetime.strptime(current_week_expiry, '%Y-%m-%d').date()
        for expiry_str in expiry_dates:
            expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
            if expiry_date > current_week_date:
                next_week_expiry = expiry_str
                break

    # Find monthly expiries
    current_month_expiry = None
    next_month_expiry = None

    for expiry_str in expiry_dates:
        expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
        if expiry_date >= today and expiry_date.day >= 24:
            if not current_month_expiry:
                current_month_expiry = expiry_str
            elif not next_month_expiry and expiry_date.month != datetime.strptime(current_month_expiry, '%Y-%m-%d').date().month:
                next_month_expiry = expiry_str

    # Set mappings
    if current_week_expiry:
        options_mapping['current_week'] = current_week_expiry
    if next_week_expiry:
        options_mapping['next_week'] = next_week_expiry
    if current_month_expiry:
        options_mapping['current_month'] = current_month_expiry
    if next_month_expiry:
        options_mapping['next_month'] = next_month_expiry

    # Create cache data structure (FUTURES + OPTIONS)
    cache_data = {
        'timestamp': datetime.now().isoformat(),
        'symbol': 'NIFTY',
        'exchange': 'NFO',
        'futures': {
            'contracts': futures_contracts,
            'mapping': futures_mapping
        },
        'options': {
            'expiry_dates': expiry_dates,
            'mapping': options_mapping,
            'strikes': strikes_info,
            'lot_size': lot_size
        }
    }

    # Save to cache file
    cache_file = Path('contracts_cache.json')
    with open(cache_file, 'w') as f:
        json.dump(cache_data, f, indent=2)

    logger.info(f"Saved {len(futures_contracts)} futures and {len(expiry_dates)} options expiries to cache: {cache_file}")

    # Return mock manager object
    class MockManager:
        def __init__(self):
            self.futures_mapping = futures_mapping
            self.options_mapping = options_mapping

        def get_futures_contract(self, contract_type):
            return self.futures_mapping.get(contract_type)

        def get_current_month(self):
            return self.futures_mapping.get('current_month')

        def get_next_month(self):
            return self.futures_mapping.get('next_month')

        def get_far_next_month(self):
            return self.futures_mapping.get('far_next_month')

        def get_options_expiry(self, expiry_type):
            return self.options_mapping.get(expiry_type)

        def _calculate_days_to_expiry(self, expiry_str):
            expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
            return (expiry_date - today).days

        def should_rollover_futures(self, contract_type, days_threshold=7):
            contract = self.get_futures_contract(contract_type)
            if not contract:
                return False
            return contract['days_to_expiry'] <= days_threshold

        def should_rollover_options(self, expiry_type, days_threshold=2):
            expiry = self.get_options_expiry(expiry_type)
            if not expiry:
                return False
            days_left = self._calculate_days_to_expiry(expiry)
            return days_left <= days_threshold

    return MockManager()


def _create_cache_from_angelone(broker):
    """
    Create cache file from AngelOne broker data.
    Fetches BOTH futures AND options (same as Zerodha).

    Args:
        broker: AngelOneBroker instance with loaded instruments

    Returns:
        Mock manager object with the expiry data
    """
    import json
    from datetime import datetime
    import pandas as pd

    logger = logging.getLogger(__name__)

    # Get all NFO instruments
    if not hasattr(broker, 'nfo_instruments') or broker.nfo_instruments is None or broker.nfo_instruments.empty:
        logger.error("No NFO instruments data available from AngelOne")
        return None

    nfo_df = broker.nfo_instruments

    # === PROCESS FUTURES ===
    logger.info("Processing NIFTY futures...")
    futures = nfo_df[
        (nfo_df['name'] == 'NIFTY') &
        (nfo_df['instrumenttype'] == 'FUTIDX')
    ].copy()

    # Parse expiry dates for futures
    futures['expiry'] = pd.to_datetime(futures['expiry'], format='%d%b%Y').dt.date

    # Sort by expiry
    futures = futures.sort_values('expiry')

    # Calculate days to expiry
    today = datetime.now().date()
    futures['days_to_expiry'] = futures['expiry'].apply(lambda x: (x - today).days)

    # Filter for future expiries only
    futures = futures[futures['days_to_expiry'] >= 0]

    # Build futures contracts list
    futures_contracts = []
    for _, row in futures.iterrows():
        futures_contracts.append({
            'symbol': row['symbol'],
            'exchange': 'NFO',
            'instrument_token': row['token'],
            'expiry': row['expiry'].strftime('%Y-%m-%d'),
            'lot_size': int(row.get('lotsize', 25)),
            'tick_size': float(row.get('tick_size', 0.05)),
            'name': 'NIFTY',
            'days_to_expiry': int(row['days_to_expiry'])
        })

    logger.info(f"Found {len(futures_contracts)} NIFTY futures contracts")

    # Create futures mapping
    futures_mapping = {}
    if len(futures_contracts) >= 1:
        futures_mapping['current_month'] = futures_contracts[0]
    if len(futures_contracts) >= 2:
        futures_mapping['next_month'] = futures_contracts[1]
    if len(futures_contracts) >= 3:
        futures_mapping['far_next_month'] = futures_contracts[2]

    # === PROCESS OPTIONS ===
    logger.info("Processing NIFTY options...")

    # Get NIFTY options from broker (already parsed)
    if not hasattr(broker, 'nifty_options') or broker.nifty_options is None or broker.nifty_options.empty:
        logger.error("No NIFTY options data available from AngelOne")
        return None

    nifty_opts = broker.nifty_options

    # Extract expiry dates
    expiry_dates = sorted(list(set([
        exp.strftime('%Y-%m-%d') if hasattr(exp, 'strftime') else str(exp)
        for exp in nifty_opts['expiry'].unique()
    ])))

    logger.info(f"Found {len(expiry_dates)} unique options expiry dates")

    # Get strike range
    strikes = sorted(list(set(nifty_opts['strike'].dropna())))
    strikes_info = {
        'min': strikes[0] if strikes else 0,
        'max': strikes[-1] if strikes else 0,
        'step': strikes[1] - strikes[0] if len(strikes) > 1 else 50
    }

    # Get lot size (same for all NIFTY options typically)
    lot_size = int(nifty_opts['lotsize'].iloc[0]) if not nifty_opts.empty and 'lotsize' in nifty_opts.columns else 65
    logger.info(f"Options lot size: {lot_size} units per lot")

    # Create options expiry mapping
    options_mapping = {}

    # Find current week expiry
    current_week_expiry = None
    for expiry_str in expiry_dates:
        expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
        if expiry_date >= today:
            days_away = (expiry_date - today).days
            if days_away <= 7:
                current_week_expiry = expiry_str
                break

    # Find next week expiry
    next_week_expiry = None
    if current_week_expiry:
        current_week_date = datetime.strptime(current_week_expiry, '%Y-%m-%d').date()
        for expiry_str in expiry_dates:
            expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
            if expiry_date > current_week_date:
                next_week_expiry = expiry_str
                break

    # Find monthly expiries
    current_month_expiry = None
    next_month_expiry = None

    for expiry_str in expiry_dates:
        expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
        if expiry_date >= today and expiry_date.day >= 24:
            if not current_month_expiry:
                current_month_expiry = expiry_str
            elif not next_month_expiry and expiry_date.month != datetime.strptime(current_month_expiry, '%Y-%m-%d').date().month:
                next_month_expiry = expiry_str

    # Set mappings
    if current_week_expiry:
        options_mapping['current_week'] = current_week_expiry
    if next_week_expiry:
        options_mapping['next_week'] = next_week_expiry
    if current_month_expiry:
        options_mapping['current_month'] = current_month_expiry
    if next_month_expiry:
        options_mapping['next_month'] = next_month_expiry

    # Create cache data structure (FUTURES + OPTIONS - same as Zerodha)
    cache_data = {
        'timestamp': datetime.now().isoformat(),
        'symbol': 'NIFTY',
        'exchange': 'NFO',
        'futures': {
            'contracts': futures_contracts,
            'mapping': futures_mapping
        },
        'options': {
            'expiry_dates': expiry_dates,
            'mapping': options_mapping,
            'strikes': strikes_info,
            'lot_size': lot_size
        }
    }

    # Save to cache file
    cache_file = Path('contracts_cache.json')
    with open(cache_file, 'w') as f:
        json.dump(cache_data, f, indent=2)

    logger.info(f"Saved {len(futures_contracts)} futures and {len(expiry_dates)} options expiries to cache: {cache_file}")

    # Return mock manager object
    class MockManager:
        def __init__(self):
            self.futures_mapping = futures_mapping
            self.options_mapping = options_mapping

        def get_futures_contract(self, contract_type):
            return self.futures_mapping.get(contract_type)

        def get_current_month(self):
            return self.futures_mapping.get('current_month')

        def get_next_month(self):
            return self.futures_mapping.get('next_month')

        def get_far_next_month(self):
            return self.futures_mapping.get('far_next_month')

        def get_options_expiry(self, expiry_type):
            return self.options_mapping.get(expiry_type)

        def _calculate_days_to_expiry(self, expiry_str):
            expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
            return (expiry_date - today).days

        def should_rollover_futures(self, contract_type, days_threshold=7):
            contract = self.get_futures_contract(contract_type)
            if not contract:
                return False
            return contract['days_to_expiry'] <= days_threshold

        def should_rollover_options(self, expiry_type, days_threshold=2):
            expiry = self.get_options_expiry(expiry_type)
            if not expiry:
                return False
            days_left = self._calculate_days_to_expiry(expiry)
            return days_left <= days_threshold

    return MockManager()


def main():
    """Main refresh function."""
    parser = argparse.ArgumentParser(description='Refresh contracts cache from broker')
    parser.add_argument('--broker', choices=['zerodha', 'angelone'], default='zerodha',
                       help='Broker to use (default: zerodha)')
    args = parser.parse_args()

    logger = setup_logging()

    logger.info("=" * 70)
    logger.info("DAILY CONTRACT REFRESH (FUTURES + OPTIONS) - %s", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    logger.info("=" * 70)
    logger.info("Broker: %s", args.broker.upper())

    try:
        # Authenticate with selected broker
        logger.info("\nStep 1/3: Authenticating with %s...", args.broker.capitalize())

        if args.broker == 'zerodha':
            # Use paper trading broker infrastructure for Zerodha
            from paper_trading.legacy.zerodha_connection import load_credentials_from_file
            from paper_trading.utils.factory import create_broker

            # Load Zerodha credentials
            creds_file = Path(__file__).parent / 'paper_trading' / 'config' / 'credentials_zerodha.txt'
            logger.info("Loading credentials from: %s", creds_file)
            credentials = load_credentials_from_file(str(creds_file))

            if not credentials:
                logger.error("Failed to load Zerodha credentials")
                return 1

            # Create Zerodha broker
            broker = create_broker(credentials, 'zerodha')
            if not broker.connect():
                logger.error("Failed to connect to Zerodha")
                return 1

            logger.info("✓ Authentication successful")

            # Load instruments
            logger.info("\nStep 2/3: Loading instruments from Zerodha...")
            if not broker.load_instruments():
                logger.error("Failed to load instruments")
                return 1

            # Create cache using broker's Kite instance
            logger.info("Refreshing contracts...")
            kite = broker.connection.kite
            manager = _create_cache_from_zerodha(kite)

            # Logout
            broker.logout()

        elif args.broker == 'angelone':
            # Use paper trading broker infrastructure for AngelOne
            from paper_trading.legacy.zerodha_connection import load_credentials_from_file
            from paper_trading.utils.factory import create_broker

            # Load AngelOne credentials
            creds_file = Path(__file__).parent / 'paper_trading' / 'config' / 'credentials_angelone.txt'
            logger.info("Loading credentials from: %s", creds_file)
            credentials = load_credentials_from_file(str(creds_file))

            if not credentials:
                logger.error("Failed to load AngelOne credentials")
                return 1

            # Create AngelOne broker
            broker = create_broker(credentials, 'angelone')
            if not broker.connect():
                logger.error("Failed to connect to AngelOne")
                return 1

            logger.info("✓ Authentication successful")

            # Load instruments
            logger.info("\nStep 2/3: Loading instruments from AngelOne...")
            if not broker.load_instruments():
                logger.error("Failed to load instruments")
                return 1

            # Create contract manager using broker's instruments
            logger.info("Refreshing contracts...")
            manager = _create_cache_from_angelone(broker)

            # Logout
            broker.logout()

        logger.info("✓ Contracts refreshed successfully")

        # Display futures contract summary (both brokers)
        logger.info("\nStep 3/3: Verifying contracts...")
        logger.info("\n" + "=" * 70)
        logger.info("FUTURES CONTRACTS")
        logger.info("=" * 70)

        current = manager.get_current_month()
        next_month = manager.get_next_month()
        far_next = manager.get_far_next_month()

        if current:
            logger.info("Current Month:  %s - Expiry: %s (%d days)",
                       current['symbol'], current['expiry'], current['days_to_expiry'])

        if next_month:
            logger.info("Next Month:     %s - Expiry: %s (%d days)",
                       next_month['symbol'], next_month['expiry'], next_month['days_to_expiry'])

        if far_next:
            logger.info("Far Next Month: %s - Expiry: %s (%d days)",
                       far_next['symbol'], far_next['expiry'], far_next['days_to_expiry'])

        # Display options expiry summary
        logger.info("\n" + "=" * 70)
        logger.info("OPTIONS EXPIRY DATES")
        logger.info("=" * 70)

        current_week = manager.get_options_expiry('current_week')
        next_week = manager.get_options_expiry('next_week')
        current_month_opt = manager.get_options_expiry('current_month')
        next_month_opt = manager.get_options_expiry('next_month')

        if current_week:
            days = manager._calculate_days_to_expiry(current_week)
            logger.info("Current Week:   %s (%d days)", current_week, days)

        if next_week:
            days = manager._calculate_days_to_expiry(next_week)
            logger.info("Next Week:      %s (%d days)", next_week, days)

        if current_month_opt:
            days = manager._calculate_days_to_expiry(current_month_opt)
            logger.info("Current Month:  %s (%d days)", current_month_opt, days)

        if next_month_opt:
            days = manager._calculate_days_to_expiry(next_month_opt)
            logger.info("Next Month:     %s (%d days)", next_month_opt, days)

        # Check for futures rollover warnings (both brokers)
        logger.info("\n" + "=" * 70)
        logger.info("FUTURES ROLLOVER CHECK (7-day threshold)")
        logger.info("=" * 70)

        for contract_type in ['current_month', 'next_month', 'far_next_month']:
            contract = manager.get_futures_contract(contract_type)
            if contract:
                needs_rollover = manager.should_rollover_futures(contract_type, days_threshold=7)
                if needs_rollover:
                    logger.warning("⚠️  ROLLOVER NEEDED: %s (%s - %d days to expiry)",
                                 contract_type, contract['symbol'], contract['days_to_expiry'])
                else:
                    logger.info("✓ OK: %s (%s - %d days to expiry)",
                               contract_type, contract['symbol'], contract['days_to_expiry'])

        # Check for options rollover warnings
        logger.info("\n" + "=" * 70)
        logger.info("OPTIONS ROLLOVER CHECK (2-day threshold)")
        logger.info("=" * 70)

        for expiry_type in ['current_week', 'current_month']:
            expiry = manager.get_options_expiry(expiry_type)
            if expiry:
                days = manager._calculate_days_to_expiry(expiry)
                needs_rollover = manager.should_rollover_options(expiry_type, days_threshold=2)
                if needs_rollover:
                    logger.warning("⚠️  ROLLOVER NEEDED: %s (%s - %d days to expiry)",
                                 expiry_type, expiry, days)
                else:
                    logger.info("✓ OK: %s (%s - %d days to expiry)",
                               expiry_type, expiry, days)

        logger.info("\n" + "=" * 70)
        logger.info("REFRESH COMPLETED SUCCESSFULLY")
        logger.info("=" * 70 + "\n")

        return 0

    except Exception as e:
        logger.error("=" * 70)
        logger.error("REFRESH FAILED")
        logger.error("=" * 70)
        logger.error("Error: %s", str(e), exc_info=True)
        logger.error("=" * 70 + "\n")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
