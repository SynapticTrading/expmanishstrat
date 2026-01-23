"""
Tests for base BrokerAdapter class.

Tests the abstract base class functionality including:
- Instrument resolution using ContractManager
- Token-based lookups
- Base interface methods
"""

import pytest
from unittest.mock import Mock, patch
from paper_trading.brokers.adapter.base import BrokerAdapter
from paper_trading.brokers.adapter.types import (
    OrderRequest, OrderResponse, Quote, Position, Funds, OrderStatus
)


class ConcreteBrokerAdapter(BrokerAdapter):
    """Concrete implementation for testing abstract base class."""

    @property
    def broker_name(self) -> str:
        return "test_broker"

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def get_ltp(self, underlying, option_type, strike, expiry):
        return 150.50

    def get_quote(self, underlying, option_type, strike, expiry):
        return Quote(ltp=150.50)

    def get_quotes(self, instruments):
        return {}

    def get_option_chain(self, underlying, expiry, strikes):
        import pandas as pd
        return pd.DataFrame()

    def get_spot_price(self, underlying="NIFTY"):
        return 23456.75

    def place_order(self, order):
        return OrderResponse(
            success=True,
            order_id="TEST123",
            status=OrderStatus.PENDING
        )

    def modify_order(self, order_id, changes):
        return OrderResponse(
            success=True,
            order_id=order_id,
            status=OrderStatus.PENDING
        )

    def cancel_order(self, order_id):
        return OrderResponse(
            success=True,
            order_id=order_id,
            status=OrderStatus.CANCELLED
        )

    def get_order(self, order_id):
        return OrderResponse(
            success=True,
            order_id=order_id,
            status=OrderStatus.COMPLETE
        )

    def get_orders(self):
        return []

    def get_positions(self):
        return []

    def get_holdings(self):
        return []

    def get_funds(self):
        return Funds(
            available_cash=50000,
            used_margin=20000,
            available_margin=100000
        )

    def is_market_open(self):
        return True

    def load_instruments(self):
        return True

    def logout(self):
        self.disconnect()


class TestBrokerAdapterBase:
    """Test base adapter functionality."""

    def test_adapter_initialization(self):
        """Test adapter initialization."""
        credentials = {'api_key': 'test123'}
        adapter = ConcreteBrokerAdapter(credentials)

        assert adapter.credentials == credentials
        assert adapter._connected is False
        assert adapter.contract_manager is None

    def test_adapter_with_contract_manager(self, mock_contract_manager):
        """Test adapter initialization with ContractManager."""
        credentials = {'api_key': 'test123'}
        adapter = ConcreteBrokerAdapter(credentials, mock_contract_manager)

        assert adapter.contract_manager is not None
        assert adapter.contract_manager == mock_contract_manager

    def test_connection_lifecycle(self):
        """Test connect, is_connected, disconnect."""
        adapter = ConcreteBrokerAdapter({'api_key': 'test'})

        assert not adapter.is_connected()

        adapter.connect()
        assert adapter.is_connected()

        adapter.disconnect()
        assert not adapter.is_connected()

    def test_broker_name_property(self):
        """Test broker_name property."""
        adapter = ConcreteBrokerAdapter({'api_key': 'test'})
        assert adapter.broker_name == "test_broker"


class TestInstrumentResolution:
    """Test instrument resolution methods using ContractManager."""

    def test_resolve_instrument_ce_option(self, mock_contract_manager, sample_option_contract):
        """Test resolving CE option using ContractManager."""
        adapter = ConcreteBrokerAdapter({'api_key': 'test'}, mock_contract_manager)

        contract = adapter._resolve_instrument(
            underlying='NIFTY',
            option_type='CE',
            strike=sample_option_contract['strike'],
            expiry=sample_option_contract['expiry']
        )

        assert contract is not None
        assert contract['strike'] == sample_option_contract['strike']
        assert contract['option_type'] == 'CE'
        mock_contract_manager.get_option_contract.assert_called_once()

    def test_resolve_instrument_pe_option(self, mock_contract_manager, sample_pe_contract):
        """Test resolving PE option using ContractManager."""
        adapter = ConcreteBrokerAdapter({'api_key': 'test'}, mock_contract_manager)

        contract = adapter._resolve_instrument(
            underlying='NIFTY',
            option_type='PE',
            strike=sample_pe_contract['strike'],
            expiry=sample_pe_contract['expiry']
        )

        assert contract is not None
        assert contract['strike'] == sample_pe_contract['strike']
        assert contract['option_type'] == 'PE'

    def test_resolve_instrument_no_contract_manager(self):
        """Test resolution fails gracefully without ContractManager."""
        adapter = ConcreteBrokerAdapter({'api_key': 'test'})

        contract = adapter._resolve_instrument(
            underlying='NIFTY',
            option_type='CE',
            strike=25000,
            expiry='2026-02-26'
        )

        assert contract is None

    def test_resolve_instrument_not_found(self, mock_contract_manager):
        """Test resolution when contract not found."""
        adapter = ConcreteBrokerAdapter({'api_key': 'test'}, mock_contract_manager)

        # Use strike that doesn't exist in mock
        contract = adapter._resolve_instrument(
            underlying='NIFTY',
            option_type='CE',
            strike=99999,  # Invalid strike
            expiry='2026-02-26'
        )

        assert contract is None

    def test_get_instrument_key_with_token(self, mock_contract_manager, sample_option_contract):
        """Test getting instrument key (token preferred)."""
        adapter = ConcreteBrokerAdapter({'api_key': 'test'}, mock_contract_manager)

        key = adapter._get_instrument_key(
            underlying='NIFTY',
            option_type='CE',
            strike=sample_option_contract['strike'],
            expiry=sample_option_contract['expiry']
        )

        assert key is not None
        # Should return token (preferred) or symbol as fallback
        assert key == sample_option_contract.get('token') or key == sample_option_contract.get('symbol')

    def test_get_instrument_key_not_found(self, mock_contract_manager):
        """Test getting instrument key when contract not found."""
        adapter = ConcreteBrokerAdapter({'api_key': 'test'}, mock_contract_manager)

        key = adapter._get_instrument_key(
            underlying='NIFTY',
            option_type='CE',
            strike=99999,
            expiry='2026-02-26'
        )

        assert key is None


class TestExpiryMethods:
    """Test expiry-related methods."""

    def test_get_next_expiry_with_contract_manager(self, mock_contract_manager):
        """Test getting next expiry using ContractManager."""
        adapter = ConcreteBrokerAdapter({'api_key': 'test'}, mock_contract_manager)

        expiry = adapter.get_next_expiry()

        assert expiry is not None
        assert expiry == '2026-02-26'
        mock_contract_manager.get_options_expiry.assert_called_once_with('current_week')

    def test_get_next_expiry_without_contract_manager(self):
        """Test getting next expiry without ContractManager."""
        adapter = ConcreteBrokerAdapter({'api_key': 'test'})

        expiry = adapter.get_next_expiry()

        # Should return None without contract manager
        assert expiry is None


class TestWaitForNextCandle:
    """Test wait_for_next_candle utility method."""

    @patch('time.sleep')
    @patch('paper_trading.brokers.adapter.base.datetime')
    def test_wait_for_next_candle_5min(self, mock_datetime, mock_sleep):
        """Test waiting for next 5-minute candle."""
        from datetime import datetime, timedelta

        # Mock current time as 9:12:30 (2 min 30 sec past 9:10 candle)
        mock_now = datetime(2026, 2, 26, 9, 12, 30)
        mock_datetime.now.return_value = mock_now
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        adapter = ConcreteBrokerAdapter({'api_key': 'test'})
        adapter.wait_for_next_candle(interval_minutes=5)

        # Should wait until 9:15:00 (next 5-min boundary)
        # That's 2 min 30 sec = 150 seconds
        assert mock_sleep.called
        wait_seconds = mock_sleep.call_args[0][0]
        assert 149 <= wait_seconds <= 151  # Allow small tolerance

    @patch('time.sleep')
    @patch('paper_trading.brokers.adapter.base.datetime')
    def test_wait_for_next_candle_exact_boundary(self, mock_datetime, mock_sleep):
        """Test waiting when exactly on candle boundary."""
        from datetime import datetime

        # Mock current time as exactly 9:15:00
        mock_now = datetime(2026, 2, 26, 9, 15, 0)
        mock_datetime.now.return_value = mock_now
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        adapter = ConcreteBrokerAdapter({'api_key': 'test'})
        adapter.wait_for_next_candle(interval_minutes=5)

        # Should wait full interval (5 minutes = 300 seconds)
        assert mock_sleep.called
        wait_seconds = mock_sleep.call_args[0][0]
        assert 299 <= wait_seconds <= 301
