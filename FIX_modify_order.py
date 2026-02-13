"""
FIXED modify_order() method for AngelOne Adapter
=================================================

This is the corrected version that includes ALL required AngelOne API fields.

To apply this fix:
1. Open: /Users/Algo_Trading/manishsir_options/paper_trading/brokers/adapter/plugins/angelone.py
2. Replace the modify_order() method (lines 609-656) with this version
3. Test with: python -m pytest paper_trading/tests/test_components_stop_limit.py::TestComponent5 -v -s

Date: 2026-02-05
"""

def modify_order(self, order_id: str, changes: dict) -> OrderResponse:
    """
    Modify existing order.

    FIXED VERSION - Includes all required AngelOne API fields.

    Args:
        order_id: Order ID to modify
        changes: Dict with fields to modify ('price', 'quantity', 'trigger_price')

    Returns:
        OrderResponse with success status

    Note:
        This method fetches the full order details from order book first,
        then includes all required fields in the modify request.
    """
    if not self._connected:
        return OrderResponse(
            success=False,
            order_id=order_id,
            status=OrderStatus.REJECTED,
            message="Not connected"
        )

    try:
        # Fetch full order book to get current order details
        logger.debug(f"Fetching order book to get details for order {order_id}")
        orders = self._smart_api.orderBook()

        if not orders or not orders.get('status'):
            return OrderResponse(
                success=False,
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message="Could not fetch order book"
            )

        # Find our order in the order book
        order_data = None
        for o in orders.get('data', []):
            if str(o.get('orderid')) == str(order_id):
                order_data = o
                break

        if not order_data:
            return OrderResponse(
                success=False,
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message=f"Order {order_id} not found in order book"
            )

        logger.debug(f"Found order {order_id} in order book")
        logger.debug(f"Current order data: tradingsymbol={order_data.get('tradingsymbol')}, "
                    f"ordertype={order_data.get('ordertype')}, "
                    f"producttype={order_data.get('producttype')}")

        # Build modify_params with ALL required fields from current order
        modify_params = {
            'variety': order_data.get('variety', 'NORMAL'),
            'orderid': order_id,
            'tradingsymbol': order_data.get('tradingsymbol'),
            'symboltoken': order_data.get('symboltoken'),
            'exchange': order_data.get('exchange', 'NFO'),
            'ordertype': order_data.get('ordertype', 'MARKET'),
            'producttype': order_data.get('producttype', 'INTRADAY'),
            'duration': order_data.get('duration', 'DAY'),
            'quantity': str(order_data.get('quantity', 0))
        }

        # Get current prices from order data (for logging)
        current_price = order_data.get('price', 0)
        current_trigger = order_data.get('triggerprice', 0)

        # Apply modifications
        if 'price' in changes:
            modify_params['price'] = str(changes['price'])
            logger.info(f"Modifying price: {current_price} -> {changes['price']}")
        else:
            modify_params['price'] = str(current_price)

        if 'trigger_price' in changes:
            modify_params['triggerprice'] = str(changes['trigger_price'])
            logger.info(f"Modifying trigger price: {current_trigger} -> {changes['trigger_price']}")
        else:
            modify_params['triggerprice'] = str(current_trigger)

        if 'quantity' in changes:
            modify_params['quantity'] = str(changes['quantity'])
            logger.info(f"Modifying quantity: {order_data.get('quantity')} -> {changes['quantity']}")

        # Log all parameters being sent
        logger.debug(f"Modify order params: {modify_params}")

        # Send modification request
        response = self._smart_api.modifyOrder(modify_params)

        logger.debug(f"Modify response: {response}")

        if response and response.get('status'):
            return OrderResponse(
                success=True,
                order_id=order_id,
                status=OrderStatus.PENDING,
                message="Order modified successfully"
            )
        else:
            error_msg = response.get('message', 'Modification failed')
            logger.error(f"Modification failed: {error_msg}")
            return OrderResponse(
                success=False,
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message=error_msg
            )

    except Exception as e:
        logger.error(f"Order modification error: {e}")
        import traceback
        traceback.print_exc()
        return OrderResponse(
            success=False,
            order_id=order_id,
            status=OrderStatus.REJECTED,
            message=str(e)
        )


# HOW TO APPLY THIS FIX:
# =======================
#
# 1. Open the file:
#    /Users/Algo_Trading/manishsir_options/paper_trading/brokers/adapter/plugins/angelone.py
#
# 2. Find the modify_order method (starts at line 609)
#
# 3. Replace lines 609-656 with the code above (the entire modify_order method)
#
# 4. Save the file
#
# 5. Test the fix:
#    python -m pytest paper_trading/tests/test_components_stop_limit.py::TestComponent5 -v -s
#
# 6. If Test 5 passes, the fix is working!
#
# WHAT THIS FIX DOES:
# ===================
#
# OLD CODE (BROKEN):
#   - Only sent: variety, orderid, price, quantity, triggerprice
#   - Missing: tradingsymbol, symboltoken, exchange, ordertype, producttype, duration
#   - Result: AngelOne API rejects the request
#
# NEW CODE (FIXED):
#   - Fetches current order details from order book
#   - Extracts all required fields from current order
#   - Sends complete modify request with ALL required fields
#   - Result: AngelOne API accepts the modification
#
# WHY THIS IS NECESSARY:
# ======================
#
# AngelOne SmartAPI requires these fields for modifyOrder:
#   - tradingsymbol: "NIFTY10FEB2626000CE" (which option)
#   - symboltoken: "58661" (exchange token)
#   - exchange: "NFO" (which exchange)
#   - ordertype: "STOPLOSS_LIMIT" (order type)
#   - producttype: "INTRADAY" (product type)
#   - duration: "DAY" (order duration)
#
# Without these, the API cannot identify which order to modify or how.
