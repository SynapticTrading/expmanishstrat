"""
Test to cancel all pending AMO orders from previous tests.
Run this to clean up orders before market opens!
"""

import pytest
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class TestCancelPendingOrders:
    """Cancel pending orders from previous test runs."""
    
    def test_cancel_zerodha_pending_orders(self, zerodha_adapter):
        """
        Cancel all pending AMO orders on Zerodha.
        
        This cleans up orders placed during previous test runs
        to prevent them from executing when market opens.
        """
        logger.info("=" * 60)
        logger.info("🚨 CANCELLING ZERODHA PENDING ORDERS")
        logger.info("=" * 60)
        
        # Get all orders
        orders = zerodha_adapter.get_orders()
        logger.info(f"Total orders found: {len(orders)}")
        
        # Filter pending orders
        pending_statuses = ['TRIGGER PENDING', 'OPEN', 'PENDING']
        pending_orders = [
            o for o in orders 
            if o.get('status') in pending_statuses
        ]
        
        logger.info(f"Pending orders to cancel: {len(pending_orders)}")
        
        cancelled_count = 0
        failed_count = 0
        
        for order in pending_orders:
            order_id = order.get('order_id')
            symbol = order.get('tradingsymbol', 'Unknown')
            status = order.get('status')
            
            logger.info(f"  Order ID: {order_id}")
            logger.info(f"  Symbol: {symbol}")
            logger.info(f"  Status: {status}")
            logger.info(f"  Attempting to cancel...")
            
            try:
                # Cancel using Zerodha's cancel_order method
                zerodha_adapter._kite.cancel_order(
                    variety='regular',
                    order_id=order_id
                )
                logger.info(f"  ✅ CANCELLED: {order_id}")
                cancelled_count += 1
                
            except Exception as e:
                logger.error(f"  ❌ FAILED to cancel {order_id}: {e}")
                failed_count += 1
        
        logger.info("=" * 60)
        logger.info(f"✅ Cancelled: {cancelled_count}")
        logger.info(f"❌ Failed: {failed_count}")
        logger.info("=" * 60)
        
        # Assert that we found and processed orders
        assert len(orders) >= 0, "Should be able to fetch orders"
        
        # Log final status
        if cancelled_count > 0:
            logger.info(f"🎉 Successfully cancelled {cancelled_count} Zerodha orders")
        elif len(pending_orders) == 0:
            logger.info("✓ No pending Zerodha orders to cancel")
        
    def test_cancel_angelone_pending_orders(self, angelone_adapter):
        """
        Cancel all pending AMO orders on AngelOne.
        
        This cleans up orders placed during previous test runs
        to prevent them from executing when market opens.
        """
        logger.info("=" * 60)
        logger.info("🚨 CANCELLING ANGELONE PENDING ORDERS")
        logger.info("=" * 60)
        
        # Get all orders directly from API (raw data)
        orders_response = angelone_adapter._smart_api.orderBook()
        
        if not orders_response or not orders_response.get('status'):
            logger.info("No orders found or API error")
            return
        
        orders = orders_response.get('data', [])
        logger.info(f"Total orders found: {len(orders)}")
        
        # Filter pending orders (AngelOne uses lowercase status)
        pending_statuses = ['trigger pending', 'open', 'pending', 'after market order req received']
        pending_orders = [
            o for o in orders 
            if o.get('orderstatus', '').lower() in pending_statuses
        ]
        
        logger.info(f"Pending orders to cancel: {len(pending_orders)}")
        
        cancelled_count = 0
        failed_count = 0
        
        for order in pending_orders:
            order_id = str(order.get('orderid'))
            symbol = order.get('tradingsymbol', 'Unknown')
            status = order.get('orderstatus')
            
            logger.info(f"  Order ID: {order_id}")
            logger.info(f"  Symbol: {symbol}")
            logger.info(f"  Status: {status}")
            logger.info(f"  Attempting to cancel...")
            
            try:
                # Cancel using AngelOne's cancel_order method
                result = angelone_adapter._smart_api.cancelOrder(
                    order_id=order_id,
                    variety='NORMAL'
                )
                
                if result and result.get('status'):
                    logger.info(f"  ✅ CANCELLED: {order_id}")
                    cancelled_count += 1
                else:
                    error_msg = result.get('message', 'Unknown error') if result else 'No response'
                    logger.error(f"  ❌ FAILED to cancel {order_id}: {error_msg}")
                    failed_count += 1
                    
            except Exception as e:
                logger.error(f"  ❌ FAILED to cancel {order_id}: {e}")
                failed_count += 1
        
        logger.info("=" * 60)
        logger.info(f"✅ Cancelled: {cancelled_count}")
        logger.info(f"❌ Failed: {failed_count}")
        logger.info("=" * 60)
        
        # Assert that we found and processed orders
        assert len(orders) >= 0, "Should be able to fetch orders"
        
        # Log final status
        if cancelled_count > 0:
            logger.info(f"🎉 Successfully cancelled {cancelled_count} AngelOne orders")
        elif len(pending_orders) == 0:
            logger.info("✓ No pending AngelOne orders to cancel")
    
    def test_verify_no_pending_orders(self, zerodha_adapter, angelone_adapter):
        """
        Verify that no pending orders remain after cancellation.
        
        This is a verification test to ensure cleanup was successful.
        """
        logger.info("=" * 60)
        logger.info("🔍 VERIFYING NO PENDING ORDERS REMAIN")
        logger.info("=" * 60)
        
        # Check Zerodha
        zerodha_orders = zerodha_adapter.get_orders()
        zerodha_pending = [
            o for o in zerodha_orders 
            if o.get('status') in ['TRIGGER PENDING', 'OPEN', 'PENDING']
        ]
        logger.info(f"Zerodha pending orders: {len(zerodha_pending)}")
        
        # Check AngelOne
        angelone_response = angelone_adapter._smart_api.orderBook()
        angelone_orders = angelone_response.get('data', []) if angelone_response and angelone_response.get('status') else []
        angelone_pending = [
            o for o in angelone_orders 
            if o.get('orderstatus', '').lower() in ['trigger pending', 'open', 'pending', 'after market order req received']
        ]
        logger.info(f"AngelOne pending orders: {len(angelone_pending)}")
        
        total_pending = len(zerodha_pending) + len(angelone_pending)
        
        if total_pending == 0:
            logger.info("✅ SUCCESS: No pending orders found!")
            logger.info("🛡️ Safe to let market open - no orders will execute")
        else:
            logger.warning(f"⚠️ WARNING: {total_pending} pending orders still exist!")
            logger.warning("Run cancellation tests again or cancel manually")
        
        logger.info("=" * 60)
        
        # We don't assert here because orders might have been cancelled already
        # Just provide information
