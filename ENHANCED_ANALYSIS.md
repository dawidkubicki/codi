# Enhanced Stock Analysis System

## Overview

The trading bot now uses an advanced analysis system that combines technical price patterns with fundamental metrics to select the best trading opportunities.

## Key Improvements

### 1. Increased Analysis Capacity
- **Before**: Analyzed up to 20 stocks per day
- **After**: Analyzes up to 100 stocks per day (5x increase)
- **Configuration**: Set via `MAX_STOCKS_TO_ANALYZE` environment variable

### 2. Fundamental Analysis Integration

The bot now evaluates stocks based on three key fundamental metrics (optimized to avoid API rate limiting):

#### a) EPS Beat Rate (60% weight)
- Percentage of times the company beat earnings estimates
- **Filter**: Stocks with <30% beat rate are automatically excluded
- Higher rate = more consistent earnings performance
- Most reliable fundamental indicator

#### b) Average EPS Surprise (30% weight)
- Average percentage by which earnings exceeded or missed estimates
- Normalized: -20% = 0.0, 0% = 0.5, +20% = 1.0
- Positive surprises indicate strong performance
- Shows magnitude of earnings quality

#### c) Revenue Growth Trend (10% weight)
- Quarter-over-quarter revenue growth pattern
- Normalized: +20%+ = 1.0, 0% = 0.5, -20%- = 0.0
- Indicates business expansion/contraction

**Note**: All fundamental data now comes from Finnhub API (same API used for earnings calendar), which has better rate limits and more reliable data than Yahoo Finance.

### 3. Enhanced Scoring System

**Formula:**
```
Price Pattern Score = Win Rate × Average Gain
Fundamental Score = (EPS Beat Rate × 0.5) + (EPS Surprise × 0.3) + (Analyst Rating × 0.15) + (Revenue Growth × 0.05)
Final Score = (Price Pattern Score × 0.7) + (Fundamental Score × 0.3)
```

**API Optimization:**
- **Finnhub API**: 0.25 second delays between API calls (3 calls per stock)
- **Reliable data**: No "delisted" errors like Yahoo Finance
- **Better rate limits**: Finnhub Premium features with existing API key
- **Graceful fallbacks**: Returns neutral scores if data unavailable

**Weighting Rationale:**
- 70% price patterns: Historical behavior is the strongest predictor
- 30% fundamentals: Filters out low-quality stocks and adds confidence

### 4. Quality Filtering

Stocks are now filtered at multiple stages:
1. **Tradable Filter**: Must be in stocks.txt (Alpaca-tradable)
2. **Data Filter**: Requires 4+ years of earnings history
3. **Fundamental Filter**: Must have EPS beat rate ≥ 30%
4. **Score Filter**: Must meet minimum score thresholds

### 5. Enhanced Logging

Logs now show comprehensive analysis data:

```
📊 Analysis Complete: AAPL | Final Score: 0.0542 | Price Score: 0.0654 | Fundamental Score: 0.0321
📈 Technical: Win Rate=68.2%, Avg Gain=9.6%, Avg Drawdown=-4.2%
💼 Fundamentals: EPS Beat=75.0%, EPS Surprise=+5.2%, Analyst Rating=0.85
```

## Configuration

### Environment Variables

```bash
# Analysis settings
MAX_STOCKS_TO_ANALYZE=100        # Number of stocks to analyze per day
HISTORY_YEARS=4                  # Years of historical data to analyze
MIN_SCORE_THRESHOLD=0.0          # Minimum combined score to trade
MIN_AVG_GAIN_PERCENT=1.0         # Minimum average gain percentage
```

## Data Sources

**Price Data**:
- **Alpaca API** (backtesting): Historical OHLCV data for trade simulation
- **yfinance** (live analysis): Historical price data and earnings dates for pattern analysis

**Fundamental Data** - Finnhub API (already configured):
- **Company Earnings**: Actual vs Estimated EPS for last 8 quarters
- **Financial Metrics**: Quarterly revenue per share data
- **Analyst Ratings**: Recommendation trends (Strong Buy/Buy/Hold/Sell/Strong Sell)
- **Earnings Calendar**: Upcoming earnings announcements

**Trade Execution** - Alpaca API:
- Real-time market data
- Order placement and management

## Error Handling

The system gracefully handles missing data:
- **Missing EPS data**: Uses neutral score (0.5)
- **No analyst ratings**: Uses neutral score (0.5)
- **No revenue data**: Uses neutral score (0.5)
- **Partial data**: Combines available metrics with defaults

This ensures all stocks can be analyzed even if some fundamental data is unavailable.

## Expected Benefits

1. **Better Stock Selection**: Only trades stocks with strong fundamentals AND good price patterns
2. **Reduced False Positives**: Filters out stocks that may have good price patterns but poor business fundamentals
3. **More Opportunities**: 5x increase in analysis capacity finds more potential trades
4. **Higher Confidence**: Dual-score system provides transparency in decision-making
5. **Lower Risk**: Fundamental filter eliminates consistently underperforming companies

## Performance Impact

- **Analysis Time**: ~100-120 seconds for 100 stocks (1 second per stock for rate limiting)
- **API Calls**: All data from Yahoo Finance (free, no API key required)
- **Memory Usage**: Minimal increase (~50MB for caching stock data)

## Example Analysis Output

```
2025-10-22 15:30:00 - INFO - Filtered 150 tickers to 120 in TRADABLE_STOCKS
2025-10-22 15:30:01 - INFO - Limiting analysis from 120 to 100 stocks
2025-10-22 15:31:45 - INFO - AAPL: Final=0.0542 (Price=0.0654, Fund=0.0321) | Freq=68%, Gain=9.60%, EPS Beat=75%
2025-10-22 15:31:47 - INFO - MSFT: Final=0.0498 (Price=0.0587, Fund=0.0298) | Freq=72%, Gain=8.15%, EPS Beat=80%
...
2025-10-22 15:33:30 - INFO - Fundamental filter: 78/100 stocks passed (EPS beat rate >= 30%)
2025-10-22 15:33:30 - INFO - Best candidate: NVDA | Score=0.0612 (Price=0.0712, Fund=0.0371) | EPS Beat=85%
2025-10-22 15:33:31 - INFO - 📊 Analysis Complete: NVDA | Final Score: 0.0612 | Price Score: 0.0712 | Fundamental Score: 0.0371
2025-10-22 15:33:31 - INFO - 📈 Technical: Win Rate=74.5%, Avg Gain=9.56%, Avg Drawdown=-3.87%
2025-10-22 15:33:31 - INFO - 💼 Fundamentals: EPS Beat=85.0%, EPS Surprise=+7.3%, Analyst Rating=0.90
```

## Testing

To test the enhanced analysis:

```bash
# Run a backtest with the new system
python backtest_full.py

# Or test live analysis
python main.py

# Test fundamental analysis specifically
python test_fundamental_analysis.py
```

The system will automatically use the new scoring system for all analyses, including backtesting.

## Backtest Integration

The enhanced fundamental analysis is fully integrated into the backtesting system (`backtest_full.py`):

- **Increased capacity**: Backtests now analyze up to 100 stocks per day (configurable via `MAX_STOCKS_TO_ANALYZE`)
- **Fundamental filtering**: Stocks with EPS beat rate <30% are excluded from backtest trades
- **Enhanced logging**: Backtest output shows both price and fundamental scores
- **Detailed reports**: Trade details include fundamental metrics for each trade
- **CSV export**: Fundamental metrics are included in the exported backtest results

Example backtest output:
```
🎯 NVDA | Final=0.0612 (Price=0.0712, Fund=0.0371) | Win Rate: 74.5% | EPS Beat: 85%
🟢 Take profit hit | P&L: $+1,245.32 (+12.45%)

Trade Details:
   Scores:   Price=0.0712, Fund=0.0371
   Metrics:  EPS Beat=85%, EPS Surprise=+7.3%, Analyst=0.90
```

## Rollback

To revert to the simpler analysis (technical only):

1. Set `MAX_STOCKS_TO_ANALYZE=20` in .env
2. The fundamental analysis will still run but with less impact due to sample size

Note: The fundamental analysis code is designed to gracefully degrade if data is unavailable, so it won't break existing functionality.

## Future Enhancements

Potential improvements for future versions:
- Add sector rotation analysis
- Include momentum indicators (RSI, MACD)
- Integrate options flow data
- Add sentiment analysis from news/social media
- Machine learning for pattern recognition

