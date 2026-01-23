"""
Tests for adapter factory pattern.

Tests adapter creation, broker auto-detection, and registry management.
"""

import pytest
from paper_trading.brokers.adapter.factory import (
    create_adapter, get_available_brokers, register_adapter, _detect_broker
)
from paper_trading.brokers.adapter.base import BrokerAdapter
from paper_trading.brokers.adapter.plugins.zerodha import ZerodhaAdapter
from paper_trading.brokers.adapter.plugins.angelone import AngelOneAdapter


class TestAdapterCreation:
    """Test adapter creation via factory."""

    def test_create_zerodha_adapter_explicit(self, zerodha_credentials, mock_contract_manager):
        """Test creating Zerodha adapter with explicit broker name."""
        adapter = create_adapter(
            credentials=zerodha_credentials,
            broker='zerodha',
            contract_manager=mock_contract_manager
        )

        assert isinstance(adapter, ZerodhaAdapter)
        assert adapter.broker_name == 'zerodha'
        assert adapter.credentials == zerodha_credentials
        assert adapter.contract_manager == mock_contract_manager

    def test_create_angelone_adapter_explicit(self, angelone_credentials, mock_contract_manager):
        """Test creating AngelOne adapter with explicit broker name."""
        adapter = create_adapter(
            credentials=angelone_credentials,
            broker='angelone',
            contract_manager=mock_contract_manager
        )

        assert isinstance(adapter, AngelOneAdapter)
        assert adapter.broker_name == 'angelone'
        assert adapter.credentials == angelone_credentials
        assert adapter.contract_manager == mock_contract_manager

    def test_create_adapter_case_insensitive(self, zerodha_credentials):
        """Test that broker name is case-insensitive."""
        adapter1 = create_adapter(zerodha_credentials, broker='ZERODHA')
        adapter2 = create_adapter(zerodha_credentials, broker='Zerodha')
        adapter3 = create_adapter(zerodha_credentials, broker='zerodha')

        assert isinstance(adapter1, ZerodhaAdapter)
        assert isinstance(adapter2, ZerodhaAdapter)
        assert isinstance(adapter3, ZerodhaAdapter)

    def test_create_adapter_unknown_broker(self, zerodha_credentials):
        """Test error handling for unknown broker."""
        with pytest.raises(ValueError) as exc_info:
            create_adapter(zerodha_credentials, broker='unknown_broker')

        assert 'Unknown broker' in str(exc_info.value)
        assert 'unknown_broker' in str(exc_info.value)

    def test_create_adapter_without_contract_manager(self, zerodha_credentials):
        """Test creating adapter without ContractManager."""
        adapter = create_adapter(zerodha_credentials, broker='zerodha')

        assert isinstance(adapter, ZerodhaAdapter)
        assert adapter.contract_manager is None


class TestBrokerAutoDetection:
    """Test automatic broker detection from credentials."""

    def test_detect_zerodha_credentials(self, zerodha_credentials):
        """Test detecting Zerodha from credentials."""
        detected = _detect_broker(zerodha_credentials)
        assert detected == 'zerodha'

    def test_detect_angelone_credentials(self, angelone_credentials):
        """Test detecting AngelOne from credentials."""
        detected = _detect_broker(angelone_credentials)
        assert detected == 'angelone'

    def test_detect_zerodha_with_api_secret(self):
        """Test Zerodha detection based on api_secret field."""
        credentials = {
            'api_key': 'test_key',
            'api_secret': 'test_secret'  # Unique to Zerodha
        }
        detected = _detect_broker(credentials)
        assert detected == 'zerodha'

    def test_detect_angelone_with_username(self):
        """Test AngelOne detection based on username field."""
        credentials = {
            'api_key': 'test_key',
            'username': 'A123456'  # Unique to AngelOne
        }
        detected = _detect_broker(credentials)
        assert detected == 'angelone'

    def test_detect_broker_empty_credentials(self):
        """Test detection fails with empty credentials."""
        with pytest.raises(ValueError) as exc_info:
            _detect_broker({})

        assert 'No credentials provided' in str(exc_info.value)

    def test_detect_broker_ambiguous_credentials(self):
        """Test detection fails with ambiguous credentials."""
        credentials = {
            'api_key': 'test_key'
            # Missing unique fields for both brokers
        }

        with pytest.raises(ValueError) as exc_info:
            _detect_broker(credentials)

        assert 'Could not detect broker type' in str(exc_info.value)

    def test_auto_detect_zerodha_on_create(self, zerodha_credentials, mock_contract_manager):
        """Test auto-detection during adapter creation (Zerodha)."""
        # Don't specify broker - let factory auto-detect
        adapter = create_adapter(
            credentials=zerodha_credentials,
            contract_manager=mock_contract_manager
        )

        assert isinstance(adapter, ZerodhaAdapter)
        assert adapter.broker_name == 'zerodha'

    def test_auto_detect_angelone_on_create(self, angelone_credentials, mock_contract_manager):
        """Test auto-detection during adapter creation (AngelOne)."""
        adapter = create_adapter(
            credentials=angelone_credentials,
            contract_manager=mock_contract_manager
        )

        assert isinstance(adapter, AngelOneAdapter)
        assert adapter.broker_name == 'angelone'


class TestBrokerRegistry:
    """Test broker registry management."""

    def test_get_available_brokers(self):
        """Test getting list of available brokers."""
        brokers = get_available_brokers()

        assert isinstance(brokers, list)
        assert 'zerodha' in brokers
        assert 'angelone' in brokers
        assert len(brokers) >= 2

    def test_register_custom_adapter(self):
        """Test registering a custom adapter."""
        class CustomBrokerAdapter(BrokerAdapter):
            @property
            def broker_name(self):
                return "custom"

            def connect(self):
                return True

            def disconnect(self):
                pass

            def get_ltp(self, underlying, option_type, strike, expiry):
                return 100.0

            def get_quote(self, underlying, option_type, strike, expiry):
                pass

            def get_quotes(self, instruments):
                return {}

            def get_option_chain(self, underlying, expiry, strikes):
                import pandas as pd
                return pd.DataFrame()

            def get_spot_price(self, underlying="NIFTY"):
                return 23000.0

            def place_order(self, order):
                pass

            def modify_order(self, order_id, changes):
                pass

            def cancel_order(self, order_id):
                pass

            def get_order(self, order_id):
                pass

            def get_orders(self):
                return []

            def get_positions(self):
                return []

            def get_holdings(self):
                return []

            def get_funds(self):
                pass

            def is_market_open(self):
                return True

            def load_instruments(self):
                return True

            def logout(self):
                pass

        # Register custom adapter
        register_adapter('custom', CustomBrokerAdapter)

        # Verify it's in the registry
        brokers = get_available_brokers()
        assert 'custom' in brokers

        # Create instance of custom adapter
        credentials = {'api_key': 'test'}
        adapter = create_adapter(credentials, broker='custom')

        assert isinstance(adapter, CustomBrokerAdapter)
        assert adapter.broker_name == 'custom'

    def test_register_invalid_adapter_type(self):
        """Test registering non-BrokerAdapter class fails."""
        class NotAnAdapter:
            pass

        with pytest.raises(TypeError) as exc_info:
            register_adapter('invalid', NotAnAdapter)

        assert 'must inherit from BrokerAdapter' in str(exc_info.value)

    def test_register_adapter_case_normalization(self):
        """Test adapter names are normalized to lowercase."""
        class TestAdapter(BrokerAdapter):
            @property
            def broker_name(self):
                return "test"

            # Implement all abstract methods minimally
            def connect(self):
                return True

            def disconnect(self):
                pass

            def get_ltp(self, underlying, option_type, strike, expiry):
                pass

            def get_quote(self, underlying, option_type, strike, expiry):
                pass

            def get_quotes(self, instruments):
                return {}

            def get_option_chain(self, underlying, expiry, strikes):
                import pandas as pd
                return pd.DataFrame()

            def get_spot_price(self, underlying="NIFTY"):
                pass

            def place_order(self, order):
                pass

            def modify_order(self, order_id, changes):
                pass

            def cancel_order(self, order_id):
                pass

            def get_order(self, order_id):
                pass

            def get_orders(self):
                return []

            def get_positions(self):
                return []

            def get_holdings(self):
                return []

            def get_funds(self):
                pass

            def is_market_open(self):
                return True

            def load_instruments(self):
                return True

            def logout(self):
                pass

        # Register with mixed case
        register_adapter('TestBroker', TestAdapter)

        # Should be accessible with any case
        brokers = get_available_brokers()
        assert 'testbroker' in brokers

        # Creation should work with any case
        credentials = {'api_key': 'test'}
        adapter = create_adapter(credentials, broker='TESTBROKER')
        assert isinstance(adapter, TestAdapter)


class TestFactoryIntegration:
    """Integration tests for factory with real adapters."""

    def test_factory_preserves_contract_manager(self, zerodha_credentials, mock_contract_manager):
        """Test that factory properly passes ContractManager to adapter."""
        adapter = create_adapter(
            zerodha_credentials,
            broker='zerodha',
            contract_manager=mock_contract_manager
        )

        assert adapter.contract_manager is mock_contract_manager

        # Verify adapter can use it
        expiry = adapter.get_next_expiry()
        assert expiry is not None
        mock_contract_manager.get_options_expiry.assert_called()

    def test_multiple_adapter_creation_independence(
        self, zerodha_credentials, angelone_credentials, mock_contract_manager
    ):
        """Test creating multiple adapters doesn't interfere."""
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

        # Both should be independent instances
        assert isinstance(zerodha_adapter, ZerodhaAdapter)
        assert isinstance(angelone_adapter, AngelOneAdapter)
        assert zerodha_adapter is not angelone_adapter
        assert zerodha_adapter.broker_name == 'zerodha'
        assert angelone_adapter.broker_name == 'angelone'
