"""
Enhanced Earnings Jump Trading Bot
Automated trading bot with comprehensive risk management, notifications, and analytics.
"""
import sys
import time
import logging
from datetime import datetime, date
from typing import Optional

import alpaca_trade_api as tradeapi
import finnhub

# Import our modules
from config import config
from database import Database
from notifier import TelegramNotifier
from risk_manager import RiskManager
from analyzer import StockAnalyzer
from trader import Trader
from analytics import Analytics


def setup_logging() -> logging.Logger:
    """Setup logging configuration."""
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # File handler (if configured)
    handlers = [console_handler]
    if config.bot.log_file:
        try:
            file_handler = logging.FileHandler(config.bot.log_file)
            file_handler.setFormatter(formatter)
            handlers.append(file_handler)
        except Exception as e:
            print(f"Warning: Could not create log file: {e}")

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, config.bot.log_level.upper()),
        handlers=handlers
    )

    return logging.getLogger(__name__)


def validate_configuration() -> bool:
    """Validate all configuration settings."""
    logger = logging.getLogger(__name__)
    logger.info("Validating configuration...")

    if not config.validate():
        logger.error("Configuration validation failed!")
        logger.error("Please check your .env file and ensure all settings are correct.")
        return False

    logger.info("✅ Configuration validated successfully")
    return True


def initialize_components():
    """Initialize all bot components."""
    logger = logging.getLogger(__name__)
    logger.info("Initializing bot components...")

    try:
        # Initialize Alpaca API
        logger.info("Connecting to Alpaca...")
        alpaca_api = tradeapi.REST(
            config.alpaca.api_key,
            config.alpaca.secret_key,
            config.alpaca.base_url,
            api_version='v2'
        )

        # Test connection
        account = alpaca_api.get_account()
        logger.info(f"✅ Connected to Alpaca - Account Equity: ${float(account.equity):,.2f}")

        # Initialize Finnhub
        logger.info("Connecting to Finnhub...")
        finnhub_client = finnhub.Client(api_key=config.finnhub.api_key)
        logger.info("✅ Connected to Finnhub")

        # Initialize Database
        logger.info("Initializing database...")
        database = Database(config.bot.database_path)
        logger.info(f"✅ Database ready: {config.bot.database_path}")

        # Initialize Telegram Notifier
        logger.info("Connecting to Telegram...")
        notifier = TelegramNotifier(
            config.telegram.bot_token,
            config.telegram.chat_id
        )
        logger.info("✅ Telegram notifier ready")

        # Initialize Risk Manager
        logger.info("Initializing risk manager...")
        risk_manager = RiskManager(config.risk, database)
        logger.info("✅ Risk manager ready")

        # Initialize Stock Analyzer
        logger.info("Initializing stock analyzer...")
        analyzer = StockAnalyzer(finnhub_client, config.analysis)
        logger.info("✅ Stock analyzer ready")

        # Initialize Trader
        logger.info("Initializing trader...")
        trader = Trader(alpaca_api, risk_manager, database, notifier)
        logger.info("✅ Trader ready")

        # Initialize Analytics
        analytics = Analytics(database)

        logger.info("🎉 All components initialized successfully!")

        return {
            'alpaca_api': alpaca_api,
            'finnhub_client': finnhub_client,
            'database': database,
            'notifier': notifier,
            'risk_manager': risk_manager,
            'analyzer': analyzer,
            'trader': trader,
            'analytics': analytics
        }

    except Exception as e:
        logger.error(f"❌ Failed to initialize components: {e}")
        raise


def run_daily_analysis(components) -> Optional[str]:
    """
    Run daily analysis and place trade if opportunity found.
    Returns ticker symbol if trade placed, None otherwise.
    """
    logger = logging.getLogger(__name__)
    analyzer = components['analyzer']
    trader = components['trader']
    risk_manager = components['risk_manager']
    notifier = components['notifier']
    database = components['database']

    logger.info("=" * 60)
    logger.info("STARTING DAILY ANALYSIS")
    logger.info("=" * 60)

    # Get account info
    account_info = trader.get_account_info()
    if not account_info:
        logger.error("Could not get account information")
        notifier.notify_error("Failed to get account info", critical=False)
        return None

    equity = account_info['equity']
    logger.info(f"Current account equity: ${equity:,.2f}")

    # Set daily start balance for risk management
    risk_manager.set_daily_start_balance(equity)

    # Log account snapshot
    database.log_account_snapshot(
        equity=equity,
        cash=account_info['cash'],
        buying_power=account_info['buying_power'],
        portfolio_value=account_info['portfolio_value']
    )

    # Check if we can trade (risk limits)
    can_trade, reason = risk_manager.can_trade(equity)
    if not can_trade:
        logger.warning(f"Cannot trade: {reason}")
        notifier.notify_risk_limit_hit("Trading Disabled", 0)
        return None
    
    # Find best stock
    notifier.notify_analysis_start(0)
    best_stock = analyzer.find_best_stock(components['alpaca_api'])

    if not best_stock:
        logger.info("No suitable trading opportunities found")
        notifier.notify_no_opportunities("No stocks met analysis criteria")
        return None
        
    # Log analysis result with fundamental metrics
    logger.info(
        f"📊 Analysis Complete: {best_stock['ticker']} | "
        f"Final Score: {best_stock['score']:.4f} | "
        f"Price Score: {best_stock['price_score']:.4f} | "
        f"Fundamental Score: {best_stock['fundamental_score']:.4f}"
    )
    logger.info(
        f"📈 Technical: Win Rate={best_stock['frequency']:.1%}, "
        f"Avg Gain={best_stock['avg_gain']:.2%}, "
        f"Avg Drawdown={best_stock['avg_drawdown']:.2%}"
    )
    logger.info(
        f"💼 Fundamentals: EPS Beat={best_stock['eps_beat_rate']:.1%}, "
        f"EPS Surprise={best_stock['avg_eps_surprise']:.1f}%, "
        f"Analyst Rating={best_stock['analyst_rating']:.2f}"
    )
    
    database.log_analysis_result(
        ticker=best_stock['ticker'],
        analysis_date=date.today().isoformat(),
        earnings_date=None,
        score=best_stock['score'],
        avg_gain=best_stock['avg_gain'],
        avg_drawdown=best_stock['avg_drawdown'],
        frequency=best_stock['frequency'],
        selected=True
    )

    # Notify analysis complete
    notifier.notify_analysis_complete(
        best_ticker=best_stock['ticker'],
        score=best_stock['score'],
        avg_gain=best_stock['avg_gain'],
        frequency=best_stock['frequency']
    )

    # Place trade
    ticker = trader.place_bracket_order(best_stock)

    if ticker:
        logger.info(f"✅ Successfully placed trade for {ticker}")
    else:
        logger.warning("Failed to place trade")

    return ticker


def monitor_position(components, ticker: str) -> None:
    """
    Monitor an open position until it closes.
    """
    logger = logging.getLogger(__name__)
    trader = components['trader']
    notifier = components['notifier']
    database = components['database']

    logger.info(f"Monitoring position: {ticker}")

    last_notification_time = None
    notification_interval = 3600  # Notify hourly

    while True:
        time.sleep(config.bot.poll_sleep_seconds)

        # Check if position still exists
        is_open, position = trader.monitor_position(ticker)

        if not is_open:
            logger.info(f"Position {ticker} has been closed")

            # Get final price and calculate P&L
            # The database logging is handled by trader module
            # when the bracket order exits
            notifier.notify_trade_exit(
                ticker=ticker,
                exit_price=position['current_price'] if position else 0,
                pnl=position['unrealized_pl'] if position else 0,
                pnl_percent=position['unrealized_plpc'] * 100 if position else 0,
                reason="Bracket order executed"
            )
            break

        # Position still open - log status
        if position:
            logger.info(
                f"Position {ticker}: Price ${position['current_price']:.2f}, "
                f"P&L ${position['unrealized_pl']:+.2f} "
                f"({position['unrealized_plpc']*100:+.2f}%)"
            )

            # Send periodic updates
            current_time = time.time()
            if (last_notification_time is None or
                current_time - last_notification_time >= notification_interval):

                notifier.notify_position_update(
                    ticker=ticker,
                    current_price=position['current_price'],
                    unrealized_pnl=position['unrealized_pl'],
                    unrealized_pnl_percent=position['unrealized_plpc'] * 100
                )
                last_notification_time = current_time


def main_loop(components) -> None:
    """
    Main trading bot loop.
    """
    logger = logging.getLogger(__name__)
    trader = components['trader']
    notifier = components['notifier']

    last_analysis_date = None

    logger.info("🤖 Trading bot started")
    notifier.notify_startup(mode="Paper Trading")

    while True:
        try:
            # Check for open positions
            positions = trader.get_all_positions()
            
            if positions:
                # Monitor existing position(s)
                for position in positions:
                    ticker = position['ticker']
                    logger.info(
                        f"Found open position: {position['qty']} x {ticker} "
                        f"@ ${position['entry_price']:.2f}"
                    )
                    monitor_position(components, ticker)

                # After all positions are closed, continue
                continue
            
            # No positions - check if it's time to analyze
            logger.info("No open positions")
            
            now = datetime.now()
            today = date.today()

            if now.hour == config.bot.analysis_hour and today != last_analysis_date:
                logger.info(f"It's {config.bot.analysis_hour}:00 - Running daily analysis")
                
                # Run analysis and potentially place trade
                run_daily_analysis(components)
                
                # Mark analysis as complete for today
                last_analysis_date = today
                logger.info("Daily analysis complete. Waiting until tomorrow...")

                # Sleep for most of the day
                time.sleep(60 * 60 * 23)
            
            else:
                # Not time for analysis yet
                logger.info(
                    f"Waiting for analysis time ({config.bot.analysis_hour}:00). "
                    f"Sleeping for {config.bot.loop_sleep_seconds / 3600:.1f} hours..."
                )
                time.sleep(config.bot.loop_sleep_seconds)

        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
            notifier.send_message("🛑 <b>Bot Shutting Down</b>\n\nGraceful shutdown initiated.")
            break

        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
            notifier.notify_error(f"Main loop error: {str(e)}", critical=False)
            logger.info("Retrying in 5 minutes...")
            time.sleep(300)


def main():
    """Main entry point."""
    # Setup logging
    logger = setup_logging()

    logger.info("=" * 60)
    logger.info("EARNINGS JUMP TRADING BOT")
    logger.info("=" * 60)

    # Validate configuration
    if not validate_configuration():
        logger.error("Exiting due to configuration errors")
        sys.exit(1)

    try:
        # Initialize components
        components = initialize_components()

        # Start main loop
        main_loop(components)

    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

    logger.info("Bot shutdown complete")


if __name__ == "__main__":
    main()