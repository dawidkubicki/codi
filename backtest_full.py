"""
Full backtesting simulation.
Simulates the bot running over a historical period, getting earnings calendars
and making trades as if it were running in real-time.
"""
import logging
from datetime import date, timedelta, datetime
from typing import List, Dict, Any, Optional
import pandas as pd
import time
import os
import requests
from dotenv import load_dotenv
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from config import config, TRADABLE_STOCKS
from backtester import Backtester
from analyzer import StockAnalyzer

load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FullBacktester:
    """Full simulation of bot running over historical period."""

    def __init__(self):
        """Initialize full backtester."""
        self.backtester = Backtester(config.analysis)
        self.capital = 10000.0
        self.initial_capital = 10000.0
        self.trades = []
        self.daily_log = []
        self.config = config.analysis
        
        # Initialize Alpaca data client (using IEX feed for free tier)
        alpaca_api_key = os.getenv('ALPACA_API_KEY')
        alpaca_secret_key = os.getenv('ALPACA_SECRET_KEY')
        
        if not alpaca_api_key or alpaca_api_key == 'your_alpaca_api_key_here':
            raise ValueError("ALPACA_API_KEY not configured in .env file")
        
        # Use raw=True to avoid subscription errors with free tier
        self.alpaca_data = StockHistoricalDataClient(
            api_key=alpaca_api_key, 
            secret_key=alpaca_secret_key,
            raw_data=False
        )
        
        # Initialize analyzer for fundamental analysis
        self.analyzer = StockAnalyzer(finnhub_client=None, analysis_config=config.analysis)

    def analyze_stock_history(self, ticker: str, upcoming_earnings_date: date) -> Optional[Dict[str, Any]]:
        """
        Analyze historical price action around past earnings dates using Alpaca.
        Estimates quarterly earnings (every ~90 days) and analyzes price movement.
        
        Args:
            ticker: Stock symbol
            upcoming_earnings_date: The upcoming earnings date to analyze for
            
        Returns:
            Dictionary with analysis results or None
        """
        logger.info(f"  Analyzing {ticker}...")
        
        try:
            # Estimate past quarterly earnings dates (every ~90 days going back)
            past_earnings_dates = []
            current_est = upcoming_earnings_date - timedelta(days=90)
            
            # Go back 2 years to get ~8 quarters of data
            cutoff = upcoming_earnings_date - timedelta(days=730)
            
            while current_est >= cutoff:
                past_earnings_dates.append(current_est)
                current_est -= timedelta(days=90)
            
            if len(past_earnings_dates) < 3:
                logger.debug(f"    Not enough estimated earnings dates")
                return None
            
            # Get historical price data from Alpaca (using IEX feed for free tier)
            start_date = cutoff - timedelta(days=10)  # Add buffer
            end_date = upcoming_earnings_date - timedelta(days=1)
            
            request_params = StockBarsRequest(
                symbol_or_symbols=[ticker],
                timeframe=TimeFrame.Day,
                start=start_date,
                end=end_date,
                feed='iex'  # Use IEX feed for free tier accounts
            )
            
            bars = self.alpaca_data.get_stock_bars(request_params)
            
            if ticker not in bars.data or not bars.data[ticker]:
                logger.debug(f"    No price data from Alpaca")
                return None
            
            # Convert to DataFrame for easier analysis
            df = pd.DataFrame([{
                'timestamp': bar.timestamp,
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume
            } for bar in bars.data[ticker]])
            
            df['date'] = pd.to_datetime(df['timestamp']).dt.date
            df = df.set_index('date')
            
            # Analyze each estimated earnings date
            all_gains = []
            all_drawdowns = []
            
            for earnings_est_date in past_earnings_dates:
                try:
                    # Find closest trading day to earnings estimate
                    if earnings_est_date not in df.index:
                        # Find nearest date
                        nearest_idx = df.index[df.index >= earnings_est_date][0] if any(df.index >= earnings_est_date) else None
                        if nearest_idx is None:
                            continue
                        earnings_est_date = nearest_idx
                    
                    t_close = df.loc[earnings_est_date, 'close']
                    
                    # Get next 5 trading days
                    future_dates = [d for d in df.index if d > earnings_est_date][:5]
                    if len(future_dates) < 3:  # Need at least 3 days
                        continue
                    
                    window = df.loc[future_dates]
                    
                    # Calculate gain and drawdown
                    perc_gain = (window['high'].max() - t_close) / t_close
                    perc_drawdown = (window['low'].min() - t_close) / t_close
                    
                    all_gains.append(perc_gain)
                    all_drawdowns.append(perc_drawdown)
                    
                except Exception as e:
                    logger.debug(f"    Error analyzing {earnings_est_date}: {e}")
                    continue
            
            if not all_gains or len(all_gains) < 3:
                logger.debug(f"    Insufficient data points ({len(all_gains)})")
                return None
            
            # Calculate statistics
            positive_gains = [g for g in all_gains if g > 0.01]  # >1% gain
            negative_drawdowns = [d for d in all_drawdowns if d < 0]
            
            frequency = len(positive_gains) / len(all_gains) if all_gains else 0
            avg_gain = sum(positive_gains) / len(positive_gains) if positive_gains else 0
            avg_drawdown = sum(negative_drawdowns) / len(negative_drawdowns) if negative_drawdowns else -0.05
            
            # Price pattern score (historical performance)
            price_score = frequency * avg_gain
            
            # Get fundamental metrics (with error handling for delisted/problematic stocks)
            try:
                fundamentals = self.analyzer.get_fundamental_metrics(ticker)
            except Exception as e:
                logger.debug(f"    Could not fetch fundamentals: {e}")
                # Use neutral defaults if fundamentals fail
                fundamentals = {
                    'eps_beat_rate': 0.5,
                    'avg_eps_surprise_pct': 0.0,
                    'revenue_growth_trend': 0.5,
                    'analyst_score': 0.5,
                    'institutional_ownership_pct': 0.0
                }
            
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
            
            # Filter by fundamental quality
            if fundamentals['eps_beat_rate'] < 0.3:
                logger.debug(f"    Filtered out: EPS beat rate {fundamentals['eps_beat_rate']:.0%} < 30%")
                return None
            
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
                'analyst_rating': fundamentals['analyst_score']
            }
            
        except Exception as e:
            logger.debug(f"    Error analyzing {ticker}: {e}")
            return None

    def get_historical_earnings_calendar(self, target_date: date) -> List[str]:
        """
        Get stocks that had earnings on the target date using Finnhub API.
        Only returns liquid, major US stocks.
        
        Args:
            target_date: The date to check for earnings
            
        Returns:
            List of ticker symbols with earnings on that date
        """
        api_key = os.getenv('FINNHUB_API_KEY')
        
        if not api_key or api_key == 'your_finnhub_api_key_here':
            logger.warning("⚠️  FINNHUB_API_KEY not configured - using sample data")
            return self._get_sample_earnings(target_date)
        
        date_str = target_date.strftime("%Y-%m-%d")
        logger.debug(f"Fetching earnings for {date_str}...")
        
        # Use tradable stocks from config (loaded from stocks.txt)
        # stocks.txt is generated by fetch_alpaca_stocks.py
        
        try:
            # Finnhub API endpoint
            url = "https://finnhub.io/api/v1/calendar/earnings"
            params = {
                'from': date_str,
                'to': date_str,
                'token': api_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                earnings_calendar = data.get('earningsCalendar', [])
                
                if earnings_calendar:
                    # Extract symbols and filter to whitelist
                    all_tickers = [event.get('symbol') for event in earnings_calendar if event.get('symbol')]
                    
                    # Filter to our tradable stocks
                    filtered_tickers = [t for t in all_tickers if t in TRADABLE_STOCKS]
                    
                    logger.debug(f"  Found {len(all_tickers)} total, {len(filtered_tickers)} tradable")
                    return filtered_tickers
                else:
                    logger.debug(f"  No earnings found")
                    return []
            elif response.status_code == 429:
                logger.warning("  Rate limit hit - waiting...")
                time.sleep(2)
                return []
            else:
                logger.warning(f"  API error {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"  Error fetching earnings: {e}")
            return []
    
    def _get_sample_earnings(self, target_date: date) -> List[str]:
        """Fallback: return sample earnings for testing without API key."""
        # Sample October 2024 earnings
        sample_data = {
            date(2024, 10, 8): ['PEP'],
            date(2024, 10, 11): ['JPM', 'WFC'],
            date(2024, 10, 17): ['NFLX'],
            date(2024, 10, 22): ['VZ'],
            date(2024, 10, 23): ['TSLA', 'T', 'IBM', 'KO'],
        }
        return sample_data.get(target_date, [])

    def simulate_day(self, current_date: date, day_num: int, total_days: int) -> Optional[Dict[str, Any]]:
        """
        Simulate one day of bot operation.
        
        Args:
            current_date: The date we're simulating
            day_num: Current day number
            total_days: Total days in backtest
            
        Returns:
            Trade result if a trade was made, None otherwise
        """
        progress_pct = (day_num / total_days) * 100
        logger.info(f"\n[Day {day_num}/{total_days} - {progress_pct:.0f}%] {current_date.strftime('%Y-%m-%d (%A)')}")
        logger.info(f"Capital: ${self.capital:,.2f} | Trades: {len(self.trades)}")
        logger.info("-" * 60)

        # Check if market was open (skip weekends)
        if current_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
            logger.info("⏭️  Weekend - Skipped")
            return None

        # Get stocks with earnings tomorrow
        next_day = current_date + timedelta(days=1)
        earnings_stocks = self.get_historical_earnings_calendar(next_day)

        if not earnings_stocks:
            logger.info("📊 No earnings tomorrow - Skipped")
            return None

        logger.info(f"📊 {len(earnings_stocks)} stocks have earnings tomorrow")
        
        # Analyze top stocks (using configured max from config)
        max_analyze = min(len(earnings_stocks), self.config.max_stocks_to_analyze)
        logger.info(f"📈 Analyzing up to {max_analyze} stocks...")
        analyzed_stocks = []

        for ticker in earnings_stocks[:max_analyze]:
            analysis = self.analyze_stock_history(ticker, next_day)
            if analysis:
                analyzed_stocks.append(analysis)

        if not analyzed_stocks:
            logger.info("❌ No qualifying stocks - Skipped")
            return None

        # Select best stock
        best_stock = max(analyzed_stocks, key=lambda x: x['score'])
        
        # Check minimum thresholds
        if best_stock['frequency'] < 0.4 or best_stock['avg_gain'] < 0.01:
            logger.info(f"⚠️  {best_stock['ticker']} doesn't meet criteria - Skipped")
            return None

        logger.info(
            f"🎯 {best_stock['ticker']} | "
            f"Final={best_stock['score']:.4f} (Price={best_stock['price_score']:.4f}, Fund={best_stock['fundamental_score']:.4f}) | "
            f"Win Rate: {best_stock['frequency']:.1%} | "
            f"EPS Beat: {best_stock['eps_beat_rate']:.0%}"
        )

        # Simulate the trade (wider stop loss for more aggressive strategy)
        trade_result = self.backtester.simulate_trade(
            ticker=best_stock['ticker'],
            entry_date=next_day,
            take_profit_pct=best_stock['avg_gain'],
            stop_loss_pct=best_stock['avg_drawdown'] * 1.5,  # 150% of historical drawdown (more risky)
            hold_days=5
        )

        if trade_result:
            position_size = self.capital * 0.85
            shares = position_size / trade_result['entry_price']
            trade_pnl = shares * trade_result['pnl']
            
            old_capital = self.capital
            self.capital += trade_pnl
            
            trade_result['shares'] = shares
            trade_result['position_size'] = position_size
            trade_result['trade_pnl'] = trade_pnl
            trade_result['capital_before'] = old_capital
            trade_result['capital_after'] = self.capital
            trade_result['analysis_date'] = current_date
            
            # Add fundamental metrics from analysis
            trade_result['price_score'] = best_stock['price_score']
            trade_result['fundamental_score'] = best_stock['fundamental_score']
            trade_result['eps_beat_rate'] = best_stock['eps_beat_rate']
            trade_result['avg_eps_surprise'] = best_stock['avg_eps_surprise']
            trade_result['analyst_rating'] = best_stock['analyst_rating']
            
            result_emoji = "🟢" if trade_pnl > 0 else "🔴"
            logger.info(f"{result_emoji} {trade_result['exit_reason']} | P&L: ${trade_pnl:+,.2f} ({trade_result['pnl_percent']:+.2f}%)")
            
            self.trades.append(trade_result)
            return trade_result
        else:
            logger.info("❌ Trade simulation failed")
            return None

    def run_full_backtest(self, weeks: int = 3) -> Dict[str, Any]:
        """
        Run full backtest for specified number of weeks.
        
        Args:
            weeks: Number of weeks to backtest
            
        Returns:
            Dictionary with complete backtest results
        """
        end_date = date.today()
        start_date = end_date - timedelta(weeks=weeks)
        total_days = (end_date - start_date).days + 1
        
        print(f"\n{'='*60}")
        print(f"🚀 FULL BACKTEST - {weeks} Weeks")
        print(f"{'='*60}")
        print(f"Period:          {start_date} to {end_date}")
        print(f"Total Days:      {total_days}")
        print(f"Initial Capital: ${self.initial_capital:,.2f}")
        print(f"Position Size:   85% of capital")
        print(f"Max Hold:        5 days")
        
        api_key = os.getenv('FINNHUB_API_KEY')
        if api_key and api_key != 'your_finnhub_api_key_here':
            print(f"Data Source:     Finnhub API (Real Data)")
        else:
            print(f"Data Source:     Sample Data (Add FINNHUB_API_KEY for real data)")
        
        print(f"{'='*60}\n")
        
        # Simulate each day
        current_date = start_date
        day_num = 1
        
        while current_date <= end_date:
            self.daily_log.append({
                'date': current_date,
                'capital': self.capital
            })
            
            self.simulate_day(current_date, day_num, total_days)
            current_date += timedelta(days=1)
            day_num += 1
            
            # Small delay to avoid rate limiting
            time.sleep(0.1)

        # Calculate final statistics
        return self.calculate_statistics()

    def calculate_statistics(self) -> Dict[str, Any]:
        """Calculate final backtest statistics."""
        if not self.trades:
            return {
                'error': 'No trades executed',
                'initial_capital': self.initial_capital,
                'final_capital': self.capital
            }

        total_pnl = self.capital - self.initial_capital
        total_pnl_pct = (total_pnl / self.initial_capital) * 100

        wins = [t for t in self.trades if t['pnl'] > 0]
        losses = [t for t in self.trades if t['pnl'] <= 0]

        win_rate = (len(wins) / len(self.trades)) * 100 if self.trades else 0

        avg_win = sum(t['trade_pnl'] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t['trade_pnl'] for t in losses) / len(losses) if losses else 0

        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0

        # Calculate max drawdown
        max_capital = self.initial_capital
        max_drawdown = 0
        for log in self.daily_log:
            max_capital = max(max_capital, log['capital'])
            drawdown = (max_capital - log['capital']) / max_capital
            max_drawdown = max(max_drawdown, drawdown)

        return {
            'initial_capital': self.initial_capital,
            'final_capital': self.capital,
            'total_pnl': total_pnl,
            'total_pnl_percent': total_pnl_pct,
            'num_trades': len(self.trades),
            'num_wins': len(wins),
            'num_losses': len(losses),
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown * 100,
            'trades': self.trades,
            'daily_log': self.daily_log
        }

    def print_report(self, results: Dict[str, Any]) -> None:
        """Print formatted backtest report."""
        if 'error' in results:
            print(f"\n❌ {results['error']}")
            return

        print(f"\n")
        print(f"╔{'═'*58}╗")
        print(f"║{' '*15}FULL BACKTEST RESULTS{' '*22}║")
        print(f"╚{'═'*58}╝")
        print(f"")
        print(f"💰 CAPITAL")
        print(f"   Initial:        ${results['initial_capital']:>12,.2f}")
        print(f"   Final:          ${results['final_capital']:>12,.2f}")
        print(f"   Total P&L:      ${results['total_pnl']:>+12,.2f}  ({results['total_pnl_percent']:+.2f}%)")
        print(f"")
        print(f"📊 TRADES")
        print(f"   Total:          {results['num_trades']:>12}")
        print(f"   Wins:           {results['num_wins']:>12}  {'🟢' if results['num_wins'] > results['num_losses'] else ''}")
        print(f"   Losses:         {results['num_losses']:>12}  {'🔴' if results['num_losses'] > results['num_wins'] else ''}")
        print(f"   Win Rate:       {results['win_rate']:>11.1f}%")
        print(f"")
        print(f"💵 PERFORMANCE")
        print(f"   Avg Win:        ${results['avg_win']:>12,.2f}")
        print(f"   Avg Loss:       ${results['avg_loss']:>12,.2f}")
        print(f"   Profit Factor:  {results['profit_factor']:>12.2f}")
        print(f"   Max Drawdown:   {results['max_drawdown']:>11.2f}%")
        print(f"")
        print(f"{'─'*60}")
        print(f"\n📋 TRADE DETAILS:\n")
        
        for i, trade in enumerate(results['trades'], 1):
            status = "🟢 WIN" if trade['trade_pnl'] > 0 else "🔴 LOSS"
            print(f"{i}. {trade['ticker']:5} {status}")
            print(f"   Analysis: {trade['analysis_date']}")
            print(f"   Entry:    {trade['entry_date']} @ ${trade['entry_price']:.2f}")
            print(f"   Exit:     {trade['exit_date']} @ ${trade['exit_price']:.2f}")
            print(f"   Reason:   {trade['exit_reason']}")
            print(f"   P&L:      ${trade['trade_pnl']:+,.2f} ({trade['pnl_percent']:+.2f}%)")
            print(f"   Capital:  ${trade['capital_before']:,.2f} → ${trade['capital_after']:,.2f}")
            # Show fundamental metrics if available
            if 'fundamental_score' in trade:
                print(f"   Scores:   Price={trade.get('price_score', 0):.4f}, Fund={trade.get('fundamental_score', 0):.4f}")
                print(f"   Metrics:  EPS Beat={trade.get('eps_beat_rate', 0):.0%}, EPS Surprise={trade.get('avg_eps_surprise', 0):+.1f}%, Analyst={trade.get('analyst_rating', 0):.2f}")
            print()


def main():
    """Run full backtest."""
    # Run backtest
    backtester = FullBacktester()
    results = backtester.run_full_backtest(weeks=3)
    
    # Print results
    backtester.print_report(results)
    
    # Export to CSV
    if results.get('trades'):
        df = pd.DataFrame(results['trades'])
        df.to_csv('backtest_results.csv', index=False)
        print(f"\n💾 Detailed results: backtest_results.csv")
        
        # Also export daily capital log
        daily_df = pd.DataFrame(results['daily_log'])
        daily_df.to_csv('backtest_daily.csv', index=False)
        print(f"💾 Daily log:        backtest_daily.csv\n")


if __name__ == "__main__":
    main()

