"""
Tests for Zerodha adapter plugin.

Tests Zerodha-specific implementation including:
- Token-based API calls using zerodha_instrument_token from cache
- LTP and quote fetching
- Order placement with different order types
- Position and margin management
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import pandas as pd
from datetime import datetime

from paper_trading.brokers.adapter.plugins.zerodha import ZerodhaAdapter
from paper_trading.brokers.adapter.types import (
    OrderRequest, OrderType, ProductType, TransactionType,
    Exchange, OrderStatus
)


class TestZerodhaAdapterInitialization:
    """Test Zerodha adapter initialization."""

    def test_initialization(self, zerodha_credentials):
        """Test adapter initializes correctly."""
        adapter = ZerodhaAdapter(zerodha_credentials)

        assert adapter.credentials == zerodha_credentials
        assert adapter.broker_name == 'zerodha'
        assert adapter._connected is False
        assert adapter._kite is None

    def test_initialization_with_contract_manager(self, zerodha_credentials, mock_contract_manager):
        """Test initialization with ContractManager."""
        adapter = ZerodhaAdapter(zerodha_credentials, mock_contract_manager)

        assert adapter.contract_manager == mock_contract_manager


class TestZerodhaConnection:
    """Test Zerodha connection management."""

    @patch('paper_trading.brokers.adapter.plugins.zerodha.ZerodhaConnection')
    @patch('paper_trading.brokers.adapter.plugins.zerodha.ZerodhaDataFeed')
    def test_connect_success(self, mock_data_feed_class, mock_conn_class,
                            zerodha_credentials, mock_contract_manager, mock_kite_api):
        """Test successful connection to Zerodha."""
        # Setup mocks
        mock_conn = Mock()
        mock_conn.connect.return_value = mock_kite_api
        mock_conn_class.return_value = mock_conn

        mock_data_feed = Mock()
        mock_data_feed_class.return_value = mock_data_feed

        # Create adapter and connect
        adapter = ZerodhaAdapter(zerodha_credentials, mock_contract_manager)
        result = adapter.connect()

        assert result is True
        assert adapter.is_connected()
        assert adapter._kite == mock_kite_api
        assert adapter._data_feed == mock_data_feed

        # Verify connection was created with correct credentials
        mock_conn_class.assert_called_once_with(
            api_key=zerodha_credentials['api_key'],
            api_secret=zerodha_credentials['api_secret'],
            user_id=zerodha_credentials['user_id'],
            user_password=zerodha_credentials['user_password'],
            totp_key=zerodha_credentials['totp_key']
        )

    @patch('paper_trading.brokers.adapter.plugins.zerodha.ZerodhaConnection')
    def test_connect_failure(self, mock_conn_class, zerodha_credentials):
        """Test connection failure handling."""
        mock_conn = Mock()
        mock_conn.connect.return_value = None  # Connection failed
        mock_conn_class.return_value = mock_conn

        adapter = ZerodhaAdapter(zerodha_credentials)
        result = adapter.connect()

        assert result is False
        assert not adapter.is_connected()

    def test_disconnect(self, zerodha_credentials):
        """Test disconnect functionality."""
        adapter = ZerodhaAdapter(zerodha_credentials)
        adapter._connected = True
        adapter._connection = Mock()

        adapter.disconnect()

        assert not adapter.is_connected()
        adapter._connection.logout.assert_called_once()


class TestZerodhaTokenBasedLookup:
    """Test token-based instrument lookups (core feature)."""

    @patch.object(ZerodhaAdapter, 'connect')
    def test_get_ltp_uses_token_from_cache(self, mock_connect,
                                           zerodha_credentials, mock_contract_manager,
                                           sample_option_contract, mock_kite_api):
        """Test LTP fetch uses zerodha_instrument_token from cache."""
        adapter = ZerodhaAdapter(zerodha_credentials, mock_contract_manager)
        adapter._connected = True
        adapter._kite = mock_kite_api

        # Mock contract with zerodha_instrument_token
        contract_with_token = sample_option_contract.copy()
        contract_with_token['zerodha_instrument_token'] = 12345678
        mock_contract_manager.get_option_contract.return_value = contract_with_token

        # Get LTP
        ltp = adapter.get_ltp(
            underlying='NIFTY',
            option_type='CE',
            strike=contract_with_token['strike'],
            expiry=contract_with_token['expiry']
        )

        # Verify it called Kite API with token (not symbol!)
        assert ltp == 150.50
        mock_kite_api.ltp.assert_called_once_with(['NFO:12345678'])

    @patch.object(ZerodhaAdapter, 'connect')
    def test_get_ltp_fails_without_token(self, mock_connect,
                                        zerodha_credentials, mock_contract_manager,
                                        sample_option_contract, mock_kite_api):
        """Test LTP fetch fails when zerodha_instrument_token missing."""
        adapter = ZerodhaAdapter(zerodha_credentials, mock_contract_manager)
        adapter._connected = True
        adapter._kite = mock_kite_api

        # Contract WITHOUT zerodha_instrument_token
        contract_no_token = sample_option_contract.copy()
        contract_no_token.pop('zerodha_instrument_token', None)
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
        mock_kite_api.ltp.assert_not_called()

    @patch.object(ZerodhaAdapter, 'connect')
    def test_get_quote_uses_token(self, mock_connect,
                                  zerodha_credentials, mock_contract_manager,
                                  sample_option_contract, mock_kite_api):
        """Test quote fetch uses token from cache."""
        adapter = ZerodhaAdapter(zerodha_credentials, mock_contract_manager)
        adapter._connected = True
        adapter._kite = mock_kite_api

        contract_with_token = sample_option_contract.copy()
        contract_with_token['zerodha_instrument_token'] = 12345678
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
        mock_kite_api.quote.assert_called_once_with(['NFO:12345678'])


class TestZerodhaMarketData:
    """Test market data methods."""

    @patch.object(ZerodhaAdapter, 'connect')
    def test_get_spot_price(self, mock_connect, zerodha_credentials, mock_contract_manager):
        """Test getting spot price."""
        adapter = ZerodhaAdapter(zerodha_credentials, mock_contract_manager)
        adapter._connected = True

        mock_data_feed = Mock()
        mock_data_feed.get_spot_price.return_value = 23456.75
        adapter._data_feed = mock_data_feed

        spot = adapter.get_spot_price()

        assert spot == 23456.75
        mock_data_feed.get_spot_price.assert_called_once()

    @patch.object(ZerodhaAdapter, 'connect')
    def test_get_option_chain(self, mock_connect, zerodha_credentials, mock_contract_manager):
        """Test getting option chain."""
        adapter = ZerodhaAdapter(zerodha_credentials, mock_contract_manager)
        adapter._connected = True

        # Mock data feed response
        mock_df = pd.DataFrame({
            'strike': [25000, 25000],
            'option_type': ['CE', 'PE'],
            'close': [150.0, 140.0]
        })

        mock_data_feed = Mock()
        mock_data_feed.get_options_chain.return_value = mock_df
        adapter._data_feed = mock_data_feed

        result = adapter.get_option_chain('NIFTY', '2026-02-26', [25000, 25100])

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        mock_data_feed.get_options_chain.assert_called_once()


class TestZerodhaOrderManagement:
    """Test order placement and management."""

    @patch.object(ZerodhaAdapter, 'connect')
    def test_place_market_order(self, mock_connect,
                                zerodha_credentials, mock_contract_manager,
                                sample_option_contract, mock_kite_api,
                                sample_order_request):
        """Test placing a market order."""
        adapter = ZerodhaAdapter(zerodha_credentials, mock_contract_manager)
        adapter._connected = True
        adapter._kite = mock_kite_api

        # Setup contract resolution
        contract_with_token = sample_option_contract.copy()
        mock_contract_manager.get_option_contract.return_value = contract_with_token

        # Place order
        response = adapter.place_order(sample_order_request)

        assert response.success is True
        assert response.order_id == '230125000123456'
        assert response.status == OrderStatus.PENDING

        # Verify Kite API was called with correct params
        mock_kite_api.place_order.assert_called_once()
        call_kwargs = mock_kite_api.place_order.call_args[1]

        assert call_kwargs['exchange'] == 'NFO'
        assert call_kwargs['tradingsymbol'] == sample_option_contract['symbol']
        assert call_kwargs['transaction_type'] == 'BUY'
        assert call_kwargs['order_type'] == 'MARKET'
        assert call_kwargs['product'] == 'MIS'  # INTRADAY maps to MIS
        assert call_kwargs['quantity'] == 65

    @patch.object(ZerodhaAdapter, 'connect')
    def test_place_limit_order(self, mock_connect,
                               zerodha_credentials, mock_contract_manager,
                               sample_option_contract, mock_kite_api):
        """Test placing a limit order."""
        adapter = ZerodhaAdapter(zerodha_credentials, mock_contract_manager)
        adapter._connected = True
        adapter._kite = mock_kite_api

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
        call_kwargs = mock_kite_api.place_order.call_args[1]
        assert call_kwargs['order_type'] == 'LIMIT'
        assert call_kwargs['price'] == 150.50

    @patch.object(ZerodhaAdapter, 'connect')
    def test_place_stop_loss_order(self, mock_connect,
                                   zerodha_credentials, mock_contract_manager,
                                   sample_option_contract, mock_kite_api):
        """Test placing a stop-loss order."""
        adapter = ZerodhaAdapter(zerodha_credentials, mock_contract_manager)
        adapter._connected = True
        adapter._kite = mock_kite_api

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

        # Verify SL params
        call_kwargs = mock_kite_api.place_order.call_args[1]
        assert call_kwargs['order_type'] == 'SL'
        assert call_kwargs['price'] == 100.0
        assert call_kwargs['trigger_price'] == 105.0

    @patch.object(ZerodhaAdapter, 'connect')
    def test_order_product_type_mapping(self, mock_connect,
                                       zerodha_credentials, mock_contract_manager,
                                       sample_option_contract, mock_kite_api):
        """Test product type mapping (INTRADAY->MIS, CARRYFORWARD->NRML)."""
        adapter = ZerodhaAdapter(zerodha_credentials, mock_contract_manager)
        adapter._connected = True
        adapter._kite = mock_kite_api

        mock_contract_manager.get_option_contract.return_value = sample_option_contract

        # Test CARRYFORWARD -> NRML
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

        call_kwargs = mock_kite_api.place_order.call_args[1]
        assert call_kwargs['product'] == 'NRML'

    @patch.object(ZerodhaAdapter, 'connect')
    def test_modify_order(self, mock_connect, zerodha_credentials, mock_kite_api):
        """Test modifying an order."""
        adapter = ZerodhaAdapter(zerodha_credentials)
        adapter._connected = True
        adapter._kite = mock_kite_api

        mock_kite_api.modify_order = Mock()

        changes = {'price': 155.0, 'quantity': 130}
        response = adapter.modify_order('ORD123', changes)

        assert response.success is True
        mock_kite_api.modify_order.assert_called_once()

    @patch.object(ZerodhaAdapter, 'connect')
    def test_cancel_order(self, mock_connect, zerodha_credentials, mock_kite_api):
        """Test cancelling an order."""
        adapter = ZerodhaAdapter(zerodha_credentials)
        adapter._connected = True
        adapter._kite = mock_kite_api

        mock_kite_api.cancel_order = Mock()

        response = adapter.cancel_order('ORD123')

        assert response.success is True
        assert response.status == OrderStatus.CANCELLED
        mock_kite_api.cancel_order.assert_called_once_with(
            order_id='ORD123',
            variety='regular'
        )

    @patch.object(ZerodhaAdapter, 'connect')
    def test_get_orders(self, mock_connect, zerodha_credentials, mock_kite_api):
        """Test getting all orders."""
        adapter = ZerodhaAdapter(zerodha_credentials)
        adapter._connected = True
        adapter._kite = mock_kite_api

        orders = adapter.get_orders()

        assert len(orders) == 1
        assert orders[0].order_id == '230125000123456'
        assert orders[0].status == OrderStatus.COMPLETE
        assert orders[0].filled_quantity == 65
        assert orders[0].average_price == 150.25


class TestZerodhaPositionsAndFunds:
    """Test position and fund management."""

    @patch.object(ZerodhaAdapter, 'connect')
    def test_get_positions(self, mock_connect, zerodha_credentials, mock_kite_api):
        """Test getting positions."""
        adapter = ZerodhaAdapter(zerodha_credentials)
        adapter._connected = True
        adapter._kite = mock_kite_api

        positions = adapter.get_positions()

        assert len(positions) == 1
        assert positions[0].quantity == 65
        assert positions[0].avg_price == 150.0
        assert positions[0].ltp == 155.0
        assert positions[0].pnl == 325.0

    @patch.object(ZerodhaAdapter, 'connect')
    def test_get_funds(self, mock_connect, zerodha_credentials, mock_kite_api):
        """Test getting account funds."""
        adapter = ZerodhaAdapter(zerodha_credentials)
        adapter._connected = True
        adapter._kite = mock_kite_api

        funds = adapter.get_funds()

        assert funds is not None
        assert funds.available_cash == 50000
        assert funds.used_margin == 20000
        assert funds.available_margin == 100000


class TestZerodhaMarketStatus:
    """Test market status checks."""

    @patch.object(ZerodhaAdapter, 'connect')
    def test_is_market_open(self, mock_connect, zerodha_credentials):
        """Test market open check."""
        adapter = ZerodhaAdapter(zerodha_credentials)
        adapter._connected = True

        mock_data_feed = Mock()
        mock_data_feed.is_market_open.return_value = True
        adapter._data_feed = mock_data_feed

        is_open = adapter.is_market_open()

        assert is_open is True
        mock_data_feed.is_market_open.assert_called_once()


class TestZerodhaDeprecatedMethods:
    """Test deprecated methods for backward compatibility."""

    def test_load_instruments_deprecated(self, zerodha_credentials):
        """Test load_instruments is deprecated but doesn't break."""
        adapter = ZerodhaAdapter(zerodha_credentials)
        adapter._data_feed = Mock()
        adapter._data_feed.load_instruments.return_value = True

        result = adapter.load_instruments()

        # Should return True (no-op in token-based mode)
        assert result is True
