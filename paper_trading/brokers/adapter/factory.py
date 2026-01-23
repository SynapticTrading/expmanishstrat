"""
Broker Adapter Factory

Creates broker adapter instances based on configuration.
Supports auto-detection of broker type from credentials.
"""

from typing import Dict, Type
import logging

from .base import BrokerAdapter

logger = logging.getLogger(__name__)

# Registry of available broker adapters
# Populated lazily to avoid circular imports
_BROKER_REGISTRY: Dict[str, Type[BrokerAdapter]] = {}


def _register_adapters():
    """Register available broker adapters."""
    global _BROKER_REGISTRY

    if _BROKER_REGISTRY:
        return  # Already registered

    # Import adapters here to avoid circular imports
    from .plugins.zerodha import ZerodhaAdapter
    from .plugins.angelone import AngelOneAdapter

    _BROKER_REGISTRY = {
        'zerodha': ZerodhaAdapter,
        'angelone': AngelOneAdapter
    }


def create_adapter(credentials: dict, broker: str = None,
                   contract_manager=None) -> BrokerAdapter:
    """
    Create a broker adapter instance.

    Args:
        credentials: Broker credentials dict
        broker: Broker name ('zerodha', 'angelone', 'paper')
                If None, auto-detected from credentials
        contract_manager: ContractManager for instrument resolution

    Returns:
        BrokerAdapter: Configured adapter instance

    Raises:
        ValueError: If broker type is unknown or cannot be detected
    """
    _register_adapters()

    # Auto-detect broker if not specified
    if broker is None:
        broker = _detect_broker(credentials)
        logger.info(f"Auto-detected broker: {broker}")

    broker = broker.lower()

    if broker not in _BROKER_REGISTRY:
        raise ValueError(
            f"Unknown broker: {broker}. "
            f"Available: {list(_BROKER_REGISTRY.keys())}"
        )

    adapter_class = _BROKER_REGISTRY[broker]
    adapter = adapter_class(credentials, contract_manager)

    logger.info(f"Created {broker} adapter")
    return adapter


def _detect_broker(credentials: dict) -> str:
    """
    Auto-detect broker type from credentials.

    Detection heuristics:
    - Zerodha: has 'api_secret' field
    - AngelOne: has 'username' (client code) field

    Args:
        credentials: Credentials dict

    Returns:
        str: Detected broker name

    Raises:
        ValueError: If broker type cannot be detected
    """
    if not credentials:
        raise ValueError("No credentials provided - cannot detect broker type")

    # Zerodha has api_key + api_secret
    if 'api_secret' in credentials:
        return 'zerodha'

    # AngelOne has username (client code) + api_key
    if 'username' in credentials and 'api_key' in credentials:
        return 'angelone'

    raise ValueError(
        "Could not detect broker type from credentials. "
        "Please specify broker explicitly: broker='zerodha' or broker='angelone'"
    )


def get_available_brokers() -> list:
    """
    Get list of available broker adapters.

    Returns:
        list: Broker names
    """
    _register_adapters()
    return list(_BROKER_REGISTRY.keys())


def register_adapter(name: str, adapter_class: Type[BrokerAdapter]):
    """
    Register a custom broker adapter.

    Args:
        name: Broker name
        adapter_class: Adapter class (must inherit from BrokerAdapter)
    """
    _register_adapters()

    if not issubclass(adapter_class, BrokerAdapter):
        raise TypeError(f"{adapter_class} must inherit from BrokerAdapter")

    _BROKER_REGISTRY[name.lower()] = adapter_class
    logger.info(f"Registered custom adapter: {name}")
