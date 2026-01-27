"""
Pytest Configuration for Integration Tests

Provides real broker connections and fixtures for integration testing.
"""

import pytest
import yaml
from pathlib import Path
from datetime import datetime, time
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def test_config():
    """Load test configuration from YAML file."""
    config_file = Path(__file__).parent / "test_credentials.yaml"
    
    if not config_file.exists():
        pytest.skip(
            f"Integration test credentials not found at {config_file}. "
            f"Copy test_credentials.yaml.template and fill in your credentials."
        )
    
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    logger.info("Loaded integration test configuration")
    return config


@pytest.fixture(scope="session")
def zerodha_credentials(test_config):
    """Get Zerodha credentials from config."""
    return test_config['zerodha']


@pytest.fixture(scope="session")
def angelone_credentials(test_config):
    """Get AngelOne credentials from config."""
    return test_config['angelone']


@pytest.fixture(scope="session")
def test_settings(test_config):
    """Get test configuration settings."""
    return test_config['test_config']


# ══════════════════════════════════════════════════════════════════════════════
# CONTRACT MANAGER
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def contract_manager():
    """Real ContractManager instance."""
    from paper_trading.core.contract_manager import ContractManager
    
    # Initialize contract manager
    manager = ContractManager()
    
    # Load contracts if not already loaded
    if not manager.has_instrument_tokens():
        logger.info("Loading instrument tokens...")
        manager.refresh_contracts()
    
    logger.info("Contract manager initialized")
    return manager


# ══════════════════════════════════════════════════════════════════════════════
# BROKER ADAPTERS
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def zerodha_adapter(zerodha_credentials, contract_manager):
    """
    Real Zerodha adapter with connection.
    Session scope - shared connection across all tests (avoids rate limiting).
    """
    from paper_trading.brokers.adapter.plugins.zerodha import ZerodhaAdapter
    
    logger.info("Creating Zerodha adapter...")
    adapter = ZerodhaAdapter(zerodha_credentials, contract_manager)
    
    # Connect
    success = adapter.connect()
    if not success:
        pytest.fail("Failed to connect to Zerodha API")
    
    logger.info("✓ Connected to Zerodha")
    
    yield adapter
    
    # Cleanup
    logger.info("Disconnecting from Zerodha...")
    adapter.disconnect()


@pytest.fixture(scope="session")
def angelone_adapter(angelone_credentials, contract_manager):
    """
    Real AngelOne adapter with connection.
    Session scope - shared connection across all tests (avoids rate limiting).
    """
    from paper_trading.brokers.adapter.plugins.angelone import AngelOneAdapter
    
    logger.info("Creating AngelOne adapter...")
    adapter = AngelOneAdapter(angelone_credentials, contract_manager)
    
    # Connect
    success = adapter.connect()
    if not success:
        pytest.fail("Failed to connect to AngelOne API")
    
    logger.info("✓ Connected to AngelOne")
    
    yield adapter
    
    # Cleanup
    logger.info("Disconnecting from AngelOne...")
    adapter.disconnect()


# ══════════════════════════════════════════════════════════════════════════════
# MARKET CHECKS
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="function")
def skip_if_market_open(test_settings):
    """Skip test if market is currently open (for AMO tests)."""
    if test_settings.get('skip_live_orders', True):
        now = datetime.now().time()
        market_open = time(9, 15)
        market_close = time(15, 30)
        
        if market_open <= now <= market_close:
            pytest.skip("Skipping AMO test during market hours for safety")


@pytest.fixture(scope="function")
def require_market_open():
    """Skip test if market is closed (for live data tests)."""
    now = datetime.now().time()
    market_open = time(9, 15)
    market_close = time(15, 30)
    
    if not (market_open <= now <= market_close):
        pytest.skip("Test requires market to be open")


# ══════════════════════════════════════════════════════════════════════════════
# ORDER HELPERS
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def amo_order_helper(test_settings):
    """
    Helper for creating and managing AMO orders safely.
    Automatically tracks and cancels orders.
    """
    placed_orders = []
    
    class AMOOrderHelper:
        def __init__(self):
            self.orders = placed_orders
        
        def create_amo_request(self, adapter, underlying='NIFTY', option_type='CE',
                              strike=25000, quantity=65, order_type='MARKET'):  # 65 = NIFTY lot size
            """Create an AMO order request."""
            from paper_trading.brokers.adapter.types import (
                OrderRequest, OrderType, TransactionType, 
                Exchange, ProductType
            )
            from datetime import datetime, timedelta
            
            # Get next expiry (use current_week as default)
            expiry = adapter.contract_manager.get_options_expiry('current_week')
            
            order_request = OrderRequest(
                underlying=underlying,
                option_type=option_type,
                strike=strike,
                expiry=expiry,
                exchange=Exchange.NFO,
                transaction_type=TransactionType.BUY,
                order_type=OrderType[order_type],
                quantity=quantity,
                product_type=ProductType.INTRADAY,
                tag='integration_test_amo'
            )
            
            return order_request
        
        def place_and_track(self, adapter, order_request):
            """Place AMO order and track for cleanup."""
            response = adapter.place_order(order_request)
            if response.success:
                self.orders.append({
                    'adapter': adapter,
                    'order_id': response.order_id
                })
                logger.info(f"✓ Placed AMO order: {response.order_id}")
            return response
        
        def cleanup_all(self):
            """Cancel all tracked orders."""
            logger.info(f"Cleaning up {len(self.orders)} AMO orders...")
            for order_info in self.orders:
                try:
                    adapter = order_info['adapter']
                    order_id = order_info['order_id']
                    adapter.cancel_order(order_id)
                    logger.info(f"✓ Cancelled order: {order_id}")
                except Exception as e:
                    logger.warning(f"Failed to cancel order {order_id}: {e}")
            self.orders.clear()
    
    helper = AMOOrderHelper()
    yield helper
    
    # Auto-cleanup after test
    if test_settings.get('auto_cancel_orders', True):
        helper.cleanup_all()


# ══════════════════════════════════════════════════════════════════════════════
# TEST DATA
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def test_instruments(test_settings):
    """Common test instruments."""
    return {
        'underlying': test_settings.get('test_symbol', 'NIFTY'),
        'strike': test_settings.get('test_strike', 25000),
        'quantity': test_settings.get('test_quantity', 65)  # NIFTY lot size = 65
    }


# ══════════════════════════════════════════════════════════════════════════════
# HOOKS
# ══════════════════════════════════════════════════════════════════════════════

def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires real broker connection)"
    )
    config.addinivalue_line(
        "markers", "amo_order: mark test as AMO order test (safe for testing)"
    )
    config.addinivalue_line(
        "markers", "websocket: mark test as WebSocket test (requires market hours)"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow (may take longer)"
    )


def pytest_collection_modifyitems(config, items):
    """Add markers to tests automatically."""
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        
        if "websocket" in item.name:
            item.add_marker(pytest.mark.websocket)
        
        if "amo" in item.name or "order" in item.name:
            item.add_marker(pytest.mark.amo_order)
