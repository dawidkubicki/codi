# 🤖 Earnings Jump Trading Bot

An automated trading bot that identifies and trades stocks with favorable historical price action around earnings announcements. The bot uses the Alpaca API for trading and Finnhub for earnings calendar data.

## ✨ Features

- **Automated Earnings Analysis**: Automatically fetches upcoming earnings and analyzes historical price patterns
- **Risk Management**: Comprehensive risk controls including:
  - Position sizing limits
  - Daily loss limits  
  - Maximum drawdown protection
  - Stock price and volume filters
- **Telegram Notifications**: Real-time alerts for all trading activities
- **Trade Logging**: Complete database tracking of all trades and analysis
- **Performance Analytics**: Detailed statistics and reporting
- **Backtesting**: Test strategies on historical data before going live
- **Type Hints**: Full type annotations for better code quality
- **Modular Architecture**: Clean separation of concerns

## 📋 Requirements

- Python 3.8+
- Alpaca Paper Trading Account (FREE)
- Finnhub API Key (FREE tier available)
- Telegram Bot (for notifications)

## 🚀 Installation

1. **Clone or download this repository**

2. **Create a virtual environment**:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**:

Create a `.env` file in the project root:

```bash
# Alpaca API Configuration
ALPACA_API_KEY=your_alpaca_api_key_here
ALPACA_SECRET_KEY=your_alpaca_secret_key_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Finnhub API Configuration
FINNHUB_API_KEY=your_finnhub_api_key_here

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_telegram_chat_id_here

# Trading Configuration
ANALYSIS_HOUR=8
POLL_SLEEP_SECONDS=300
LOOP_SLEEP_SECONDS=3600

# Risk Management
MAX_POSITION_SIZE_PERCENT=85.0
MAX_DAILY_LOSS_PERCENT=5.0
MAX_DRAWDOWN_PERCENT=10.0
MIN_STOCK_PRICE=5.0
MAX_STOCK_PRICE=500.0
MIN_DAILY_VOLUME=1000000

# Analysis Configuration
HISTORY_YEARS=4
MAX_STOCKS_TO_ANALYZE=20
MIN_SCORE_THRESHOLD=0.0
MIN_AVG_GAIN_PERCENT=1.0

# Database Configuration
DATABASE_PATH=trading_bot.db

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=trading_bot.log
```

## 🔑 Getting API Keys

### Alpaca (Paper Trading)
1. Go to [Alpaca](https://alpaca.markets/)
2. Sign up for a FREE paper trading account
3. Navigate to "Your API Keys" and generate keys
4. ⚠️ **IMPORTANT**: Use only Paper Trading URL: `https://paper-api.alpaca.markets`

### Finnhub
1. Go to [Finnhub](https://finnhub.io/)
2. Sign up for a FREE account
3. Copy your API key from the dashboard

### Telegram Bot
1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot` and follow instructions
3. Copy the bot token
4. Start a chat with your bot and send any message
5. Get your chat ID from: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`

## 📊 How It Works

### Trading Strategy

1. **Daily Analysis**: Every day at the configured hour (default 8 AM), the bot:
   - Fetches stocks reporting earnings tomorrow
   - Filters to only tradable stocks on Alpaca
   - Analyzes historical price action around past earnings dates

2. **Stock Scoring**: For each stock, the bot calculates:
   - **Frequency**: % of times the stock went up >1% in the 5 days after earnings
   - **Average Gain**: Average highest gain in those 5-day windows
   - **Average Drawdown**: Average worst drop in those windows
   - **Score**: `frequency × avg_gain` (higher is better)

3. **Position Entry**: The highest-scoring stock gets traded with:
   - **Entry**: Market buy order
   - **Take Profit**: Limit sell at historical average gain
   - **Stop Loss**: Stop sell at 110% of historical drawdown (min -8%, max -20%)

4. **Position Monitoring**: The bot monitors the position every 5 minutes until closed

5. **Risk Controls**: All trades are subject to:
   - Maximum 20% of account per trade (configurable)
   - Daily loss limit (default 5%)
   - Maximum drawdown limit (default 10%)

## 🎮 Usage

### Start the Bot

```bash
python main.py
```

The bot will:
- Validate configuration
- Connect to APIs
- Send a startup notification via Telegram
- Enter the main trading loop

### Stop the Bot

Press `Ctrl+C` to gracefully shut down.

## 📈 Analytics

The bot includes built-in analytics accessible through Python:

```python
from database import Database
from analytics import Analytics

db = Database('trading_bot.db')
analytics = Analytics(db)

# Get 30-day performance summary
summary = analytics.get_performance_summary(days=30)
print(analytics.format_summary_report(30))

# Get best and worst trades
trades = analytics.get_best_and_worst_trades(limit=5)
print(trades)

# Get performance by ticker
ticker_perf = analytics.get_ticker_performance()
```

## 🧪 Backtesting

Test the strategy on historical data:

```python
from backtester import Backtester
from config import config

backtester = Backtester(config.analysis)

# Example: test on specific stocks/dates
test_stocks = [
    {
        'ticker': 'AAPL',
        'entry_date': '2024-01-25',
        'avg_gain': 0.08,
        'avg_drawdown': -0.05
    },
    # ... more stocks
]

results = backtester.backtest_strategy(test_stocks, initial_capital=10000)
print(backtester.print_backtest_report(results))

# Export to CSV
backtester.export_results_to_csv('my_backtest.csv')
```

## 📁 Project Structure

```
codibot/
├── main.py              # Main bot loop
├── config.py            # Configuration management
├── database.py          # Database operations
├── notifier.py          # Telegram notifications
├── risk_manager.py      # Risk management
├── analyzer.py          # Stock analysis
├── trader.py            # Trade execution
├── analytics.py         # Performance analytics
├── backtester.py        # Backtesting engine
├── test_bot.py          # Unit tests
├── requirements.txt     # Python dependencies
├── .env                 # Environment variables (create this)
└── README.md           # This file
```

## ⚙️ Configuration Guide

### Risk Management Settings

- **MAX_POSITION_SIZE_PERCENT** (default: 85.0)
  - Maximum % of account equity to use per trade
  - Lower = more conservative, higher = more aggressive
  - Recommended: 20-95%

- **MAX_DAILY_LOSS_PERCENT** (default: 5.0)
  - Stop trading if daily losses exceed this %
  - Recommended: 3-7%

- **MAX_DRAWDOWN_PERCENT** (default: 10.0)
  - Stop trading if total drawdown exceeds this %
  - Recommended: 10-20%

- **MIN_STOCK_PRICE** / **MAX_STOCK_PRICE** (default: 5.0 / 500.0)
  - Only trade stocks within this price range
  - Avoid penny stocks and very expensive stocks

- **MIN_DAILY_VOLUME** (default: 1,000,000)
  - Minimum average daily volume for liquidity
  - Higher = more liquid but fewer opportunities

### Analysis Settings

- **HISTORY_YEARS** (default: 4)
  - Years of historical earnings to analyze
  - More = better data, but slower analysis

- **MAX_STOCKS_TO_ANALYZE** (default: 20)
  - Limit analysis to first N stocks
  - Prevents API rate limiting

## 🔒 Safety Features

1. **Paper Trading Only**: Configured for Alpaca paper trading by default
2. **Risk Limits**: Multiple layers of risk management
3. **Error Handling**: Comprehensive try-catch blocks with logging
4. **Graceful Shutdown**: Properly handles interrupts
5. **Configuration Validation**: Validates all settings on startup
6. **Position Limits**: Only one position at a time by default

## 📝 Logging

Logs are written to:
- **Console**: INFO level and above
- **File**: `trading_bot.log` (if configured)
- **Database**: All trades and analysis results

## 🧪 Testing

Run the unit tests:

```bash
pytest test_bot.py -v
```

Run with coverage:

```bash
pytest test_bot.py --cov=. --cov-report=html
```

## ⚠️ Disclaimer

**This bot is for educational purposes only.**

- Trading involves substantial risk of loss
- Past performance does not guarantee future results
- Always start with paper trading
- Never risk more than you can afford to lose
- The authors are not responsible for any financial losses

## 🤝 Contributing

Improvements welcome! Areas for enhancement:
- Additional technical indicators
- Multiple position management
- Advanced order types
- Machine learning integration
- Web dashboard
- More comprehensive backtesting

## 📄 License

MIT License - feel free to modify and use as you wish.

## 🐛 Troubleshooting

### "API keys not set properly"
- Check your `.env` file exists and has correct values
- Make sure you're using Paper Trading URL for Alpaca

### "Telegram connection failed"
- Verify bot token is correct
- Make sure you've started a chat with your bot
- Check your chat ID is correct

### "No earnings found"
- This is normal - not every day has earnings
- The bot will wait for the next earnings date

### Database errors
- Delete `trading_bot.db` to reset the database
- Check file permissions

## 📧 Support

For issues or questions, please create an issue on GitHub or check the code comments for detailed explanations.

---

**Happy Trading! 🚀**

