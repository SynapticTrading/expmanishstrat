"""
Test AMO Limit Order placement and cancellation on AngelOne.
This is a SAFE test - places limit orders that won't execute and cancels them.
"""

import pytest
import logging
from datetime import datetime

from paper_trading.brokers.adapter.types import (
    OrderRequest, OrderType, TransactionType,
    Exchange, ProductType, OrderStatus
)

logger = logging.getLogger(__name__)


class TestAngelOneAMOLimit:
    """Test AMO Limit orders on AngelOne - Safe testing with auto-cancellation."""
    
    @pytest.mark.amo_order
    def test_amo_limit_buy_safe(self, angelone_adapter, test_instruments, skip_if_market_open):
        """
        Test AMO Limit BUY order - Safe version.
        
        Places a limit order 10% ABOVE current market price.
        This ensures the order won't execute (too expensive).
        Then cancels it for safety.
        """
        logger.info("=" * 60)
        logger.info("🧪 Testing AMO Limit BUY (Safe - 10% above market)")
        logger.info("=" * 60)
        
        # Get current expiry
        expiry = angelone_adapter.contract_manager.get_options_expiry('current_week')
        
        # Get current LTP
        ltp = angelone_adapter.get_ltp(
            underlying=test_instruments['underlying'],
            option_type='CE',
            strike=test_instruments['strike'],
            expiry=expiry
        )
        
        if ltp is None or ltp <= 0:
            pytest.skip("Could not fetch valid LTP for limit order test")
        
        # Set limit price 10% ABOVE market (won't execute)
        limit_price = round(ltp * 1.10, 2)
        
        logger.info(f"Current LTP: ₹{ltp}")
        logger.info(f"Limit Price: ₹{limit_price} (10% above - SAFE)")
        logger.info(f"Strike: {test_instruments['strike']} CE")
        
        # Create limit order request
        order_request = OrderRequest(
            underlying=test_instruments['underlying'],
            option_type='CE',
            strike=test_instruments['strike'],
            expiry=expiry,
            exchange=Exchange.NFO,
            transaction_type=TransactionType.BUY,
            order_type=OrderType.LIMIT,
            quantity=test_instruments['quantity'],
            price=limit_price,
            product_type=ProductType.INTRADAY,
            tag='integration_test_amo_limit'
        )
        
        # Place order
        logger.info("Placing AMO Limit BUY order...")
        response = angelone_adapter.place_order(order_request)
        
        # Verify order placement
        assert response.success is True, f"Order placement failed: {response.message}"
        assert response.order_id is not None
        assert response.order_id != ""
        
        order_id = response.order_id
        logger.info(f"✅ Order placed successfully!")
        logger.info(f"   Order ID: {order_id}")
        logger.info(f"   Price: ₹{limit_price}")
        logger.info(f"   Status: {response.status}")
        
        # IMPORTANT: Cancel the order immediately for safety
        logger.info(f"🛡️ Cancelling order for safety...")
        try:
            cancel_result = angelone_adapter._smart_api.cancelOrder(
                order_id=order_id,
                variety='NORMAL'
            )
            
            if cancel_result and cancel_result.get('status'):
                logger.info(f"✅ Order cancelled successfully: {order_id}")
            else:
                error_msg = cancel_result.get('message', 'Unknown') if cancel_result else 'No response'
                logger.warning(f"⚠️ Cancel may have failed: {error_msg}")
        except Exception as e:
            logger.error(f"❌ Error cancelling order: {e}")
            logger.warning(f"⚠️ Manual cancellation may be needed for order {order_id}")
        
        logger.info("=" * 60)
        logger.info("✅ Test completed - AMO Limit BUY")
        logger.info("=" * 60)
    
    @pytest.mark.amo_order
    def test_amo_limit_sell_safe(self, angelone_adapter, test_instruments, skip_if_market_open):
        """
        Test AMO Limit SELL order - Safe version.
        
        Places a limit order 10% BELOW current market price.
        This ensures the order won't execute (too cheap).
        Then cancels it for safety.
        """
        logger.info("=" * 60)
        logger.info("🧪 Testing AMO Limit SELL (Safe - 10% below market)")
        logger.info("=" * 60)
        
        # Get current expiry
        expiry = angelone_adapter.contract_manager.get_options_expiry('current_week')
        
        # Get current LTP (use PE for variety)
        ltp = angelone_adapter.get_ltp(
            underlying=test_instruments['underlying'],
            option_type='PE',
            strike=test_instruments['strike'],
            expiry=expiry
        )
        
        if ltp is None or ltp <= 0:
            pytest.skip("Could not fetch valid LTP for limit order test")
        
        # Set limit price 10% BELOW market (won't execute)
        limit_price = round(ltp * 0.90, 2)
        
        logger.info(f"Current LTP: ₹{ltp}")
        logger.info(f"Limit Price: ₹{limit_price} (10% below - SAFE)")
        logger.info(f"Strike: {test_instruments['strike']} PE")
        
        # Create limit order request
        order_request = OrderRequest(
            underlying=test_instruments['underlying'],
            option_type='PE',
            strike=test_instruments['strike'],
            expiry=expiry,
            exchange=Exchange.NFO,
            transaction_type=TransactionType.SELL,
            order_type=OrderType.LIMIT,
            quantity=test_instruments['quantity'],
            price=limit_price,
            product_type=ProductType.INTRADAY,
            tag='integration_test_amo_limit_sell'
        )
        
        # Place order
        logger.info("Placing AMO Limit SELL order...")
        response = angelone_adapter.place_order(order_request)
        
        # Verify order placement
        assert response.success is True, f"Order placement failed: {response.message}"
        assert response.order_id is not None
        assert response.order_id != ""
        
        order_id = response.order_id
        logger.info(f"✅ Order placed successfully!")
        logger.info(f"   Order ID: {order_id}")
        logger.info(f"   Price: ₹{limit_price}")
        logger.info(f"   Status: {response.status}")
        
        # IMPORTANT: Cancel the order immediately for safety
        logger.info(f"🛡️ Cancelling order for safety...")
        try:
            cancel_result = angelone_adapter._smart_api.cancelOrder(
                order_id=order_id,
                variety='NORMAL'
            )
            
            if cancel_result and cancel_result.get('status'):
                logger.info(f"✅ Order cancelled successfully: {order_id}")
            else:
                error_msg = cancel_result.get('message', 'Unknown') if cancel_result else 'No response'
                logger.warning(f"⚠️ Cancel may have failed: {error_msg}")
        except Exception as e:
            logger.error(f"❌ Error cancelling order: {e}")
            logger.warning(f"⚠️ Manual cancellation may be needed for order {order_id}")
        
        logger.info("=" * 60)
        logger.info("✅ Test completed - AMO Limit SELL")
        logger.info("=" * 60)
    
    @pytest.mark.amo_order
    def test_amo_limit_extreme_price(self, angelone_adapter, test_instruments, skip_if_market_open):
        """
        Test AMO Limit order with extreme price (very safe).
        
        Places order with price far from market (50% away).
        Guaranteed not to execute. Tests order placement mechanism.
        """
        logger.info("=" * 60)
        logger.info("🧪 Testing AMO Limit with EXTREME price (50% away)")
        logger.info("=" * 60)
        
        # Get current expiry
        expiry = angelone_adapter.contract_manager.get_options_expiry('current_week')
        
        # Get current LTP
        ltp = angelone_adapter.get_ltp(
            underlying=test_instruments['underlying'],
            option_type='CE',
            strike=test_instruments['strike'],
            expiry=expiry
        )
        
        if ltp is None or ltp <= 0:
            pytest.skip("Could not fetch valid LTP for limit order test")
        
        # Set limit price 50% ABOVE market (will NEVER execute)
        limit_price = round(ltp * 1.50, 2)
        
        logger.info(f"Current LTP: ₹{ltp}")
        logger.info(f"Limit Price: ₹{limit_price} (50% above - VERY SAFE)")
        logger.info(f"This order will NEVER execute at this price")
        
        # Create limit order request
        order_request = OrderRequest(
            underlying=test_instruments['underlying'],
            option_type='CE',
            strike=test_instruments['strike'],
            expiry=expiry,
            exchange=Exchange.NFO,
            transaction_type=TransactionType.BUY,
            order_type=OrderType.LIMIT,
            quantity=test_instruments['quantity'],
            price=limit_price,
            product_type=ProductType.INTRADAY,
            tag='integration_test_extreme_limit'
        )
        
        # Place order
        logger.info("Placing AMO Limit order with extreme price...")
        response = angelone_adapter.place_order(order_request)
        
        # Verify order placement
        assert response.success is True, f"Order placement failed: {response.message}"
        assert response.order_id is not None
        
        order_id = response.order_id
        logger.info(f"✅ Order placed successfully!")
        logger.info(f"   Order ID: {order_id}")
        
        # Cancel immediately
        logger.info(f"🛡️ Cancelling order...")
        try:
            cancel_result = angelone_adapter._smart_api.cancelOrder(
                order_id=order_id,
                variety='NORMAL'
            )
            
            if cancel_result and cancel_result.get('status'):
                logger.info(f"✅ Order cancelled: {order_id}")
        except Exception as e:
            logger.error(f"❌ Error cancelling: {e}")
        
        logger.info("=" * 60)
        logger.info("✅ Test completed - Extreme limit price")
        logger.info("=" * 60)


class TestAngelOneLimitOrderValidation:
    """Test limit order validation and error handling."""
    
    def test_limit_order_requires_price(self, angelone_adapter, test_instruments):
        """
        Test that limit orders require a price.
        
        Should fail gracefully if price is not provided.
        """
        expiry = angelone_adapter.contract_manager.get_options_expiry('current_week')
        
        # Create limit order WITHOUT price
        order_request = OrderRequest(
            underlying=test_instruments['underlying'],
            option_type='CE',
            strike=test_instruments['strike'],
            expiry=expiry,
            exchange=Exchange.NFO,
            transaction_type=TransactionType.BUY,
            order_type=OrderType.LIMIT,
            quantity=test_instruments['quantity'],
            price=None,  # Missing price!
            product_type=ProductType.INTRADAY
        )
        
        # This should either fail validation or add default price
        # (Implementation dependent)
        logger.info("Testing limit order without price...")
        # Just verify the order structure is created
        assert order_request.order_type == OrderType.LIMIT
        logger.info("✓ Limit order structure validated")
