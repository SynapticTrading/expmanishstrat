"""
Broker Interface - Base class for all broker implementations
"""

from abc import ABC, abstractmethod


class BrokerInterface(ABC):
    """Abstract base class for broker implementations"""

    @abstractmethod
    def connect(self):
        """
        Connect to broker API

        Returns:
            bool: True if connected successfully
        """
        pass

    @abstractmethod
    def get_spot_price(self, symbol="NIFTY 50"):
        """
        Get current spot price

        Args:
            symbol: Symbol name

        Returns:
            float: Current price
        """
        pass

    @abstractmethod
    def get_ltp(self, instrument_token):
        """
        Get Last Traded Price

        Args:
            instrument_token: Instrument identifier

        Returns:
            float: LTP
        """
        pass

    @abstractmethod
    def get_quote(self, instrument_token):
        """
        Get full quote

        Args:
            instrument_token: Instrument identifier

        Returns:
            dict: Quote data with OHLC, volume, OI
        """
        pass

    @abstractmethod
    def get_historical_data(self, instrument_token, from_date, to_date, interval="5minute"):
        """
        Get historical candle data

        Args:
            instrument_token: Instrument identifier
            from_date: Start date
            to_date: End date
            interval: Candle interval

        Returns:
            DataFrame: Historical data
        """
        pass

    @abstractmethod
    def get_instruments(self, exchange="NFO"):
        """
        Get instrument list

        Args:
            exchange: Exchange name

        Returns:
            DataFrame: Instrument list
        """
        pass

    @abstractmethod
    def get_options_chain(self, expiry, strikes):
        """
        Get options chain data

        Args:
            expiry: Expiry date
            strikes: List of strikes

        Returns:
            DataFrame: Options data
        """
        pass

    @abstractmethod
    def logout(self):
        """Logout from broker"""
        pass

    @property
    @abstractmethod
    def name(self):
        """Broker name"""
        pass
