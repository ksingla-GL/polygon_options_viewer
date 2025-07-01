"""
Data formatting utilities for the options chain viewer
Enhanced with S3 data handling
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional

def format_number(value) -> str:
    """Format large numbers with commas"""
    if pd.isna(value) or value == 0:
        return '-'
    try:
        return f"{int(value):,}"
    except:
        return '-'

def format_price(value) -> str:
    """Format price values"""
    if pd.isna(value) or value is None:
        return '-'
    try:
        return f"{float(value):.2f}"
    except:
        return '-'

def format_change(value) -> str:
    """Format change values with + or - sign"""
    if pd.isna(value) or value is None:
        return '-'
    try:
        return f"{float(value):+.2f}"
    except:
        return '-'

def format_percent(value) -> str:
    """Format percentage values"""
    if pd.isna(value) or value is None:
        return '-'
    try:
        return f"{float(value):.1f}%"
    except:
        return '-'

def format_greek(value) -> str:
    """Format Greek values"""
    if pd.isna(value) or value is None:
        return '-'
    try:
        return f"{float(value):.3f}"
    except:
        return '-'

def get_strike_range_around_atm(strikes: List[float], current_price: float, 
                               num_strikes: int = 10) -> List[float]:
    """Get a range of strikes centered around ATM"""
    if not strikes:
        return []
    
    # Find ATM strike
    atm_strike = min(strikes, key=lambda x: abs(x - current_price))
    atm_index = strikes.index(atm_strike)
    
    # Get range
    start_idx = max(0, atm_index - num_strikes)
    end_idx = min(len(strikes), atm_index + num_strikes + 1)
    
    return strikes[start_idx:end_idx]

def parse_option_symbol(symbol: str) -> Optional[Dict[str, any]]:
    """
    Parse Polygon option symbol format
    Example: O:AAPL240119C00175000
    
    Returns:
        Dictionary with parsed components or None if invalid
    """
    if not symbol or not symbol.startswith('O:'):
        return None
    
    try:
        # Remove the O: prefix
        parts = symbol[2:]
        
        # Find where the ticker ends (first digit)
        ticker_end = 0
        for i, char in enumerate(parts):
            if char.isdigit():
                ticker_end = i
                break
        
        if ticker_end == 0:
            return None
        
        ticker = parts[:ticker_end]
        remaining = parts[ticker_end:]
        
        # Parse date (YYMMDD format)
        if len(remaining) < 7:
            return None
        
        date_str = remaining[:6]
        option_type = remaining[6]  # C or P
        strike_str = remaining[7:15]  # 8 digits for strike
        
        # Convert date
        from datetime import datetime
        expiration = datetime.strptime(date_str, "%y%m%d").strftime("%Y-%m-%d")
        
        # Convert strike (divided by 1000)
        strike = float(strike_str) / 1000
        
        return {
            'ticker': ticker,
            'expiration': expiration,
            'type': 'call' if option_type == 'C' else 'put',
            'strike': strike,
            'symbol': symbol
        }
    except:
        return None

def estimate_bid_ask_spread(last_price: float, volume: int, 
                           option_type: str = 'call') -> Tuple[float, float]:
    """
    Estimate bid/ask spread based on last price and volume
    
    Returns:
        Tuple of (bid, ask)
    """
    if last_price <= 0:
        return (0, 0)
    
    # Estimate spread percentage based on liquidity
    if volume > 10000:
        spread_pct = 0.02  # 2% for very liquid
    elif volume > 1000:
        spread_pct = 0.04  # 4% for liquid
    elif volume > 100:
        spread_pct = 0.08  # 8% for semi-liquid
    elif volume > 10:
        spread_pct = 0.15  # 15% for illiquid
    else:
        spread_pct = 0.25  # 25% for very illiquid
    
    # Calculate spread
    half_spread = last_price * spread_pct / 2
    
    # Ensure minimum tick size
    bid = max(0.01, round(last_price - half_spread, 2))
    ask = round(last_price + half_spread, 2)
    
    return (bid, ask)

def calculate_moneyness(stock_price: float, strike: float, 
                       option_type: str) -> Dict[str, any]:
    """
    Calculate moneyness metrics for an option
    
    Returns:
        Dictionary with moneyness info
    """
    if stock_price <= 0 or strike <= 0:
        return {
            'moneyness_pct': 0,
            'is_itm': False,
            'is_atm': False,
            'is_otm': False,
            'intrinsic_value': 0
        }
    
    # Calculate percentage moneyness
    moneyness_pct = ((stock_price - strike) / stock_price) * 100
    
    # Determine ITM/ATM/OTM status
    atm_threshold = 0.5  # 0.5% threshold for ATM
    
    if option_type.lower() == 'call':
        is_itm = stock_price > strike * (1 + atm_threshold/100)
        is_otm = stock_price < strike * (1 - atm_threshold/100)
        intrinsic_value = max(0, stock_price - strike)
    else:  # put
        is_itm = stock_price < strike * (1 - atm_threshold/100)
        is_otm = stock_price > strike * (1 + atm_threshold/100)
        intrinsic_value = max(0, strike - stock_price)
    
    is_atm = not is_itm and not is_otm
    
    return {
        'moneyness_pct': moneyness_pct,
        'is_itm': is_itm,
        'is_atm': is_atm,
        'is_otm': is_otm,
        'intrinsic_value': intrinsic_value
    }

def aggregate_option_metrics(option_chain: pd.DataFrame) -> Dict[str, any]:
    """
    Calculate aggregate metrics for an option chain
    
    Returns:
        Dictionary with summary statistics
    """
    if option_chain.empty:
        return {
            'total_call_volume': 0,
            'total_put_volume': 0,
            'total_call_oi': 0,
            'total_put_oi': 0,
            'pc_ratio_volume': 0,
            'pc_ratio_oi': 0,
            'avg_iv_calls': 0,
            'avg_iv_puts': 0,
            'num_contracts': 0
        }
    
    # Separate calls and puts
    calls = option_chain[option_chain['type'] == 'call']
    puts = option_chain[option_chain['type'] == 'put']
    
    # Volume metrics
    total_call_volume = calls['volume'].sum() if not calls.empty else 0
    total_put_volume = puts['volume'].sum() if not puts.empty else 0
    
    # Open interest metrics
    total_call_oi = calls['open_interest'].sum() if not calls.empty else 0
    total_put_oi = puts['open_interest'].sum() if not puts.empty else 0
    
    # Put/Call ratios
    pc_ratio_volume = total_put_volume / total_call_volume if total_call_volume > 0 else 0
    pc_ratio_oi = total_put_oi / total_call_oi if total_call_oi > 0 else 0
    
    # Average IV (if available)
    avg_iv_calls = 0
    avg_iv_puts = 0
    
    if 'implied_volatility' in option_chain.columns:
        if not calls.empty:
            calls_with_iv = calls.dropna(subset=['implied_volatility'])
            if not calls_with_iv.empty:
                avg_iv_calls = calls_with_iv['implied_volatility'].mean()
        
        if not puts.empty:
            puts_with_iv = puts.dropna(subset=['implied_volatility'])
            if not puts_with_iv.empty:
                avg_iv_puts = puts_with_iv['implied_volatility'].mean()
    
    return {
        'total_call_volume': int(total_call_volume),
        'total_put_volume': int(total_put_volume),
        'total_call_oi': int(total_call_oi),
        'total_put_oi': int(total_put_oi),
        'pc_ratio_volume': round(pc_ratio_volume, 2),
        'pc_ratio_oi': round(pc_ratio_oi, 2),
        'avg_iv_calls': round(avg_iv_calls, 3),
        'avg_iv_puts': round(avg_iv_puts, 3),
        'num_contracts': len(option_chain)
    }

def determine_market_sentiment(pc_ratio_volume: float, pc_ratio_oi: float) -> str:
    """
    Determine market sentiment based on put/call ratios
    
    Returns:
        Sentiment string with emoji
    """
    # Average the two ratios
    if pc_ratio_volume > 0 and pc_ratio_oi > 0:
        avg_pc_ratio = (pc_ratio_volume + pc_ratio_oi) / 2
    elif pc_ratio_volume > 0:
        avg_pc_ratio = pc_ratio_volume
    elif pc_ratio_oi > 0:
        avg_pc_ratio = pc_ratio_oi
    else:
        return "📊 No Data"
    
    # Determine sentiment
    if avg_pc_ratio > 1.2:
        return "🐻 Bearish"
    elif avg_pc_ratio > 1.0:
        return "🐻 Slightly Bearish"
    elif avg_pc_ratio < 0.7:
        return "🐂 Bullish"
    elif avg_pc_ratio < 0.9:
        return "🐂 Slightly Bullish"
    else:
        return "😐 Neutral"

def format_option_chain_for_display(option_chain: pd.DataFrame, 
                                   stock_price: float,
                                   strikes_around_atm: int = 10) -> pd.DataFrame:
    """
    Format option chain data for display in the UI
    
    Returns:
        Formatted DataFrame ready for display
    """
    if option_chain.empty:
        return pd.DataFrame()
    
    # Get unique strikes and filter around ATM
    strikes = sorted(option_chain['strike'].unique())
    display_strikes = get_strike_range_around_atm(strikes, stock_price, strikes_around_atm)
    
    # Filter to display strikes
    filtered_chain = option_chain[option_chain['strike'].isin(display_strikes)].copy()
    
    # Add moneyness calculations
    for idx, row in filtered_chain.iterrows():
        moneyness = calculate_moneyness(stock_price, row['strike'], row['type'])
        filtered_chain.loc[idx, 'moneyness_pct'] = moneyness['moneyness_pct']
        filtered_chain.loc[idx, 'is_itm'] = moneyness['is_itm']
        filtered_chain.loc[idx, 'is_atm'] = moneyness['is_atm']
        filtered_chain.loc[idx, 'intrinsic_value'] = moneyness['intrinsic_value']
    
    return filtered_chain

def validate_spread_parameters(sell_strike: float, buy_strike: float,
                              sell_type: str, buy_type: str) -> Tuple[bool, str]:
    """
    Validate credit spread parameters
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if sell_type != buy_type:
        return False, "Both legs must be the same type (both Calls or both Puts)"
    
    if sell_type.lower() == "call":
        # Bear Call Spread
        if sell_strike >= buy_strike:
            return False, "For a Call Credit Spread, sell strike must be lower than buy strike"
    else:
        # Bull Put Spread
        if sell_strike <= buy_strike:
            return False, "For a Put Credit Spread, sell strike must be higher than buy strike"
    
    return True, ""