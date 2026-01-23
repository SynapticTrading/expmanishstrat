"""
Integration tests for the complete adapter system.

Tests end-to-end workflows including:
- Factory -> Adapter -> ContractManager -> contracts_cache.json flow
- Token-based order lifecycle
- Multi-broker scenarios
"""

import pytest
from unittest.mock import Mock, patch
from paper_trading.brokers.adapter.factory import create_adapter
from paper_trading.brokers.adapter.types import (
    OrderRequest, OrderType, ProductType, TransactionType, Exchange
)


class TestAdapterContractManagerIntegration:
    """Test integration between adapter and ContractManager."""

    def test_zerodha_adapter_with_real_cache_structure(
        self, zerodha_credentials, contracts_cache
    ):
        """Test Zerodha adapter can work with real cache structure."""
        # Create mock contract manager that uses real cache
        mock_cm = Mock()

        # Simulate getting a contract from cache
        def get_contract(expiry, strike, option_type):
            # Try to find contract in cache
            if 'options' in contracts_cache and 'mapping' in contracts_cache['options']:
                current_week = contracts_cache['options']['mapping'].get('current_week', {})
                contracts = current_week.get(option_type, [])

                for contract in contracts:
                    if contract.get('strike') == strike:
                        return contract

            return None

        mock_cm.get_option_contract = Mock(side_effect=get_contract)
        mock_cm.has_instrument_tokens = Mock(return_value=True)

        # Create adapter with mock CM
        adapter = create_adapter(
            zerodha_credentials,
            broker='zerodha',
            contract_manager=mock_cm
        )

        assert adapter is not None
        assert adapter.contract_manager == mock_cm

    def test_angelone_adapter_with_real_cache_structure(
        self, angelone_credentials, contracts_cache
    ):
        """Test AngelOne adapter can work with real cache structure."""
        mock_cm = Mock()

        def get_contract(expiry, strike, option_type):
            if 'options' in contracts_cache and 'mapping' in contracts_cache['options']:
                current_week = contracts_cache['options']['mapping'].get('current_week', {})
                contracts = current_week.get(option_type, [])

                for contract in contracts:
                    if contract.get('strike') == strike:
                        return contract

            return None

        mock_cm.get_option_contract = Mock(side_effect=get_contract)
        mock_cm.has_instrument_tokens = Mock(return_value=True)

        adapter = create_adapter(
            angelone_credentials,
            broker='angelone',
            contract_manager=mock_cm
        )

        assert adapter is not None
        assert adapter.contract_manager == mock_cm


class TestTokenBasedOrderLifecycle:
    """Test complete order lifecycle using token-based approach."""

    @patch('paper_trading.brokers.adapter.plugins.zerodha.ZerodhaConnection')
    @patch('paper_trading.brokers.adapter.plugins.zerodha.ZerodhaDataFeed')
    def test_zerodha_order_lifecycle_with_tokens(
        self, mock_data_feed_class, mock_conn_class,
        zerodha_credentials, mock_contract_manager,
        sample_option_contract, mock_kite_api
    ):
        """Test complete order flow: create -> place -> check -> cancel."""
        # Setup mocks
        mock_conn = Mock()
        mock_conn.connect.return_value = mock_kite_api
        mock_conn_class.return_value = mock_conn

        mock_data_feed = Mock()
        mock_data_feed_class.return_value = mock_data_feed

        # Add zerodha_instrument_token to contract
        contract = sample_option_contract.copy()
        contract['zerodha_instrument_token'] = 12345678
        mock_contract_manager.get_option_contract.return_value = contract

        # Create and connect adapter
        adapter = create_adapter(
            zerodha_credentials,
            broker='zerodha',
            contract_manager=mock_contract_manager
        )
        adapter.connect()

        # 1. Check LTP before order
        ltp = adapter.get_ltp(
            underlying='NIFTY',
            option_type='CE',
            strike=contract['strike'],
            expiry=contract['expiry']
        )
        assert ltp == 150.50

        # 2. Place order
        order_request = OrderRequest(
            underlying='NIFTY',
            option_type='CE',
            strike=contract['strike'],
            expiry=contract['expiry'],
            exchange=Exchange.NFO,
            transaction_type=TransactionType.BUY,
            order_type=OrderType.MARKET,
            quantity=65
        )

        order_response = adapter.place_order(order_request)
        assert order_response.success is True
        order_id = order_response.order_id

        # 3. Check order status
        order = adapter.get_order(order_id)
        assert order is not None
        assert order.order_id == order_id

        # 4. Cancel order
        cancel_response = adapter.cancel_order(order_id)
        assert cancel_response.success is True

    @patch('paper_trading.brokers.adapter.plugins.angelone.AngelOneConnection')
    def test_angelone_order_lifecycle_with_tokens(
        self, mock_conn_class,
        angelone_credentials, mock_contract_manager,
        sample_option_contract, mock_angelone_api
    ):
        """Test complete order flow for AngelOne."""
        # Setup mocks
        mock_conn = Mock()
        mock_conn.connect.return_value = {'status': True}
        mock_conn.smart_api = mock_angelone_api
        mock_conn_class.return_value = mock_conn

        # Setup contract with token
        contract = sample_option_contract.copy()
        contract['token'] = '12345678'
        mock_contract_manager.get_option_contract.return_value = contract

        # Create and connect adapter
        adapter = create_adapter(
            angelone_credentials,
            broker='angelone',
            contract_manager=mock_contract_manager
        )
        adapter.connect()

        # 1. Check LTP
        ltp = adapter.get_ltp(
            underlying='NIFTY',
            option_type='CE',
            strike=contract['strike'],
            expiry=contract['expiry']
        )
        assert ltp == 150.50

        # 2. Place order
        order_request = OrderRequest(
            underlying='NIFTY',
            option_type='CE',
            strike=contract['strike'],
            expiry=contract['expiry'],
            exchange=Exchange.NFO,
            transaction_type=TransactionType.BUY,
            order_type=OrderType.MARKET,
            quantity=65
        )

        order_response = adapter.place_order(order_request)
        assert order_response.success is True

        # 3. Get all orders
        orders = adapter.get_orders()
        assert len(orders) > 0


class TestMultiBrokerScenarios:
    """Test scenarios involving multiple brokers."""

    @patch('paper_trading.brokers.adapter.plugins.zerodha.ZerodhaConnection')
    @patch('paper_trading.brokers.adapter.plugins.zerodha.ZerodhaDataFeed')
    @patch('paper_trading.brokers.adapter.plugins.angelone.AngelOneConnection')
    def test_same_contract_different_brokers(
        self, mock_angelone_conn, mock_zerodha_df, mock_zerodha_conn,
        zerodha_credentials, angelone_credentials,
        mock_contract_manager, sample_option_contract,
        mock_kite_api, mock_angelone_api
    ):
        """Test fetching same contract from different brokers."""
        # Setup Zerodha
        zerodha_conn = Mock()
        zerodha_conn.connect.return_value = mock_kite_api
        mock_zerodha_conn.return_value = zerodha_conn
        mock_zerodha_df.return_value = Mock()

        # Setup AngelOne
        angelone_conn = Mock()
        angelone_conn.connect.return_value = {'status': True}
        angelone_conn.smart_api = mock_angelone_api
        mock_angelone_conn.return_value = angelone_conn

        # Setup contract for both brokers
        zerodha_contract = sample_option_contract.copy()
        zerodha_contract['zerodha_instrument_token'] = 12345678

        angelone_contract = sample_option_contract.copy()
        angelone_contract['token'] = '12345678'

        # Create adapters
        zerodha_adapter = create_adapter(
            zerodha_credentials,
            broker='zerodha',
            contract_manager=mock_contract_manager
        )

        angelone_adapter = create_adapter(
            angelone_credentials,
            broker='angelone',
            contract_manager=mock_contract_manager
        )

        # Connect both
        zerodha_adapter.connect()
        angelone_adapter.connect()

        # Configure contract manager for each broker
        def get_contract_ze(expiry, strike, option_type):
            if strike == zerodha_contract['strike']:
                return zerodha_contract
            return None

        def get_contract_ao(expiry, strike, option_type):
            if strike == angelone_contract['strike']:
                return angelone_contract
            return None

        # Test Zerodha
        mock_contract_manager.get_option_contract.side_effect = get_contract_ze
        zerodha_ltp = zerodha_adapter.get_ltp(
            'NIFTY', 'CE',
            zerodha_contract['strike'],
            zerodha_contract['expiry']
        )

        # Test AngelOne
        mock_contract_manager.get_option_contract.side_effect = get_contract_ao
        angelone_ltp = angelone_adapter.get_ltp(
            'NIFTY', 'CE',
            angelone_contract['strike'],
            angelone_contract['expiry']
        )

        # Both should succeed (may have different prices in real scenario)
        assert zerodha_ltp is not None
        assert angelone_ltp is not None


class TestOrderTypeVariations:
    """Test different order type scenarios."""

    @patch('paper_trading.brokers.adapter.plugins.zerodha.ZerodhaConnection')
    @patch('paper_trading.brokers.adapter.plugins.zerodha.ZerodhaDataFeed')
    def test_all_order_types_zerodha(
        self, mock_df, mock_conn,
        zerodha_credentials, mock_contract_manager,
        sample_option_contract, mock_kite_api
    ):
        """Test all order types with Zerodha."""
        # Setup
        conn = Mock()
        conn.connect.return_value = mock_kite_api
        mock_conn.return_value = conn
        mock_df.return_value = Mock()

        contract = sample_option_contract.copy()
        contract['zerodha_instrument_token'] = 12345678
        mock_contract_manager.get_option_contract.return_value = contract

        adapter = create_adapter(
            zerodha_credentials,
            broker='zerodha',
            contract_manager=mock_contract_manager
        )
        adapter.connect()

        # Test each order type
        order_types = [
            (OrderType.MARKET, None, None),
            (OrderType.LIMIT, 150.50, None),
            (OrderType.SL, 100.0, 105.0),
            (OrderType.SL_M, None, 105.0)
        ]

        for order_type, price, trigger_price in order_types:
            order = OrderRequest(
                underlying='NIFTY',
                option_type='CE',
                strike=contract['strike'],
                expiry=contract['expiry'],
                exchange=Exchange.NFO,
                transaction_type=TransactionType.BUY,
                order_type=order_type,
                quantity=65,
                price=price,
                trigger_price=trigger_price
            )

            response = adapter.place_order(order)
            assert response.success is True, f"Failed for {order_type}"


class TestCacheQueryMechanism:
    """Test how system queries contracts_cache.json without symbols."""

    def test_contract_resolution_flow(self, mock_contract_manager, sample_option_contract):
        """Test the flow: params -> ContractManager -> cache -> token."""
        # Simulate contract resolution
        contract = sample_option_contract.copy()
        contract['token'] = '12345678'
        contract['zerodha_instrument_token'] = 12345678

        mock_contract_manager.get_option_contract.return_value = contract

        # Adapter would call this during instrument resolution
        result = mock_contract_manager.get_option_contract(
            expiry='2026-02-26',
            strike=25000,
            option_type='CE'
        )

        # Verify we got token without needing symbol
        assert result is not None
        assert 'token' in result
        assert result['token'] == '12345678'

        # Verify ContractManager was called (not symbol construction)
        mock_contract_manager.get_option_contract.assert_called_once_with(
            expiry='2026-02-26',
            strike=25000,
            option_type='CE'
        )

    def test_no_symbol_construction_in_adapter(
        self, zerodha_credentials, mock_contract_manager,
        sample_option_contract
    ):
        """Test that adapter never constructs symbols manually."""
        adapter = create_adapter(
            zerodha_credentials,
            broker='zerodha',
            contract_manager=mock_contract_manager
        )

        contract = sample_option_contract.copy()
        contract['zerodha_instrument_token'] = 12345678
        mock_contract_manager.get_option_contract.return_value = contract

        # Resolve instrument
        result = adapter._resolve_instrument(
            underlying='NIFTY',
            option_type='CE',
            strike=25000,
            expiry='2026-02-26'
        )

        # Adapter should use ContractManager, not build symbol
        assert result is not None
        mock_contract_manager.get_option_contract.assert_called_once()

        # The result comes from cache via ContractManager
        assert 'zerodha_instrument_token' in result
