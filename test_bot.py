"""
Unit tests for the trading bot.
Run with: pytest test_bot.py -v
"""
import pytest
import os
from datetime import date
from unittest.mock import Mock, MagicMock, patch

# Set test environment variables before importing config
os.environ['ALPACA_API_KEY'] = 'test_key'
os.environ['ALPACA_SECRET_KEY'] = 'test_secret'
os.environ['FINNHUB_API_KEY'] = 'test_finnhub'
os.environ['TELEGRAM_BOT_TOKEN'] = 'test_token'
os.environ['TELEGRAM_CHAT_ID'] = 'test_chat_id'
os.environ['DATABASE_PATH'] = ':memory:'  # Use in-memory database for tests

from config import Config, RiskConfig
from database import Database
from risk_manager import RiskManager
from analytics import Analytics


class TestConfig:
    """Test configuration module."""

    def test_config_loads_from_env(self):
        """Test that config loads from environment variables."""
        config = Config()
        assert config.alpaca.api_key == 'test_key'
        assert config.finnhub.api_key == 'test_finnhub'

    def test_risk_config_validation(self):
        """Test risk configuration validation."""
        # Valid config
        valid_config = RiskConfig(
            max_position_size_percent=60.0,
            max_daily_loss_percent=5.0,
            max_drawdown_percent=10.0,
            min_stock_price=5.0,
            max_stock_price=500.0,
            min_daily_volume=1000000
        )
        assert valid_config.validate() is True

        # Invalid config (negative value)
        invalid_config = RiskConfig(
            max_position_size_percent=-10.0,
            max_daily_loss_percent=5.0,
            max_drawdown_percent=10.0,
            min_stock_price=5.0,
            max_stock_price=500.0,
            min_daily_volume=1000000
        )
        assert invalid_config.validate() is False


class TestDatabase:
    """Test database module."""

    @pytest.fixture
    def db(self):
        """Create a test database."""
        database = Database(':memory:')
        yield database

    def test_database_initialization(self, db):
        """Test that database initializes with correct schema."""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='trades'"
            )
            assert cursor.fetchone() is not None

    def test_log_trade_entry(self, db):
        """Test logging a trade entry."""
        trade_id = db.log_trade_entry(
            ticker='AAPL',
            entry_price=150.0,
            quantity=10.0,
            score=0.05,
            avg_gain=0.08,
            avg_drawdown=-0.05,
            frequency=0.6,
            take_profit_price=162.0,
            stop_loss_price=142.5
        )
        assert trade_id > 0

        # Verify trade was logged
        open_trades = db.get_open_trades()
        assert len(open_trades) == 1
        assert open_trades[0]['ticker'] == 'AAPL'

    def test_log_trade_exit(self, db):
        """Test logging a trade exit."""
        # First create an entry
        db.log_trade_entry(
            ticker='MSFT',
            entry_price=300.0,
            quantity=5.0,
            score=0.04,
            avg_gain=0.07,
            avg_drawdown=-0.04,
            frequency=0.7,
            take_profit_price=321.0,
            stop_loss_price=288.0
        )

        # Log exit
        db.log_trade_exit(
            ticker='MSFT',
            exit_price=315.0,
            pnl=75.0,
            pnl_percent=5.0
        )

        # Verify no open trades
        open_trades = db.get_open_trades()
        assert len(open_trades) == 0

    def test_get_trade_statistics(self, db):
        """Test getting trade statistics."""
        # Create and close a winning trade
        db.log_trade_entry(
            ticker='TSLA',
            entry_price=200.0,
            quantity=10.0,
            score=0.06,
            avg_gain=0.10,
            avg_drawdown=-0.06,
            frequency=0.8,
            take_profit_price=220.0,
            stop_loss_price=188.0
        )
        db.log_trade_exit(
            ticker='TSLA',
            exit_price=220.0,
            pnl=200.0,
            pnl_percent=10.0
        )

        stats = db.get_trade_statistics(days=30)
        assert stats['total_trades'] == 1
        assert stats['winning_trades'] == 1
        assert stats['total_pnl'] == 200.0


class TestRiskManager:
    """Test risk management module."""

    @pytest.fixture
    def risk_config(self):
        """Create test risk config."""
        return RiskConfig(
            max_position_size_percent=60.0,
            max_daily_loss_percent=5.0,
            max_drawdown_percent=10.0,
            min_stock_price=5.0,
            max_stock_price=500.0,
            min_daily_volume=1000000
        )

    @pytest.fixture
    def risk_manager(self, risk_config):
        """Create test risk manager."""
        db = Database(':memory:')
        return RiskManager(risk_config, db)

    def test_daily_loss_limit(self, risk_manager):
        """Test daily loss limit checking."""
        risk_manager.set_daily_start_balance(10000.0)

        # Within limit
        can_trade, loss_pct = risk_manager.check_daily_loss_limit(9600.0)
        assert can_trade is True
        assert loss_pct < 5.0

        # Exceeds limit
        can_trade, loss_pct = risk_manager.check_daily_loss_limit(9400.0)
        assert can_trade is False
        assert loss_pct >= 5.0

    def test_position_sizing(self, risk_manager):
        """Test position size calculation."""
        # Test normal position sizing
        qty, capital = risk_manager.calculate_position_size(
            account_balance=10000.0,
            buying_power=10000.0,
            stock_price=100.0
        )

        # Should use max 60% of account = $6000 / $100 = 60 shares
        assert qty == 58  # 98% of 60 (rounded down)
        assert capital <= 6000.0

    def test_stock_validation(self, risk_manager):
        """Test stock validation."""
        # Valid stock
        is_valid, reason = risk_manager.validate_stock(
            ticker='AAPL',
            price=150.0,
            volume=50000000
        )
        assert is_valid is True

        # Price too low
        is_valid, reason = risk_manager.validate_stock(
            ticker='PENNY',
            price=2.0,
            volume=10000000
        )
        assert is_valid is False

        # Volume too low
        is_valid, reason = risk_manager.validate_stock(
            ticker='ILLIQUID',
            price=50.0,
            volume=500000
        )
        assert is_valid is False

    def test_stop_loss_calculation(self, risk_manager):
        """Test stop loss calculation."""
        entry_price = 100.0
        avg_drawdown = -0.05  # -5%

        stop_loss = risk_manager.calculate_stop_loss(entry_price, avg_drawdown)

        # Should be 110% of drawdown = -5.5% = $94.50
        assert 94.0 <= stop_loss <= 95.0

    def test_take_profit_calculation(self, risk_manager):
        """Test take profit calculation."""
        entry_price = 100.0
        avg_gain = 0.10  # 10%

        take_profit = risk_manager.calculate_take_profit(entry_price, avg_gain)

        # Should be $110
        assert take_profit == 110.0


class TestAnalytics:
    """Test analytics module."""

    @pytest.fixture
    def db_with_trades(self):
        """Create database with sample trades."""
        db = Database(':memory:')

        # Add winning trade
        db.log_trade_entry(
            ticker='WIN',
            entry_price=100.0,
            quantity=10.0,
            score=0.05,
            avg_gain=0.10,
            avg_drawdown=-0.05,
            frequency=0.7,
            take_profit_price=110.0,
            stop_loss_price=95.0
        )
        db.log_trade_exit(
            ticker='WIN',
            exit_price=110.0,
            pnl=100.0,
            pnl_percent=10.0
        )

        # Add losing trade
        db.log_trade_entry(
            ticker='LOSS',
            entry_price=200.0,
            quantity=5.0,
            score=0.04,
            avg_gain=0.08,
            avg_drawdown=-0.06,
            frequency=0.6,
            take_profit_price=216.0,
            stop_loss_price=188.0
        )
        db.log_trade_exit(
            ticker='LOSS',
            exit_price=188.0,
            pnl=-60.0,
            pnl_percent=-6.0
        )

        return db

    def test_performance_summary(self, db_with_trades):
        """Test performance summary calculation."""
        analytics = Analytics(db_with_trades)
        summary = analytics.get_performance_summary(days=30)

        assert summary['total_trades'] == 2
        assert summary['winning_trades'] == 1
        assert summary['losing_trades'] == 1
        assert summary['win_rate'] == 50.0
        assert summary['total_pnl'] == 40.0  # 100 - 60

    def test_best_and_worst_trades(self, db_with_trades):
        """Test best and worst trades retrieval."""
        analytics = Analytics(db_with_trades)
        trades = analytics.get_best_and_worst_trades(limit=5)

        assert len(trades['best']) >= 1
        assert len(trades['worst']) >= 1
        assert trades['best'][0]['ticker'] == 'WIN'
        assert trades['worst'][0]['ticker'] == 'LOSS'


def test_integration():
    """Basic integration test."""
    # Create components
    db = Database(':memory:')
    risk_config = RiskConfig(
        max_position_size_percent=60.0,
        max_daily_loss_percent=5.0,
        max_drawdown_percent=10.0,
        min_stock_price=5.0,
        max_stock_price=500.0,
        min_daily_volume=1000000
    )
    risk_manager = RiskManager(risk_config, db)
    analytics = Analytics(db)

    # Set initial balance
    risk_manager.set_daily_start_balance(10000.0)

    # Simulate a trade
    trade_id = db.log_trade_entry(
        ticker='TEST',
        entry_price=100.0,
        quantity=10.0,
        score=0.05,
        avg_gain=0.08,
        avg_drawdown=-0.05,
        frequency=0.6,
        take_profit_price=108.0,
        stop_loss_price=95.0
    )

    assert trade_id > 0

    # Check that trade exists
    open_trades = db.get_open_trades()
    assert len(open_trades) == 1

    # Close trade
    db.log_trade_exit(
        ticker='TEST',
        exit_price=108.0,
        pnl=80.0,
        pnl_percent=8.0
    )

    # Get statistics
    stats = db.get_trade_statistics(days=30)
    assert stats['total_trades'] == 1
    assert stats['winning_trades'] == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

