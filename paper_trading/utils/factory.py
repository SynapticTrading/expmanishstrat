"""
Broker Factory - Creates appropriate broker instance based on credentials
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from paper_trading.brokers.zerodha import ZerodhaBroker
from paper_trading.brokers.angelone import AngelOneBroker


class BrokerFactory:
    """Factory to create broker instances"""

    @staticmethod
    def create_broker(credentials, broker_type=None):
        """
        Create broker instance based on credentials

        Args:
            credentials: Dict with broker credentials
            broker_type: 'zerodha' or 'angelone' (auto-detected if None)

        Returns:
            BrokerInterface: Broker instance

        Raises:
            ValueError: If broker type cannot be determined
        """

        # Auto-detect broker type from credentials
        if broker_type is None:
            broker_type = BrokerFactory._detect_broker_type(credentials)

        if broker_type == 'zerodha':
            return BrokerFactory._create_zerodha(credentials)
        elif broker_type == 'angelone':
            return BrokerFactory._create_angelone(credentials)
        else:
            raise ValueError(f"Unknown broker type: {broker_type}")

    @staticmethod
    def _detect_broker_type(credentials):
        """
        Auto-detect broker type from credentials

        Args:
            credentials: Dict with credentials

        Returns:
            str: 'zerodha' or 'angelone'
        """
        # Zerodha has: api_key, api_secret, user_id, user_password, totp_key
        # AngelOne has: api_key, username, password, totp_token

        has_api_secret = 'api_secret' in credentials
        has_username = 'username' in credentials
        has_user_id = 'user_id' in credentials

        if has_api_secret and has_user_id:
            return 'zerodha'
        elif has_username:
            return 'angelone'
        else:
            raise ValueError("Cannot determine broker type from credentials")

    @staticmethod
    def _create_zerodha(credentials):
        """
        Create Zerodha broker instance

        Args:
            credentials: Zerodha credentials dict

        Returns:
            ZerodhaBroker: Zerodha broker instance
        """
        required_keys = ['api_key', 'api_secret', 'user_id', 'user_password', 'totp_key']
        missing_keys = [key for key in required_keys if key not in credentials]

        if missing_keys:
            raise ValueError(f"Missing Zerodha credentials: {missing_keys}")

        return ZerodhaBroker(
            api_key=credentials['api_key'],
            api_secret=credentials['api_secret'],
            user_id=credentials['user_id'],
            user_password=credentials['user_password'],
            totp_key=credentials['totp_key']
        )

    @staticmethod
    def _create_angelone(credentials):
        """
        Create AngelOne broker instance

        Args:
            credentials: AngelOne credentials dict

        Returns:
            AngelOneBroker: AngelOne broker instance
        """
        required_keys = ['api_key', 'username', 'password', 'totp_token']
        missing_keys = [key for key in required_keys if key not in credentials]

        if missing_keys:
            raise ValueError(f"Missing AngelOne credentials: {missing_keys}")

        return AngelOneBroker(
            api_key=credentials['api_key'],
            username=credentials['username'],
            password=credentials['password'],
            totp_token=credentials['totp_token']
        )


# Helper function for easy import
def create_broker(credentials, broker_type=None):
    """
    Convenience function to create broker

    Args:
        credentials: Broker credentials dict
        broker_type: 'zerodha' or 'angelone' (auto-detected if None)

    Returns:
        BrokerInterface: Broker instance
    """
    return BrokerFactory.create_broker(credentials, broker_type)
