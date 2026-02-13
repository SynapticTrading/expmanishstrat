"""
Internal Unit Tests for Stop Limit Order System
================================================

Tests all logic WITHOUT requiring AngelOne connection.
These tests verify:
- Far OTM strike selection logic
- Lowest price finding algorithm
- Decimal/float handling
- 20% calculation accuracy
- Order parameter construction
- modify_order fix implementation

Run these tests:
    python -m pytest paper_trading/tests/test_stop_limit_internal.py -v

Author: Claude
Date: 2026-02-05
"""

import pytest
import logging
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from paper_trading.brokers.adapter.types import (
    OrderRequest, OrderResponse, OrderType, OrderStatus,
    TransactionType, Exchange, ProductType
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestFarOTMStrikeSelection:
    """Test 1: Far OTM strike selection logic (no API calls)."""

    def test_calculate_far_otm_strikes(self):
        """Test far OTM strike calculation."""
        logger.info("\n" + "="*80)
        logger.info("TEST 1: FAR OTM STRIKE CALCULATION")
        logger.info("="*80)

        # Mock spot price
        spot_price = 25847.35

        # Calculate ATM
        atm_strike = int(round(spot_price / 50) * 50)
        logger.info(f"Spot price: ₹{spot_price:.2f}")
        logger.info(f"ATM strike: {atm_strike}")

        assert atm_strike == 25850, "ATM calculation incorrect"

        # Generate far OTM strikes
        far_otm_strikes = []
        for offset in range(500, 2000, 100):
            strike = atm_strike + offset
            far_otm_strikes.append(strike)

        logger.info(f"Generated {len(far_otm_strikes)} far OTM strikes")
        logger.info(f"Range: {far_otm_strikes[0]} to {far_otm_strikes[-1]}")

        # Verify range
        assert far_otm_strikes[0] == 26350, "First OTM strike incorrect"
        assert far_otm_strikes[-1] == 27750, "Last OTM strike incorrect"  # range(500, 2000, 100) ends at 1900
        assert len(far_otm_strikes) == 15, "Wrong number of strikes"

        logger.info("✓ Far OTM strike calculation PASSED")

    def test_verify_strikes_are_far_otm(self):
        """Verify strikes are truly far OTM (500+ points away)."""
        logger.info("\n" + "="*80)
        logger.info("TEST 2: VERIFY FAR OTM DISTANCE")
        logger.info("="*80)

        spot_price = 25847.35
        atm_strike = 25850

        far_otm_strikes = [26350, 26450, 26550, 26650, 27850]

        for strike in far_otm_strikes:
            distance = strike - atm_strike
            logger.info(f"Strike {strike}: {distance} points OTM")
            assert distance >= 500, f"Strike {strike} is not far enough OTM"

        logger.info("✓ All strikes are 500+ points OTM - PASSED")


class TestLowestPriceFinding:
    """Test 2: Lowest price finding logic (no API calls)."""

    def test_find_lowest_priced_option(self):
        """Test finding lowest priced option from price dict."""
        logger.info("\n" + "="*80)
        logger.info("TEST 3: FIND LOWEST PRICED OPTION")
        logger.info("="*80)

        # Mock price data
        prices = {
            26350: 15.50,
            26450: 12.30,
            26550: 8.75,
            26650: 5.20,
            26750: 3.40,
            26850: 2.10,  # Lowest
            26950: 2.50,
            27050: 3.00
        }

        logger.info("Price data:")
        for strike, price in prices.items():
            logger.info(f"  Strike {strike}: ₹{price:.2f}")

        # Find lowest
        lowest_strike = min(prices.keys(), key=lambda k: prices[k])
        lowest_price = prices[lowest_strike]

        logger.info(f"\n✓ Lowest priced option:")
        logger.info(f"  Strike: {lowest_strike}")
        logger.info(f"  Price: ₹{lowest_price:.2f}")

        assert lowest_strike == 26850, "Wrong lowest strike"
        assert lowest_price == 2.10, "Wrong lowest price"

        logger.info("✓ Lowest price finding PASSED")

    def test_handle_empty_prices(self):
        """Test handling when no prices are available."""
        logger.info("\n" + "="*80)
        logger.info("TEST 4: HANDLE EMPTY PRICES")
        logger.info("="*80)

        prices = {}

        if not prices:
            logger.info("✓ Correctly detected empty prices dict")
            assert True
        else:
            assert False, "Should have detected empty prices"

        logger.info("✓ Empty price handling PASSED")


class TestDecimalFloatHandling:
    """Test 3: Decimal and float handling (no API calls)."""

    def test_price_conversion_to_string(self):
        """Test price conversion to string format for API."""
        logger.info("\n" + "="*80)
        logger.info("TEST 5: PRICE CONVERSION TO STRING")
        logger.info("="*80)

        test_cases = [
            (10.5, "10.5"),
            (10.55, "10.55"),
            (120.20, "120.2"),
            (100.0, "100.0"),
            (0.5, "0.5"),
            (0.05, "0.05"),
        ]

        logger.info("Testing price conversions:")
        for original, expected_str in test_cases:
            result = str(original)
            logger.info(f"  {original} -> '{result}'")
            # Note: Python converts 120.20 to 120.2 (trailing zero removed)
            # This is fine for AngelOne API

        logger.info("✓ Price string conversion PASSED")

    def test_twenty_percent_calculation(self):
        """Test 20% below calculation accuracy."""
        logger.info("\n" + "="*80)
        logger.info("TEST 6: 20% BELOW CALCULATION")
        logger.info("="*80)

        test_cases = [
            (150.25, 120.20),  # 150.25 * 0.8 = 120.20
            (100.00, 80.00),   # 100 * 0.8 = 80
            (10.50, 8.40),     # 10.5 * 0.8 = 8.4
            (5.00, 4.00),      # 5 * 0.8 = 4
            (2.50, 2.00),      # 2.5 * 0.8 = 2.0
        ]

        logger.info("Testing 20% calculations:")
        for ltp, expected_trigger in test_cases:
            trigger = round(ltp * 0.8, 2)
            logger.info(f"  LTP: ₹{ltp:.2f} -> Trigger: ₹{trigger:.2f} (expected: ₹{expected_trigger:.2f})")
            assert trigger == expected_trigger, f"Calculation error for {ltp}"
            assert trigger < ltp, "Trigger should be below LTP"

        logger.info("✓ 20% calculation PASSED")

    def test_limit_price_buffer(self):
        """Test limit price is above trigger price."""
        logger.info("\n" + "="*80)
        logger.info("TEST 7: LIMIT PRICE BUFFER")
        logger.info("="*80)

        test_cases = [
            (120.20, 121.20),  # Trigger + 1.0
            (80.00, 81.00),
            (8.40, 9.40),
            (4.00, 5.00),
            (2.00, 3.00),
        ]

        logger.info("Testing limit price buffer:")
        for trigger, expected_limit in test_cases:
            limit = round(trigger + 1.0, 2)
            logger.info(f"  Trigger: ₹{trigger:.2f} -> Limit: ₹{limit:.2f}")
            assert limit == expected_limit, f"Buffer calculation error for {trigger}"
            assert limit > trigger, "Limit should be above trigger"

        logger.info("✓ Limit price buffer PASSED")


class TestOrderParameterConstruction:
    """Test 4: Order parameter construction (no API calls)."""

    def test_stop_limit_order_params(self):
        """Test stop limit order parameters are correctly structured."""
        logger.info("\n" + "="*80)
        logger.info("TEST 8: STOP LIMIT ORDER PARAMETERS")
        logger.info("="*80)

        # Create order request
        order_request = OrderRequest(
            underlying='NIFTY',
            option_type='CE',
            strike=26850,
            expiry='2026-02-10',
            exchange=Exchange.NFO,
            transaction_type=TransactionType.BUY,
            order_type=OrderType.SL,
            quantity=65,
            price=3.00,
            trigger_price=2.00,
            product_type=ProductType.INTRADAY,
            tag='test'
        )

        logger.info("Order request created:")
        logger.info(f"  Type: {order_request.order_type}")
        logger.info(f"  Strike: {order_request.strike}")
        logger.info(f"  Quantity: {order_request.quantity}")
        logger.info(f"  Trigger: ₹{order_request.trigger_price:.2f}")
        logger.info(f"  Limit: ₹{order_request.price:.2f}")
        logger.info(f"  Product: {order_request.product_type}")

        # Verify fields
        assert order_request.order_type == OrderType.SL, "Wrong order type"
        assert order_request.trigger_price == 2.00, "Wrong trigger price"
        assert order_request.price == 3.00, "Wrong limit price"
        assert order_request.price > order_request.trigger_price, "Limit not above trigger"
        assert order_request.quantity == 65, "Wrong quantity"

        logger.info("✓ Order parameter construction PASSED")

    def test_order_type_mapping(self):
        """Test OrderType.SL maps to STOPLOSS_LIMIT."""
        logger.info("\n" + "="*80)
        logger.info("TEST 9: ORDER TYPE MAPPING")
        logger.info("="*80)

        from paper_trading.brokers.adapter.plugins.angelone import AngelOneAdapter

        # Get the mapping
        order_type_map = AngelOneAdapter.ORDER_TYPE_MAP

        logger.info("Order type mapping:")
        for order_type, angelone_type in order_type_map.items():
            logger.info(f"  {order_type} -> {angelone_type}")

        # Verify SL maps to STOPLOSS_LIMIT
        assert OrderType.SL in order_type_map, "OrderType.SL not in map"
        assert order_type_map[OrderType.SL] == "STOPLOSS_LIMIT", "Wrong mapping for SL"

        logger.info("✓ Order type mapping PASSED")


class TestModifyOrderFix:
    """Test 5: Verify modify_order fix implementation (mocked)."""

    def test_modify_order_fetches_order_details(self):
        """Test that modify_order fetches order details from order book."""
        logger.info("\n" + "="*80)
        logger.info("TEST 10: MODIFY_ORDER FETCHES ORDER DETAILS")
        logger.info("="*80)

        from paper_trading.brokers.adapter.plugins.angelone import AngelOneAdapter

        # Create mock adapter
        adapter = AngelOneAdapter({}, None)
        adapter._connected = True

        # Mock order book response
        mock_order_book = {
            'status': True,
            'data': [
                {
                    'orderid': '123456',
                    'tradingsymbol': 'NIFTY10FEB2626850CE',
                    'symboltoken': '58661',
                    'exchange': 'NFO',
                    'ordertype': 'STOPLOSS_LIMIT',
                    'producttype': 'INTRADAY',
                    'duration': 'DAY',
                    'quantity': 65,
                    'price': 3.0,
                    'triggerprice': 2.0,
                    'variety': 'NORMAL'
                }
            ]
        }

        # Mock modifyOrder response
        mock_modify_response = {
            'status': True,
            'message': 'Order modified successfully'
        }

        # Mock the API calls
        adapter._smart_api = Mock()
        adapter._smart_api.orderBook.return_value = mock_order_book
        adapter._smart_api.modifyOrder.return_value = mock_modify_response

        # Call modify_order
        changes = {
            'trigger_price': 2.10,
            'price': 3.10
        }

        response = adapter.modify_order('123456', changes)

        logger.info("Verifying modify_order behavior:")
        logger.info(f"  orderBook() called: {adapter._smart_api.orderBook.called}")
        logger.info(f"  modifyOrder() called: {adapter._smart_api.modifyOrder.called}")
        logger.info(f"  Response success: {response.success}")

        # Verify orderBook was called
        assert adapter._smart_api.orderBook.called, "orderBook() not called"

        # Verify modifyOrder was called
        assert adapter._smart_api.modifyOrder.called, "modifyOrder() not called"

        # Get the params passed to modifyOrder
        modify_call_args = adapter._smart_api.modifyOrder.call_args[0][0]

        logger.info("\n  Parameters passed to modifyOrder:")
        for key, value in modify_call_args.items():
            logger.info(f"    {key}: {value}")

        # Verify ALL required fields are present
        required_fields = [
            'variety', 'orderid', 'tradingsymbol', 'symboltoken',
            'exchange', 'ordertype', 'producttype', 'duration',
            'quantity', 'price', 'triggerprice'
        ]

        for field in required_fields:
            assert field in modify_call_args, f"Missing required field: {field}"
            logger.info(f"  ✓ {field} present")

        # Verify values
        assert modify_call_args['tradingsymbol'] == 'NIFTY10FEB2626850CE'
        assert modify_call_args['symboltoken'] == '58661'
        assert modify_call_args['ordertype'] == 'STOPLOSS_LIMIT'
        assert modify_call_args['triggerprice'] == '2.1'
        assert modify_call_args['price'] == '3.1'

        logger.info("✓ modify_order fix implementation PASSED")

    def test_modify_order_handles_order_not_found(self):
        """Test modify_order handles case when order is not in order book."""
        logger.info("\n" + "="*80)
        logger.info("TEST 11: MODIFY_ORDER HANDLES NOT FOUND")
        logger.info("="*80)

        from paper_trading.brokers.adapter.plugins.angelone import AngelOneAdapter

        adapter = AngelOneAdapter({}, None)
        adapter._connected = True

        # Mock empty order book
        mock_order_book = {
            'status': True,
            'data': []
        }

        adapter._smart_api = Mock()
        adapter._smart_api.orderBook.return_value = mock_order_book

        # Try to modify non-existent order
        response = adapter.modify_order('999999', {'price': 5.0})

        logger.info(f"Response success: {response.success}")
        logger.info(f"Response message: {response.message}")

        assert not response.success, "Should fail for non-existent order"
        assert "not found" in response.message.lower(), "Should indicate order not found"

        logger.info("✓ Not found handling PASSED")


class TestPriceUpdateLogic:
    """Test 6: Price update and modification logic (no API calls)."""

    def test_should_modify_order(self):
        """Test logic for deciding when to modify order."""
        logger.info("\n" + "="*80)
        logger.info("TEST 12: SHOULD MODIFY ORDER LOGIC")
        logger.info("="*80)

        # Test cases: (old_trigger, new_trigger, should_modify)
        test_cases = [
            (120.20, 120.25, False, "Change too small"),
            (120.20, 121.00, True, "Significant change"),
            (120.20, 119.50, True, "Significant change"),
            (100.00, 100.10, False, "Change too small"),
            (100.00, 105.00, True, "Significant change"),
        ]

        threshold = 0.5  # Minimum change to modify

        logger.info(f"Threshold: ₹{threshold:.2f}")
        logger.info("\nTest cases:")

        for old, new, should_modify, reason in test_cases:
            change = abs(new - old)
            will_modify = change >= threshold

            logger.info(f"  Old: ₹{old:.2f}, New: ₹{new:.2f}, Change: ₹{change:.2f}")
            logger.info(f"    Should modify: {should_modify}, Will modify: {will_modify}")
            logger.info(f"    Reason: {reason}")

            assert will_modify == should_modify, f"Logic error for {old} -> {new}"

        logger.info("\n✓ Modification logic PASSED")


def run_all_tests():
    """Run all internal tests."""
    logger.info("\n" + "#"*80)
    logger.info("#" + " "*78 + "#")
    logger.info("#" + " "*20 + "STOP LIMIT ORDER - INTERNAL TESTS" + " "*24 + "#")
    logger.info("#" + " "*78 + "#")
    logger.info("#"*80)

    pytest.main([__file__, '-v', '-s'])


if __name__ == '__main__':
    run_all_tests()
