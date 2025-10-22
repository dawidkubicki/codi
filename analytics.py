"""
Performance analytics module.
Provides statistics and reporting on trading performance.
"""
import logging
from typing import Dict, Any, List
from datetime import date, datetime, timedelta
from database import Database

logger = logging.getLogger(__name__)


class Analytics:
    """Handles performance analytics and reporting."""

    def __init__(self, database: Database):
        """Initialize analytics."""
        self.db = database

    def get_performance_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive performance summary for the last N days."""
        stats = self.db.get_trade_statistics(days)

        if not stats or stats.get('total_trades', 0) == 0:
            return {
                'period_days': days,
                'total_trades': 0,
                'message': 'No trades in this period'
            }

        win_rate = (
            (stats['winning_trades'] / stats['total_trades'] * 100)
            if stats['total_trades'] > 0 else 0
        )

        # Calculate profit factor
        winning_pnl = 0
        losing_pnl = 0

        # We'd need to query this separately, simplified here
        profit_factor = 0
        if stats['winning_trades'] > 0 and stats['losing_trades'] > 0:
            # Rough estimate
            avg_win = stats['max_win'] if stats['max_win'] else 0
            avg_loss = abs(stats['max_loss']) if stats['max_loss'] else 0
            if avg_loss > 0:
                profit_factor = avg_win / avg_loss

        return {
            'period_days': days,
            'total_trades': stats['total_trades'],
            'winning_trades': stats['winning_trades'],
            'losing_trades': stats['losing_trades'],
            'win_rate': win_rate,
            'total_pnl': stats['total_pnl'],
            'avg_pnl': stats['avg_pnl'],
            'avg_pnl_percent': stats['avg_pnl_percent'],
            'max_win': stats['max_win'],
            'max_loss': stats['max_loss'],
            'profit_factor': profit_factor
        }

    def get_daily_summary(self, target_date: str) -> Dict[str, Any]:
        """Get summary for a specific date."""
        total_pnl = self.db.get_daily_pnl(target_date)

        # Get trades for that day
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as count,
                       SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins
                FROM trades
                WHERE DATE(exit_time) = ? AND status = 'closed'
            """, (target_date,))
            result = cursor.fetchone()

            num_trades = result['count'] if result else 0
            wins = result['wins'] if result else 0

        win_rate = (wins / num_trades * 100) if num_trades > 0 else 0

        return {
            'date': target_date,
            'total_pnl': total_pnl,
            'num_trades': num_trades,
            'wins': wins,
            'losses': num_trades - wins,
            'win_rate': win_rate
        }

    def get_equity_curve(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get equity curve data for the last N days."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT date, ending_balance, pnl, pnl_percent
                FROM daily_performance
                WHERE date >= date('now', '-' || ? || ' days')
                ORDER BY date ASC
            """, (days,))

            return [dict(row) for row in cursor.fetchall()]

    def get_best_and_worst_trades(self, limit: int = 5) -> Dict[str, List[Dict[str, Any]]]:
        """Get best and worst performing trades."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Best trades
            cursor.execute("""
                SELECT ticker, entry_time, exit_time, entry_price, exit_price,
                       pnl, pnl_percent
                FROM trades
                WHERE status = 'closed'
                ORDER BY pnl DESC
                LIMIT ?
            """, (limit,))
            best = [dict(row) for row in cursor.fetchall()]

            # Worst trades
            cursor.execute("""
                SELECT ticker, entry_time, exit_time, entry_price, exit_price,
                       pnl, pnl_percent
                FROM trades
                WHERE status = 'closed'
                ORDER BY pnl ASC
                LIMIT ?
            """, (limit,))
            worst = [dict(row) for row in cursor.fetchall()]

        return {'best': best, 'worst': worst}

    def get_ticker_performance(self) -> List[Dict[str, Any]]:
        """Get performance grouped by ticker."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    ticker,
                    COUNT(*) as num_trades,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(pnl) as total_pnl,
                    AVG(pnl) as avg_pnl,
                    AVG(pnl_percent) as avg_pnl_percent
                FROM trades
                WHERE status = 'closed'
                GROUP BY ticker
                ORDER BY total_pnl DESC
            """)

            results = []
            for row in cursor.fetchall():
                row_dict = dict(row)
                row_dict['win_rate'] = (
                    (row_dict['wins'] / row_dict['num_trades'] * 100)
                    if row_dict['num_trades'] > 0 else 0
                )
                results.append(row_dict)

            return results

    def format_summary_report(self, days: int = 30) -> str:
        """Generate a formatted text report of performance."""
        summary = self.get_performance_summary(days)

        if summary.get('total_trades', 0) == 0:
            return f"No trades in the last {days} days."

        report = f"""
=== PERFORMANCE SUMMARY ({days} days) ===

Total Trades: {summary['total_trades']}
Wins: {summary['winning_trades']} | Losses: {summary['losing_trades']}
Win Rate: {summary['win_rate']:.1f}%

Total P&L: ${summary['total_pnl']:.2f}
Average P&L: ${summary['avg_pnl']:.2f} ({summary['avg_pnl_percent']:.2f}%)

Best Trade: ${summary['max_win']:.2f}
Worst Trade: ${summary['max_loss']:.2f}
Profit Factor: {summary['profit_factor']:.2f}

=====================================
        """

        return report.strip()

    def get_monthly_summary(self) -> Dict[str, Any]:
        """Get summary for the current month."""
        today = date.today()
        first_day = today.replace(day=1)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(pnl) as total_pnl,
                    AVG(pnl) as avg_pnl
                FROM trades
                WHERE DATE(exit_time) >= ? AND status = 'closed'
            """, (first_day.isoformat(),))

            result = cursor.fetchone()
            if result:
                data = dict(result)
                data['win_rate'] = (
                    (data['wins'] / data['total_trades'] * 100)
                    if data['total_trades'] and data['total_trades'] > 0 else 0
                )
                return data

        return {'total_trades': 0}

