"""
Pytest configuration and shared fixtures for adapter tests.

Provides mock objects and test data from contracts_cache.json
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock
from datetime import datetime, date


@pytest.fixture
def contracts_cache():
    """Load contracts_cache.json for testing."""
    cache_path = Path(__file__).parent.parent.parent / "contracts_cache.json"

    if not cache_path.exists():
        pytest.skip("contracts_cache.json not found - run refresh_contracts.py first")

    with open(cache_path, 'r') as f:
        return json.load(f)


@pytest.fixture
def sample_option_contract(contracts_cache):
    """Get a sample option contract from cache."""
    # Get first available CE contract from current_week
    if 'options' in contracts_cache and 'mapping' in contracts_cache['options']:
        current_week = contracts_cache['options']['mapping'].get('current_week', {})
        ce_contracts = current_week.get('CE', [])
        if ce_contracts and len(ce_contracts) > 0:
            return ce_contracts[0]

    # Fallback: create sample contract
    return {
        'symbol': 'NIFTY26FEB25000CE',
        'token': '12345678',
        'zerodha_instrument_token': 12345678,
        'strike': 25000,
        'option_type': 'CE',
        'expiry': '2026-02-26',
        'lot_size': 65
    }


@pytest.fixture
def sample_pe_contract(contracts_cache):
    """Get a sample PE contract from cache."""
    if 'options' in contracts_cache and 'mapping' in contracts_cache['options']:
        current_week = contracts_cache['options']['mapping'].get('current_week', {})
        pe_contracts = current_week.get('PE', [])
        if pe_contracts and len(pe_contracts) > 0:
            return pe_contracts[0]

    return {
        'symbol': 'NIFTY26FEB24500PE',
        'token': '87654321',
        'zerodha_instrument_token': 87654321,
        'strike': 24500,
        'option_type': 'PE',
        'expiry': '2026-02-26',
        'lot_size': 65
    }


@pytest.fixture
def mock_contract_manager(sample_option_contract, sample_pe_contract):
    """Mock ContractManager for testing."""
    mock_cm = Mock()

    # Mock get_option_contract method
    def get_option_contract(expiry, strike, option_type):
        if option_type == 'CE' and strike == sample_option_contract['strike']:
            return sample_option_contract
        elif option_type == 'PE' and strike == sample_pe_contract['strike']:
            return sample_pe_contract
        return None

    mock_cm.get_option_contract = Mock(side_effect=get_option_contract)
    mock_cm.get_options_expiry = Mock(return_value='2026-02-26')
    mock_cm.has_instrument_tokens = Mock(return_value=True)

    return mock_cm


@pytest.fixture
def zerodha_credentials():
    """Sample Zerodha credentials for testing."""
    return {
        'api_key': 'test_zerodha_key',
        'api_secret': 'test_zerodha_secret',
        'user_id': 'TEST01',
        'user_password': 'password',
        'totp_key': 'TOTPKEY123456'
    }


@pytest.fixture
def angelone_credentials():
    """Sample AngelOne credentials for testing."""
    return {
        'api_key': 'test_angelone_key',
        'username': 'A123456',
        'password': 'password',
        'totp_token': 'TOTPTOKEN123'
    }


@pytest.fixture
def mock_kite_api():
    """Mock Zerodha Kite API."""
    mock = MagicMock()

    # Mock LTP response
    mock.ltp.return_value = {
        'NFO:12345678': {'last_price': 150.50}
    }

    # Mock quote response
    mock.quote.return_value = {
        'NFO:12345678': {
            'last_price': 150.50,
            'ohlc': {'open': 145.0, 'high': 155.0, 'low': 144.0, 'close': 148.0},
            'volume': 10000,
            'oi': 50000,
            'depth': {
                'buy': [{'price': 150.0, 'quantity': 100}],
                'sell': [{'price': 151.0, 'quantity': 100}]
            },
            'change': 2.5
        }
    }

    # Mock place_order response
    mock.place_order.return_value = '230125000123456'

    # Mock orders response
    mock.orders.return_value = [
        {
            'order_id': '230125000123456',
            'status': 'COMPLETE',
            'filled_quantity': 65,
            'average_price': 150.25,
            'status_message': 'Order executed'
        }
    ]

    # Mock positions response
    mock.positions.return_value = {
        'day': [
            {
                'tradingsymbol': 'NIFTY26FEB25000CE',
                'quantity': 65,
                'average_price': 150.0,
                'last_price': 155.0,
                'pnl': 325.0,
                'exchange': 'NFO',
                'product': 'MIS'
            }
        ]
    }

    # Mock margins response
    mock.margins.return_value = {
        'equity': {
            'available': {'cash': 50000, 'live_balance': 100000},
            'utilised': {'debits': 20000},
            'net': 80000
        }
    }

    return mock


@pytest.fixture
def mock_angelone_api():
    """Mock AngelOne SmartAPI."""
    mock = MagicMock()

    # Mock getMarketData (LTP mode)
    def market_data_ltp(*args, **kwargs):
        return {
            'status': True,
            'data': {
                'fetched': [
                    {'ltp': 150.50}
                ]
            }
        }

    # Mock getMarketData (FULL mode)
    def market_data_full(*args, **kwargs):
        return {
            'status': True,
            'data': {
                'fetched': [
                    {
                        'symbolToken': '12345678',
                        'ltp': 150.50,
                        'open': 145.0,
                        'high': 155.0,
                        'low': 144.0,
                        'close': 148.0,
                        'tradeVolume': 10000,
                        'opnInterest': 50000,
                        'totBuyQuan': 5000,
                        'totSellQuan': 4500
                    }
                ]
            }
        }

    mock.getMarketData = Mock(side_effect=lambda mode, **kwargs:
        market_data_ltp() if mode == "LTP" else market_data_full())

    # Mock ltpData (for spot price)
    mock.ltpData.return_value = {
        'status': True,
        'data': {'ltp': 23456.75}
    }

    # Mock placeOrder
    mock.placeOrder.return_value = {
        'status': True,
        'data': {'orderid': 'AO123456789'}
    }

    # Mock orderBook
    mock.orderBook.return_value = {
        'status': True,
        'data': [
            {
                'orderid': 'AO123456789',
                'orderstatus': 'complete',
                'filledshares': 65,
                'averageprice': 150.25,
                'text': 'Order executed successfully'
            }
        ]
    }

    # Mock position
    mock.position.return_value = {
        'status': True,
        'data': [
            {
                'tradingsymbol': 'NIFTY26FEB25000CE',
                'netqty': 65,
                'netprice': 150.0,
                'ltp': 155.0,
                'unrealised': 325.0,
                'exchange': 'NFO',
                'producttype': 'INTRADAY',
                'symboltoken': '12345678'
            }
        ]
    }

    # Mock rmsLimit
    mock.rmsLimit.return_value = {
        'status': True,
        'data': {
            'availablecash': 50000,
            'utiliseddebits': 20000,
            'availablelimitmargin': 100000,
            'net': 80000
        }
    }

    return mock


@pytest.fixture
def sample_order_request():
    """Sample OrderRequest for testing."""
    from paper_trading.brokers.adapter.types import (
        OrderRequest, Exchange, TransactionType, OrderType, ProductType
    )

    return OrderRequest(
        underlying='NIFTY',
        option_type='CE',
        strike=25000,
        expiry='2026-02-26',
        exchange=Exchange.NFO,
        transaction_type=TransactionType.BUY,
        order_type=OrderType.MARKET,
        quantity=65,
        product_type=ProductType.INTRADAY
    )
