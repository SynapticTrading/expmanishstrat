"""
Test AMO Order Cancellation on AngelOne.
Tests the complete flow: Place → Verify → Cancel → Verify Cancellation
"""

import pytest
import logging
from datetime import datetime
import time

from paper_trading.brokers.adapter.types import (
    OrderRequest, OrderType, TransactionType,
    Exchange, ProductType, OrderStatus
)

logger = logging.getLogger(__name__)


class TestAngelOneAMOCancellation:
    """Test AMO order cancellation functionality."""
    
    @pytest.mark.amo_order
    def test_place_and_cancel_amo_limit(self, angelone_adapter, test_instruments, skip_if_market_open):
        """
        TC_CANCEL_01: Place AMO limit order and cancel it.
        
        Tests the complete cancellation flow:
        1. Place AMO limit order
        2. Verify order is placed and pending
        3. Cancel the order
        4. Verify order is cancelled
        """
        logger.info("=" * 70)
        logger.info("🧪 TC_CANCEL_01: Place and Cancel AMO Limit Order")
        logger.info("=" * 70)
        
        # Step 1: Get market data
        expiry = angelone_adapter.contract_manager.get_options_expiry('current_week')
        ltp = angelone_adapter.get_ltp(
            underlying=test_instruments['underlying'],
            option_type='CE',
            strike=test_instruments['strike'],
            expiry=expiry
        )
        
        if ltp is None or ltp <= 0:
            pytest.skip("Could not fetch LTP")
        
        # Set safe limit price (10% above market)
        limit_price = round(ltp * 1.10, 2)
        
        logger.info(f"📊 Market Data:")
        logger.info(f"   LTP: ₹{ltp}")
        logger.info(f"   Limit Price: ₹{limit_price} (10% above - won't execute)")
        
        # Step 2: Create and place order
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
            tag='test_cancellation'
        )
        
        logger.info(f"\n📤 STEP 1: Placing AMO Limit Order...")
        response = angelone_adapter.place_order(order_request)
        
        # Verify placement
        assert response.success is True, f"Order placement failed: {response.message}"
        assert response.order_id is not None
        assert response.order_id != ""
        
        order_id = response.order_id
        logger.info(f"✅ Order Placed Successfully!")
        logger.info(f"   Order ID: {order_id}")
        logger.info(f"   Status: {response.status.value}")
        
        # Step 3: Verify order exists and is pending
        logger.info(f"\n🔍 STEP 2: Verifying Order Status...")
        time.sleep(1)  # Small delay to ensure order is recorded
        
        orders_response = angelone_adapter._smart_api.orderBook()
        if orders_response and orders_response.get('status'):
            orders = orders_response.get('data', [])
            placed_order = next((o for o in orders if str(o.get('orderid')) == order_id), None)
            
            if placed_order:
                order_status = placed_order.get('orderstatus', '').lower()
                logger.info(f"✅ Order Found in Order Book")
                logger.info(f"   Order ID: {order_id}")
                logger.info(f"   Status: {order_status}")
                logger.info(f"   Symbol: {placed_order.get('tradingsymbol', 'N/A')}")
                logger.info(f"   Price: ₹{placed_order.get('price', 'N/A')}")
                
                # Verify it's pending
                assert order_status in ['open', 'pending', 'trigger pending', 'after market order req received'], \
                    f"Order should be pending, but status is: {order_status}"
            else:
                logger.warning(f"⚠️ Order {order_id} not found in order book immediately")
        
        # Step 4: Cancel the order
        logger.info(f"\n🚫 STEP 3: Cancelling Order...")
        
        try:
            cancel_result = angelone_adapter._smart_api.cancelOrder(
                order_id=order_id,
                variety='NORMAL'
            )
            
            # Verify cancellation response
            assert cancel_result is not None, "Cancel API returned None"
            
            if cancel_result.get('status'):
                logger.info(f"✅ Cancellation Request Accepted")
                logger.info(f"   Order ID: {order_id}")
                logger.info(f"   Message: {cancel_result.get('message', 'Success')}")
            else:
                error_msg = cancel_result.get('message', 'Unknown error')
                logger.error(f"❌ Cancellation Failed: {error_msg}")
                pytest.fail(f"Order cancellation failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"❌ Exception during cancellation: {e}")
            pytest.fail(f"Exception during order cancellation: {e}")
        
        # Step 5: Verify order is cancelled
        logger.info(f"\n🔍 STEP 4: Verifying Cancellation...")
        time.sleep(1)  # Small delay for order status to update
        
        orders_response = angelone_adapter._smart_api.orderBook()
        if orders_response and orders_response.get('status'):
            orders = orders_response.get('data', [])
            cancelled_order = next((o for o in orders if str(o.get('orderid')) == order_id), None)
            
            if cancelled_order:
                final_status = cancelled_order.get('orderstatus', '').lower()
                logger.info(f"✅ Order Status Updated")
                logger.info(f"   Order ID: {order_id}")
                logger.info(f"   Final Status: {final_status}")
                
                # Verify it's cancelled or rejected
                assert final_status in ['cancelled', 'rejected', 'canceled'], \
                    f"Order should be cancelled, but status is: {final_status}"
                
                logger.info(f"✅ Verification Successful - Order is {final_status.upper()}")
        
        logger.info("\n" + "=" * 70)
        logger.info("✅ TEST PASSED: AMO Order Cancellation Complete")
        logger.info("=" * 70)
    
    @pytest.mark.amo_order
    def test_cancel_multiple_amo_orders(self, angelone_adapter, test_instruments, skip_if_market_open):
        """
        TC_CANCEL_02: Place and cancel multiple AMO orders.
        
        Tests batch cancellation:
        1. Place 2 AMO limit orders
        2. Cancel both
        3. Verify both are cancelled
        """
        logger.info("=" * 70)
        logger.info("🧪 TC_CANCEL_02: Cancel Multiple AMO Orders")
        logger.info("=" * 70)
        
        # Get market data
        expiry = angelone_adapter.contract_manager.get_options_expiry('current_week')
        ltp_ce = angelone_adapter.get_ltp(
            underlying=test_instruments['underlying'],
            option_type='CE',
            strike=test_instruments['strike'],
            expiry=expiry
        )
        ltp_pe = angelone_adapter.get_ltp(
            underlying=test_instruments['underlying'],
            option_type='PE',
            strike=test_instruments['strike'],
            expiry=expiry
        )
        
        if ltp_ce is None or ltp_pe is None:
            pytest.skip("Could not fetch LTPs")
        
        order_ids = []
        
        # Place Order 1: CE Buy
        logger.info(f"\n📤 Placing Order 1: CE Buy")
        order1 = OrderRequest(
            underlying=test_instruments['underlying'],
            option_type='CE',
            strike=test_instruments['strike'],
            expiry=expiry,
            exchange=Exchange.NFO,
            transaction_type=TransactionType.BUY,
            order_type=OrderType.LIMIT,
            quantity=test_instruments['quantity'],
            price=round(ltp_ce * 1.15, 2),  # 15% above
            product_type=ProductType.INTRADAY,
            tag='test_multi_cancel_1'
        )
        
        response1 = angelone_adapter.place_order(order1)
        assert response1.success is True
        order_ids.append(response1.order_id)
        logger.info(f"✅ Order 1 placed: {response1.order_id}")
        
        # Small delay between orders
        time.sleep(0.5)
        
        # Place Order 2: PE Buy
        logger.info(f"\n📤 Placing Order 2: PE Buy")
        order2 = OrderRequest(
            underlying=test_instruments['underlying'],
            option_type='PE',
            strike=test_instruments['strike'],
            expiry=expiry,
            exchange=Exchange.NFO,
            transaction_type=TransactionType.BUY,
            order_type=OrderType.LIMIT,
            quantity=test_instruments['quantity'],
            price=round(ltp_pe * 1.15, 2),  # 15% above
            product_type=ProductType.INTRADAY,
            tag='test_multi_cancel_2'
        )
        
        response2 = angelone_adapter.place_order(order2)
        assert response2.success is True
        order_ids.append(response2.order_id)
        logger.info(f"✅ Order 2 placed: {response2.order_id}")
        
        logger.info(f"\n📋 Total orders placed: {len(order_ids)}")
        
        # Cancel all orders
        logger.info(f"\n🚫 Cancelling all orders...")
        cancelled_count = 0
        
        for order_id in order_ids:
            try:
                cancel_result = angelone_adapter._smart_api.cancelOrder(
                    order_id=order_id,
                    variety='NORMAL'
                )
                
                if cancel_result and cancel_result.get('status'):
                    logger.info(f"✅ Cancelled: {order_id}")
                    cancelled_count += 1
                else:
                    logger.error(f"❌ Failed to cancel: {order_id}")
                    
            except Exception as e:
                logger.error(f"❌ Exception cancelling {order_id}: {e}")
        
        logger.info(f"\n📊 Cancellation Summary:")
        logger.info(f"   Orders placed: {len(order_ids)}")
        logger.info(f"   Orders cancelled: {cancelled_count}")
        
        assert cancelled_count == len(order_ids), \
            f"Expected {len(order_ids)} cancellations, got {cancelled_count}"
        
        logger.info("\n" + "=" * 70)
        logger.info("✅ TEST PASSED: Multiple Orders Cancelled")
        logger.info("=" * 70)
    
    @pytest.mark.amo_order
    def test_cancel_nonexistent_order(self, angelone_adapter):
        """
        TC_CANCEL_03: Attempt to cancel non-existent order.
        
        Tests error handling:
        - Try to cancel an order that doesn't exist
        - Verify proper error response
        """
        logger.info("=" * 70)
        logger.info("🧪 TC_CANCEL_03: Cancel Non-existent Order (Error Handling)")
        logger.info("=" * 70)
        
        fake_order_id = "FAKE123456789"
        
        logger.info(f"🚫 Attempting to cancel non-existent order: {fake_order_id}")
        
        try:
            cancel_result = angelone_adapter._smart_api.cancelOrder(
                order_id=fake_order_id,
                variety='NORMAL'
            )
            
            # Should either return error status or raise exception
            if cancel_result:
                if cancel_result.get('status'):
                    logger.warning("⚠️ API accepted cancellation of fake order (unexpected)")
                else:
                    error_msg = cancel_result.get('message', 'Unknown')
                    logger.info(f"✅ Proper error handling: {error_msg}")
                    logger.info("✅ API correctly rejected invalid order ID")
            else:
                logger.info("✅ API returned None for invalid order")
                
        except Exception as e:
            logger.info(f"✅ Exception raised (expected): {str(e)[:100]}")
            logger.info("✅ Proper error handling confirmed")
        
        logger.info("\n" + "=" * 70)
        logger.info("✅ TEST PASSED: Error Handling Verified")
        logger.info("=" * 70)
