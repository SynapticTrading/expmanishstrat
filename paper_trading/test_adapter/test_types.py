"""
Tests for adapter types and enums.

Tests the standard types that provide broker-agnostic interfaces.
"""

import pytest
from datetime import datetime
from paper_trading.brokers.adapter.types import (
    Exchange, TransactionType, OrderType, ProductType, OrderStatus, OptionType,
    OrderRequest, OrderResponse, Quote, Position, Funds, InstrumentInfo
)


class TestEnums:
    """Test enum definitions."""

    def test_exchange_enum(self):
        """Test Exchange enum values."""
        assert Exchange.NSE.value == "NSE"
        assert Exchange.NFO.value == "NFO"
        assert Exchange.BSE.value == "BSE"
        assert Exchange.MCX.value == "MCX"

    def test_transaction_type_enum(self):
        """Test TransactionType enum."""
        assert TransactionType.BUY.value == "BUY"
        assert TransactionType.SELL.value == "SELL"

    def test_order_type_enum(self):
        """Test OrderType enum."""
        assert OrderType.MARKET.value == "MARKET"
        assert OrderType.LIMIT.value == "LIMIT"
        assert OrderType.SL.value == "SL"
        assert OrderType.SL_M.value == "SL_M"

    def test_product_type_enum(self):
        """Test ProductType enum."""
        assert ProductType.INTRADAY.value == "INTRADAY"
        assert ProductType.DELIVERY.value == "DELIVERY"
        assert ProductType.CARRYFORWARD.value == "CARRYFORWARD"

    def test_order_status_enum(self):
        """Test OrderStatus enum."""
        assert OrderStatus.PENDING.value == "PENDING"
        assert OrderStatus.OPEN.value == "OPEN"
        assert OrderStatus.COMPLETE.value == "COMPLETE"
        assert OrderStatus.REJECTED.value == "REJECTED"
        assert OrderStatus.CANCELLED.value == "CANCELLED"
        assert OrderStatus.TRIGGER_PENDING.value == "TRIGGER_PENDING"

    def test_option_type_enum(self):
        """Test OptionType enum."""
        assert OptionType.CE.value == "CE"
        assert OptionType.PE.value == "PE"
        assert OptionType.FUT.value == "FUT"
        assert OptionType.EQ.value == "EQ"


class TestOrderRequest:
    """Test OrderRequest dataclass."""

    def test_market_order_creation(self):
        """Test creating a market order request."""
        order = OrderRequest(
            underlying='NIFTY',
            option_type='CE',
            strike=25000,
            expiry='2026-02-26',
            exchange=Exchange.NFO,
            transaction_type=TransactionType.BUY,
            order_type=OrderType.MARKET,
            quantity=65
        )

        assert order.underlying == 'NIFTY'
        assert order.option_type == 'CE'
        assert order.strike == 25000
        assert order.expiry == '2026-02-26'
        assert order.exchange == Exchange.NFO
        assert order.transaction_type == TransactionType.BUY
        assert order.order_type == OrderType.MARKET
        assert order.quantity == 65
        assert order.price is None
        assert order.trigger_price is None
        assert order.product_type == ProductType.INTRADAY  # Default

    def test_limit_order_creation(self):
        """Test creating a limit order request."""
        order = OrderRequest(
            underlying='BANKNIFTY',
            option_type='PE',
            strike=48000,
            expiry='2026-02-26',
            exchange=Exchange.NFO,
            transaction_type=TransactionType.SELL,
            order_type=OrderType.LIMIT,
            quantity=30,
            price=200.50,
            product_type=ProductType.CARRYFORWARD
        )

        assert order.order_type == OrderType.LIMIT
        assert order.price == 200.50
        assert order.product_type == ProductType.CARRYFORWARD

    def test_stop_loss_order_creation(self):
        """Test creating a stop-loss order."""
        order = OrderRequest(
            underlying='NIFTY',
            option_type='CE',
            strike=25000,
            expiry='2026-02-26',
            exchange=Exchange.NFO,
            transaction_type=TransactionType.SELL,
            order_type=OrderType.SL,
            quantity=65,
            price=100.0,
            trigger_price=105.0
        )

        assert order.order_type == OrderType.SL
        assert order.price == 100.0
        assert order.trigger_price == 105.0

    def test_order_with_tag(self):
        """Test order with custom tag."""
        order = OrderRequest(
            underlying='NIFTY',
            option_type='CE',
            strike=25000,
            expiry='2026-02-26',
            exchange=Exchange.NFO,
            transaction_type=TransactionType.BUY,
            order_type=OrderType.MARKET,
            quantity=65,
            tag='strategy_v1'
        )

        assert order.tag == 'strategy_v1'


class TestOrderResponse:
    """Test OrderResponse dataclass."""

    def test_successful_response(self):
        """Test successful order response."""
        response = OrderResponse(
            success=True,
            order_id='ORD123456',
            status=OrderStatus.COMPLETE,
            message='Order executed',
            filled_quantity=65,
            average_price=150.25,
            timestamp=datetime.now()
        )

        assert response.success is True
        assert response.order_id == 'ORD123456'
        assert response.status == OrderStatus.COMPLETE
        assert response.filled_quantity == 65
        assert response.average_price == 150.25

    def test_failed_response(self):
        """Test failed order response."""
        response = OrderResponse(
            success=False,
            order_id='',
            status=OrderStatus.REJECTED,
            message='Insufficient margin'
        )

        assert response.success is False
        assert response.status == OrderStatus.REJECTED
        assert 'margin' in response.message.lower()


class TestQuote:
    """Test Quote dataclass."""

    def test_quote_creation(self):
        """Test creating a quote object."""
        quote = Quote(
            ltp=150.50,
            open=145.0,
            high=155.0,
            low=144.0,
            close=148.0,
            volume=10000,
            oi=50000,
            bid=150.0,
            ask=151.0,
            bid_qty=100,
            ask_qty=100,
            change=2.5,
            change_pct=1.69
        )

        assert quote.ltp == 150.50
        assert quote.open == 145.0
        assert quote.high == 155.0
        assert quote.low == 144.0
        assert quote.volume == 10000
        assert quote.oi == 50000
        assert quote.bid == 150.0
        assert quote.ask == 151.0

    def test_minimal_quote(self):
        """Test quote with only LTP."""
        quote = Quote(ltp=150.50)

        assert quote.ltp == 150.50
        assert quote.volume == 0
        assert quote.oi == 0


class TestPosition:
    """Test Position dataclass."""

    def test_position_creation(self):
        """Test creating a position."""
        position = Position(
            underlying='NIFTY',
            option_type='CE',
            strike=25000,
            expiry='2026-02-26',
            exchange='NFO',
            quantity=65,
            avg_price=150.0,
            ltp=155.0,
            pnl=325.0,
            pnl_pct=2.17,
            product_type='INTRADAY',
            token='12345678',
            symbol='NIFTY26FEB25000CE'
        )

        assert position.underlying == 'NIFTY'
        assert position.option_type == 'CE'
        assert position.strike == 25000
        assert position.quantity == 65
        assert position.avg_price == 150.0
        assert position.ltp == 155.0
        assert position.pnl == 325.0

    def test_short_position(self):
        """Test short position (negative quantity)."""
        position = Position(
            underlying='NIFTY',
            option_type='PE',
            strike=24500,
            expiry='2026-02-26',
            exchange='NFO',
            quantity=-65,  # Short position
            avg_price=120.0,
            ltp=115.0,
            pnl=325.0  # Profit on short
        )

        assert position.quantity == -65
        assert position.pnl > 0  # Profit when price drops


class TestFunds:
    """Test Funds dataclass."""

    def test_funds_creation(self):
        """Test creating funds object."""
        funds = Funds(
            available_cash=50000,
            used_margin=20000,
            available_margin=100000,
            total_balance=80000,
            realized_pnl=5000
        )

        assert funds.available_cash == 50000
        assert funds.used_margin == 20000
        assert funds.available_margin == 100000
        assert funds.total_balance == 80000
        assert funds.realized_pnl == 5000


class TestInstrumentInfo:
    """Test InstrumentInfo dataclass."""

    def test_instrument_info_creation(self):
        """Test creating instrument info."""
        instrument = InstrumentInfo(
            token='12345678',
            symbol='NIFTY26FEB25000CE',
            underlying='NIFTY',
            option_type='CE',
            strike=25000,
            expiry='2026-02-26',
            exchange='NFO',
            lot_size=65,
            tick_size=0.05
        )

        assert instrument.token == '12345678'
        assert instrument.symbol == 'NIFTY26FEB25000CE'
        assert instrument.underlying == 'NIFTY'
        assert instrument.option_type == 'CE'
        assert instrument.strike == 25000
        assert instrument.lot_size == 65
        assert instrument.tick_size == 0.05
