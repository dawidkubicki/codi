"""
Stock analysis module.
Handles earnings calendar fetching and historical analysis.

Data Sources:
- Finnhub API: Fundamental metrics (EPS, revenue, analyst ratings), earnings calendar
- yfinance: Historical earnings dates and price history for pattern analysis
"""
import logging
from typing import List, Optional, Dict, Any
import finnhub
import yfinance as yf
import pandas as pd
from datetime import date, timedelta
import time

from config import AnalysisConfig, TRADABLE_STOCKS

logger = logging.getLogger(__name__)


class StockAnalyzer:
    """Handles stock analysis and earnings calendar operations."""

    def __init__(self, finnhub_client: finnhub.Client, analysis_config: AnalysisConfig):
        """Initialize stock analyzer."""
        self.finnhub_client = finnhub_client
        self.config = analysis_config

    def get_tomorrows_earnings(self) -> List[str]:
        """
        Fetch earnings calendar for the next business day from Finnhub.
        Returns list of ticker symbols.
        """
        today = date.today()

        # Look ahead up to 7 days to find next earnings date
        for i in range(1, 8):
            check_date = today + timedelta(days=i)
            check_date_str = check_date.strftime("%Y-%m-%d")

            try:
                earnings = self.finnhub_client.earnings_calendar(
                    _from=check_date_str,
                    to=check_date_str,
                    international=False
                )

                if earnings and earnings.get('earningsCalendar'):
                    tickers = [event['symbol'] for event in earnings['earningsCalendar']]
                    logger.info(
                        f"Found {len(tickers)} stocks reporting earnings on {check_date_str}"
                    )
                    return tickers

            except Exception as e:
                logger.warning(f"Finnhub API error for {check_date_str}: {e}")
                time.sleep(1)

        logger.info("No earnings found in the next 7 days")
        return []

    def filter_tradable_assets(self, tickers: List[str], alpaca_api) -> List[str]:
        """
        Filter tickers to only those tradable on Alpaca and in our TRADABLE_STOCKS list.
        Uses stocks.txt (loaded as TRADABLE_STOCKS) for filtering.
        """
        try:
            # First filter by our curated TRADABLE_STOCKS list from stocks.txt
            filtered = [ticker for ticker in tickers if ticker in TRADABLE_STOCKS]

            logger.info(
                f"Filtered {len(tickers)} tickers to {len(filtered)} in TRADABLE_STOCKS"
            )

            return filtered

        except Exception as e:
            logger.error(f"Error filtering tradable assets: {e}")
            return []

    def get_fundamental_metrics(self, ticker: str) -> Dict[str, Any]:
        """
        Fetch fundamental metrics for a stock using Finnhub API.
        
        Returns dict with:
        - eps_beat_rate: % of times EPS beat estimates (0-1)
        - avg_eps_surprise_pct: Average surprise percentage
        - revenue_growth_trend: Revenue growth score (0-1)
        - analyst_score: Normalized score from recommendations (0-1)
        """
        metrics = {
            'eps_beat_rate': 0.5,  # Default neutral
            'avg_eps_surprise_pct': 0.0,
            'revenue_growth_trend': 0.5,
            'analyst_score': 0.5
        }
        
        if not self.finnhub_client:
            logger.debug(f"Finnhub client not available for {ticker}")
            return metrics
        
        try:
            # 1. Get company earnings (EPS data) from Finnhub
            try:
                time.sleep(0.25)  # Rate limiting
                earnings = self.finnhub_client.company_earnings(ticker, limit=8)
                
                if earnings and len(earnings) > 0:
                    beats = 0
                    surprises = []
                    
                    for earning in earnings:
                        actual = earning.get('actual')
                        estimate = earning.get('estimate')
                        
                        if actual is not None and estimate is not None and estimate != 0:
                            # Check if beat estimate
                            if actual > estimate:
                                beats += 1
                            
                            # Calculate surprise percentage
                            surprise_pct = ((actual - estimate) / abs(estimate)) * 100
                            surprises.append(surprise_pct)
                    
                    if len(earnings) > 0:
                        metrics['eps_beat_rate'] = beats / len(earnings)
                    
                    if surprises:
                        metrics['avg_eps_surprise_pct'] = sum(surprises) / len(surprises)
                        
            except Exception as e:
                logger.debug(f"Could not fetch earnings for {ticker}: {e}")
            
            # 2. Get company financials (revenue) from Finnhub
            try:
                time.sleep(0.25)  # Rate limiting
                financials = self.finnhub_client.company_basic_financials(ticker, 'all')
                
                if financials and 'series' in financials and 'quarterly' in financials['series']:
                    quarterly = financials['series']['quarterly']
                    
                    # Get revenue data
                    if 'revenuePerShare' in quarterly:
                        revenue_data = quarterly['revenuePerShare']
                        
                        if len(revenue_data) >= 2:
                            # Sort by period (most recent first typically)
                            revenue_data = sorted(revenue_data, key=lambda x: x['period'], reverse=True)
                            
                            # Calculate growth from last 4 quarters
                            revenues = [r['v'] for r in revenue_data[:4] if 'v' in r]
                            
                            if len(revenues) >= 2:
                                # Calculate average growth rate
                                growth_rates = []
                                for i in range(len(revenues) - 1):
                                    if revenues[i+1] != 0:
                                        growth = (revenues[i] - revenues[i+1]) / abs(revenues[i+1])
                                        growth_rates.append(growth)
                                
                                if growth_rates:
                                    avg_growth = sum(growth_rates) / len(growth_rates)
                                    # Normalize: 0% = 0.5, +10% = 0.75, +20%+ = 1.0
                                    if avg_growth > 0:
                                        metrics['revenue_growth_trend'] = min(0.5 + (avg_growth * 2.5), 1.0)
                                    else:
                                        metrics['revenue_growth_trend'] = max(0.5 + (avg_growth * 2.5), 0.0)
                                        
            except Exception as e:
                logger.debug(f"Could not fetch financials for {ticker}: {e}")
            
            # 3. Get recommendation trends from Finnhub
            try:
                time.sleep(0.25)  # Rate limiting
                recommendations = self.finnhub_client.recommendation_trends(ticker)
                
                if recommendations and len(recommendations) > 0:
                    # Use most recent recommendation data
                    recent = recommendations[0]
                    
                    # Calculate weighted score based on analyst recommendations
                    strong_buy = recent.get('strongBuy', 0)
                    buy = recent.get('buy', 0)
                    hold = recent.get('hold', 0)
                    sell = recent.get('sell', 0)
                    strong_sell = recent.get('strongSell', 0)
                    
                    total = strong_buy + buy + hold + sell + strong_sell
                    
                    if total > 0:
                        # Weighted average: Strong Buy=1.0, Buy=0.75, Hold=0.5, Sell=0.25, Strong Sell=0.0
                        score = (
                            (strong_buy * 1.0) +
                            (buy * 0.75) +
                            (hold * 0.5) +
                            (sell * 0.25) +
                            (strong_sell * 0.0)
                        ) / total
                        
                        metrics['analyst_score'] = score
                        
            except Exception as e:
                logger.debug(f"Could not fetch recommendations for {ticker}: {e}")
            
            return metrics
            
        except Exception as e:
            logger.warning(f"Error fetching fundamentals from Finnhub for {ticker}: {e}")
            return metrics

    def analyze_stock_earnings(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Analyze historical price action around earnings dates.

        Returns dictionary with:
        - ticker: stock symbol
        - score: frequency * avg_gain
        - avg_gain: average gain in the 5 days after earnings
        - avg_drawdown: average drawdown in the 5 days after earnings
        - frequency: % of times stock went up >1% after earnings
        """
        logger.info(f"Analyzing {ticker}...")

        try:
            stock = yf.Ticker(ticker)

            # Get earnings dates
            earnings_dates = stock.earnings_dates
            if earnings_dates is None or earnings_dates.empty:
                logger.info(f"No earnings data for {ticker}")
                return None

            # Filter to last N years
            cutoff_date = pd.to_datetime('today') - pd.DateOffset(years=self.config.history_years)
            relevant_dates = earnings_dates[earnings_dates.index >= cutoff_date].index

            if len(relevant_dates) < 4:
                logger.info(
                    f"Insufficient earnings history for {ticker} "
                    f"(found {len(relevant_dates)}, need 4)"
                )
                return None

            # Get historical price data
            hist = stock.history(period="5y")
            if hist.empty:
                logger.info(f"No price history for {ticker}")
                return None

            # Analyze each earnings event
            all_gains = []
            all_drawdowns = []

            for earnings_date in relevant_dates:
                try:
                    # Find the closing price on earnings date
                    t_idx = hist.index.get_loc(earnings_date.normalize(), method='ffill')
                    t_close = hist.iloc[t_idx]['Close']

                    # Get the next 5 trading days
                    window = hist.iloc[t_idx + 1 : t_idx + 6]
                    if window.empty:
                        continue

                    # Calculate gain (highest high vs earnings close)
                    perc_gain = (window['High'].max() - t_close) / t_close

                    # Calculate drawdown (lowest low vs earnings close)
                    perc_drawdown = (window['Low'].min() - t_close) / t_close

                    all_gains.append(perc_gain)
                    all_drawdowns.append(perc_drawdown)

                except Exception as e:
                    logger.debug(f"Error analyzing date {earnings_date} for {ticker}: {e}")
                    continue

            if not all_gains:
                logger.info(f"No complete data windows for {ticker}")
                return None

            # Calculate statistics
            positive_gains = [g for g in all_gains if g > 0.01]  # >1% gain
            negative_drawdowns = [d for d in all_drawdowns if d < 0]

            frequency = len(positive_gains) / len(all_gains) if all_gains else 0
            avg_gain = sum(positive_gains) / len(positive_gains) if positive_gains else 0
            avg_drawdown = (
                sum(negative_drawdowns) / len(negative_drawdowns)
                if negative_drawdowns else -0.05
            )

            # Price pattern score (historical performance)
            price_score = frequency * avg_gain
            
            # Get fundamental metrics
            fundamentals = self.get_fundamental_metrics(ticker)
            
            # Calculate fundamental score (weighted combination using Finnhub data)
            # Normalize EPS surprise: -20% = 0, 0% = 0.5, +20% = 1.0
            normalized_eps_surprise = min(max((fundamentals['avg_eps_surprise_pct'] / 40.0) + 0.5, 0.0), 1.0)
            
            fundamental_score = (
                fundamentals['eps_beat_rate'] * 0.5 +           # 50% weight on EPS beat rate
                normalized_eps_surprise * 0.3 +                 # 30% weight on EPS surprise magnitude
                fundamentals['analyst_score'] * 0.15 +          # 15% weight on analyst ratings
                fundamentals['revenue_growth_trend'] * 0.05     # 5% weight on revenue growth
            )
            
            # Combined score: 70% price pattern, 30% fundamentals
            final_score = (price_score * 0.7) + (fundamental_score * 0.3)

            logger.info(
                f"{ticker}: Final={final_score:.4f} (Price={price_score:.4f}, Fund={fundamental_score:.4f}) | "
                f"Freq={frequency:.2%}, Gain={avg_gain:.2%}, EPS Beat={fundamentals['eps_beat_rate']:.0%}"
            )

            return {
                'ticker': ticker,
                'score': final_score,
                'price_score': price_score,
                'fundamental_score': fundamental_score,
                'avg_gain': avg_gain,
                'avg_drawdown': avg_drawdown,
                'frequency': frequency,
                'eps_beat_rate': fundamentals['eps_beat_rate'],
                'avg_eps_surprise': fundamentals['avg_eps_surprise_pct'],
                'analyst_rating': fundamentals['analyst_score'],
                'revenue_growth': fundamentals['revenue_growth_trend']
            }

        except Exception as e:
            logger.error(f"Error analyzing {ticker}: {e}")
            return None

    def find_best_stock(self, alpaca_api) -> Optional[Dict[str, Any]]:
        """
        Complete analysis pipeline: fetch earnings, filter, analyze, and select best.
        Returns the best stock analysis or None.
        """
        # Step 1: Get earnings calendar
        tickers = self.get_tomorrows_earnings()
        if not tickers:
            logger.info("No stocks with upcoming earnings")
            return None

        # Step 2: Filter to tradable assets
        tradable = self.filter_tradable_assets(tickers, alpaca_api)
        if not tradable:
            logger.info("No tradable stocks found")
            return None

        # Limit analysis to configured maximum
        if len(tradable) > self.config.max_stocks_to_analyze:
            logger.info(
                f"Limiting analysis from {len(tradable)} to "
                f"{self.config.max_stocks_to_analyze} stocks"
            )
            tradable = tradable[:self.config.max_stocks_to_analyze]

        # Step 3: Analyze each stock
        results = []
        for ticker in tradable:
            analysis = self.analyze_stock_earnings(ticker)
            if analysis:
                results.append(analysis)
            time.sleep(1)  # Rate limiting

        if not results:
            logger.info("No stocks successfully analyzed")
            return None

        # Step 3.5: Filter by fundamental quality
        # Skip stocks with poor fundamental metrics (EPS beat rate < 30%)
        quality_results = []
        for result in results:
            if result.get('eps_beat_rate', 0.5) >= 0.3:
                quality_results.append(result)
            else:
                logger.debug(
                    f"Filtered out {result['ticker']}: EPS beat rate "
                    f"{result.get('eps_beat_rate', 0):.0%} < 30%"
                )
        
        if not quality_results:
            logger.info("No stocks passed fundamental quality filter")
            return None
        
        logger.info(
            f"Fundamental filter: {len(quality_results)}/{len(results)} stocks passed "
            f"(EPS beat rate >= 30%)"
        )

        # Step 4: Sort by score and get best
        quality_results.sort(key=lambda x: x['score'], reverse=True)
        best = quality_results[0]

        logger.info(
            f"Best candidate: {best['ticker']} | Score={best['score']:.4f} "
            f"(Price={best['price_score']:.4f}, Fund={best['fundamental_score']:.4f}) | "
            f"EPS Beat={best['eps_beat_rate']:.0%}"
        )

        # Check minimum thresholds
        if best['score'] < self.config.min_score_threshold:
            logger.info(
                f"Best score {best['score']:.4f} below threshold "
                f"{self.config.min_score_threshold}"
            )
            return None

        if best['avg_gain'] < (self.config.min_avg_gain_percent / 100):
            logger.info(
                f"Best avg_gain {best['avg_gain']:.2%} below threshold "
                f"{self.config.min_avg_gain_percent}%"
            )
            return None

        return best

    def get_stock_info(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get current stock information including price and volume."""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            return {
                'ticker': ticker,
                'current_price': info.get('currentPrice', info.get('regularMarketPrice', 0)),
                'volume': info.get('volume', 0),
                'avg_volume': info.get('averageVolume', 0),
                'market_cap': info.get('marketCap', 0),
            }

        except Exception as e:
            logger.error(f"Error getting info for {ticker}: {e}")
            return None

