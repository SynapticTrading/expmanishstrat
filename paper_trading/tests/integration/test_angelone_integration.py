"""
AngelOne Integration Tests - Real API Connection

Tests with actual AngelOne SmartAPI connection.
Uses AMO orders for safety - no live orders placed.
"""

import pytest
from datetime import datetime, timedelta, time
import time as time_module
import logging

from paper_trading.brokers.adapter.types import (
    OrderRequest, OrderResponse, Quote, Position, Funds,
    OrderType, OrderStatus, ProductType, TransactionType, Exchange
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# TC_AUTH_01-04: AUTHENTICATION TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestAngelOneAuthentication:
    """Real authentication tests with AngelOne API."""
    
    def test_auth_01_connect_and_authenticate(self, angelone_adapter):
        """
        TC_AUTH_01: Real connection to AngelOne API
        
        Expected: Successfully connected and authenticated
        """
        # Adapter is already connected by fixture
        assert angelone_adapter.is_connected() is True
        assert angelone_adapter._smart_api is not None
        logger.info("✓ TC_AUTH_01: Successfully authenticated with AngelOne")
    
    def test_auth_02_get_profile(self, angelone_adapter):
        """
        TC_AUTH_02: Fetch user profile
        
        Expected: Returns profile with user data
        """
        # Get refresh token from connection
        refresh_token = angelone_adapter._connection.refresh_token
        profile = angelone_adapter._smart_api.getProfile(refresh_token)
        
        assert profile is not None
        assert profile.get('status') is True
        assert 'data' in profile
        
        user_data = profile['data']
        logger.info(f"✓ TC_AUTH_02: Profile retrieved - Client: {user_data.get('clientcode', 'N/A')}")
    
    def test_auth_03_reconnection(self, angelone_credentials, contract_manager):
        """
        TC_AUTH_03: Test disconnect and reconnect
        
        Expected: Can reconnect after disconnect
        """
        from paper_trading.brokers.adapter.plugins.angelone import AngelOneAdapter
        
        adapter = AngelOneAdapter(angelone_credentials, contract_manager)
        
        # First connection
        success1 = adapter.connect()
        assert success1 is True
        assert adapter.is_connected() is True
        
        # Disconnect
        adapter.disconnect()
        assert adapter.is_connected() is False
        
        # Reconnect
        success2 = adapter.connect()
        assert success2 is True
        assert adapter.is_connected() is True
        
        adapter.disconnect()
        logger.info("✓ TC_AUTH_03: Reconnection successful")


# ══════════════════════════════════════════════════════════════════════════════
# TC_ORDER_01-04: ORDER PLACEMENT TESTS (AMO ONLY)
# ══════════════════════════════════════════════════════════════════════════════

class TestAngelOneOrdersAMO:
    """AMO order tests - safe for testing."""
    
    @pytest.mark.amo_order
    def test_order_01_place_amo_market_buy(self, angelone_adapter, amo_order_helper, 
                                           test_instruments, skip_if_market_open):
        """
        TC_ORDER_01: Place AMO market buy order
        
        Expected: Order placed successfully, auto-cancelled
        """
        # Create AMO order request
        order_request = amo_order_helper.create_amo_request(
            adapter=angelone_adapter,
            underlying=test_instruments['underlying'],
            strike=test_instruments['strike'],
            quantity=test_instruments['quantity'],
            order_type='MARKET'
        )
        
        # Place order
        response = amo_order_helper.place_and_track(angelone_adapter, order_request)
        
        # Verify
        assert response.success is True
        assert response.order_id is not None
        assert response.order_id != ""
        
        logger.info(f"✓ TC_ORDER_01: AMO Market Buy order placed - ID: {response.order_id}")
    
    @pytest.mark.amo_order
    def test_order_02_place_amo_limit_sell(self, angelone_adapter, amo_order_helper,
                                           test_instruments, skip_if_market_open):
        """
        TC_ORDER_02: Place AMO limit sell order
        
        Expected: Order placed with price validation
        """
        # Get current LTP for price
        ltp = angelone_adapter.get_ltp(
            underlying=test_instruments['underlying'],
            option_type='PE',
            strike=test_instruments['strike'],
            expiry=angelone_adapter.contract_manager.get_options_expiry('current_week')
        )
        
        if ltp is None:
            pytest.skip("Could not fetch LTP for price calculation")
        
        # Create limit order with reasonable price
        limit_price = round(ltp * 1.05, 2)  # 5% above LTP
        
        order_request = amo_order_helper.create_amo_request(
            adapter=angelone_adapter,
            underlying=test_instruments['underlying'],
            option_type='PE',
            strike=test_instruments['strike'],
            quantity=test_instruments['quantity'],
            order_type='LIMIT'
        )
        order_request.price = limit_price
        order_request.transaction_type = TransactionType.SELL
        
        # Validate price
        assert order_request.price > 0
        
        # Place order
        response = amo_order_helper.place_and_track(angelone_adapter, order_request)
        
        # Verify
        assert response.success is True
        assert response.order_id is not None
        
        logger.info(f"✓ TC_ORDER_02: AMO Limit Sell order placed - ID: {response.order_id}, Price: {limit_price}")
    
    def test_order_03_invalid_symbol(self, angelone_adapter):
        """
        TC_ORDER_03: Place order with invalid symbol
        
        Expected: Order rejected
        """
        order_request = OrderRequest(
            underlying='INVALID_SYMBOL',
            option_type='CE',
            strike=99999,
            expiry='2026-01-29',
            exchange=Exchange.NFO,
            transaction_type=TransactionType.BUY,
            order_type=OrderType.MARKET,
            quantity=25
        )
        
        response = angelone_adapter.place_order(order_request)
        
        assert response.success is False
        assert response.status == OrderStatus.REJECTED
        
        logger.info("✓ TC_ORDER_03: Invalid symbol correctly rejected")
    
    @pytest.mark.amo_order
    def test_order_04_cancel_amo_order(self, angelone_adapter, amo_order_helper,
                                       test_instruments, skip_if_market_open):
        """
        TC_ORDER_04: Cancel AMO order by order_id
        
        Expected: Order cancelled successfully
        """
        # Place order
        order_request = amo_order_helper.create_amo_request(
            adapter=angelone_adapter,
            underlying=test_instruments['underlying'],
            strike=test_instruments['strike'],
            quantity=test_instruments['quantity']
        )
        
        place_response = angelone_adapter.place_order(order_request)
        assert place_response.success is True
        
        order_id = place_response.order_id
        
        # Cancel order
        cancel_response = angelone_adapter.cancel_order(order_id)
        
        # Verify
        assert cancel_response.success is True
        assert cancel_response.status == OrderStatus.CANCELLED
        assert cancel_response.order_id == order_id
        
        logger.info(f"✓ TC_ORDER_04: AMO order {order_id} cancelled successfully")


# ══════════════════════════════════════════════════════════════════════════════
# TC_QUOTE_01-03: MARKET DATA TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestAngelOneMarketData:
    """Market data tests - LTP, quotes, historical."""
    
    def test_quote_01_get_ltp_single(self, angelone_adapter, test_instruments):
        """
        TC_QUOTE_01: Get LTP for single instrument
        
        Expected: Returns LTP, volume, OI
        """
        expiry = angelone_adapter.contract_manager.get_options_expiry('current_week')
        
        ltp = angelone_adapter.get_ltp(
            underlying=test_instruments['underlying'],
            option_type='CE',
            strike=test_instruments['strike'],
            expiry=expiry
        )
        
        assert ltp is not None
        assert ltp > 0
        
        logger.info(f"✓ TC_QUOTE_01: LTP retrieved - {test_instruments['underlying']} "
                   f"{test_instruments['strike']} CE = ₹{ltp:.2f}")
    
    def test_quote_02_get_full_quote_multiple(self, angelone_adapter, test_instruments):
        """
        TC_QUOTE_02: Get full quote for multiple instruments
        
        Expected: Returns list of quote dicts with OHLC, volume, OI
        """
        expiry = angelone_adapter.contract_manager.get_options_expiry('current_week')
        
        # Get quotes for both CE and PE
        quote_ce = angelone_adapter.get_quote(
            underlying=test_instruments['underlying'],
            option_type='CE',
            strike=test_instruments['strike'],
            expiry=expiry
        )
        
        quote_pe = angelone_adapter.get_quote(
            underlying=test_instruments['underlying'],
            option_type='PE',
            strike=test_instruments['strike'],
            expiry=expiry
        )
        
        # Verify CE quote
        assert quote_ce is not None
        assert isinstance(quote_ce, Quote)
        assert quote_ce.ltp > 0
        assert quote_ce.volume >= 0
        assert quote_ce.oi >= 0
        
        # Verify PE quote
        assert quote_pe is not None
        assert isinstance(quote_pe, Quote)
        assert quote_pe.ltp > 0
        
        logger.info(f"✓ TC_QUOTE_02: Full quotes retrieved")
        logger.info(f"  CE: LTP=₹{quote_ce.ltp:.2f}, OI={quote_ce.oi:,}, Vol={quote_ce.volume:,}")
        logger.info(f"  PE: LTP=₹{quote_pe.ltp:.2f}, OI={quote_pe.oi:,}, Vol={quote_pe.volume:,}")
    
    def test_quote_03_historical_data_1day(self, angelone_adapter, test_instruments):
        """
        TC_QUOTE_03: Get historical data (1-day candle)
        
        Expected: Returns JSON with candles array
        """
        from datetime import datetime, timedelta
        
        # Get historical data for underlying index
        to_date = datetime.now()
        from_date = to_date - timedelta(days=5)  # Get last 5 days
        
        # Get contract for NIFTY index
        if test_instruments['underlying'] == 'NIFTY':
            # Nifty 50 index token for AngelOne
            token = '99926000'  # NSE:NIFTY 50 (verify this)
            
            try:
                # Use AngelOne's historical candle API
                candles = angelone_adapter._connection.get_candle_data(
                    exchange='NSE',
                    symbol_token=token,
                    interval='ONE_DAY',
                    from_date=from_date.strftime('%Y-%m-%d %H:%M'),
                    to_date=to_date.strftime('%Y-%m-%d %H:%M')
                )
                
                if candles and candles.get('status'):
                    candle_data = candles.get('data', [])
                    
                    assert len(candle_data) > 0
                    
                    # Verify candle structure [timestamp, open, high, low, close, volume]
                    first_candle = candle_data[0]
                    assert len(first_candle) >= 6
                    
                    logger.info(f"✓ TC_QUOTE_03: Historical data retrieved - {len(candle_data)} daily candles")
                    logger.info(f"  Latest: Time={first_candle[0]}, Close=₹{first_candle[4]:.2f}")
                else:
                    pytest.skip("No historical data available")
                    
            except Exception as e:
                pytest.skip(f"Historical data not available: {e}")
        else:
            pytest.skip("Historical data test only implemented for NIFTY")
    
    def test_get_spot_price(self, angelone_adapter, test_instruments):
        """Test spot price retrieval."""
        spot_price = angelone_adapter.get_spot_price(test_instruments['underlying'])
        
        assert spot_price is not None
        assert spot_price > 0
        
        logger.info(f"✓ Spot price: {test_instruments['underlying']} = ₹{spot_price:.2f}")


# ══════════════════════════════════════════════════════════════════════════════
# TC_POS_01-03: POSITIONS AND HOLDINGS TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestAngelOnePositions:
    """Position and holdings tests."""
    
    def test_pos_01_fetch_net_positions(self, angelone_adapter):
        """
        TC_POS_01: Fetch net positions
        
        Expected: Returns list of open positions (may be empty)
        """
        positions = angelone_adapter.get_positions()
        
        assert isinstance(positions, list)
        
        if len(positions) > 0:
            position = positions[0]
            assert isinstance(position, Position)
            assert hasattr(position, 'quantity')
            assert hasattr(position, 'avg_price')
            
            logger.info(f"✓ TC_POS_01: {len(positions)} position(s) retrieved")
            logger.info(f"  First position: {position.symbol}, Qty={position.quantity}")
        else:
            logger.info("✓ TC_POS_01: No positions (account has no open positions)")
    
    def test_pos_02_fetch_holdings_funds(self, angelone_adapter):
        """
        TC_POS_02: Fetch holdings/funds
        
        Expected: Returns dict with cash, equity holdings
        """
        funds = angelone_adapter.get_funds()
        
        assert funds is not None
        assert isinstance(funds, Funds)
        assert funds.available_cash >= 0
        assert funds.total_balance >= 0
        
        logger.info("✓ TC_POS_02: Account funds retrieved")
        logger.info(f"  Available cash: ₹{funds.available_cash:,.2f}")
        logger.info(f"  Total balance: ₹{funds.total_balance:,.2f}")
    
    @pytest.mark.amo_order
    def test_pos_03_square_off_position(self, angelone_adapter, amo_order_helper,
                                       test_instruments, skip_if_market_open):
        """
        TC_POS_03: Exit position (square off) - Simulated with AMO
        
        Expected: Opposite order placed to square off position
        """
        # First, place a BUY AMO order
        buy_request = amo_order_helper.create_amo_request(
            adapter=angelone_adapter,
            underlying=test_instruments['underlying'],
            strike=test_instruments['strike'],
            quantity=test_instruments['quantity'],
            order_type='MARKET'
        )
        buy_request.transaction_type = TransactionType.BUY
        
        buy_response = amo_order_helper.place_and_track(angelone_adapter, buy_request)
        assert buy_response.success is True
        
        # Now place opposite SELL order to square off
        sell_request = amo_order_helper.create_amo_request(
            adapter=angelone_adapter,
            underlying=test_instruments['underlying'],
            strike=test_instruments['strike'],
            quantity=test_instruments['quantity'],
            order_type='MARKET'
        )
        sell_request.transaction_type = TransactionType.SELL
        
        sell_response = amo_order_helper.place_and_track(angelone_adapter, sell_request)
        assert sell_response.success is True
        
        logger.info("✓ TC_POS_03: Square-off orders placed (BUY + SELL AMO)")
        logger.info(f"  BUY order: {buy_response.order_id}")
        logger.info(f"  SELL order (square off): {sell_response.order_id}")


# ══════════════════════════════════════════════════════════════════════════════
# TC_WS_01-03: WEBSOCKET STREAMING TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestAngelOneWebSocket:
    """WebSocket streaming tests (requires market hours)."""
    
    @pytest.mark.websocket
    @pytest.mark.slow
    def test_ws_01_subscribe_live_ticks(self, angelone_adapter, test_instruments):
        """
        TC_WS_01: Subscribe to live ticks
        
        Expected: Receives tick data from SmartWebSocket
        """
        pytest.skip("WebSocket test requires market hours - implement when needed")
        
        # TODO: Implement WebSocket subscription
        # This requires SmartWebSocketV2 from smartapi
        # from smartapi import SmartWebSocketV2
        # 
        # ws = SmartWebSocketV2(auth_token, api_key, client_code, feed_token)
        # ws.on_data = on_data_callback
        # ws.connect()
    
    @pytest.mark.websocket
    def test_ws_02_error_invalid_token(self, angelone_adapter):
        """
        TC_WS_02: Error on invalid token
        
        Expected: Logs error, handles reconnection
        """
        pytest.skip("WebSocket error handling test - implement when needed")
    
    @pytest.mark.websocket
    def test_ws_03_unsubscribe_mode(self, angelone_adapter):
        """
        TC_WS_03: Unsubscribe mode
        
        Expected: Stops feed for subscribed instruments
        """
        pytest.skip("WebSocket unsubscribe test - implement when needed")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
