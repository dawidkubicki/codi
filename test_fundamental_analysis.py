"""
Quick test script to verify the enhanced fundamental analysis system.
Tests the get_fundamental_metrics method with a few well-known stocks.
"""
import logging
from analyzer import StockAnalyzer
from config import config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_fundamental_analysis():
    """Test fundamental analysis on sample stocks."""
    
    # Initialize analyzer (no Finnhub needed for this test)
    analyzer = StockAnalyzer(
        finnhub_client=None,
        analysis_config=config.analysis
    )
    
    # Test stocks with good data availability
    test_tickers = ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'GOOGL']
    
    print("="*80)
    print("TESTING FUNDAMENTAL ANALYSIS")
    print("="*80)
    print()
    
    for ticker in test_tickers:
        print(f"\n{'='*80}")
        print(f"Analyzing {ticker}")
        print(f"{'='*80}")
        
        try:
            # Get fundamental metrics
            metrics = analyzer.get_fundamental_metrics(ticker)
            
            print(f"\n📊 Fundamental Metrics for {ticker}:")
            print(f"  • EPS Beat Rate:          {metrics['eps_beat_rate']:.1%}")
            print(f"  • Avg EPS Surprise:       {metrics['avg_eps_surprise_pct']:+.2f}%")
            print(f"  • Revenue Growth Score:   {metrics['revenue_growth_trend']:.2f} (0-1)")
            print(f"  • Analyst Rating Score:   {metrics['analyst_score']:.2f} (0-1)")
            print(f"  • Institutional Ownership: {metrics['institutional_ownership_pct']:.1f}%")
            
            # Calculate the fundamental score like the analyzer does
            normalized_eps_surprise = min(max((metrics['avg_eps_surprise_pct'] / 40.0) + 0.5, 0.0), 1.0)
            
            fundamental_score = (
                metrics['eps_beat_rate'] * 0.4 +
                normalized_eps_surprise * 0.3 +
                metrics['analyst_score'] * 0.2 +
                metrics['revenue_growth_trend'] * 0.1
            )
            
            print(f"\n  📈 Fundamental Score:     {fundamental_score:.4f}")
            
            # Interpret the score
            if fundamental_score >= 0.7:
                quality = "Excellent"
            elif fundamental_score >= 0.6:
                quality = "Good"
            elif fundamental_score >= 0.5:
                quality = "Average"
            elif fundamental_score >= 0.4:
                quality = "Below Average"
            else:
                quality = "Poor"
            
            print(f"  ✨ Quality Rating:        {quality}")
            
        except Exception as e:
            logger.error(f"Error analyzing {ticker}: {e}")
            continue
    
    print(f"\n{'='*80}")
    print("TEST COMPLETE")
    print(f"{'='*80}")
    print("\nIf you see fundamental data above, the enhancement is working correctly!")
    print("Scores near 0.5 indicate neutral/average metrics.")
    print("Scores above 0.6 indicate strong fundamentals.")
    print("Scores below 0.4 would be filtered out by the trading system.")

if __name__ == "__main__":
    test_fundamental_analysis()

