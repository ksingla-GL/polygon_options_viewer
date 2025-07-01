# -*- coding: utf-8 -*-
"""
Created on Mon Jun 30 22:30:15 2025

@author: kshit
"""

"""
Debug script to identify ATM strike calculation issues
Run this to understand why ATM strikes are so far from the current price
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils.polygon_api import PolygonOptionsAPI

# Load environment variables
load_dotenv()

def debug_option_chain():
    """Comprehensive debugging of option chain data"""
    
    # Initialize API
    api_key = os.getenv('POLYGON_API_KEY')
    if not api_key:
        print("❌ No API key found!")
        return
    
    api = PolygonOptionsAPI(api_key)
    
    # Test parameters
    ticker = "SPY"
    test_date = "2025-06-29"  # Your test date
    
    print(f"🔍 Debugging Option Chain for {ticker} on {test_date}")
    print("=" * 60)
    
    # Step 1: Check stock price
    print("\n📈 STEP 1: Checking Stock Price")
    stock_price = api.get_stock_price(ticker, test_date)
    if not stock_price:
        print(f"  ❌ No stock price for {test_date}, trying previous close...")
        stock_price = api.get_previous_close(ticker)
    
    print(f"  Current/Previous Price: ${stock_price:.2f}")
    
    # Step 2: Get available expirations
    print("\n📅 STEP 2: Checking Available Expirations")
    expirations = api.get_available_expirations(ticker, test_date)
    print(f"  Found {len(expirations)} expirations")
    if expirations:
        print(f"  Next 5 expirations: {expirations[:5]}")
        test_expiration = "2025-06-30"  # Your test expiration
        if test_expiration in expirations:
            print(f"  ✅ Test expiration {test_expiration} is available")
        else:
            print(f"  ❌ Test expiration {test_expiration} NOT in available list!")
    
    # Step 3: Get option chain for the expiration
    print(f"\n⛓️ STEP 3: Fetching Option Chain for {test_expiration}")
    option_chain = api.get_option_chain(ticker, test_expiration, test_date)
    
    if option_chain.empty:
        print("  ❌ No option data returned!")
        return
    
    print(f"  ✅ Retrieved {len(option_chain)} options")
    
    # Step 4: Analyze strikes
    print("\n🎯 STEP 4: Analyzing Strikes")
    strikes = sorted(option_chain['strike'].unique())
    print(f"  Total unique strikes: {len(strikes)}")
    print(f"  Strike range: ${min(strikes):.2f} - ${max(strikes):.2f}")
    print(f"  Stock price: ${stock_price:.2f}")
    
    # Check if stock price is within strike range
    if stock_price < min(strikes):
        print(f"  ⚠️ WARNING: Stock price ${stock_price:.2f} is BELOW all strikes!")
        print(f"  Lowest strike: ${min(strikes):.2f}")
        print(f"  This explains why all options appear far OTM!")
    elif stock_price > max(strikes):
        print(f"  ⚠️ WARNING: Stock price ${stock_price:.2f} is ABOVE all strikes!")
        print(f"  Highest strike: ${max(strikes):.2f}")
        print(f"  This explains why all options appear far ITM!")
    else:
        print(f"  ✅ Stock price is within strike range")
    
    # Find closest strike to stock price
    atm_strike = min(strikes, key=lambda x: abs(x - stock_price))
    distance = abs(atm_strike - stock_price)
    distance_pct = (distance / stock_price) * 100
    
    print(f"\n  Calculated ATM strike: ${atm_strike:.2f}")
    print(f"  Distance from stock price: ${distance:.2f} ({distance_pct:.1f}%)")
    
    if distance_pct > 5:
        print(f"  ⚠️ WARNING: ATM strike is more than 5% away from stock price!")
        print(f"  This indicates a serious data mismatch!")
    
    # Step 5: Check data quality around ATM
    print(f"\n📊 STEP 5: Data Quality Check Around ATM Strike ${atm_strike:.2f}")
    
    # Get 5 strikes around ATM
    atm_index = strikes.index(atm_strike)
    start_idx = max(0, atm_index - 2)
    end_idx = min(len(strikes), atm_index + 3)
    nearby_strikes = strikes[start_idx:end_idx]
    
    print("\n  Checking nearby strikes:")
    for strike in nearby_strikes:
        call_data = option_chain[(option_chain['strike'] == strike) & (option_chain['type'] == 'call')]
        put_data = option_chain[(option_chain['strike'] == strike) & (option_chain['type'] == 'put')]
        
        if not call_data.empty:
            call = call_data.iloc[0]
            call_bid = call.get('bid', 'N/A')
            call_ask = call.get('ask', 'N/A')
            call_vol = call.get('volume', 0)
            
            # Check if call is ITM/OTM
            if strike < stock_price:
                intrinsic = stock_price - strike
                status = f"ITM by ${intrinsic:.2f}"
            else:
                status = f"OTM by ${strike - stock_price:.2f}"
            
            print(f"    Strike ${strike:.2f} CALL - {status}")
            print(f"      Bid: {call_bid}, Ask: {call_ask}, Volume: {call_vol}")
            
            # Flag issues
            if strike < stock_price and pd.isna(call_bid):
                print(f"      ⚠️ ITM call with no bid - DATA ISSUE!")
    
    # Step 6: Look for strikes closer to current price
    print(f"\n🔍 STEP 6: Searching for Strikes Closer to ${stock_price:.2f}")
    
    # What strikes would we expect for SPY at $614?
    expected_strikes = [round(stock_price + i, 0) for i in range(-10, 11)]
    print(f"  Expected strikes around ${stock_price:.2f}: {expected_strikes[:5]}...{expected_strikes[-5:]}")
    
    # Check if any expected strikes exist
    missing_strikes = [s for s in expected_strikes if s not in strikes]
    if missing_strikes:
        print(f"  ❌ Missing {len(missing_strikes)} expected strikes")
        print(f"  Missing range: ${min(missing_strikes):.0f} - ${max(missing_strikes):.0f}")
    
    # Step 7: Diagnosis
    print("\n🏥 DIAGNOSIS:")
    if stock_price > max(strikes) * 1.1:
        print("  The option chain data appears to be severely outdated or for the wrong date.")
        print("  SPY has likely had a significant move since this option data was created.")
        print("\n  POSSIBLE CAUSES:")
        print("  1. Using historical option data that doesn't match the stock price date")
        print("  2. Data provider issue - options not updated")
        print("  3. Selecting an expiration that's not actively traded")
        print("\n  RECOMMENDED FIXES:")
        print("  1. Use a more recent date closer to today")
        print("  2. Check if the Polygon subscription includes real-time option chains")
        print("  3. Verify the expiration date has active trading")
    
    return {
        'stock_price': stock_price,
        'strikes': strikes,
        'atm_strike': atm_strike,
        'distance_pct': distance_pct,
        'option_chain': option_chain
    }

# Run the debug if this script is executed directly
if __name__ == "__main__":
    print("🚀 Starting Option Chain Debugger\n")
    results = debug_option_chain()
    
    if results:
        print("\n\n📋 SUMMARY:")
        print(f"Stock Price: ${results['stock_price']:.2f}")
        print(f"Strike Range: ${min(results['strikes']):.2f} - ${max(results['strikes']):.2f}")
        print(f"Calculated ATM: ${results['atm_strike']:.2f}")
        print(f"Distance from Stock: {results['distance_pct']:.1f}%")
        
        # Offer to save debug data
        print("\n💾 Saving debug data to 'option_chain_debug.csv'...")
        results['option_chain'].to_csv('option_chain_debug.csv', index=False)
        print("✅ Debug data saved!")