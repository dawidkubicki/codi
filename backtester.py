"""
Backtesting module.
Test trading strategies on historical data.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import date, timedelta, datetime
import pandas as pd
import os
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from analyzer import StockAnalyzer
from config import AnalysisConfig

logger = logging.getLogger(__name__)


class Backtester:
    """Backtests the earnings jump strategy on historical data using Alpaca."""

    def __init__(self, analysis_config: AnalysisConfig):
        """Initialize backtester with Alpaca data client."""
        self.config = analysis_config
        self.results: List[Dict[str, Any]] = []
        
        # Initialize Alpaca data client (using IEX feed for free tier)
        alpaca_api_key = os.getenv('ALPACA_API_KEY')
        alpaca_secret_key = os.getenv('ALPACA_SECRET_KEY')
        
        if alpaca_api_key and alpaca_api_key != 'your_alpaca_api_key_here':
            self.alpaca_data = StockHistoricalDataClient(
                api_key=alpaca_api_key,
                secret_key=alpaca_secret_key,
                raw_data=False
            )
        else:
            self.alpaca_data = None

    def simulate_trade(self, ticker: str, entry_date: date,
                      take_profit_pct: float, stop_loss_pct: float,
                      hold_days: int = 5) -> Dict[str, Any]:
        """
        Simulate a single trade using Alpaca historical data.

        Args:
            ticker: Stock symbol
            entry_date: Date of entry
            take_profit_pct: Take profit percentage (e.g., 0.10 for 10%)
            stop_loss_pct: Stop loss percentage (e.g., -0.08 for -8%)
            hold_days: Maximum days to hold

        Returns:
            Dictionary with trade results
        """
        if not self.alpaca_data:
            logger.error("Alpaca data client not initialized")
            return None
            
        try:
            # Get historical data from Alpaca (using IEX feed for free tier)
            start_date = entry_date - timedelta(days=5)
            end_date = entry_date + timedelta(days=hold_days + 10)

            request_params = StockBarsRequest(
                symbol_or_symbols=[ticker],
                timeframe=TimeFrame.Day,
                start=start_date,
                end=end_date,
                feed='iex'  # Use IEX feed for free tier accounts
            )
            
            bars = self.alpaca_data.get_stock_bars(request_params)
            
            if ticker not in bars.data or not bars.data[ticker]:
                logger.warning(f"No data for {ticker} around {entry_date}")
                return None

            # Convert to DataFrame
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

            # Find entry price (close on entry date or nearest)
            if entry_date not in df.index:
                # Find nearest trading day
                nearest = [d for d in df.index if d >= entry_date]
                if not nearest:
                    logger.warning(f"No trading data on or after {entry_date}")
                    return None
                entry_date = nearest[0]
            
            entry_price = df.loc[entry_date, 'close']

            # Calculate target prices
            take_profit_price = entry_price * (1 + take_profit_pct)
            stop_loss_price = entry_price * (1 + stop_loss_pct)

            # Get holding period data
            future_dates = [d for d in df.index if d > entry_date][:hold_days]
            
            if not future_dates:
                logger.warning(f"No future trading dates available for {ticker} after {entry_date}")
                return None

            # Simulate each day
            exit_date = None
            exit_price = None
            exit_reason = "Hold period expired"

            for trade_date in future_dates:
                row = df.loc[trade_date]
                
                # Check if take profit hit
                if row['high'] >= take_profit_price:
                    exit_date = trade_date
                    exit_price = take_profit_price
                    exit_reason = "Take profit hit"
                    break

                # Check if stop loss hit
                if row['low'] <= stop_loss_price:
                    exit_date = trade_date
                    exit_price = stop_loss_price
                    exit_reason = "Stop loss hit"
                    break

            # If neither hit, exit at close of last day
            if exit_price is None:
                exit_date = future_dates[-1]
                exit_price = df.loc[exit_date, 'close']

            # Calculate results
            pnl = exit_price - entry_price
            pnl_pct = (pnl / entry_price) * 100

            return {
                'ticker': ticker,
                'entry_date': entry_date,
                'exit_date': exit_date,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'pnl': pnl,
                'pnl_percent': pnl_pct,
                'exit_reason': exit_reason,
                'take_profit_price': take_profit_price,
                'stop_loss_price': stop_loss_price
            }

        except Exception as e:
            logger.error(f"Error simulating trade for {ticker}: {e}")
            return None

    def backtest_strategy(self, test_stocks: List[Dict[str, Any]],
                         initial_capital: float = 10000.0) -> Dict[str, Any]:
        """
        Backtest the strategy on a list of stocks.

        Args:
            test_stocks: List of dicts with 'ticker', 'entry_date', 'avg_gain', 'avg_drawdown'
            initial_capital: Starting capital for backtest

        Returns:
            Dictionary with backtest results
        """
        capital = initial_capital
        trades = []

        logger.info(f"Starting backtest with ${initial_capital:.2f}")
        logger.info(f"Testing {len(test_stocks)} trades")

        for stock_data in test_stocks:
            ticker = stock_data['ticker']
            entry_date = stock_data['entry_date']
            avg_gain = stock_data.get('avg_gain', 0.10)
            avg_drawdown = stock_data.get('avg_drawdown', -0.08)

            # Simulate the trade
            result = self.simulate_trade(
                ticker=ticker,
                entry_date=entry_date,
                take_profit_pct=avg_gain,
                stop_loss_pct=avg_drawdown * 1.1,  # 110% of historical drawdown (more risky)
                hold_days=5
            )

            if result:
                # Calculate position size (using 85% of capital)
                position_size = capital * 0.85
                shares = position_size / result['entry_price']
                trade_pnl = shares * result['pnl']
                capital += trade_pnl

                result['shares'] = shares
                result['position_size'] = position_size
                result['trade_pnl'] = trade_pnl
                result['capital_after'] = capital

                trades.append(result)

                logger.info(
                    f"{ticker}: {result['pnl_percent']:+.2f}% "
                    f"| P&L: ${trade_pnl:+.2f} | Capital: ${capital:.2f}"
                )

        # Calculate statistics
        if not trades:
            logger.warning("No successful trades in backtest")
            return {'error': 'No trades executed'}

        total_pnl = capital - initial_capital
        total_pnl_pct = (total_pnl / initial_capital) * 100

        wins = [t for t in trades if t['pnl'] > 0]
        losses = [t for t in trades if t['pnl'] <= 0]

        win_rate = (len(wins) / len(trades)) * 100 if trades else 0

        avg_win = sum(t['trade_pnl'] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t['trade_pnl'] for t in losses) / len(losses) if losses else 0

        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0

        max_capital = initial_capital
        max_drawdown = 0
        for trade in trades:
            max_capital = max(max_capital, trade['capital_after'])
            drawdown = (max_capital - trade['capital_after']) / max_capital
            max_drawdown = max(max_drawdown, drawdown)

        results = {
            'initial_capital': initial_capital,
            'final_capital': capital,
            'total_pnl': total_pnl,
            'total_pnl_percent': total_pnl_pct,
            'num_trades': len(trades),
            'num_wins': len(wins),
            'num_losses': len(losses),
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown * 100,
            'trades': trades
        }

        self.results = trades
        return results

    def print_backtest_report(self, results: Dict[str, Any]) -> str:
        """Generate a formatted backtest report."""
        if 'error' in results:
            return f"Backtest Error: {results['error']}"

        report = f"""
╔════════════════════════════════════════╗
║       BACKTEST RESULTS                 ║
╚════════════════════════════════════════╝

Initial Capital:  ${results['initial_capital']:,.2f}
Final Capital:    ${results['final_capital']:,.2f}
Total P&L:        ${results['total_pnl']:+,.2f} ({results['total_pnl_percent']:+.2f}%)

Total Trades:     {results['num_trades']}
Wins:             {results['num_wins']}
Losses:           {results['num_losses']}
Win Rate:         {results['win_rate']:.1f}%

Average Win:      ${results['avg_win']:,.2f}
Average Loss:     ${results['avg_loss']:,.2f}
Profit Factor:    {results['profit_factor']:.2f}

Max Drawdown:     {results['max_drawdown']:.2f}%

========================================
        """

        return report.strip()

    def export_results_to_csv(self, filename: str = "backtest_results.csv") -> bool:
        """Export backtest results to CSV."""
        if not self.results:
            logger.warning("No results to export")
            return False

        try:
            df = pd.DataFrame(self.results)
            df.to_csv(filename, index=False)
            logger.info(f"Results exported to {filename}")
            return True
        except Exception as e:
            logger.error(f"Error exporting results: {e}")
            return False

