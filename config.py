"""
Configuration management module.
Handles loading and validation of configuration from environment variables.
"""
import os
from typing import Optional
from dataclasses import dataclass
from dotenv import load_dotenv
import logging

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class AlpacaConfig:
    """Alpaca API configuration."""
    api_key: str
    secret_key: str
    base_url: str

    def validate(self) -> bool:
        """Validate Alpaca configuration."""
        if not self.api_key or self.api_key == "your_alpaca_api_key_here":
            logger.error("ALPACA_API_KEY not set properly")
            return False
        if not self.secret_key or self.secret_key == "your_alpaca_secret_key_here":
            logger.error("ALPACA_SECRET_KEY not set properly")
            return False
        if not self.base_url:
            logger.error("ALPACA_BASE_URL not set")
            return False
        return True


@dataclass
class FinnhubConfig:
    """Finnhub API configuration."""
    api_key: str

    def validate(self) -> bool:
        """Validate Finnhub configuration."""
        if not self.api_key or self.api_key == "your_finnhub_api_key_here":
            logger.error("FINNHUB_API_KEY not set properly")
            return False
        return True


@dataclass
class TelegramConfig:
    """Telegram bot configuration."""
    bot_token: str
    chat_id: str

    def validate(self) -> bool:
        """Validate Telegram configuration."""
        if not self.bot_token or self.bot_token == "your_telegram_bot_token_here":
            logger.error("TELEGRAM_BOT_TOKEN not set properly")
            return False
        if not self.chat_id or self.chat_id == "your_telegram_chat_id_here":
            logger.error("TELEGRAM_CHAT_ID not set properly")
            return False
        return True


@dataclass
class RiskConfig:
    """Risk management configuration."""
    max_position_size_percent: float
    max_daily_loss_percent: float
    max_drawdown_percent: float
    min_stock_price: float
    max_stock_price: float
    min_daily_volume: int

    def validate(self) -> bool:
        """Validate risk configuration."""
        if not 0 < self.max_position_size_percent <= 100:
            logger.error("MAX_POSITION_SIZE_PERCENT must be between 0 and 100")
            return False
        if not 0 < self.max_daily_loss_percent <= 100:
            logger.error("MAX_DAILY_LOSS_PERCENT must be between 0 and 100")
            return False
        if not 0 < self.max_drawdown_percent <= 100:
            logger.error("MAX_DRAWDOWN_PERCENT must be between 0 and 100")
            return False
        if self.min_stock_price <= 0:
            logger.error("MIN_STOCK_PRICE must be positive")
            return False
        if self.max_stock_price <= self.min_stock_price:
            logger.error("MAX_STOCK_PRICE must be greater than MIN_STOCK_PRICE")
            return False
        if self.min_daily_volume <= 0:
            logger.error("MIN_DAILY_VOLUME must be positive")
            return False
        return True


@dataclass
class AnalysisConfig:
    """Analysis configuration."""
    history_years: int
    max_stocks_to_analyze: int
    min_score_threshold: float
    min_avg_gain_percent: float

    def validate(self) -> bool:
        """Validate analysis configuration."""
        if self.history_years <= 0:
            logger.error("HISTORY_YEARS must be positive")
            return False
        if self.max_stocks_to_analyze <= 0:
            logger.error("MAX_STOCKS_TO_ANALYZE must be positive")
            return False
        return True


@dataclass
class BotConfig:
    """Main bot configuration."""
    analysis_hour: int
    poll_sleep_seconds: int
    loop_sleep_seconds: int
    database_path: str
    log_level: str
    log_file: str

    def validate(self) -> bool:
        """Validate bot configuration."""
        if not 0 <= self.analysis_hour <= 23:
            logger.error("ANALYSIS_HOUR must be between 0 and 23")
            return False
        if self.poll_sleep_seconds <= 0:
            logger.error("POLL_SLEEP_SECONDS must be positive")
            return False
        if self.loop_sleep_seconds <= 0:
            logger.error("LOOP_SLEEP_SECONDS must be positive")
            return False
        return True


class Config:
    """Main configuration class that aggregates all configurations."""

    def __init__(self):
        """Initialize configuration from environment variables."""
        self.alpaca = AlpacaConfig(
            api_key=os.getenv("ALPACA_API_KEY", ""),
            secret_key=os.getenv("ALPACA_SECRET_KEY", ""),
            base_url=os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
        )

        self.finnhub = FinnhubConfig(
            api_key=os.getenv("FINNHUB_API_KEY", "")
        )

        self.telegram = TelegramConfig(
            bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            chat_id=os.getenv("TELEGRAM_CHAT_ID", "")
        )

        self.risk = RiskConfig(
            max_position_size_percent=float(os.getenv("MAX_POSITION_SIZE_PERCENT", "85.0")),
            max_daily_loss_percent=float(os.getenv("MAX_DAILY_LOSS_PERCENT", "5.0")),
            max_drawdown_percent=float(os.getenv("MAX_DRAWDOWN_PERCENT", "10.0")),
            min_stock_price=float(os.getenv("MIN_STOCK_PRICE", "5.0")),
            max_stock_price=float(os.getenv("MAX_STOCK_PRICE", "500.0")),
            min_daily_volume=int(os.getenv("MIN_DAILY_VOLUME", "1000000"))
        )

        self.analysis = AnalysisConfig(
            history_years=int(os.getenv("HISTORY_YEARS", "4")),
            max_stocks_to_analyze=int(os.getenv("MAX_STOCKS_TO_ANALYZE", "100")),
            min_score_threshold=float(os.getenv("MIN_SCORE_THRESHOLD", "0.0")),
            min_avg_gain_percent=float(os.getenv("MIN_AVG_GAIN_PERCENT", "1.0"))
        )

        self.bot = BotConfig(
            analysis_hour=int(os.getenv("ANALYSIS_HOUR", "8")),
            poll_sleep_seconds=int(os.getenv("POLL_SLEEP_SECONDS", "300")),
            loop_sleep_seconds=int(os.getenv("LOOP_SLEEP_SECONDS", "3600")),
            database_path=os.getenv("DATABASE_PATH", "trading_bot.db"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_file=os.getenv("LOG_FILE", "trading_bot.log")
        )

    def validate(self) -> bool:
        """Validate all configuration sections."""
        valid = True
        valid &= self.alpaca.validate()
        valid &= self.finnhub.validate()
        valid &= self.telegram.validate()
        valid &= self.risk.validate()
        valid &= self.analysis.validate()
        valid &= self.bot.validate()
        return valid


# Global configuration instance
config = Config()


def load_tradable_stocks(filename: str = "stocks.txt") -> set:
    """
    Load tradable stock symbols from file.
    
    Args:
        filename: Path to the stocks file (default: stocks.txt)
    
    Returns:
        Set of stock symbols
    """
    try:
        stocks = set()
        with open(filename, 'r') as f:
            for line in f:
                # Skip comments and empty lines
                line = line.strip()
                if line and not line.startswith('#'):
                    stocks.add(line)
        
        logger.info(f"Loaded {len(stocks)} tradable stocks from {filename}")
        return stocks
    
    except FileNotFoundError:
        logger.warning(f"Stock file {filename} not found. Run fetch_alpaca_stocks.py first.")
        return set()
    
    except Exception as e:
        logger.error(f"Error loading stocks from {filename}: {e}")
        return set()


# Load tradable stocks on module import
TRADABLE_STOCKS = load_tradable_stocks()

