"""
Telegram notification module.
"""
import logging
from typing import Optional
import requests
from datetime import datetime

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Handles Telegram notifications for the trading bot."""

    def __init__(self, bot_token: str, chat_id: str):
        """Initialize Telegram notifier."""
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.enabled = True

        # Test connection
        if not self._test_connection():
            logger.warning("Telegram connection test failed. Notifications disabled.")
            self.enabled = False

    def _test_connection(self) -> bool:
        """Test Telegram bot connection."""
        try:
            response = requests.get(f"{self.base_url}/getMe", timeout=5)
            if response.status_code == 200:
                logger.info("Telegram bot connected successfully")
                return True
            else:
                logger.error(f"Telegram connection failed: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Telegram connection error: {e}")
            return False

    def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """Send a message via Telegram."""
        if not self.enabled:
            logger.debug(f"Telegram disabled. Message: {message}")
            return False

        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode
            }
            response = requests.post(url, json=payload, timeout=10)

            if response.status_code == 200:
                logger.debug("Telegram message sent successfully")
                return True
            else:
                logger.error(f"Failed to send Telegram message: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False

    def notify_startup(self, mode: str = "Paper Trading") -> None:
        """Notify bot startup."""
        message = f"""
🤖 <b>Trading Bot Started</b>

⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
📊 Mode: {mode}
✅ Status: Running

The bot is now monitoring the market.
        """
        self.send_message(message.strip())

    def notify_analysis_start(self, num_stocks: int) -> None:
        """Notify analysis start."""
        message = f"""
🔍 <b>Daily Analysis Started</b>

📅 Date: {datetime.now().strftime('%Y-%m-%d')}
📈 Stocks to analyze: {num_stocks}

Searching for the best earnings play...
        """
        self.send_message(message.strip())

    def notify_analysis_complete(self, best_ticker: str, score: float,
                                 avg_gain: float, frequency: float) -> None:
        """Notify analysis completion."""
        message = f"""
✅ <b>Analysis Complete</b>

🎯 Best Candidate: <b>{best_ticker}</b>
⭐ Score: {score:.4f}
📊 Avg Gain: {avg_gain:.2%}
🎲 Success Rate: {frequency:.2%}
        """
        self.send_message(message.strip())

    def notify_trade_entry(self, ticker: str, quantity: float, entry_price: float,
                          take_profit: float, stop_loss: float, capital_used: float) -> None:
        """Notify trade entry."""
        take_profit_pct = ((take_profit / entry_price) - 1) * 100
        stop_loss_pct = ((stop_loss / entry_price) - 1) * 100

        message = f"""
🚀 <b>TRADE OPENED</b>

📈 Symbol: <b>{ticker}</b>
💵 Quantity: {quantity:.4f}
💰 Entry Price: ${entry_price:.2f}
💸 Capital Used: ${capital_used:.2f}

🎯 Take Profit: ${take_profit:.2f} (+{take_profit_pct:.2f}%)
🛡️ Stop Loss: ${stop_loss:.2f} ({stop_loss_pct:.2f}%)

⏰ Time: {datetime.now().strftime('%H:%M:%S')}
        """
        self.send_message(message.strip())

    def notify_trade_exit(self, ticker: str, exit_price: float, pnl: float,
                         pnl_percent: float, reason: str = "Position Closed") -> None:
        """Notify trade exit."""
        emoji = "🟢" if pnl > 0 else "🔴"
        status = "WIN" if pnl > 0 else "LOSS"

        message = f"""
{emoji} <b>TRADE CLOSED - {status}</b>

📈 Symbol: <b>{ticker}</b>
💰 Exit Price: ${exit_price:.2f}
{'💵' if pnl > 0 else '💸'} P&L: ${pnl:.2f} ({pnl_percent:+.2f}%)

📝 Reason: {reason}
⏰ Time: {datetime.now().strftime('%H:%M:%S')}
        """
        self.send_message(message.strip())

    def notify_position_update(self, ticker: str, current_price: float,
                               unrealized_pnl: float, unrealized_pnl_percent: float) -> None:
        """Notify position update."""
        emoji = "📈" if unrealized_pnl > 0 else "📉"

        message = f"""
{emoji} <b>Position Update</b>

Symbol: <b>{ticker}</b>
Current Price: ${current_price:.2f}
Unrealized P&L: ${unrealized_pnl:.2f} ({unrealized_pnl_percent:+.2f}%)
        """
        self.send_message(message.strip())

    def notify_daily_summary(self, date: str, total_pnl: float, num_trades: int,
                            win_rate: float, equity: float) -> None:
        """Notify daily summary."""
        emoji = "🟢" if total_pnl > 0 else "🔴" if total_pnl < 0 else "⚪"

        message = f"""
{emoji} <b>Daily Summary</b>

📅 Date: {date}
💰 Total P&L: ${total_pnl:.2f}
📊 Trades: {num_trades}
🎯 Win Rate: {win_rate:.1f}%
💵 Account Equity: ${equity:.2f}
        """
        self.send_message(message.strip())

    def notify_error(self, error_msg: str, critical: bool = False) -> None:
        """Notify error."""
        emoji = "🚨" if critical else "⚠️"
        level = "CRITICAL ERROR" if critical else "Warning"

        message = f"""
{emoji} <b>{level}</b>

{error_msg}

⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        self.send_message(message.strip())

    def notify_risk_limit_hit(self, limit_type: str, value: float) -> None:
        """Notify when risk limit is hit."""
        message = f"""
🛑 <b>RISK LIMIT HIT</b>

Type: {limit_type}
Value: {value:.2f}%

Trading halted for risk management.
⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        self.send_message(message.strip())

    def notify_no_opportunities(self, reason: str) -> None:
        """Notify when no trading opportunities found."""
        message = f"""
ℹ️ <b>No Trading Opportunities</b>

Reason: {reason}
📅 Date: {datetime.now().strftime('%Y-%m-%d')}

The bot will continue monitoring.
        """
        self.send_message(message.strip())

