"""
Tests for AngelOne adapter plugin.

Tests AngelOne-specific implementation including:
- Token-based API calls (no symbols required)
- LTP and quote fetching using tokens
- Order placement with AngelOne-specific parameters
- Batch market data fetching
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import pandas as pd
from datetime import datetime

from paper_trading.brokers.adapter.plugins.angelone import AngelOneAdapter
from paper_trading.brokers.adapter.types import (
    OrderRequest, OrderType, ProductType, TransactionType,
    Exchange, OrderStatus
)


class TestAngelOneAdapterInitialization:
    """Test AngelOne adapter initialization."""

    def test_initialization(self, angelone_credentials):
        """Test adapter initializes correctly."""
        adapter = AngelOneAdapter(angelone_credentials)

        assert adapter.credentials == angelone_credentials
        assert adapter.broker_name == 'angelone'
        assert adapter._connected is False
        assert adapter._smart_api is None

    def test_initialization_with_contract_manager(self, angelone_credentials, mock_contract_manager):
        """Test initialization with ContractManager."""
        adapter = AngelOneAdapter(angelone_credentials, mock_contract_manager)

        assert adapter.contract_manager == mock_contract_manager


class TestAngelOneConnection:
    """Test AngelOne connection management."""

    @patch('paper_trading.brokers.adapter.plugins.angelone.AngelOneConnection')
    def test_connect_success(self, mock_conn_class, angelone_credentials,
                            mock_contract_manager, mock_angelone_api):
        """Test successful connection to AngelOne."""
        # Setup mock connection
        mock_conn = Mock()
        mock_conn.connect.return_value = {'status': True}
        mock_conn.smart_api = mock_angelone_api
        mock_conn_class.return_value = mock_conn

        # Create adapter and connect
        adapter = AngelOneAdapter(angelone_credentials, mock_contract_manager)
        result = adapter.connect()

        assert result is True
        assert adapter.is_connected()
        assert adapter._smart_api == mock_angelone_api

        # Verify connection was created with correct credentials
        mock_conn_class.assert_called_once_with(
            api_key=angelone_credentials['api_key'],
            username=angelone_credentials['username'],
            password=angelone_credentials['password'],
            totp_token=angelone_credentials['totp_token']
        )

    @patch('paper_trading.brokers.adapter.plugins.angelone.AngelOneConnection')
    def test_connect_failure(self, mock_conn_class, angelone_credentials):
        """Test connection failure handling."""
        mock_conn = Mock()
        mock_conn.connect.return_value = None
        mock_conn_class.return_value = mock_conn

        adapter = AngelOneAdapter(angelone_credentials)
        result = adapter.connect()

        assert result is False
        assert not adapter.is_connected()

    def test_disconnect(self, angelone_credentials):
        """Test disconnect functionality."""
        adapter = AngelOneAdapter(angelone_credentials)
        adapter._connected = True
        adapter._connection = Mock()

        adapter.disconnect()

        assert not adapter.is_connected()
        adapter._connection.logout.assert_called_once()


class TestAngelOneTokenBasedLookup:
    """Test token-based lookups (NO symbols required!)."""

    @patch.object(AngelOneAdapter, 'connect')
    def test_get_ltp_uses_token_only(self, mock_connect,
                                     angelone_credentials, mock_contract_manager,
                                     sample_option_contract, mock_angelone_api):
        """Test LTP fetch uses ONLY token from cache (no symbol needed)."""
        adapter = AngelOneAdapter(angelone_credentials, mock_contract_manager)
        adapter._connected = True
        adapter._smart_api = mock_angelone_api

        # Setup contract with token
        contract_with_token = sample_option_contract.copy()
        contract_with_token['token'] = '12345678'
        mock_contract_manager.get_option_contract.return_value = contract_with_token

        # Get LTP
        ltp = adapter.get_ltp(
            underlying='NIFTY',
            option_type='CE',
            strike=contract_with_token['strike'],
            expiry=contract_with_token['expiry']
        )

        # Verify it called AngelOne API with token (not symbol!)
        assert ltp == 150.50
        mock_angelone_api.getMarketData.assert_called_once()

        call_kwargs = mock_angelone_api.getMarketData.call_args[1]
        assert call_kwargs['mode'] == 'LTP'
        assert call_kwargs['exchangeTokens'] == {'NFO': ['12345678']}

    @patch.object(AngelOneAdapter, 'connect')
    def test_get_ltp_fails_without_token(self, mock_connect,
                                        angelone_credentials, mock_contract_manager,
                                        sample_option_contract, mock_angelone_api):
        """Test LTP fetch fails when token is missing."""
        adapter = AngelOneAdapter(angelone_credentials, mock_contract_manager)
        adapter._connected = True
        adapter._smart_api = mock_angelone_api

        # Contract WITHOUT token
        contract_no_token = sample_option_contract.copy()
        contract_no_token.pop('token', None)
        mock_contract_manager.get_option_contract.return_value = contract_no_token

        # Get LTP should fail
        ltp = adapter.get_ltp(
            underlying='NIFTY',
            option_type='CE',
            strike=contract_no_token['strike'],
            expiry=contract_no_token['expiry']
        )

        assert ltp is None
        # API should NOT be called without token
        mock_angelone_api.getMarketData.assert_not_called()

    @patch.object(AngelOneAdapter, 'connect')
    def test_get_quote_uses_token(self, mock_connect,
                                  angelone_credentials, mock_contract_manager,
                                  sample_option_contract, mock_angelone_api):
        """Test quote fetch uses token from cache."""
        adapter = AngelOneAdapter(angelone_credentials, mock_contract_manager)
        adapter._connected = True
        adapter._smart_api = mock_angelone_api

        contract_with_token = sample_option_contract.copy()
        contract_with_token['token'] = '12345678'
        mock_contract_manager.get_option_contract.return_value = contract_with_token

        # Get quote
        quote = adapter.get_quote(
            underlying='NIFTY',
            option_type='CE',
            strike=contract_with_token['strike'],
            expiry=contract_with_token['expiry']
        )

        assert quote is not None
        assert quote.ltp == 150.50
        assert quote.volume == 10000
        assert quote.oi == 50000

        # Verify it used FULL mode for complete quote
        call_kwargs = mock_angelone_api.getMarketData.call_args[1]
        assert call_kwargs['mode'] == 'FULL'
        assert call_kwargs['exchangeTokens'] == {'NFO': ['12345678']}


class TestAngelOneMarketData:
    """Test market data methods."""

    @patch.object(AngelOneAdapter, 'connect')
    def test_get_spot_price(self, mock_connect, angelone_credentials, mock_angelone_api):
        """Test getting NIFTY spot price."""
        adapter = AngelOneAdapter(angelone_credentials)
        adapter._connected = True
        adapter._smart_api = mock_angelone_api

        spot = adapter.get_spot_price()

        assert spot == 23456.75
        mock_angelone_api.ltpData.assert_called_once_with(
            'NSE', 'NIFTY 50', AngelOneAdapter.NIFTY_TOKEN
        )

    @patch.object(AngelOneAdapter, 'connect')
    @patch('time.sleep')  # Mock sleep to speed up test
    def test_get_option_chain_batch_fetching(self, mock_sleep, mock_connect,
                                             angelone_credentials, mock_contract_manager,
                                             mock_angelone_api):
        """Test option chain fetching with batch token lookups."""
        adapter = AngelOneAdapter(angelone_credentials, mock_contract_manager)
        adapter._connected = True
        adapter._smart_api = mock_angelone_api

        # Mock contract manager to return contracts for strikes
        def get_contract(expiry, strike, option_type):
            return {
                'symbol': f'NIFTY26FEB{strike}{option_type}',
                'token': f'{strike}{option_type}',
                'strike': strike,
                'option_type': option_type,
                'expiry': expiry
            }

        mock_contract_manager.get_option_contract.side_effect = get_contract

        # Get option chain
        result = adapter.get_option_chain('NIFTY', '2026-02-26', [25000, 25100])

        assert isinstance(result, pd.DataFrame)
        # Should have called getMarketData with batched tokens
        assert mock_angelone_api.getMarketData.called

    @patch.object(AngelOneAdapter, 'connect')
    def test_get_quotes_multiple_instruments(self, mock_connect,
                                             angelone_credentials, mock_contract_manager,
                                             mock_angelone_api):
        """Test getting quotes for multiple instruments."""
        adapter = AngelOneAdapter(angelone_credentials, mock_contract_manager)
        adapter._connected = True
        adapter._smart_api = mock_angelone_api

        def get_contract(expiry, strike, option_type):
            return {
                'token': f'{strike}{option_type}',
                'strike': strike,
                'option_type': option_type
            }

        mock_contract_manager.get_option_contract.side_effect = get_contract

        instruments = [
            ('NIFTY', 'CE', 25000, '2026-02-26'),
            ('NIFTY', 'PE', 25000, '2026-02-26')
        ]

        with patch('time.sleep'):  # Speed up test
            quotes = adapter.get_quotes(instruments)

        assert len(quotes) == 2
        assert ('NIFTY', 'CE', 25000, '2026-02-26') in quotes
        assert ('NIFTY', 'PE', 25000, '2026-02-26') in quotes


class TestAngelOneOrderManagement:
    """Test order placement and management."""

    @patch.object(AngelOneAdapter, 'connect')
    def test_place_market_order(self, mock_connect,
                                angelone_credentials, mock_contract_manager,
                                sample_option_contract, mock_angelone_api,
                                sample_order_request):
        """Test placing a market order."""
        adapter = AngelOneAdapter(angelone_credentials, mock_contract_manager)
        adapter._connected = True
        adapter._smart_api = mock_angelone_api

        # Setup contract resolution
        mock_contract_manager.get_option_contract.return_value = sample_option_contract

        # Place order
        response = adapter.place_order(sample_order_request)

        assert response.success is True
        assert response.order_id == 'AO123456789'
        assert response.status == OrderStatus.PENDING

        # Verify AngelOne API was called with correct params
        mock_angelone_api.placeOrder.assert_called_once()
        call_args = mock_angelone_api.placeOrder.call_args[0][0]

        assert call_args['variety'] == 'NORMAL'
        assert call_args['tradingsymbol'] == sample_option_contract['symbol']
        assert call_args['symboltoken'] == sample_option_contract['token']
        assert call_args['transactiontype'] == 'BUY'
        assert call_args['ordertype'] == 'MARKET'
        assert call_args['producttype'] == 'INTRADAY'
        assert call_args['quantity'] == '65'

    @patch.object(AngelOneAdapter, 'connect')
    def test_place_limit_order(self, mock_connect,
                               angelone_credentials, mock_contract_manager,
                               sample_option_contract, mock_angelone_api):
        """Test placing a limit order."""
        adapter = AngelOneAdapter(angelone_credentials, mock_contract_manager)
        adapter._connected = True
        adapter._smart_api = mock_angelone_api

        mock_contract_manager.get_option_contract.return_value = sample_option_contract

        # Create limit order
        order = OrderRequest(
            underlying='NIFTY',
            option_type='CE',
            strike=sample_option_contract['strike'],
            expiry=sample_option_contract['expiry'],
            exchange=Exchange.NFO,
            transaction_type=TransactionType.BUY,
            order_type=OrderType.LIMIT,
            quantity=65,
            price=150.50,
            product_type=ProductType.INTRADAY
        )

        response = adapter.place_order(order)

        assert response.success is True

        # Verify limit price was included
        call_args = mock_angelone_api.placeOrder.call_args[0][0]
        assert call_args['ordertype'] == 'LIMIT'
        assert call_args['price'] == '150.5'

    @patch.object(AngelOneAdapter, 'connect')
    def test_place_stop_loss_order(self, mock_connect,
                                   angelone_credentials, mock_contract_manager,
                                   sample_option_contract, mock_angelone_api):
        """Test placing a stop-loss order."""
        adapter = AngelOneAdapter(angelone_credentials, mock_contract_manager)
        adapter._connected = True
        adapter._smart_api = mock_angelone_api

        mock_contract_manager.get_option_contract.return_value = sample_option_contract

        # Create SL order
        order = OrderRequest(
            underlying='NIFTY',
            option_type='CE',
            strike=sample_option_contract['strike'],
            expiry=sample_option_contract['expiry'],
            exchange=Exchange.NFO,
            transaction_type=TransactionType.SELL,
            order_type=OrderType.SL,
            quantity=65,
            price=100.0,
            trigger_price=105.0,
            product_type=ProductType.INTRADAY
        )

        response = adapter.place_order(order)

        assert response.success is True

        # Verify SL params - AngelOne uses STOPLOSS_LIMIT
        call_args = mock_angelone_api.placeOrder.call_args[0][0]
        assert call_args['ordertype'] == 'STOPLOSS_LIMIT'
        assert call_args['price'] == '100.0'
        assert call_args['triggerprice'] == '105.0'

    @patch.object(AngelOneAdapter, 'connect')
    def test_order_product_type_mapping(self, mock_connect,
                                       angelone_credentials, mock_contract_manager,
                                       sample_option_contract, mock_angelone_api):
        """Test product type mapping (CARRYFORWARD->CARRYFORWARD)."""
        adapter = AngelOneAdapter(angelone_credentials, mock_contract_manager)
        adapter._connected = True
        adapter._smart_api = mock_angelone_api

        mock_contract_manager.get_option_contract.return_value = sample_option_contract

        # Test CARRYFORWARD stays CARRYFORWARD (unlike Zerodha's NRML)
        order = OrderRequest(
            underlying='NIFTY',
            option_type='CE',
            strike=sample_option_contract['strike'],
            expiry=sample_option_contract['expiry'],
            exchange=Exchange.NFO,
            transaction_type=TransactionType.BUY,
            order_type=OrderType.MARKET,
            quantity=65,
            product_type=ProductType.CARRYFORWARD
        )

        adapter.place_order(order)

        call_args = mock_angelone_api.placeOrder.call_args[0][0]
        assert call_args['producttype'] == 'CARRYFORWARD'

    @patch.object(AngelOneAdapter, 'connect')
    def test_modify_order(self, mock_connect, angelone_credentials, mock_angelone_api):
        """Test modifying an order."""
        adapter = AngelOneAdapter(angelone_credentials)
        adapter._connected = True
        adapter._smart_api = mock_angelone_api

        mock_angelone_api.modifyOrder.return_value = {
            'status': True,
            'message': 'Order modified'
        }

        changes = {'price': 155.0, 'quantity': 130}
        response = adapter.modify_order('AO123', changes)

        assert response.success is True
        mock_angelone_api.modifyOrder.assert_called_once()

    @patch.object(AngelOneAdapter, 'connect')
    def test_cancel_order(self, mock_connect, angelone_credentials, mock_angelone_api):
        """Test cancelling an order."""
        adapter = AngelOneAdapter(angelone_credentials)
        adapter._connected = True
        adapter._smart_api = mock_angelone_api

        mock_angelone_api.cancelOrder.return_value = {
            'status': True,
            'message': 'Order cancelled'
        }

        response = adapter.cancel_order('AO123')

        assert response.success is True
        assert response.status == OrderStatus.CANCELLED
        mock_angelone_api.cancelOrder.assert_called_once_with('AO123', 'NORMAL')

    @patch.object(AngelOneAdapter, 'connect')
    def test_get_orders(self, mock_connect, angelone_credentials, mock_angelone_api):
        """Test getting all orders."""
        adapter = AngelOneAdapter(angelone_credentials)
        adapter._connected = True
        adapter._smart_api = mock_angelone_api

        orders = adapter.get_orders()

        assert len(orders) == 1
        assert orders[0].order_id == 'AO123456789'
        assert orders[0].status == OrderStatus.COMPLETE
        assert orders[0].filled_quantity == 65
        assert orders[0].average_price == 150.25


class TestAngelOnePositionsAndFunds:
    """Test position and fund management."""

    @patch.object(AngelOneAdapter, 'connect')
    def test_get_positions(self, mock_connect, angelone_credentials, mock_angelone_api):
        """Test getting positions."""
        adapter = AngelOneAdapter(angelone_credentials)
        adapter._connected = True
        adapter._smart_api = mock_angelone_api

        positions = adapter.get_positions()

        assert len(positions) == 1
        assert positions[0].quantity == 65
        assert positions[0].avg_price == 150.0
        assert positions[0].ltp == 155.0
        assert positions[0].pnl == 325.0
        assert positions[0].token == '12345678'

    @patch.object(AngelOneAdapter, 'connect')
    def test_get_funds(self, mock_connect, angelone_credentials, mock_angelone_api):
        """Test getting account funds."""
        adapter = AngelOneAdapter(angelone_credentials)
        adapter._connected = True
        adapter._smart_api = mock_angelone_api

        funds = adapter.get_funds()

        assert funds is not None
        assert funds.available_cash == 50000
        assert funds.used_margin == 20000
        assert funds.available_margin == 100000


class TestAngelOneMarketStatus:
    """Test market status checks."""

    @patch('paper_trading.brokers.adapter.plugins.angelone.datetime')
    def test_is_market_open_during_hours(self, mock_datetime):
        """Test market is open during trading hours."""
        from datetime import datetime as dt, time

        # Mock time as 10:00 AM on a Monday
        mock_now = dt(2026, 2, 23, 10, 0, 0)  # Monday
        mock_datetime.now.return_value = mock_now

        adapter = AngelOneAdapter({'api_key': 'test'})
        is_open = adapter.is_market_open()

        assert is_open is True

    @patch('paper_trading.brokers.adapter.plugins.angelone.datetime')
    def test_is_market_closed_after_hours(self, mock_datetime):
        """Test market is closed after trading hours."""
        from datetime import datetime as dt

        # Mock time as 4:00 PM (after close)
        mock_now = dt(2026, 2, 23, 16, 0, 0)
        mock_datetime.now.return_value = mock_now

        adapter = AngelOneAdapter({'api_key': 'test'})
        is_open = adapter.is_market_open()

        assert is_open is False

    @patch('paper_trading.brokers.adapter.plugins.angelone.datetime')
    def test_is_market_closed_weekend(self, mock_datetime):
        """Test market is closed on weekends."""
        from datetime import datetime as dt

        # Mock time as Saturday 10:00 AM
        mock_now = dt(2026, 2, 28, 10, 0, 0)  # Saturday
        mock_datetime.now.return_value = mock_now

        adapter = AngelOneAdapter({'api_key': 'test'})
        is_open = adapter.is_market_open()

        assert is_open is False


class TestAngelOneDeprecatedMethods:
    """Test deprecated methods for backward compatibility."""

    def test_load_instruments_deprecated(self, angelone_credentials):
        """Test load_instruments is deprecated but doesn't break."""
        adapter = AngelOneAdapter(angelone_credentials)

        result = adapter.load_instruments()

        # Should return True (no-op in token-based mode)
        assert result is True


class TestAngelOneErrorHandling:
    """Test error handling scenarios."""

    @patch.object(AngelOneAdapter, 'connect')
    def test_order_placement_without_connection(self, mock_connect,
                                                angelone_credentials, sample_order_request):
        """Test order placement fails without connection."""
        adapter = AngelOneAdapter(angelone_credentials)
        adapter._connected = False

        response = adapter.place_order(sample_order_request)

        assert response.success is False
        assert response.status == OrderStatus.REJECTED
        assert 'Not connected' in response.message

    @patch.object(AngelOneAdapter, 'connect')
    def test_ltp_fetch_without_connection(self, mock_connect, angelone_credentials):
        """Test LTP fetch returns None without connection."""
        adapter = AngelOneAdapter(angelone_credentials)
        adapter._connected = False

        ltp = adapter.get_ltp('NIFTY', 'CE', 25000, '2026-02-26')

        assert ltp is None

    @patch.object(AngelOneAdapter, 'connect')
    def test_order_placement_contract_not_found(self, mock_connect,
                                                angelone_credentials, mock_contract_manager,
                                                sample_order_request):
        """Test order placement fails when contract not found."""
        adapter = AngelOneAdapter(angelone_credentials, mock_contract_manager)
        adapter._connected = True

        # Mock contract manager to return None (contract not found)
        mock_contract_manager.get_option_contract.return_value = None

        response = adapter.place_order(sample_order_request)

        assert response.success is False
        assert response.status == OrderStatus.REJECTED
        assert 'Could not resolve instrument' in response.message
