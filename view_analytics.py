"""
View trading bot analytics and performance.
Run this script to see your trading statistics.

Usage:
    python view_analytics.py
"""
from database import Database
from analytics import Analytics
from config import config


def main():
    """Display trading analytics."""
    print("=" * 60)
    print("TRADING BOT ANALYTICS")
    print("=" * 60)
    print()

    # Initialize database and analytics
    db = Database(config.bot.database_path)
    analytics = Analytics(db)

    # Performance Summary (last 30 days)
    print("📊 PERFORMANCE SUMMARY (Last 30 Days)")
    print("-" * 60)
    summary = analytics.get_performance_summary(days=30)

    if summary.get('total_trades', 0) > 0:
        print(f"Total Trades:      {summary['total_trades']}")
        print(f"Wins:              {summary['winning_trades']}")
        print(f"Losses:            {summary['losing_trades']}")
        print(f"Win Rate:          {summary['win_rate']:.1f}%")
        print()
        print(f"Total P&L:         ${summary['total_pnl']:,.2f}")
        print(f"Average P&L:       ${summary['avg_pnl']:,.2f}")
        print(f"Avg P&L %:         {summary['avg_pnl_percent']:.2f}%")
        print()
        print(f"Best Win:          ${summary['max_win']:,.2f}")
        print(f"Worst Loss:        ${summary['max_loss']:,.2f}")
        print(f"Profit Factor:     {summary['profit_factor']:.2f}")
    else:
        print("No trades recorded yet.")

    print()
    print("-" * 60)
    print()

    # Best and Worst Trades
    print("🏆 BEST AND WORST TRADES")
    print("-" * 60)
    trades = analytics.get_best_and_worst_trades(limit=3)

    if trades['best']:
        print("\nBest Trades:")
        for i, trade in enumerate(trades['best'], 1):
            print(f"{i}. {trade['ticker']}: ${trade['pnl']:+,.2f} ({trade['pnl_percent']:+.2f}%)")

    if trades['worst']:
        print("\nWorst Trades:")
        for i, trade in enumerate(trades['worst'], 1):
            print(f"{i}. {trade['ticker']}: ${trade['pnl']:+,.2f} ({trade['pnl_percent']:+.2f}%)")

    print()
    print("-" * 60)
    print()

    # Performance by Ticker
    print("📈 PERFORMANCE BY TICKER")
    print("-" * 60)
    ticker_perf = analytics.get_ticker_performance()

    if ticker_perf:
        print(f"\n{'Ticker':<8} {'Trades':<8} {'Wins':<6} {'Win%':<8} {'Total P&L':<12} {'Avg P&L'}")
        print("-" * 60)
        for perf in ticker_perf[:10]:  # Top 10
            print(
                f"{perf['ticker']:<8} "
                f"{perf['num_trades']:<8} "
                f"{perf['wins']:<6} "
                f"{perf['win_rate']:<7.1f}% "
                f"${perf['total_pnl']:<11,.2f} "
                f"${perf['avg_pnl']:,.2f}"
            )
    else:
        print("No ticker data available.")

    print()
    print("-" * 60)
    print()

    # Monthly Summary
    print("📅 CURRENT MONTH SUMMARY")
    print("-" * 60)
    monthly = analytics.get_monthly_summary()

    if monthly.get('total_trades', 0) > 0:
        print(f"Total Trades:      {monthly['total_trades']}")
        print(f"Wins:              {monthly['wins']}")
        print(f"Win Rate:          {monthly['win_rate']:.1f}%")
        print(f"Total P&L:         ${monthly['total_pnl']:,.2f}")
        print(f"Average P&L:       ${monthly['avg_pnl']:,.2f}")
    else:
        print("No trades this month.")

    print()
    print("=" * 60)
    print()

    # All Trades
    print("📋 RECENT TRADES (Last 10)")
    print("-" * 60)
    all_trades = db.get_all_trades(limit=10)

    if all_trades:
        print(f"\n{'Ticker':<8} {'Entry':<12} {'Exit':<12} {'P&L':<12} {'P&L %':<10} {'Status'}")
        print("-" * 60)
        for trade in all_trades:
            entry_str = f"${trade['entry_price']:.2f}"
            exit_str = f"${trade['exit_price']:.2f}" if trade['exit_price'] else "Open"
            pnl_str = f"${trade['pnl']:.2f}" if trade['pnl'] else "-"
            pnl_pct_str = f"{trade['pnl_percent']:+.2f}%" if trade['pnl_percent'] else "-"

            print(
                f"{trade['ticker']:<8} "
                f"{entry_str:<12} "
                f"{exit_str:<12} "
                f"{pnl_str:<12} "
                f"{pnl_pct_str:<10} "
                f"{trade['status']}"
            )
    else:
        print("No trades recorded.")

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()

