"""
Script to fetch all tradable stocks from Alpaca API and save to stocks.txt.
This will query Alpaca for all tradable US equities on major exchanges.
Run this script periodically to update the stock list.
"""
import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest
from alpaca.trading.enums import AssetClass, AssetStatus

load_dotenv()

def fetch_tradable_stocks():
    """Fetch all tradable US equity stocks from Alpaca using the Trading API."""
    api_key = os.getenv('ALPACA_API_KEY')
    secret_key = os.getenv('ALPACA_SECRET_KEY')
    
    if not api_key or api_key == 'your_alpaca_api_key_here':
        print("ERROR: ALPACA_API_KEY not configured")
        return []
    
    if not secret_key or secret_key == 'your_alpaca_secret_key_here':
        print("ERROR: ALPACA_SECRET_KEY not configured")
        return []
    
    print(f"Fetching tradable stocks from Alpaca using Trading API...")
    
    try:
        # Initialize Alpaca Trading Client
        trading_client = TradingClient(api_key, secret_key, paper=True)
        
        # Create request for active US equity assets
        search_params = GetAssetsRequest(
            status=AssetStatus.ACTIVE,
            asset_class=AssetClass.US_EQUITY
        )
        
        # Get all assets
        assets = trading_client.get_all_assets(search_params)
        
        print(f"Retrieved {len(assets)} total US equity assets from Alpaca")
        
        # Filter for tradable stocks on major exchanges
        tradable_stocks = []
        for asset in assets:
            if (asset.tradable and 
                asset.status == 'active' and
                asset.exchange in ['NASDAQ', 'NYSE', 'ARCA', 'AMEX', 'NYSEARCA'] and
                asset.shortable):  # Shortable stocks tend to be more liquid
                tradable_stocks.append(asset.symbol)
        
        print(f"Found {len(tradable_stocks)} tradable, liquid US equity stocks on Alpaca")
        return sorted(tradable_stocks)
        
    except Exception as e:
        print(f"ERROR: Failed to fetch from Alpaca API: {e}")
        return []


def save_stocks_to_file(stocks, filename='stocks.txt'):
    """Save stock symbols to a file, one per line."""
    try:
        with open(filename, 'w') as f:
            f.write("# Tradable stocks from Alpaca\n")
            f.write(f"# Total: {len(stocks)} stocks\n")
            f.write(f"# Auto-generated - do not edit manually\n")
            f.write("# Run fetch_alpaca_stocks.py to update\n")
            f.write("#\n")
            for stock in stocks:
                f.write(f"{stock}\n")
        print(f"✓ Saved {len(stocks)} stocks to {filename}")
        return True
    except Exception as e:
        print(f"ERROR: Failed to save to {filename}: {e}")
        return False


if __name__ == "__main__":
    print("="*70)
    print("ALPACA TRADABLE STOCKS FETCHER")
    print("="*70)
    print()
    
    # Fetch from Alpaca
    alpaca_stocks = fetch_tradable_stocks()
    
    if not alpaca_stocks:
        print("\n❌ Failed to fetch stocks from Alpaca API")
        print("Make sure ALPACA_API_KEY and ALPACA_SECRET_KEY are set in .env")
        exit(1)
    
    # Save to stocks.txt
    print("\n💾 Saving stocks to stocks.txt...")
    if save_stocks_to_file(alpaca_stocks):
        print(f"\n✅ Successfully saved {len(alpaca_stocks)} tradable stocks to stocks.txt")
        print("   This file will be used by the trading bot")
    else:
        print("\n❌ Failed to save stocks to file")
        exit(1)
    
    print("\n" + "="*70)
    print("✅ DONE!")
    print("="*70)
    print(f"\nThe trading bot will now use {len(alpaca_stocks)} stocks from stocks.txt")
    print("Run this script periodically to update the stock list.")

