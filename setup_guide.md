# Quick Setup Guide

## Step-by-Step Instructions

### 1. Create .env file

Copy and paste this into a new file called `.env` in the project root:

```env
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

### 2. Get Your API Keys

#### Alpaca (Paper Trading - FREE)
1. Go to https://alpaca.markets/
2. Click "Sign Up"
3. Verify your email
4. Go to "Paper Trading" → "Generate API Keys"
5. Copy the API Key and Secret Key
6. Paste them into your `.env` file

#### Finnhub (FREE)
1. Go to https://finnhub.io/
2. Click "Get free API key"
3. Sign up with email
4. Copy your API key from the dashboard
5. Paste it into your `.env` file

#### Telegram Bot (FREE)
1. Open Telegram app
2. Search for `@BotFather`
3. Send `/newbot`
4. Choose a name for your bot (e.g., "My Trading Bot")
5. Choose a username (must end in 'bot', e.g., "my_trading_bot")
6. Copy the bot token you receive
7. Paste it as `TELEGRAM_BOT_TOKEN` in your `.env` file

**Get your Chat ID:**
1. Search for `@userinfobot` in Telegram
2. Start a chat and it will send you your chat ID
3. Paste it as `TELEGRAM_CHAT_ID` in your `.env` file

### 3. Install Dependencies

```bash
# Make sure you're in the project directory
cd /Users/dawidkubicki/Desktop/codibot

# Activate virtual environment (already exists)
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 4. Test Your Setup

```bash
python -c "from config import config; print('Config OK!' if config.validate() else 'Config Error')"
```

If you see "Config OK!", you're ready to go!

### 5. Run the Bot

```bash
python main.py
```

You should receive a Telegram message confirming the bot has started!

## Testing Without Real Trading

The bot is configured for **paper trading** by default (simulated trading with fake money). This is perfect for testing!

## Common Issues

### "API keys not set properly"
- Make sure your `.env` file is in the same directory as `main.py`
- Check that there are no extra spaces or quotes around your API keys
- Verify each API key is correct by logging into the respective service

### "Telegram connection failed"
- Make sure you've started a chat with your bot (send it any message)
- Double-check your bot token and chat ID
- The chat ID should be just numbers (might start with -)

### "Module not found"
- Make sure you've activated the virtual environment: `source venv/bin/activate`
- Try reinstalling: `pip install -r requirements.txt`

## Configuration Tips

### Conservative Settings (Recommended for Testing)
```env
MAX_POSITION_SIZE_PERCENT=20.0  # Use only 20% per trade
MAX_DAILY_LOSS_PERCENT=3.0      # Stop after 3% daily loss
MAX_DRAWDOWN_PERCENT=10.0       # Stop after 10% total drawdown
```

### Balanced Settings (Default)
```env
MAX_POSITION_SIZE_PERCENT=85.0  # Use 85% per trade
MAX_DAILY_LOSS_PERCENT=5.0      # Stop after 5% daily loss
MAX_DRAWDOWN_PERCENT=10.0       # Stop after 10% total drawdown
```

### Aggressive Settings (Higher Risk)
```env
MAX_POSITION_SIZE_PERCENT=95.0  # Use 95% per trade
MAX_DAILY_LOSS_PERCENT=10.0     # Stop after 10% daily loss
MAX_DRAWDOWN_PERCENT=20.0       # Stop after 20% total drawdown
```

## Next Steps

1. Let the bot run and observe its behavior
2. Check your Telegram for notifications
3. Review the database: `sqlite3 trading_bot.db "SELECT * FROM trades;"`
4. Analyze performance using the analytics module

## Support

Check the main README.md for detailed documentation and troubleshooting.

