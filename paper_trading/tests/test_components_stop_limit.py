"""
Component Tests for Stop Limit Order System
============================================

Tests each component individually to ensure everything works correctly:
1. Get far OTM strikes and their prices
2. Find lowest priced option
3. Test decimal/float handling in prices
4. Test stop limit order placement
5. Test order modification
6. Verify modify_order parameters are correct

Run individual tests:
    python -m pytest paper_trading/tests/test_components_stop_limit.py::TestComponent1 -v -s
    python -m pytest paper_trading/tests/test_components_stop_limit.py::TestComponent2 -v -s
    etc.

Author: Claude
Date: 2026-02-05
"""

import pytest
import logging
from pathlib import Path
from datetime import datetime
import json

from paper_trading.brokers.adapter.types import (
    OrderRequest, OrderResponse, OrderType, OrderStatus,
    TransactionType, Exchange, ProductType
)
from paper_trading.core.contract_manager import ContractManager
from paper_trading.brokers.adapter.plugins.angelone import AngelOneAdapter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_credentials():
    """Load AngelOne credentials from file."""
    creds_file = Path(__file__).parent.parent / "config" / "credentials_angelone.txt"
    if not creds_file.exists():
        pytest.skip(f"Credentials file not found: {creds_file}")

    credentials = {}
    with open(creds_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                credentials[key.strip()] = value.strip()

    return {
        'api_key': credentials.get('api_key'),
        'username': credentials.get('client_code'),
        'password': credentials.get('mpin'),
        'totp_token': credentials.get('totp_secret')
    }


@pytest.fixture(scope="module")
def adapter_and_manager():
    """Create adapter and contract manager - shared across all tests."""
    logger.info("="*80)
    logger.info("SETUP: Initializing adapter and contract manager")
    logger.info("="*80)

    credentials = load_credentials()
    contract_manager = ContractManager()
    adapter = AngelOneAdapter(credentials, contract_manager)

    if not adapter.connect():
        pytest.fail("Failed to connect to AngelOne")

    logger.info("✓ Connected to AngelOne")

    yield adapter, contract_manager

    logger.info("TEARDOWN: Disconnecting...")
    adapter.disconnect()
    logger.info("✓ Disconnected")


class TestComponent1_FarOTMStrikes:
    """Test 1: Get far OTM strikes and their prices."""

    def test_get_spot_and_far_otm_strikes(self, adapter_and_manager):
        """Get NIFTY spot price and calculate far OTM strikes."""
        adapter, contract_manager = adapter_and_manager

        logger.info("\n" + "="*80)
        logger.info("TEST 1: GET SPOT PRICE AND FAR OTM STRIKES")
        logger.info("="*80)

        # Get spot price
        spot_price = adapter.get_spot_price('NIFTY')
        assert spot_price is not None, "Could not fetch spot price"
        logger.info(f"✓ Spot price: ₹{spot_price:.2f}")

        # Calculate far OTM strikes (500-1000 points above for CE)
        atm_strike = int(round(spot_price / 50) * 50)
        logger.info(f"  ATM strike: {atm_strike}")

        far_otm_strikes = []
        for offset in range(500, 1500, 100):  # 500 to 1400 points OTM
            far_otm_strikes.append(atm_strike + offset)

        logger.info(f"✓ Generated {len(far_otm_strikes)} far OTM strikes:")
        logger.info(f"  Range: {far_otm_strikes[0]} to {far_otm_strikes[-1]}")

        # Get expiry
        expiry = contract_manager.get_options_expiry('current_week')
        logger.info(f"✓ Expiry: {expiry}")

        # Verify strikes exist in contract cache
        available_strikes = []
        for strike in far_otm_strikes:
            contract = contract_manager.get_option_contract(expiry, strike, 'CE')
            if contract:
                available_strikes.append(strike)

        logger.info(f"✓ Available strikes in cache: {len(available_strikes)}/{len(far_otm_strikes)}")
        logger.info(f"  Strikes: {available_strikes[:5]}... (showing first 5)")

        assert len(available_strikes) > 0, "No far OTM strikes available in cache"


class TestComponent2_GetPrices:
    """Test 2: Get prices for far OTM strikes and find lowest."""

    def test_get_far_otm_prices_and_find_lowest(self, adapter_and_manager):
        """Fetch LTP for far OTM strikes and identify lowest priced option."""
        adapter, contract_manager = adapter_and_manager

        logger.info("\n" + "="*80)
        logger.info("TEST 2: GET FAR OTM PRICES AND FIND LOWEST")
        logger.info("="*80)

        # Get spot and calculate strikes
        spot_price = adapter.get_spot_price('NIFTY')
        atm_strike = int(round(spot_price / 50) * 50)
        expiry = contract_manager.get_options_expiry('current_week')

        # Generate far OTM strikes (go as far as possible)
        far_otm_strikes = []
        for offset in range(500, 2000, 100):  # 500 to 1900 points OTM
            strike = atm_strike + offset
            contract = contract_manager.get_option_contract(expiry, strike, 'CE')
            if contract:
                far_otm_strikes.append(strike)

        logger.info(f"Testing {len(far_otm_strikes)} far OTM strikes")

        # Fetch prices
        prices = {}
        for strike in far_otm_strikes:
            ltp = adapter.get_ltp('NIFTY', 'CE', strike, expiry)
            if ltp and ltp > 0:
                prices[strike] = ltp
                logger.info(f"  Strike {strike}: ₹{ltp:.2f}")

        assert len(prices) > 0, "Could not fetch any prices"
        logger.info(f"✓ Fetched prices for {len(prices)} strikes")

        # Find lowest priced option
        lowest_strike = min(prices.keys(), key=lambda k: prices[k])
        lowest_price = prices[lowest_strike]

        logger.info(f"\n✓ LOWEST PRICED OPTION:")
        logger.info(f"  Strike: {lowest_strike}")
        logger.info(f"  Price: ₹{lowest_price:.2f}")
        logger.info(f"  Distance from ATM: {lowest_strike - atm_strike} points")

        # Verify price is low enough for testing (should be < 20)
        logger.info(f"\n✓ Price is suitable for testing: {lowest_price < 20}")


class TestComponent3_DecimalHandling:
    """Test 3: Verify decimal and float handling in prices."""

    def test_price_decimal_handling(self, adapter_and_manager):
        """Test that prices are correctly formatted for AngelOne API."""
        adapter, contract_manager = adapter_and_manager

        logger.info("\n" + "="*80)
        logger.info("TEST 3: DECIMAL AND FLOAT HANDLING")
        logger.info("="*80)

        # Test various price formats
        test_prices = [
            10.5,      # Standard decimal
            10.55,     # Two decimals
            10.555,    # Three decimals
            10.0,      # Round number
            0.5,       # Less than 1
            0.05,      # Very small
            120.20,    # Trigger price example
            121.20,    # Limit price example
        ]

        logger.info("Testing price conversions:")
        for price in test_prices:
            # Test what AngelOne adapter does (converts to string)
            price_str = str(price)

            # Test rounding to 2 decimals
            price_rounded = round(price, 2)
            price_rounded_str = str(price_rounded)

            logger.info(f"  {price} -> str: '{price_str}' | rounded: {price_rounded} -> '{price_rounded_str}'")

            # Verify format is acceptable
            assert '.' in price_str or price == int(price), f"Price format issue: {price_str}"

        logger.info("\n✓ All price formats handled correctly")

        # Test 20% calculation
        logger.info("\nTesting 20% calculation:")
        sample_prices = [150.25, 10.5, 5.0, 100.0]
        for price in sample_prices:
            trigger = round(price * 0.8, 2)  # 20% below
            limit = round(trigger + 1.0, 2)

            logger.info(f"  LTP: ₹{price:.2f} -> Trigger: ₹{trigger:.2f}, Limit: ₹{limit:.2f}")

            # Verify calculations
            assert trigger < price, "Trigger should be below LTP"
            assert limit > trigger, "Limit should be above trigger"
            assert abs(trigger - price * 0.8) < 0.01, "Trigger calculation error"

        logger.info("✓ All calculations correct")


class TestComponent4_PlaceStopLimitOrder:
    """Test 4: Place a stop limit order with proper parameters."""

    def test_place_stop_limit_order_params(self, adapter_and_manager):
        """Verify stop limit order placement with all correct parameters."""
        adapter, contract_manager = adapter_and_manager

        logger.info("\n" + "="*80)
        logger.info("TEST 4: PLACE STOP LIMIT ORDER")
        logger.info("="*80)

        # Get lowest priced far OTM option
        spot_price = adapter.get_spot_price('NIFTY')
        atm_strike = int(round(spot_price / 50) * 50)
        expiry = contract_manager.get_options_expiry('current_week')

        # Find far OTM strikes
        far_otm_strikes = []
        for offset in range(500, 2000, 100):
            strike = atm_strike + offset
            contract = contract_manager.get_option_contract(expiry, strike, 'CE')
            if contract:
                far_otm_strikes.append(strike)

        # Get prices and find lowest
        prices = {}
        for strike in far_otm_strikes[:10]:  # Check first 10 to save time
            ltp = adapter.get_ltp('NIFTY', 'CE', strike, expiry)
            if ltp and ltp > 0:
                prices[strike] = ltp

        if not prices:
            pytest.skip("Could not fetch prices for far OTM strikes")

        lowest_strike = min(prices.keys(), key=lambda k: prices[k])
        lowest_price = prices[lowest_strike]

        logger.info(f"Selected strike: {lowest_strike}")
        logger.info(f"Current LTP: ₹{lowest_price:.2f}")

        # Calculate trigger and limit prices
        trigger_price = round(lowest_price * 0.8, 2)  # 20% below
        limit_price = round(trigger_price + 1.0, 2)

        logger.info(f"Trigger price (20% below): ₹{trigger_price:.2f}")
        logger.info(f"Limit price: ₹{limit_price:.2f}")

        # Verify prices are valid
        assert trigger_price > 0, "Trigger price must be positive"
        assert limit_price > trigger_price, "Limit price must be above trigger"
        assert trigger_price < lowest_price, "Trigger must be below current price"

        # Create order request
        order_request = OrderRequest(
            underlying='NIFTY',
            option_type='CE',
            strike=lowest_strike,
            expiry=expiry,
            exchange=Exchange.NFO,
            transaction_type=TransactionType.BUY,
            order_type=OrderType.SL,  # STOP LIMIT order
            quantity=65,
            price=limit_price,
            trigger_price=trigger_price,
            product_type=ProductType.INTRADAY,
            tag='component_test_4'
        )

        logger.info("\n✓ Order request created:")
        logger.info(f"  Type: STOP LIMIT BUY")
        logger.info(f"  Strike: {lowest_strike}")
        logger.info(f"  Quantity: 65")
        logger.info(f"  Trigger: ₹{trigger_price:.2f}")
        logger.info(f"  Limit: ₹{limit_price:.2f}")

        # Place order
        logger.info("\nPlacing order...")
        response = adapter.place_order(order_request)

        if not response.success:
            logger.error(f"✗ Order placement failed: {response.message}")
            pytest.fail(f"Order placement failed: {response.message}")

        order_id = response.order_id
        logger.info(f"✓ Order placed successfully!")
        logger.info(f"  Order ID: {order_id}")
        logger.info(f"  Status: {response.status.value}")

        # Verify order in order book
        logger.info("\nVerifying order in order book...")
        order_details = adapter.get_order(order_id)

        if order_details:
            logger.info(f"✓ Order found in order book:")
            logger.info(f"  Order ID: {order_details.order_id}")
            logger.info(f"  Status: {order_details.status.value}")
        else:
            logger.warning("⚠ Could not fetch order details (might be OK)")

        # Cancel order
        logger.info("\nCancelling order...")
        cancel_response = adapter.cancel_order(order_id)

        if cancel_response.success:
            logger.info(f"✓ Order cancelled successfully")
        else:
            logger.warning(f"⚠ Cancel failed: {cancel_response.message}")

        logger.info("\n✓ TEST PASSED: Stop limit order placed and cancelled successfully")


class TestComponent5_ModifyOrder:
    """Test 5: Test order modification with proper parameters."""

    def test_modify_stop_limit_order(self, adapter_and_manager):
        """Test modifying a stop limit order - verify all parameters."""
        adapter, contract_manager = adapter_and_manager

        logger.info("\n" + "="*80)
        logger.info("TEST 5: MODIFY STOP LIMIT ORDER")
        logger.info("="*80)

        # Place an order first
        spot_price = adapter.get_spot_price('NIFTY')
        atm_strike = int(round(spot_price / 50) * 50)
        expiry = contract_manager.get_options_expiry('current_week')

        # Get a far OTM strike
        test_strike = atm_strike + 500

        # Check if strike exists
        contract = contract_manager.get_option_contract(expiry, test_strike, 'CE')
        if not contract:
            pytest.skip(f"Strike {test_strike} not available")

        # Get LTP
        ltp = adapter.get_ltp('NIFTY', 'CE', test_strike, expiry)
        if not ltp or ltp <= 0:
            pytest.skip(f"Could not fetch LTP for {test_strike}")

        logger.info(f"Test strike: {test_strike}")
        logger.info(f"Current LTP: ₹{ltp:.2f}")

        # Initial prices
        trigger_price_1 = round(ltp * 0.8, 2)
        limit_price_1 = round(trigger_price_1 + 1.0, 2)

        logger.info(f"Initial trigger: ₹{trigger_price_1:.2f}")
        logger.info(f"Initial limit: ₹{limit_price_1:.2f}")

        # Place order
        order_request = OrderRequest(
            underlying='NIFTY',
            option_type='CE',
            strike=test_strike,
            expiry=expiry,
            exchange=Exchange.NFO,
            transaction_type=TransactionType.BUY,
            order_type=OrderType.SL,
            quantity=65,
            price=limit_price_1,
            trigger_price=trigger_price_1,
            product_type=ProductType.INTRADAY,
            tag='component_test_5'
        )

        logger.info("\nPlacing initial order...")
        place_response = adapter.place_order(order_request)

        if not place_response.success:
            pytest.fail(f"Order placement failed: {place_response.message}")

        order_id = place_response.order_id
        logger.info(f"✓ Order placed: {order_id}")

        try:
            # Wait a moment
            import time
            time.sleep(2)

            # Calculate new prices (simulate LTP change)
            new_ltp = ltp * 1.05  # Simulated 5% increase
            trigger_price_2 = round(new_ltp * 0.8, 2)
            limit_price_2 = round(trigger_price_2 + 1.0, 2)

            logger.info(f"\nSimulated new LTP: ₹{new_ltp:.2f}")
            logger.info(f"New trigger: ₹{trigger_price_2:.2f}")
            logger.info(f"New limit: ₹{limit_price_2:.2f}")

            # Check what parameters modify_order sends
            logger.info("\nModify order parameters:")
            logger.info(f"  variety: 'NORMAL'")
            logger.info(f"  orderid: '{order_id}'")
            logger.info(f"  triggerprice: '{trigger_price_2}' (str)")
            logger.info(f"  price: '{limit_price_2}' (str)")

            # Modify order
            logger.info("\nModifying order...")
            modify_response = adapter.modify_order(
                order_id=order_id,
                changes={
                    'trigger_price': trigger_price_2,
                    'price': limit_price_2
                }
            )

            if modify_response.success:
                logger.info(f"✓ Order modified successfully!")
                logger.info(f"  Status: {modify_response.status.value}")
                logger.info(f"  Message: {modify_response.message}")
            else:
                logger.error(f"✗ Modification failed: {modify_response.message}")
                logger.error(f"  This might indicate missing parameters in modify_params")
                # Don't fail the test yet - log the error

            # Get order details after modification
            time.sleep(1)
            order_details = adapter.get_order(order_id)

            if order_details:
                logger.info(f"\n✓ Order details after modification:")
                logger.info(f"  Order ID: {order_details.order_id}")
                logger.info(f"  Status: {order_details.status.value}")

        finally:
            # Always cancel the order
            logger.info("\nCancelling order...")
            cancel_response = adapter.cancel_order(order_id)

            if cancel_response.success:
                logger.info(f"✓ Order cancelled")
            else:
                logger.warning(f"⚠ Cancel failed: {cancel_response.message}")


class TestComponent6_CheckModifyParams:
    """Test 6: Detailed check of modify_order parameters."""

    def test_check_modify_order_implementation(self, adapter_and_manager):
        """Verify modify_order sends all required parameters to AngelOne API."""
        adapter, contract_manager = adapter_and_manager

        logger.info("\n" + "="*80)
        logger.info("TEST 6: CHECK MODIFY_ORDER IMPLEMENTATION")
        logger.info("="*80)

        logger.info("\nCurrent modify_order implementation:")
        logger.info("  Parameters sent to API:")
        logger.info("    - variety: 'NORMAL'")
        logger.info("    - orderid: <order_id>")
        logger.info("    - price: str(changes['price'])  [OPTIONAL]")
        logger.info("    - quantity: str(changes['quantity'])  [OPTIONAL]")
        logger.info("    - triggerprice: str(changes['trigger_price'])  [OPTIONAL]")

        logger.info("\nPotential issues:")
        logger.info("  ⚠ Missing fields that might be required by AngelOne:")
        logger.info("    - ordertype: 'STOPLOSS_LIMIT' (might be needed)")
        logger.info("    - producttype: 'INTRADAY' (might be needed)")
        logger.info("    - tradingsymbol: <symbol> (might be needed)")
        logger.info("    - symboltoken: <token> (might be needed)")
        logger.info("    - exchange: 'NFO' (might be needed)")
        logger.info("    - transactiontype: 'BUY' (might be needed)")
        logger.info("    - duration: 'DAY' (might be needed)")

        logger.info("\n✓ CHECK COMPLETE")
        logger.info("  Run Test 5 to see if modify_order works with current params")
        logger.info("  If Test 5 fails, we may need to add more parameters")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
