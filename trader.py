"""
Trading execution module.
Handles order placement and position monitoring.
"""
import logging
from typing import Optional, Dict, Any, Tuple, List
import alpaca_trade_api as tradeapi

from risk_manager import RiskManager
from database import Database
from notifier import TelegramNotifier

logger = logging.getLogger(__name__)


class Trader:
    """Handles trade execution and position management."""

    def __init__(self, alpaca_api: tradeapi.REST, risk_manager: RiskManager,
                 database: Database, notifier: TelegramNotifier):
        """Initialize trader."""
        self.api = alpaca_api
        self.risk = risk_manager
        self.db = database
        self.notifier = notifier

    def get_account_info(self) -> Dict[str, float]:
        """Get current account information."""
        try:
            account = self.api.get_account()
            return {
                'equity': float(account.equity),
                'cash': float(account.cash),
                'buying_power': float(account.buying_power),
                'portfolio_value': float(account.portfolio_value)
            }
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            return {}

    def get_current_price(self, ticker: str) -> Optional[float]:
        """Get current price for a ticker."""
        try:
            trade = self.api.get_latest_trade(ticker)
            return float(trade.price)
        except Exception as e:
            logger.error(f"Error getting price for {ticker}: {e}")
            return None

    def place_bracket_order(self, stock_data: Dict[str, Any]) -> Optional[str]:
        """
        Place a bracket order (market entry with take profit and stop loss).
        Returns ticker symbol if successful, None otherwise.
        """
        ticker = stock_data['ticker']
        logger.info(f"=== Attempting to place order for {ticker} ===")

        try:
            # Get account info
            account_info = self.get_account_info()
            if not account_info:
                logger.error("Could not get account information")
                return None

            current_balance = account_info['equity']

            # Risk check
            can_trade, reason = self.risk.can_trade(current_balance)
            if not can_trade:
                logger.warning(f"Risk check failed: {reason}")
                self.notifier.notify_risk_limit_hit("Trading Halted", 0)
                return None

            # Get current price
            current_price = self.get_current_price(ticker)
            if not current_price:
                logger.error(f"Could not get price for {ticker}")
                return None

            # Validate stock
            is_valid, validation_reason = self.risk.validate_stock(
                ticker, current_price
            )
            if not is_valid:
                logger.warning(f"Stock validation failed: {validation_reason}")
                return None

            # Calculate position size
            quantity, capital_used = self.risk.calculate_position_size(
                current_balance,
                account_info['buying_power'],
                current_price
            )

            if quantity == 0:
                logger.error("Position size calculated as 0")
                return None

            # Calculate stop loss and take profit
            stop_loss_price = self.risk.calculate_stop_loss(
                current_price,
                stock_data['avg_drawdown']
            )

            take_profit_price = self.risk.calculate_take_profit(
                current_price,
                stock_data['avg_gain']
            )

            # Log order details
            logger.info(f"Order details for {ticker}:")
            logger.info(f"  Quantity: {quantity:.4f}")
            logger.info(f"  Entry Price: ~${current_price:.2f}")
            logger.info(f"  Capital: ${capital_used:.2f}")
            logger.info(f"  Take Profit: ${take_profit_price:.2f} (+{stock_data['avg_gain']:.2%})")
            logger.info(f"  Stop Loss: ${stop_loss_price:.2f}")

            # Submit bracket order
            order = self.api.submit_order(
                symbol=ticker,
                qty=quantity,
                side='buy',
                type='market',
                time_in_force='day',
                order_class='bracket',
                take_profit={'limit_price': take_profit_price},
                stop_loss={'stop_price': stop_loss_price}
            )

            logger.info(f"✅ Bracket order submitted successfully for {ticker}")
            logger.info(f"   Order ID: {order.id}")

            # Log to database
            self.db.log_trade_entry(
                ticker=ticker,
                entry_price=current_price,
                quantity=quantity,
                score=stock_data['score'],
                avg_gain=stock_data['avg_gain'],
                avg_drawdown=stock_data['avg_drawdown'],
                frequency=stock_data['frequency'],
                take_profit_price=take_profit_price,
                stop_loss_price=stop_loss_price,
                order_id=order.id
            )

            # Send Telegram notification
            self.notifier.notify_trade_entry(
                ticker=ticker,
                quantity=quantity,
                entry_price=current_price,
                take_profit=take_profit_price,
                stop_loss=stop_loss_price,
                capital_used=capital_used
            )

            return ticker

        except Exception as e:
            logger.error(f"Error placing order for {ticker}: {e}")
            self.notifier.notify_error(f"Order placement failed for {ticker}: {str(e)}")
            return None

    def get_position(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get current position for a ticker."""
        try:
            position = self.api.get_position(ticker)
            return {
                'ticker': ticker,
                'qty': float(position.qty),
                'entry_price': float(position.avg_entry_price),
                'current_price': float(position.current_price),
                'market_value': float(position.market_value),
                'unrealized_pl': float(position.unrealized_pl),
                'unrealized_plpc': float(position.unrealized_plpc)
            }
        except Exception as e:
            # Position doesn't exist
            return None

    def monitor_position(self, ticker: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Check if position still exists.
        Returns (position_open, position_info)
        """
        position = self.get_position(ticker)
        return (position is not None, position)

    def get_all_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions."""
        try:
            positions = self.api.list_positions()
            return [{
                'ticker': pos.symbol,
                'qty': float(pos.qty),
                'entry_price': float(pos.avg_entry_price),
                'current_price': float(pos.current_price),
                'market_value': float(pos.market_value),
                'unrealized_pl': float(pos.unrealized_pl),
                'unrealized_plpc': float(pos.unrealized_plpc)
            } for pos in positions]
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    def close_position(self, ticker: str, reason: str = "Manual close") -> bool:
        """Manually close a position."""
        try:
            position = self.get_position(ticker)
            if not position:
                logger.warning(f"No position found for {ticker}")
                return False

            qty = position['qty']
            self.api.submit_order(
                symbol=ticker,
                qty=qty,
                side='sell',
                type='market',
                time_in_force='day'
            )

            logger.info(f"Position closed for {ticker}: {reason}")

            # Calculate P&L
            exit_price = position['current_price']
            pnl = position['unrealized_pl']
            pnl_percent = position['unrealized_plpc'] * 100

            # Log to database
            self.db.log_trade_exit(
                ticker=ticker,
                exit_price=exit_price,
                pnl=pnl,
                pnl_percent=pnl_percent
            )

            # Notify
            self.notifier.notify_trade_exit(
                ticker=ticker,
                exit_price=exit_price,
                pnl=pnl,
                pnl_percent=pnl_percent,
                reason=reason
            )

            return True

        except Exception as e:
            logger.error(f"Error closing position for {ticker}: {e}")
            return False

    def is_market_open(self) -> bool:
        """Check if market is currently open."""
        try:
            clock = self.api.get_clock()
            return clock.is_open
        except Exception as e:
            logger.error(f"Error checking market status: {e}")
            return False

    def get_market_status(self) -> Dict[str, Any]:
        """Get detailed market status."""
        try:
            clock = self.api.get_clock()
            return {
                'is_open': clock.is_open,
                'next_open': clock.next_open,
                'next_close': clock.next_close,
                'timestamp': clock.timestamp
            }
        except Exception as e:
            logger.error(f"Error getting market status: {e}")
            return {'is_open': False}

