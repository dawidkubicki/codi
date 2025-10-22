"""
Database module for trade logging and persistence.
"""
import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class Database:
    """Handles all database operations for the trading bot."""

    def __init__(self, db_path: str):
        """Initialize database connection."""
        self.db_path = db_path
        self.init_database()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

    def init_database(self) -> None:
        """Initialize database schema."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Trades table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    entry_time TIMESTAMP NOT NULL,
                    exit_time TIMESTAMP,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    quantity REAL NOT NULL,
                    side TEXT NOT NULL,
                    score REAL,
                    avg_gain REAL,
                    avg_drawdown REAL,
                    frequency REAL,
                    take_profit_price REAL,
                    stop_loss_price REAL,
                    pnl REAL,
                    pnl_percent REAL,
                    status TEXT NOT NULL,
                    order_id TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Analysis results table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS analysis_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    analysis_date DATE NOT NULL,
                    earnings_date DATE,
                    score REAL NOT NULL,
                    avg_gain REAL NOT NULL,
                    avg_drawdown REAL NOT NULL,
                    frequency REAL NOT NULL,
                    selected BOOLEAN NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Daily performance table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL UNIQUE,
                    starting_balance REAL NOT NULL,
                    ending_balance REAL NOT NULL,
                    pnl REAL NOT NULL,
                    pnl_percent REAL NOT NULL,
                    num_trades INTEGER NOT NULL,
                    num_wins INTEGER NOT NULL,
                    num_losses INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Account snapshots table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS account_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP NOT NULL,
                    equity REAL NOT NULL,
                    cash REAL NOT NULL,
                    buying_power REAL NOT NULL,
                    portfolio_value REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            logger.info("Database initialized successfully")

    def log_trade_entry(self, ticker: str, entry_price: float, quantity: float,
                       score: float, avg_gain: float, avg_drawdown: float,
                       frequency: float, take_profit_price: float,
                       stop_loss_price: float, order_id: Optional[str] = None) -> int:
        """Log a new trade entry."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO trades (
                    ticker, entry_time, entry_price, quantity, side,
                    score, avg_gain, avg_drawdown, frequency,
                    take_profit_price, stop_loss_price, status, order_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticker, datetime.now(), entry_price, quantity, 'buy',
                score, avg_gain, avg_drawdown, frequency,
                take_profit_price, stop_loss_price, 'open', order_id
            ))
            trade_id = cursor.lastrowid
            logger.info(f"Trade entry logged: ID={trade_id}, {ticker}")
            return trade_id

    def log_trade_exit(self, ticker: str, exit_price: float,
                       pnl: float, pnl_percent: float) -> None:
        """Log trade exit."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE trades
                SET exit_time = ?, exit_price = ?, pnl = ?,
                    pnl_percent = ?, status = 'closed'
                WHERE ticker = ? AND status = 'open'
            """, (datetime.now(), exit_price, pnl, pnl_percent, ticker))
            logger.info(f"Trade exit logged: {ticker}, P&L: ${pnl:.2f} ({pnl_percent:.2f}%)")

    def log_analysis_result(self, ticker: str, analysis_date: str,
                           earnings_date: Optional[str], score: float,
                           avg_gain: float, avg_drawdown: float,
                           frequency: float, selected: bool) -> None:
        """Log analysis result for a stock."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO analysis_results (
                    ticker, analysis_date, earnings_date, score,
                    avg_gain, avg_drawdown, frequency, selected
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (ticker, analysis_date, earnings_date, score,
                  avg_gain, avg_drawdown, frequency, selected))

    def log_account_snapshot(self, equity: float, cash: float,
                            buying_power: float, portfolio_value: float) -> None:
        """Log account snapshot."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO account_snapshots (
                    timestamp, equity, cash, buying_power, portfolio_value
                ) VALUES (?, ?, ?, ?, ?)
            """, (datetime.now(), equity, cash, buying_power, portfolio_value))

    def get_open_trades(self) -> List[Dict[str, Any]]:
        """Get all open trades."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trades WHERE status = 'open'")
            return [dict(row) for row in cursor.fetchall()]

    def get_daily_pnl(self, date: str) -> Optional[float]:
        """Get total P&L for a specific date."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT SUM(pnl) as total_pnl
                FROM trades
                WHERE DATE(exit_time) = ?
            """, (date,))
            result = cursor.fetchone()
            return result['total_pnl'] if result['total_pnl'] else 0.0

    def get_trade_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get trade statistics for the last N days."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                    SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
                    SUM(pnl) as total_pnl,
                    AVG(pnl) as avg_pnl,
                    MAX(pnl) as max_win,
                    MIN(pnl) as max_loss,
                    AVG(pnl_percent) as avg_pnl_percent
                FROM trades
                WHERE status = 'closed'
                AND exit_time >= datetime('now', '-' || ? || ' days')
            """, (days,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return {}

    def get_all_trades(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent trades."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM trades
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def update_daily_performance(self, date: str, starting_balance: float,
                                ending_balance: float) -> None:
        """Update or insert daily performance."""
        pnl = ending_balance - starting_balance
        pnl_percent = (pnl / starting_balance * 100) if starting_balance > 0 else 0

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Get trade counts for the day
            cursor.execute("""
                SELECT
                    COUNT(*) as num_trades,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as num_wins,
                    SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as num_losses
                FROM trades
                WHERE DATE(exit_time) = ? AND status = 'closed'
            """, (date,))
            trade_stats = cursor.fetchone()

            cursor.execute("""
                INSERT OR REPLACE INTO daily_performance (
                    date, starting_balance, ending_balance, pnl, pnl_percent,
                    num_trades, num_wins, num_losses
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (date, starting_balance, ending_balance, pnl, pnl_percent,
                  trade_stats['num_trades'] or 0,
                  trade_stats['num_wins'] or 0,
                  trade_stats['num_losses'] or 0))

