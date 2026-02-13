"""
Test: Stop Limit Order Placement and Periodic Modification
===========================================================

Purpose:
    Test the system's ability to place stop limit orders and modify them
    periodically based on changing market prices using AngelOne broker.

Test Flow:
    1. Select NIFTY FAR OTM strike (500-1900 points away)
    2. Find LOWEST priced option among far OTM strikes
    3. Place stop limit BUY order 20% below current price
    4. Periodically (1 min interval) fetch new LTP
    5. Modify order to maintain 20% below current price
    6. Log all prices and order details
    7. Order should never execute (20% below = safe)
    8. On Ctrl+C: Cancel all pending orders automatically

Usage:
    python -m pytest paper_trading/tests/test_stop_limit_modify.py -v -s

Requirements:
    - AngelOne credentials configured
    - Market should be open for accurate LTP
    - Contract cache should be up-to-date

Author: Claude
Date: 2026-02-05
"""

import pytest
import logging
import time
from datetime import datetime
from pathlib import Path
import json
import sys

from paper_trading.brokers.adapter.types import (
    OrderRequest, OrderResponse, OrderType, OrderStatus,
    TransactionType, Exchange, ProductType
)
from paper_trading.core.contract_manager import ContractManager
from paper_trading.brokers.adapter.plugins.angelone import AngelOneAdapter

# Setup logging with immediate output
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Force stdout to flush immediately
sys.stdout.reconfigure(line_buffering=True)

# Test configuration
TEST_CONFIG = {
    'underlying': 'NIFTY',
    'option_type': 'CE',  # Call option
    'far_otm_min': 500,   # Minimum points away from ATM
    'far_otm_max': 1900,  # Maximum points away from ATM
    'far_otm_step': 100,  # Step size for strikes
    'quantity': 65,  # 1 lot for NIFTY
    'stop_loss_pct': 0.40,  # 40% below current price (SAFE - won't fill easily!)
    'check_interval_seconds': 30,  # Check every 30 seconds (reduced from 15s to avoid rate limits)
    'max_iterations': None,  # Run indefinitely until Ctrl+C (None = infinite)
    'price_buffer': 0.05,  # Limit price buffer above trigger (1 tick) - BOTH prices stay below market!
    'modify_threshold': 0.01,  # Modify on any change >= ₹0.01 (1 paisa) - basically immediate
    'api_delay_seconds': 2,  # Delay between API calls to avoid rate limits
}


class TestStopLimitModify:
    """Test stop limit order placement and modification."""

    def _round_to_tick_size(self, price, tick_size=0.05):
        """
        Round price to nearest tick size (AngelOne requires 5 paise multiples).

        Args:
            price: Price to round
            tick_size: Tick size (default 0.05 for 5 paise)

        Returns:
            Price rounded to nearest tick size

        Examples:
            1.44 → 1.45 (rounds up to nearest 0.05)
            1.47 → 1.45 (rounds down to nearest 0.05)
            1.475 → 1.50 (rounds up to nearest 0.05)
        """
        return round(price / tick_size) * tick_size

    @pytest.fixture(scope="class")
    def setup(self):
        """Setup test environment."""
        print("\n" + "="*80)
        print("STOP LIMIT ORDER TEST - SETUP")
        print("="*80)
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)

        # Load credentials
        print("\n[1/6] Loading credentials...")
        creds_file = Path(__file__).parent.parent / "config" / "credentials_angelone.txt"
        if not creds_file.exists():
            pytest.skip(f"Credentials file not found: {creds_file}")

        credentials = self._load_credentials(creds_file)
        print("✓ Credentials loaded")

        # Initialize contract manager
        print("\n[2/6] Initializing contract manager...")
        contract_manager = ContractManager()
        print("✓ Contract manager initialized")

        # Initialize AngelOne adapter
        print("\n[3/6] Initializing AngelOne adapter...")
        adapter = AngelOneAdapter(credentials, contract_manager)
        print("✓ Adapter initialized")

        # Connect
        print("\n[4/6] Connecting to AngelOne...")
        print("      (This may take 10-30 seconds - downloading master instruments)")
        sys.stdout.flush()

        if not adapter.connect():
            pytest.fail("Failed to connect to AngelOne")

        print("✓ Connected to AngelOne successfully")

        # Get spot price
        print("\n[5/6] Fetching spot price...")
        sys.stdout.flush()

        spot_price = adapter.get_spot_price(TEST_CONFIG['underlying'])
        if spot_price is None:
            pytest.fail("Could not fetch spot price")

        print(f"✓ Spot price: {TEST_CONFIG['underlying']} = ₹{spot_price:.2f}")

        # Calculate ATM strike
        atm_strike = int(round(spot_price / 50) * 50)
        print(f"✓ ATM strike: {atm_strike}")

        # Find FAR OTM strikes and select lowest priced one
        print("\n[6/6] Finding FAR OTM strikes and selecting lowest priced option...")
        print(f"      Searching strikes from ATM+{TEST_CONFIG['far_otm_min']} to ATM+{TEST_CONFIG['far_otm_max']}")
        sys.stdout.flush()

        selected_strike, selected_token, selected_expiry, selected_ltp = self._find_lowest_priced_far_otm(
            adapter, contract_manager, atm_strike
        )

        if selected_strike is None:
            pytest.fail("Could not find valid far OTM strike")

        print(f"\n✓ SELECTED: Strike {selected_strike} CE (ATM+{selected_strike - atm_strike})")
        print(f"  Token: {selected_token}")
        print(f"  Expiry: {selected_expiry}")
        print(f"  Current LTP: ₹{selected_ltp:.2f}")
        print(f"  Reason: LOWEST PRICE among far OTM strikes")

        # Create logs directory
        log_dir = Path(__file__).parent / "logs"
        log_dir.mkdir(exist_ok=True)

        log_file = log_dir / f"stop_limit_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        print(f"\n✓ Setup complete!")
        print(f"✓ Logs will be saved to: {log_file}")
        print("="*80)

        setup_data = {
            'adapter': adapter,
            'contract_manager': contract_manager,
            'strike': selected_strike,
            'expiry': selected_expiry,
            'token': selected_token,
            'log_file': log_file,
            'logs': [],
            'order_id': None  # Will store the placed order ID
        }

        yield setup_data

        # Cleanup
        print("\n" + "="*80)
        print("CLEANUP")
        print("="*80)

        # Cancel any pending orders
        if setup_data['order_id']:
            print(f"Cancelling order {setup_data['order_id']}...")
            try:
                adapter.cancel_order(setup_data['order_id'])
                print(f"✓ Order cancelled")
            except Exception as e:
                print(f"⚠ Error cancelling order: {e}")

        print("Disconnecting from AngelOne...")
        adapter.disconnect()
        print("✓ Disconnected")
        print("="*80)

    def _load_credentials(self, creds_file):
        """Load credentials from file."""
        credentials = {}
        with open(creds_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    credentials[key.strip()] = value.strip()

        # Map to expected keys (read directly from file fields)
        return {
            'api_key': credentials.get('api_key'),
            'username': credentials.get('username'),
            'password': credentials.get('password'),
            'totp_token': credentials.get('totp_token')
        }

    def _find_lowest_priced_far_otm(self, adapter, contract_manager, atm_strike):
        """
        Find the lowest priced option among far OTM strikes.

        Returns:
            (strike, token, expiry, ltp) tuple or (None, None, None, None)
        """
        expiry = contract_manager.get_options_expiry('current_week')

        # Generate far OTM strikes
        far_otm_strikes = range(
            atm_strike + TEST_CONFIG['far_otm_min'],
            atm_strike + TEST_CONFIG['far_otm_max'] + TEST_CONFIG['far_otm_step'],
            TEST_CONFIG['far_otm_step']
        )

        print(f"      Generated {len(list(far_otm_strikes))} potential strikes")

        # Get prices for all available strikes
        strike_prices = {}
        available_count = 0

        for strike in far_otm_strikes:
            contract = contract_manager.get_option_contract(
                expiry, strike, TEST_CONFIG['option_type']
            )

            if contract:
                token = contract.get('token')
                ltp = adapter.get_ltp(
                    underlying=TEST_CONFIG['underlying'],
                    option_type=TEST_CONFIG['option_type'],
                    strike=strike,
                    expiry=expiry
                )

                if ltp and ltp > 0:
                    strike_prices[strike] = (token, expiry, ltp)
                    available_count += 1
                    print(f"      ✓ Strike {strike}: ₹{ltp:.2f}")
                    sys.stdout.flush()

                # Add delay to avoid rate limiting (AngelOne has ~3 requests/sec limit)
                time.sleep(1)  # Increased from 0.5s to 1s to be safer

        if not strike_prices:
            return None, None, None, None

        print(f"\n      Found {available_count} available far OTM strikes with valid prices")

        # Find the strike with lowest price
        lowest_strike = min(strike_prices.keys(), key=lambda s: strike_prices[s][2])
        lowest_token, lowest_expiry, lowest_ltp = strike_prices[lowest_strike]

        print(f"      Lowest priced: Strike {lowest_strike} at ₹{lowest_ltp:.2f}")

        return lowest_strike, lowest_token, lowest_expiry, lowest_ltp

    def test_place_and_modify_stop_limit_order(self, setup):
        """
        Main test: Place stop limit order and modify periodically.

        Flow:
            1. Get initial LTP
            2. Place stop limit order 20% below
            3. Loop indefinitely:
                - Wait 1 minute
                - Fetch new LTP
                - Calculate new trigger price (20% below)
                - Modify order if change >= ₹0.50
                - Log details
            4. On Ctrl+C: Cancel order and save logs
        """
        adapter = setup['adapter']
        strike = setup['strike']
        expiry = setup['expiry']
        log_file = setup['log_file']
        logs = setup['logs']

        print("\n" + "="*80)
        print("STEP 1: GET INITIAL LTP")
        print("="*80)
        sys.stdout.flush()

        # Get initial LTP
        initial_ltp = adapter.get_ltp(
            underlying=TEST_CONFIG['underlying'],
            option_type=TEST_CONFIG['option_type'],
            strike=strike,
            expiry=expiry
        )

        if initial_ltp is None:
            pytest.fail(f"Could not fetch LTP for {strike} {TEST_CONFIG['option_type']}")

        print(f"✓ Initial LTP: ₹{initial_ltp:.2f}")

        # Calculate initial trigger and limit prices (rounded to 5 paise tick size)
        trigger_price = self._round_to_tick_size(initial_ltp * (1 - TEST_CONFIG['stop_loss_pct']))
        limit_price = self._round_to_tick_size(trigger_price + TEST_CONFIG['price_buffer'])

        print(f"\nCALCULATION:")
        print(f"  Current LTP: ₹{initial_ltp:.2f}")
        print(f"  Trigger ({TEST_CONFIG['stop_loss_pct']*100:.0f}% below): {initial_ltp:.2f} × {1-TEST_CONFIG['stop_loss_pct']:.2f} = ₹{trigger_price:.2f}")
        print(f"  Limit (trigger + buffer): {trigger_price:.2f} + {TEST_CONFIG['price_buffer']:.2f} = ₹{limit_price:.2f}")
        print(f"  Gap to trigger: ₹{initial_ltp - trigger_price:.2f} ({TEST_CONFIG['stop_loss_pct']*100:.0f}%)")

        print("\n" + "="*80)
        print("STEP 2: PLACE STOP LIMIT ORDER")
        print("="*80)
        sys.stdout.flush()

        # Create order request
        order_request = OrderRequest(
            underlying=TEST_CONFIG['underlying'],
            option_type=TEST_CONFIG['option_type'],
            strike=strike,
            expiry=expiry,
            exchange=Exchange.NFO,
            transaction_type=TransactionType.BUY,
            order_type=OrderType.SL,  # Stop limit order
            quantity=TEST_CONFIG['quantity'],
            price=limit_price,
            trigger_price=trigger_price,
            product_type=ProductType.INTRADAY,
            tag='test_stop_limit_modify'
        )

        # Place order
        place_response = adapter.place_order(order_request)

        if not place_response.success:
            pytest.fail(f"Failed to place order: {place_response.message}")

        order_id = place_response.order_id
        setup['order_id'] = order_id  # Store for cleanup

        print(f"\n✓✓✓ ORDER PLACED SUCCESSFULLY ✓✓✓")
        print(f"    Order ID: {order_id}")
        print(f"    Strike: {strike} CE")
        print(f"    Type: STOP LIMIT BUY (variety=STOPLOSS, ordertype=STOPLOSS_LIMIT)")
        print(f"    Product: INTRADAY")
        print(f"    Quantity: {TEST_CONFIG['quantity']} (1 lot)")
        print(f"    Trigger: ₹{trigger_price:.2f}")
        print(f"    Limit: ₹{limit_price:.2f}")
        print(f"    Status: PENDING")
        print(f"\n    WHY THIS ORDER WILL NEVER FILL:")
        print(f"    • Trigger is {TEST_CONFIG['stop_loss_pct']*100:.0f}% below market (₹{trigger_price:.2f} vs ₹{initial_ltp:.2f})")
        print(f"    • We'll keep updating trigger every {TEST_CONFIG['check_interval_seconds']} seconds")
        print(f"    • Market would need to crash {TEST_CONFIG['stop_loss_pct']*100:.0f}% in <{TEST_CONFIG['check_interval_seconds']} seconds to fill")
        print(f"    • This proves our modification logic works!")

        # Log initial placement
        logs.append({
            'iteration': 0,
            'timestamp': datetime.now().isoformat(),
            'action': 'PLACE_ORDER',
            'order_id': order_id,
            'strike': strike,
            'option_type': TEST_CONFIG['option_type'],
            'product_type': 'INTRADAY',
            'ltp': initial_ltp,
            'trigger_price': trigger_price,
            'limit_price': limit_price,
            'gap_to_trigger': initial_ltp - trigger_price,
            'gap_percentage': TEST_CONFIG['stop_loss_pct'] * 100,
            'order_status': 'PENDING',
            'explanation': f"Placed stop limit BUY order {order_id} for strike {strike} CE at LTP ₹{initial_ltp:.2f}. "
                          f"Set trigger at ₹{trigger_price:.2f} (20% below LTP) and limit at ₹{limit_price:.2f}. "
                          f"Gap to trigger is ₹{initial_ltp - trigger_price:.2f} (20.0%). "
                          f"Order will not fill unless market crashes 20% before next modification."
        })

        print("\n" + "="*80)
        print("STEP 3: PERIODIC LTP CHECK AND ORDER MODIFICATION")
        print("="*80)
        print("RUNNING INDEFINITELY - Press Ctrl+C to stop")
        print(f"Checking every {TEST_CONFIG['check_interval_seconds']} seconds")
        print(f"Order will NEVER fill because trigger stays {TEST_CONFIG['stop_loss_pct']*100:.0f}% below market")
        print("="*80)
        sys.stdout.flush()

        # Store current prices
        current_trigger = trigger_price
        current_limit = limit_price
        iteration = 0

        try:
            while True:
                iteration += 1

                print(f"\n--- Iteration {iteration} ---")
                print(f"Waiting {TEST_CONFIG['check_interval_seconds']} seconds...")
                sys.stdout.flush()

                time.sleep(TEST_CONFIG['check_interval_seconds'])

                # Fetch new LTP
                new_ltp = adapter.get_ltp(
                    underlying=TEST_CONFIG['underlying'],
                    option_type=TEST_CONFIG['option_type'],
                    strike=strike,
                    expiry=expiry
                )

                if new_ltp is None:
                    print(f"⚠️  Could not fetch LTP, skipping iteration")
                    continue

                print(f"Order ID: {order_id}")
                print(f"Current LTP: ₹{new_ltp:.2f}")
                print(f"Current trigger: ₹{current_trigger:.2f}")
                print(f"Current limit: ₹{current_limit:.2f}")
                sys.stdout.flush()

                # Calculate new trigger and limit (rounded to 5 paise tick size)
                new_trigger = self._round_to_tick_size(new_ltp * (1 - TEST_CONFIG['stop_loss_pct']))
                new_limit = self._round_to_tick_size(new_trigger + TEST_CONFIG['price_buffer'])

                print(f"\nCalculation:")
                print(f"  {TEST_CONFIG['stop_loss_pct']*100:.0f}% below LTP: {new_ltp:.2f} × {1-TEST_CONFIG['stop_loss_pct']:.2f} = ₹{new_trigger:.2f}")
                print(f"  Limit price: {new_trigger:.2f} + {TEST_CONFIG['price_buffer']:.2f} = ₹{new_limit:.2f}")
                sys.stdout.flush()

                # Check if modification is needed
                trigger_change = abs(new_trigger - current_trigger)

                print(f"\nChanges:")
                print(f"  LTP change: {new_ltp - initial_ltp:+.2f}")
                print(f"  Trigger change: {new_trigger - current_trigger:+.2f} (from ₹{current_trigger:.2f} to ₹{new_trigger:.2f})")
                sys.stdout.flush()

                if trigger_change >= TEST_CONFIG['modify_threshold']:
                    print(f"\n✓ MODIFICATION NEEDED")
                    print(f"    Reason: Trigger change ₹{trigger_change:.2f} >= ₹{TEST_CONFIG['modify_threshold']:.2f} threshold")
                    print(f"    Order ID: {order_id}")
                    print(f"    Strike: {strike} CE")
                    sys.stdout.flush()

                    # STEP 1: Check order status BEFORE modifying
                    print(f"\n    STEP 1: Checking order status...")
                    sys.stdout.flush()

                    # Add delay to avoid rate limiting
                    time.sleep(TEST_CONFIG.get('api_delay_seconds', 2))

                    try:
                        order_book = adapter._smart_api.orderBook()
                        if not order_book or not order_book.get('status'):
                            print(f"    ❌ ERROR: Could not fetch order book")
                            continue

                        # Find our order
                        current_order = None
                        for o in order_book.get('data', []):
                            if str(o.get('orderid')) == str(order_id):
                                current_order = o
                                break

                        if not current_order:
                            print(f"    ❌ ERROR: Order {order_id} not found in order book")
                            print(f"    Order may have been cancelled or rejected")
                            break

                        order_status = current_order.get('orderstatus', '').lower()
                        print(f"    Order status: {order_status}")

                        # DEBUG: Show order type BEFORE modification
                        print(f"\n    DEBUG: Order details BEFORE modification:")
                        print(f"      ordertype: '{current_order.get('ordertype')}'")
                        print(f"      variety: '{current_order.get('variety')}'")
                        print(f"      triggerprice: '{current_order.get('triggerprice')}'")
                        print(f"      price: '{current_order.get('price')}'")
                        sys.stdout.flush()

                        # Check if order can be modified
                        modifiable_statuses = ['open', 'pending', 'trigger pending', 'trigger_pending']
                        if order_status not in modifiable_statuses:
                            print(f"    ❌ CANNOT MODIFY: Order status is '{order_status}'")
                            print(f"    Only orders with status {modifiable_statuses} can be modified")
                            print(f"    Order details:")
                            print(f"      Trigger price on broker: ₹{current_order.get('triggerprice', 0)}")
                            print(f"      Limit price on broker: ₹{current_order.get('price', 0)}")
                            print(f"      Status: {order_status}")
                            if current_order.get('text'):
                                print(f"      Message: {current_order.get('text')}")

                            # Log failed attempt
                            logs.append({
                                'iteration': iteration,
                                'timestamp': datetime.now().isoformat(),
                                'action': 'MODIFY_REJECTED',
                                'order_id': order_id,
                                'reason': f"Order status is '{order_status}', cannot modify",
                                'broker_trigger_price': float(current_order.get('triggerprice', 0)),
                                'broker_limit_price': float(current_order.get('price', 0)),
                                'attempted_trigger_price': new_trigger,
                                'attempted_limit_price': new_limit
                            })
                            break

                        # Get current prices from broker
                        broker_trigger = float(current_order.get('triggerprice', 0))
                        broker_limit = float(current_order.get('price', 0))

                        print(f"    ✓ Order is modifiable (status: {order_status})")
                        print(f"    Current prices on broker:")
                        print(f"      Trigger: ₹{broker_trigger:.2f}")
                        print(f"      Limit: ₹{broker_limit:.2f}")
                        sys.stdout.flush()

                    except Exception as e:
                        print(f"    ❌ ERROR checking order status: {e}")
                        continue

                    # STEP 2: Attempt modification
                    print(f"\n    STEP 2: Modifying order...")
                    print(f"    WHY: Current LTP is ₹{new_ltp:.2f}")
                    print(f"         We need trigger {TEST_CONFIG['stop_loss_pct']*100:.0f}% below = ₹{new_trigger:.2f}")
                    print(f"         Broker trigger ₹{broker_trigger:.2f} is outdated")
                    print(f"\n    HOW: Sending modify request with:")
                    print(f"         • Trigger: ₹{broker_trigger:.2f} → ₹{new_trigger:.2f} (change: {new_trigger - broker_trigger:+.2f})")
                    print(f"         • Limit:   ₹{broker_limit:.2f} → ₹{new_limit:.2f}")
                    sys.stdout.flush()

                    # SAVE old values BEFORE modification
                    old_trigger = broker_trigger
                    old_limit = broker_limit

                    # STEP 2: Modify order
                    print(f"\n    STEP 2: Modifying order...")
                    sys.stdout.flush()

                    modify_response = adapter.modify_order(
                        order_id,
                        {
                            'trigger_price': new_trigger,
                            'price': new_limit
                        }
                    )

                    if modify_response.success:
                        print(f"    ✓ Modify API returned success")
                        sys.stdout.flush()

                        # STEP 3: VERIFY modification on broker side
                        print(f"\n    STEP 3: Verifying modification on broker...")
                        sys.stdout.flush()

                        try:
                            # Wait for broker to process and avoid rate limiting
                            time.sleep(TEST_CONFIG.get('api_delay_seconds', 2))

                            # Fetch order book again to verify
                            verify_book = adapter._smart_api.orderBook()
                            if verify_book and verify_book.get('status'):
                                verified_order = None
                                for o in verify_book.get('data', []):
                                    if str(o.get('orderid')) == str(order_id):
                                        verified_order = o
                                        break

                                if verified_order:
                                    # DEBUG: Print raw order data to see what broker is returning
                                    print(f"\n    DEBUG: Raw order data from broker:")
                                    print(f"      triggerprice: '{verified_order.get('triggerprice')}'")
                                    print(f"      price: '{verified_order.get('price')}'")
                                    print(f"      ordertype: '{verified_order.get('ordertype')}'")
                                    print(f"      variety: '{verified_order.get('variety')}'")
                                    print(f"      orderstatus: '{verified_order.get('orderstatus')}'")

                                    actual_trigger = float(verified_order.get('triggerprice', 0))
                                    actual_limit = float(verified_order.get('price', 0))

                                    print(f"\n    Broker order details after modification:")
                                    print(f"      Trigger: ₹{actual_trigger:.2f}")
                                    print(f"      Limit: ₹{actual_limit:.2f}")

                                    # Check if modification actually happened
                                    if abs(actual_trigger - new_trigger) < 0.01 and abs(actual_limit - new_limit) < 0.01:
                                        print(f"\n✓✓✓ MODIFICATION VERIFIED ON BROKER ✓✓✓")
                                        print(f"    Order ID: {order_id}")
                                        print(f"    Order Type: {verified_order.get('ordertype')} (variety: {verified_order.get('variety')})")
                                        print(f"    Status: {verified_order.get('orderstatus')}")
                                        print(f"    Updated trigger: ₹{actual_trigger:.2f} (was ₹{old_trigger:.2f})")
                                        print(f"    Updated limit: ₹{actual_limit:.2f} (was ₹{old_limit:.2f})")
                                        print(f"    LTP at modification: ₹{new_ltp:.2f}")
                                        print(f"    Gap to trigger: ₹{new_ltp - actual_trigger:.2f} ({TEST_CONFIG['stop_loss_pct']*100:.0f}%)")
                                        sys.stdout.flush()

                                        # Update current prices AFTER verification
                                        current_trigger = actual_trigger
                                        current_limit = actual_limit

                                        verification_status = "VERIFIED"
                                    else:
                                        print(f"\n❌ MODIFICATION FAILED ON BROKER!")
                                        print(f"    Expected trigger: ₹{new_trigger:.2f}")
                                        print(f"    Actual trigger: ₹{actual_trigger:.2f}")
                                        print(f"    Expected limit: ₹{new_limit:.2f}")
                                        print(f"    Actual limit: ₹{actual_limit:.2f}")
                                        print(f"    The broker did NOT update the order!")
                                        sys.stdout.flush()

                                        verification_status = "FAILED"
                                        current_trigger = actual_trigger  # Use actual broker values
                                        current_limit = actual_limit
                                else:
                                    print(f"    ⚠ Could not find order in order book for verification")
                                    verification_status = "UNKNOWN"
                                    current_trigger = new_trigger
                                    current_limit = new_limit
                            else:
                                print(f"    ⚠ Could not fetch order book for verification")
                                verification_status = "UNKNOWN"
                                current_trigger = new_trigger
                                current_limit = new_limit

                        except Exception as e:
                            print(f"    ⚠ Error verifying modification: {e}")
                            verification_status = "ERROR"
                            current_trigger = new_trigger
                            current_limit = new_limit

                        # Log modification with verification status
                        logs.append({
                            'iteration': iteration,
                            'timestamp': datetime.now().isoformat(),
                            'action': 'MODIFY_ORDER',
                            'order_id': order_id,
                            'strike': strike,
                            'option_type': TEST_CONFIG['option_type'],
                            'ltp': new_ltp,
                            'ltp_change': new_ltp - initial_ltp,
                            'broker_old_trigger_price': old_trigger,  # Actual broker value before
                            'requested_trigger_price': new_trigger,  # What we asked for
                            'actual_trigger_price': current_trigger,  # Actual broker value after
                            'trigger_change': current_trigger - old_trigger,
                            'broker_old_limit_price': old_limit,
                            'requested_limit_price': new_limit,
                            'actual_limit_price': current_limit,
                            'limit_change': current_limit - old_limit,
                            'verification_status': verification_status,
                            'order_status': modify_response.status.value if hasattr(modify_response.status, 'value') else str(modify_response.status),
                            'gap_to_trigger': new_ltp - current_trigger,
                            'gap_percentage': TEST_CONFIG['stop_loss_pct'] * 100,
                            'explanation': f"Modified order {order_id} at LTP ₹{new_ltp:.2f}. "
                                          f"Requested trigger ₹{new_trigger:.2f}, actual ₹{current_trigger:.2f}. "
                                          f"Broker trigger changed from ₹{old_trigger:.2f} to ₹{current_trigger:.2f}. "
                                          f"Verification: {verification_status}."
                        })
                    else:
                        print(f"\n❌ MODIFICATION FAILED")
                        print(f"    Error: {modify_response.message}")
                        sys.stdout.flush()

                        # Log failed modification
                        logs.append({
                            'iteration': iteration,
                            'timestamp': datetime.now().isoformat(),
                            'action': 'MODIFY_FAILED',
                            'order_id': order_id,
                            'error': modify_response.message,
                            'ltp': new_ltp,
                            'attempted_trigger': new_trigger,
                            'attempted_limit': new_limit
                        })
                else:
                    print(f"\n⚠️  SKIPPING MODIFICATION")
                    print(f"    Reason: Trigger change ₹{trigger_change:.2f} < ₹{TEST_CONFIG['modify_threshold']:.2f} threshold")
                    print(f"    Order {order_id} remains unchanged")
                    print(f"    Trigger stays at: ₹{current_trigger:.2f}")
                    print(f"    Limit stays at: ₹{current_limit:.2f}")
                    sys.stdout.flush()

                    # Log skip
                    logs.append({
                        'iteration': iteration,
                        'timestamp': datetime.now().isoformat(),
                        'action': 'SKIP_MODIFY',
                        'order_id': order_id,
                        'ltp': new_ltp,
                        'ltp_change': new_ltp - initial_ltp,
                        'old_trigger_price': current_trigger,
                        'new_trigger_price': new_trigger,
                        'trigger_change': new_trigger - current_trigger,
                        'old_limit_price': current_limit,
                        'new_limit_price': new_limit,
                        'reason': 'trigger_change_below_threshold',
                        'threshold': TEST_CONFIG['modify_threshold'],
                        'explanation': f"Trigger change ₹{trigger_change:.2f} is less than ₹{TEST_CONFIG['modify_threshold']:.2f} threshold, keeping order unchanged"
                    })

        except KeyboardInterrupt:
            print("\n\n" + "="*80)
            print("STOPPED BY USER (Ctrl+C)")
            print("="*80)
            print(f"Total iterations completed: {iteration}")
            print("Proceeding to cleanup...")
            sys.stdout.flush()

            # Cancel order
            print("\n" + "="*80)
            print("STEP 4: CANCEL ORDER AND CLEANUP")
            print("="*80)

            if order_id:
                print(f"Cancelling order {order_id}...")
                sys.stdout.flush()
                try:
                    cancel_response = adapter.cancel_order(order_id)
                    if cancel_response.success:
                        print(f"✓ Order cancelled successfully")
                    else:
                        print(f"⚠ Error cancelling order: {cancel_response.message}")
                except Exception as e:
                    print(f"⚠ Error cancelling order: {e}")

                # Log cancellation
                logs.append({
                    'iteration': 'final',
                    'timestamp': datetime.now().isoformat(),
                    'action': 'CANCEL_ORDER',
                    'order_id': order_id,
                    'order_status': 'CANCELLED'
                })

            sys.stdout.flush()

            # Save logs to file
            print("\n" + "="*80)
            print("STEP 5: SAVE LOGS")
            print("="*80)

            with open(log_file, 'w') as f:
                json.dump({
                    'test_config': TEST_CONFIG,
                    'test_params': {
                        'strike': strike,
                        'expiry': expiry,
                        'token': setup['token']
                    },
                    'logs': logs
                }, f, indent=2)

            print(f"✓ Logs saved to: {log_file}")
            sys.stdout.flush()

            # Summary
            print("\n" + "="*80)
            print("TEST SUMMARY")
            print("="*80)
            modifications = len([l for l in logs if l['action'] == 'MODIFY_ORDER'])
            skipped = len([l for l in logs if l['action'] == 'SKIP_MODIFY'])
            failed = len([l for l in logs if l['action'] == 'MODIFY_FAILED'])

            print(f"Total iterations: {iteration}")
            print(f"Successful modifications: {modifications}")
            print(f"Failed modifications: {failed}")
            print(f"Skipped modifications: {skipped}")
            print("="*80)
            sys.stdout.flush()
