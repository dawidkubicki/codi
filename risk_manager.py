"""
Risk management module.
Handles position sizing, drawdown limits, and risk controls.
"""
import logging
from typing import Optional, Tuple
from datetime import date
from config import RiskConfig
from database import Database

logger = logging.getLogger(__name__)


class RiskManager:
    """Manages risk controls and position sizing."""

    def __init__(self, risk_config: RiskConfig, database: Database):
        """Initialize risk manager."""
        self.config = risk_config
        self.db = database
        self.daily_start_balance: Optional[float] = None
        self.max_drawdown_balance: Optional[float] = None

    def set_daily_start_balance(self, balance: float) -> None:
        """Set the starting balance for the day."""
        self.daily_start_balance = balance
        if self.max_drawdown_balance is None:
            self.max_drawdown_balance = balance
        else:
            # Update max if we've recovered
            self.max_drawdown_balance = max(self.max_drawdown_balance, balance)
        logger.info(f"Daily start balance set: ${balance:.2f}")

    def check_daily_loss_limit(self, current_balance: float) -> Tuple[bool, float]:
        """
        Check if daily loss limit has been hit.
        Returns (can_trade, loss_percent)
        """
        if self.daily_start_balance is None:
            logger.warning("Daily start balance not set")
            return True, 0.0

        loss = self.daily_start_balance - current_balance
        loss_percent = (loss / self.daily_start_balance) * 100

        if loss_percent >= self.config.max_daily_loss_percent:
            logger.warning(
                f"Daily loss limit hit: {loss_percent:.2f}% "
                f"(limit: {self.config.max_daily_loss_percent}%)"
            )
            return False, loss_percent

        return True, loss_percent

    def check_max_drawdown(self, current_balance: float) -> Tuple[bool, float]:
        """
        Check if maximum drawdown limit has been hit.
        Returns (can_trade, drawdown_percent)
        """
        if self.max_drawdown_balance is None:
            logger.warning("Max drawdown balance not set")
            return True, 0.0

        drawdown = self.max_drawdown_balance - current_balance
        drawdown_percent = (drawdown / self.max_drawdown_balance) * 100

        if drawdown_percent >= self.config.max_drawdown_percent:
            logger.warning(
                f"Max drawdown limit hit: {drawdown_percent:.2f}% "
                f"(limit: {self.config.max_drawdown_percent}%)"
            )
            return False, drawdown_percent

        return True, drawdown_percent

    def can_trade(self, current_balance: float) -> Tuple[bool, str]:
        """
        Comprehensive check if trading is allowed.
        Returns (can_trade, reason)
        """
        # Check daily loss limit
        can_trade_daily, daily_loss = self.check_daily_loss_limit(current_balance)
        if not can_trade_daily:
            return False, f"Daily loss limit exceeded: {daily_loss:.2f}%"

        # Check max drawdown
        can_trade_dd, drawdown = self.check_max_drawdown(current_balance)
        if not can_trade_dd:
            return False, f"Max drawdown limit exceeded: {drawdown:.2f}%"

        return True, "All risk checks passed"

    def calculate_position_size(self, account_balance: float, buying_power: float,
                               stock_price: float) -> Tuple[float, float]:
        """
        Calculate position size based on risk parameters.
        Returns (quantity, capital_to_use)
        """
        # Use the smaller of buying power and max position size
        max_capital = account_balance * (self.config.max_position_size_percent / 100)
        available_capital = min(buying_power * 0.98, max_capital)  # 98% buffer

        if available_capital <= 0:
            logger.warning("No available capital for trading")
            return 0.0, 0.0

        quantity = available_capital / stock_price

        # Round down to avoid over-spending
        if quantity < 1:
            # For fractional shares
            quantity = round(quantity, 6)
        else:
            quantity = int(quantity)

        actual_capital = quantity * stock_price

        logger.info(
            f"Position sizing: {quantity:.4f} shares @ ${stock_price:.2f} "
            f"= ${actual_capital:.2f} "
            f"({(actual_capital/account_balance*100):.2f}% of account)"
        )

        return quantity, actual_capital

    def validate_stock(self, ticker: str, price: float, volume: Optional[int] = None) -> Tuple[bool, str]:
        """
        Validate if a stock meets risk criteria.
        Returns (is_valid, reason)
        """
        # Check price range
        if price < self.config.min_stock_price:
            return False, f"Price ${price:.2f} below minimum ${self.config.min_stock_price}"

        if price > self.config.max_stock_price:
            return False, f"Price ${price:.2f} above maximum ${self.config.max_stock_price}"

        # Check volume if provided
        if volume is not None and volume < self.config.min_daily_volume:
            return False, f"Volume {volume:,} below minimum {self.config.min_daily_volume:,}"

        return True, "Stock validation passed"

    def calculate_stop_loss(self, entry_price: float, avg_drawdown: float) -> float:
        """
        Calculate stop loss price.
        Uses historical drawdown with a buffer, with a minimum stop loss.
        """
        # Use 150% of historical average drawdown (more aggressive)
        stop_loss_percent = avg_drawdown * 1.1

        # Ensure minimum stop loss of -8%
        if stop_loss_percent > -0.08:
            logger.info(f"Historical drawdown {stop_loss_percent:.2%} too small, using -8%")
            stop_loss_percent = -0.08

        # Ensure maximum stop loss of -20%
        if stop_loss_percent < -0.20:
            logger.warning(f"Historical drawdown {stop_loss_percent:.2%} too large, capping at -20%")
            stop_loss_percent = -0.20

        stop_loss_price = entry_price * (1 + stop_loss_percent)

        logger.info(
            f"Stop loss calculated: ${stop_loss_price:.2f} "
            f"({stop_loss_percent:.2%} from entry)"
        )

        return round(stop_loss_price, 2)

    def calculate_take_profit(self, entry_price: float, avg_gain: float) -> float:
        """
        Calculate take profit price based on historical average gain.
        Uses 90% of historical average for better probability of hitting target.
        """
        # Use 90% of historical average gain for more conservative target
        adjusted_gain = avg_gain * 0.90
        take_profit_price = entry_price * (1 + adjusted_gain)

        logger.info(
            f"Take profit calculated: ${take_profit_price:.2f} "
            f"({adjusted_gain:.2%} from entry, 90% of historical {avg_gain:.2%})"
        )

        return round(take_profit_price, 2)

    def get_risk_summary(self, current_balance: float) -> dict:
        """Get current risk status summary."""
        summary = {}

        if self.daily_start_balance:
            daily_pnl = current_balance - self.daily_start_balance
            daily_pnl_pct = (daily_pnl / self.daily_start_balance) * 100
            summary['daily_pnl'] = daily_pnl
            summary['daily_pnl_percent'] = daily_pnl_pct
            summary['daily_limit_remaining'] = self.config.max_daily_loss_percent + daily_pnl_pct

        if self.max_drawdown_balance:
            drawdown = self.max_drawdown_balance - current_balance
            drawdown_pct = (drawdown / self.max_drawdown_balance) * 100
            summary['current_drawdown_percent'] = drawdown_pct
            summary['drawdown_limit_remaining'] = self.config.max_drawdown_percent - drawdown_pct

        summary['max_position_size_percent'] = self.config.max_position_size_percent
        summary['can_trade'], summary['can_trade_reason'] = self.can_trade(current_balance)

        return summary

