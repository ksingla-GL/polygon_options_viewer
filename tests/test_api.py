"""
Enhanced test script to verify Polygon API access and S3 flat files functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.polygon_api import PolygonOptionsAPI
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime, timedelta

load_dotenv()

def test_api_access():
    """Test basic API and S3 functionality"""
    api_key = os.getenv('POLYGON_API_KEY')
    s3_access_key = os.getenv('POLYGON_S3_ACCESS_KEY')
    s3_secret_key = os.getenv('POLYGON_S3_SECRET_KEY')
    
    if not api_key:
        print("No API key found in .env file")
        return False
    
    print(f"API Key found: {api_key[:10]}...")
    
    # Check S3 credentials
    if s3_access_key and s3_secret_key:
        print(f"S3 credentials found")
        api = PolygonOptionsAPI(api_key, s3_access_key, s3_secret_key)
    else:
        print("No S3 credentials found - will use REST API only")
        api = PolygonOptionsAPI(api_key)
    
    # Test parameters
    test_ticker = "NVDA"
    test_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"\nTesting with {test_ticker} on {test_date}")
    
    # Test 1: Get stock price
    print("\nTest 1: Stock Price")
    price = api.get_stock_price(test_ticker, test_date)
    if price:
        print(f"  Current price: ${price:.2f}")
    else:
        print("  Could not fetch stock price, trying previous close...")
        price = api.get_previous_close(test_ticker)
        if price:
            print(f"  Previous close: ${price:.2f}")
        else:
            print("  Failed to fetch stock price")
    
    # Test 2: Test S3 Access (if available)
    if api.s3_client:
        print("\nTest 2: S3 Flat Files Access")
        try:
            # Try to fetch aggregates data
            aggs_df = api.get_s3_options_data(test_date, 'day_aggs_v1')
            if not aggs_df.empty:
                print(f"  Successfully fetched {len(aggs_df)} aggregate records")
                
                # Check for NVDA options
                nvda_options = aggs_df[aggs_df['ticker'].str.startswith('O:NVDA')]
                print(f"  Found {len(nvda_options)} NVDA option contracts")
                
                # Sample data
                if len(nvda_options) > 0:
                    sample = nvda_options.head(3)
                    print("  Sample data:")
                    for _, row in sample.iterrows():
                        print(f"    {row['ticker']}: Vol={row['volume']}, "
                              f"OHLC=[{row['open']:.2f}, {row['high']:.2f}, "
                              f"{row['low']:.2f}, {row['close']:.2f}]")
            else:
                print("  No aggregate data found for this date")
                
        except Exception as e:
            print(f"  S3 access failed: {e}")
    
    # Test 3: Get available expirations
    print("\nTest 3: Available Expirations")
    expirations = api.get_available_expirations(test_ticker, test_date)
    if expirations:
        print(f"  Found {len(expirations)} expiration dates")
        print(f"  Next 5 expirations: {expirations[:5]}")
        test_expiration = expirations[0]
    else:
        print("  Failed to fetch expirations")
        return False
    
    # Test 4: Get option chain with S3 enhancement
    print(f"\nTest 4: Option Chain for {test_expiration}")
    option_chain = api.get_option_chain(test_ticker, test_expiration, test_date)
    
    if not option_chain.empty:
        print(f"  Found {len(option_chain)} options")
        
        # Check data sources
        if 'data_source' in option_chain.columns:
            sources = option_chain['data_source'].value_counts()
            print("  Data sources:")
            for source, count in sources.items():
                print(f"    - {source}: {count} options")
        
        # Analyze data quality
        calls = option_chain[option_chain['type'] == 'call']
        puts = option_chain[option_chain['type'] == 'put']
        
        print(f"  Calls: {len(calls)}, Puts: {len(puts)}")
        
        # Check bid/ask availability
        with_quotes = option_chain.dropna(subset=['bid', 'ask'])
        print(f"  Options with bid/ask: {len(with_quotes)} ({len(with_quotes)/len(option_chain)*100:.1f}%)")
        
        # Check volume data
        with_volume = option_chain[option_chain['volume'] > 0]
        print(f"  Options with volume: {len(with_volume)} ({len(with_volume)/len(option_chain)*100:.1f}%)")
        
        # Check Greeks if available
        if 'delta' in option_chain.columns:
            with_greeks = option_chain.dropna(subset=['delta'])
            print(f"  Options with Greeks: {len(with_greeks)} ({len(with_greeks)/len(option_chain)*100:.1f}%)")
        
        # Sample data with more details
        print("\n  Sample option data (sorted by volume):")
        sample = option_chain.nlargest(3, 'volume')
        for _, opt in sample.iterrows():
            print(f"    {opt['type'].upper()} {opt['strike']} - "
                  f"Bid: ${opt.get('bid', 'N/A')}, Ask: ${opt.get('ask', 'N/A')}, "
                  f"Last: ${opt.get('last', 'N/A')}, Vol: {opt['volume']}")
            if 'delta' in opt and pd.notna(opt['delta']):
                print(f"      Greeks: Delta={opt['delta']:.3f}, Gamma={opt.get('gamma', 0):.3f}, "
                      f"Theta={opt.get('theta', 0):.3f}, Vega={opt.get('vega', 0):.3f}")
    else:
        print("  Failed to fetch option chain or no data available")
    
    # Test 5: Test Greeks calculation
    if price:
        print("\nTest 5: Greeks Calculation")
        test_greeks = api.calculate_greeks(
            S=price, K=price * 1.05, T=0.083, r=0.05, 
            sigma=0.25, option_type='call'
        )
        print(f"  Sample Greeks for OTM Call:")
        for greek, value in test_greeks.items():
            print(f"    {greek}: {value}")
    
    return True

def test_s3_data_formats():
    """Test different S3 data formats"""
    s3_access_key = os.getenv('POLYGON_S3_ACCESS_KEY')
    s3_secret_key = os.getenv('POLYGON_S3_SECRET_KEY')
    
    if not s3_access_key or not s3_secret_key:
        print("\nSkipping S3 format tests - no credentials")
        return
    
    print("\nTesting S3 Data Formats")
    api = PolygonOptionsAPI(os.getenv('POLYGON_API_KEY'), s3_access_key, s3_secret_key)
    
    test_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    # Test different data types
    data_types = ['day_aggs_v1', 'minute_aggs_v1']
    
    for data_type in data_types:
        print(f"\n  Testing {data_type}:")
        try:
            df = api.get_s3_options_data(test_date, data_type)
            if not df.empty:
                print(f"    Loaded {len(df)} records")
                print(f"    Columns: {', '.join(df.columns)}")
                print(f"    Sample tickers: {', '.join(df['ticker'].head(5).tolist())}")
            else:
                print(f"    No data found")
        except Exception as e:
            print(f"    Error: {e}")

if __name__ == "__main__":
    print("Enhanced Polygon API Test Suite with S3 Support")
    print("="*60)
    
    if test_api_access():
        test_s3_data_formats()
        print("\nAll tests completed! You can now run the app with: streamlit run app.py")
        print("\nNote: Make sure your .env file contains:")
        print("   POLYGON_API_KEY=your_api_key")
        print("   POLYGON_S3_ACCESS_KEY=your_s3_access_key")
        print("   POLYGON_S3_SECRET_KEY=your_s3_secret_key")
    else:
        print("\nTests failed. Please check your API key and connection.")