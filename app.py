"""
Historical Options Chain Viewer - Enhanced Streamlit App
Author: Kshitij Singla
Version: Enhanced with S3 Flat Files and Greeks
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import plotly.graph_objects as go

# Add parent directory to path
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.polygon_api import PolygonOptionsAPI

# Load environment variables
load_dotenv()

def date_difference_days(date_string: str, reference_date) -> int:
    """Calculate days between a date string and a date object."""
    target_date = datetime.strptime(date_string, '%Y-%m-%d').date()
    if isinstance(reference_date, datetime):
        reference_date = reference_date.date()
    return (target_date - reference_date).days

# Configuration
API_KEY = os.getenv('POLYGON_API_KEY')
S3_ACCESS_KEY = os.getenv('POLYGON_S3_ACCESS_KEY')
S3_SECRET_KEY = os.getenv('POLYGON_S3_SECRET_KEY')

if not API_KEY:
    st.error("No API key found! Please set POLYGON_API_KEY in .env file")
    st.stop()

# Initialize API with S3 support if available
@st.cache_resource
def get_api_client():
    if S3_ACCESS_KEY and S3_SECRET_KEY:
        st.sidebar.success("S3 Flat Files Enabled")
        return PolygonOptionsAPI(API_KEY, S3_ACCESS_KEY, S3_SECRET_KEY)
    else:
        st.sidebar.warning("Using REST API only (no S3)")
        return PolygonOptionsAPI(API_KEY)

# Page config
st.set_page_config(
    page_title="Historical Options Chain Viewer",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Title
st.title("Historical Options Chain Viewer")
st.markdown("View historical option chains using Polygon.io data with S3 flat files enhancement")

# Initialize session state
if 'expirations' not in st.session_state:
    st.session_state.expirations = []
if 'current_stock_price' not in st.session_state:
    st.session_state.current_stock_price = None
if 'option_chain' not in st.session_state:
    st.session_state.option_chain = None
if 'last_params' not in st.session_state:
    st.session_state.last_params = {}

# Helper functions
def format_number(value):
    """Format large numbers with commas"""
    if pd.isna(value) or value == 0:
        return '-'
    try:
        return f"{int(value):,}"
    except:
        return '-'

def format_price(value):
    """Format price values"""
    if pd.isna(value) or value is None:
        return '-'
    try:
        return f"{float(value):.2f}"
    except:
        return '-'

def format_change(value):
    """Format change values with + or - sign"""
    if pd.isna(value) or value is None:
        return '-'
    try:
        val = float(value)
        if val > 0:
            return f"+{val:.2f}"
        else:
            return f"{val:.2f}"
    except:
        return '-'

def format_greek(value):
    """Format Greek values"""
    if pd.isna(value) or value is None:
        return '-'
    try:
        return f"{float(value):.3f}"
    except:
        return '-'

# Sidebar inputs
with st.sidebar:
    st.header("Parameters")
    
    # Ticker input
    ticker = st.text_input("Ticker Symbol", value="NVDA", help="Enter stock ticker symbol").upper()
    
    # Date picker
    max_date = datetime.now().date()
    default_date = max_date - timedelta(days=1)
    
    as_of_date = st.date_input(
        "As Of Date",
        value=default_date,
        max_value=max_date,
        min_value=datetime(2020, 1, 1).date(),
        help="Select historical date for option chain (must be a past date when markets were open)"
    )
    
    # Date validation helper
    if as_of_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
        st.warning("Weekend selected - markets were closed")
        # Find last Friday
        days_to_friday = (as_of_date.weekday() - 4) % 7
        last_friday = as_of_date - timedelta(days=days_to_friday)
        st.info(f"Try {last_friday.strftime('%Y-%m-%d')} (last Friday)")
    
    # Fetch stock price and expirations
    api = get_api_client()
    
    if ticker:
        # Get stock price
        with st.spinner("Fetching stock price..."):
            stock_price = api.get_stock_price(ticker, as_of_date.strftime('%Y-%m-%d'))
            if not stock_price:
                stock_price = api.get_previous_close(ticker)
            st.session_state.current_stock_price = stock_price
            
            if stock_price:
                st.metric("Stock Price", f"${stock_price:,.2f}")
        
        # Get available expirations
        with st.spinner("Loading expirations..."):
            expirations = api.get_available_expirations(ticker, as_of_date.strftime('%Y-%m-%d'))
            st.session_state.expirations = expirations
    
    # Expiration dropdown
    if st.session_state.expirations:
        # Filter out same-day expirations
        valid_expirations = [exp for exp in st.session_state.expirations 
                            if date_difference_days(exp, as_of_date) > 0]
        
        if valid_expirations:
            # Try to default to an expiration around 7-30 days out
            days_out_list = [(exp, date_difference_days(exp, as_of_date)) for exp in valid_expirations]
            ideal_exp = min(days_out_list, key=lambda x: abs(x[1] - 7))  # Target ~7 days
            default_index = valid_expirations.index(ideal_exp[0])
            
            selected_expiration = st.selectbox(
                "Expiration Date",
                options=valid_expirations,
                index=default_index,
                format_func=lambda x: f"{x} ({date_difference_days(x, as_of_date)} days)"
            )
            
            # Warn about short expirations
            days_to_exp = date_difference_days(selected_expiration, as_of_date)
            if days_to_exp <= 2:
                st.warning(f"Very short expiration ({days_to_exp} days) may have limited strikes available. Try 5-30 days for better coverage.")
            elif days_to_exp >= 90:
                st.info(f"Long-dated option ({days_to_exp} days) - strikes may be sparse")
        else:
            st.warning("No valid expirations found (all are same-day or past)")
            st.info("Try selecting an earlier 'As Of Date' to see more expirations")
            selected_expiration = None
    else:
        st.warning("No expirations found. Please check ticker and date.")
        selected_expiration = None
    
    # Display settings
    st.subheader("Display Settings")
    
    # Check if parameters changed
    current_params = {
        'ticker': ticker,
        'as_of_date': as_of_date.strftime('%Y-%m-%d') if as_of_date else None,
        'expiration': selected_expiration
    }
    params_changed = current_params != st.session_state.last_params
    
    if params_changed:
        st.session_state.option_chain = None
        st.session_state.last_params = current_params
    
    strikes_around_atm = st.slider(
        "Strikes around ATM", 
        5, 30, 10,
        help="Number of strikes to show above and below ATM"
    )
    
    highlight_itm = st.checkbox("Highlight ITM Options", value=True)
    show_greeks = st.checkbox("Show Greeks", value=True, help="Display option Greeks (if available)")
    
    # Data source info
    st.subheader("Data Source")
    if api.s3_client:
        st.info("Using S3 Flat Files + REST API")
        with st.expander("Data Sources Info"):
            st.markdown("""
            **From S3 Aggregates:**
            - OHLC prices
            - Volume data
            - Complete strike coverage
            
            **Calculated/Estimated:**
            - Bid/Ask spreads (volume-based)
            - Greeks (Black-Scholes)
            - Implied Volatility
            
            *Note: Real quotes require Options Advanced plan*
            """)
    else:
        st.info("Using REST API only")
    
    # Refresh button
    if st.button("Refresh Data", type="primary", use_container_width=True):
        st.session_state.option_chain = None

# Main content area
if ticker and selected_expiration:
    # Fetch option chain data
    if st.session_state.option_chain is None:
        with st.spinner(f"Loading option chain for {ticker} - {selected_expiration}..."):
            option_chain = api.get_option_chain(ticker, selected_expiration, as_of_date.strftime('%Y-%m-%d'))
            st.session_state.option_chain = option_chain
    else:
        option_chain = st.session_state.option_chain
    
    if not option_chain.empty and st.session_state.current_stock_price:
        # Ensure required columns exist
        required_cols = ['type', 'strike', 'volume', 'open_interest']
        for col in required_cols:
            if col not in option_chain.columns:
                if col in ['volume', 'open_interest']:
                    option_chain[col] = 0
                else:
                    st.error(f"Missing required column: {col}")
                    st.stop()
        
        # Split into calls and puts
        calls = option_chain[option_chain['type'] == 'call'].copy()
        puts = option_chain[option_chain['type'] == 'put'].copy()
        
        # Get unique strikes and find ATM
        strikes = sorted(option_chain['strike'].unique())
        stock_price = st.session_state.current_stock_price
        
        # Find closest strike to current price
        atm_strike = min(strikes, key=lambda x: abs(x - stock_price))
        atm_index = strikes.index(atm_strike)
        
        # Check if we have a reasonable ATM
        atm_distance_pct = abs(atm_strike - stock_price) / stock_price * 100
        
        # Filter strikes around ATM
        # If ATM is very far (>20%), show all available strikes
        if atm_distance_pct > 20:
            st.warning(f"Limited strikes available. Closest strike is {atm_distance_pct:.1f}% away from stock price.")
            display_strikes = strikes  # Show all available
        else:
            # Normal filtering around ATM
            start_idx = max(0, atm_index - strikes_around_atm)
            end_idx = min(len(strikes), atm_index + strikes_around_atm + 1)
            display_strikes = strikes[start_idx:end_idx]
        
        
        # Filter dataframes
        calls_display = calls[calls['strike'].isin(display_strikes)].set_index('strike')
        puts_display = puts[puts['strike'].isin(display_strikes)].set_index('strike')
        
        # Calculate days to expiration
        dte = date_difference_days(selected_expiration, as_of_date)
        
        # Display header metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Underlying", f"{ticker} ${stock_price:,.2f}")
        with col2:
            st.metric("Expiration", selected_expiration)
        with col3:
            st.metric("Days to Expiry", dte)
        with col4:
            st.metric("ATM Strike", f"${atm_strike:.0f}")
            
            # Warn if ATM is far from stock price
            if atm_distance_pct > 10:
                st.caption("Limited strikes")
        
        # Strike info expander
        with st.expander("Strike Information", expanded=False):
            info_col1, info_col2 = st.columns(2)
            with info_col1:
                st.write(f"**Stock Price:** ${stock_price:.2f}")
                st.write(f"**Total Strikes Available:** {len(strikes)}")
                st.write(f"**Strike Range:** ${min(strikes):.0f} - ${max(strikes):.0f}")
                st.write(f"**ATM Strike:** ${atm_strike:.0f} ({atm_distance_pct:.1f}% from stock)")
            with info_col2:
                st.write(f"**Strikes Displayed:** {len(display_strikes)}")
                st.write(f"**Display Range:** ${min(display_strikes):.0f} - ${max(display_strikes):.0f}")
                if dte <= 2:
                    st.info("Short-dated options typically have fewer strikes")
                if atm_distance_pct > 20:
                    st.warning("Try a longer-dated expiration for more strikes near ATM")
        
        # Option chain display
        st.markdown("---")
        st.markdown("### Option Chain")
        
        # Create data for display
        option_chain_data = []
        
        # Sort strikes in descending order for display (highest first)
        for strike in sorted(display_strikes, reverse=True):
            call_data = calls_display.loc[strike] if strike in calls_display.index else pd.Series()
            put_data = puts_display.loc[strike] if strike in puts_display.index else pd.Series()
            
            # Calculate moneyness
            moneyness = ((stock_price - strike) / stock_price) * 100
            
            # Build row data based on display settings
            row = {
                'OI (C)': format_number(call_data.get('open_interest', 0)),
                'Volume (C)': format_number(call_data.get('volume', 0)),
                'Bid (C)': format_price(call_data.get('bid')) if 'bid' in call_data else '-',
                'Ask (C)': format_price(call_data.get('ask')) if 'ask' in call_data else '-',
                'Last (C)': format_price(call_data.get('last')),
            }
            
            # Add Greeks if enabled and available
            if show_greeks:
                row['Δ (C)'] = format_greek(call_data.get('delta'))
                row['IV (C)'] = format_greek(call_data.get('implied_volatility'))
            
            # Add strike info
            row['Strike'] = f"${strike:,.0f}"
            row['%'] = f"{moneyness:+.1f}%"
            
            # Add put data
            row['Last (P)'] = format_price(put_data.get('last'))
            row['Ask (P)'] = format_price(put_data.get('ask')) if 'ask' in put_data else '-'
            row['Bid (P)'] = format_price(put_data.get('bid')) if 'bid' in put_data else '-'
            
            # Add put Greeks if enabled
            if show_greeks:
                row['IV (P)'] = format_greek(put_data.get('implied_volatility'))
                row['Δ (P)'] = format_greek(put_data.get('delta'))
            
            row['Volume (P)'] = format_number(put_data.get('volume', 0))
            row['OI (P)'] = format_number(put_data.get('open_interest', 0))
            
            # Add metadata for highlighting
            row['_strike_val'] = strike
            row['_is_atm'] = abs(strike - atm_strike) < 0.01
            row['_is_call_itm'] = strike < stock_price
            row['_is_put_itm'] = strike > stock_price
            
            option_chain_data.append(row)
        
        # Create DataFrame
        df = pd.DataFrame(option_chain_data)
        
        if not df.empty:
            # Apply styling and display
            if highlight_itm:
                # Style the dataframe
                def style_option_chain(row):
                    """Apply styling to option chain rows"""
                    styles = [''] * len(row)
                    
                    # Find column indices
                    strike_idx = row.index.get_loc('Strike')
                    
                    # Get metadata from original df using the row name (index)
                    original_row = df.loc[row.name]
                    
                    if original_row.get('_is_atm', False):
                        # ATM row - highlight strike column
                        styles[strike_idx] = 'background-color: #e3f2fd; font-weight: bold'
                    elif original_row.get('_is_call_itm', False):
                        # ITM calls - light green background for call columns
                        for i, col in enumerate(row.index):
                            if '(C)' in col and not col.startswith('_'):
                                styles[i] = 'background-color: #e8f5e9'
                    elif original_row.get('_is_put_itm', False):
                        # ITM puts - light red background for put columns
                        for i, col in enumerate(row.index):
                            if '(P)' in col and not col.startswith('_'):
                                styles[i] = 'background-color: #ffebee'
                    
                    return styles
                
                # Create a copy without metadata for display
                display_df = df.drop(columns=['_strike_val', '_is_atm', '_is_call_itm', '_is_put_itm'])
                styled_df = display_df.style.apply(style_option_chain, axis=1)
                st.dataframe(styled_df, use_container_width=True, hide_index=True)
            else:
                # Remove metadata columns for non-styled display
                display_df = df.drop(columns=['_strike_val', '_is_atm', '_is_call_itm', '_is_put_itm'])
                st.dataframe(display_df, use_container_width=True, hide_index=True)
        else:
            st.warning("No option data to display")
        
        # Display headers legend
        header_cols = st.columns([5, 2, 5])
        with header_cols[0]:
            st.markdown("**CALLS** - OI: Open Interest, Δ: Delta, IV: Implied Vol")
        with header_cols[1]:
            st.markdown("**STRIKE**")
        with header_cols[2]:
            st.markdown("**PUTS** - OI: Open Interest, Δ: Delta, IV: Implied Vol")
        
        # Add legend if highlighting is enabled
        if highlight_itm:
            st.markdown("---")
            legend_cols = st.columns(3)
            with legend_cols[0]:
                st.markdown('<span style="background-color: #e3f2fd; padding: 2px 8px;">**ATM Strike**</span> - At the Money', unsafe_allow_html=True)
            with legend_cols[1]:
                st.markdown('<span style="background-color: #e8f5e9; padding: 2px 8px;">**ITM Calls**</span> - In the Money Calls', unsafe_allow_html=True)
            with legend_cols[2]:
                st.markdown('<span style="background-color: #ffebee; padding: 2px 8px;">**ITM Puts**</span> - In the Money Puts', unsafe_allow_html=True)
        
        # Credit Spread Calculator - expanded by default
        st.markdown("---")
        with st.expander("Credit Spread Calculator", expanded=True):
            st.markdown("### Option Spread Analysis")
            
            # Get available strikes and premiums from option chain if available
            if 'option_chain' in st.session_state and st.session_state.option_chain is not None and not st.session_state.option_chain.empty:
                option_data = st.session_state.option_chain
                available_strikes = sorted(option_data['strike'].unique())
                
                # Find default strikes for spread
                current_price = st.session_state.current_stock_price or 100
                atm_strike = min(available_strikes, key=lambda x: abs(x - current_price))
                atm_idx = available_strikes.index(atm_strike)
                
                # Default to 5 strikes OTM for each leg
                sell_idx = min(atm_idx + 5, len(available_strikes) - 1)
                buy_idx = min(atm_idx + 10, len(available_strikes) - 1)
                
                default_sell_strike = available_strikes[sell_idx]
                default_buy_strike = available_strikes[buy_idx]
                
                # Get last prices for defaults
                sell_call_data = option_data[(option_data['strike'] == default_sell_strike) & (option_data['type'] == 'call')]
                buy_call_data = option_data[(option_data['strike'] == default_buy_strike) & (option_data['type'] == 'call')]
                
                default_sell_premium = sell_call_data['last'].iloc[0] if not sell_call_data.empty else 2.0
                default_buy_premium = buy_call_data['last'].iloc[0] if not buy_call_data.empty else 0.5
            else:
                # Fallback values if no option chain loaded
                available_strikes = []
                default_sell_strike = 100.0
                default_buy_strike = 105.0
                default_sell_premium = 2.0
                default_buy_premium = 0.5
            
            calc_col1, calc_col2, calc_col3 = st.columns([2, 2, 1])
            
            with calc_col1:
                st.markdown("**Sell Leg (Short)**")
                sell_type = st.radio("Type", ["Call", "Put"], key="sell_type", horizontal=True)
                
                if available_strikes:
                    sell_strike = st.selectbox("Strike Price", options=available_strikes, 
                                             index=available_strikes.index(default_sell_strike), 
                                             key="sell_strike")
                    # Get premium for selected strike
                    sell_opt_data = option_data[(option_data['strike'] == sell_strike) & 
                                               (option_data['type'] == sell_type.lower())]
                    if not sell_opt_data.empty and sell_opt_data['last'].iloc[0] > 0:
                        sell_premium = st.number_input("Premium Received", 
                                                     value=float(sell_opt_data['last'].iloc[0]), 
                                                     step=0.05, key="sell_premium")
                    else:
                        sell_premium = st.number_input("Premium Received", value=default_sell_premium, 
                                                     step=0.05, key="sell_premium")
                else:
                    sell_strike = st.number_input("Strike Price", min_value=0.0, value=default_sell_strike, 
                                                step=0.5, key="sell_strike")
                    sell_premium = st.number_input("Premium Received", min_value=0.0, value=default_sell_premium, 
                                                 step=0.05, key="sell_premium")
            
            with calc_col2:
                st.markdown("**Buy Leg (Long)**")
                buy_type = st.radio("Type", ["Call", "Put"], key="buy_type", horizontal=True)
                
                if available_strikes:
                    buy_strike = st.selectbox("Strike Price", options=available_strikes, 
                                            index=available_strikes.index(default_buy_strike), 
                                            key="buy_strike")
                    # Get premium for selected strike
                    buy_opt_data = option_data[(option_data['strike'] == buy_strike) & 
                                              (option_data['type'] == buy_type.lower())]
                    if not buy_opt_data.empty and buy_opt_data['last'].iloc[0] > 0:
                        buy_premium = st.number_input("Premium Paid", 
                                                    value=float(buy_opt_data['last'].iloc[0]), 
                                                    step=0.05, key="buy_premium")
                    else:
                        buy_premium = st.number_input("Premium Paid", value=default_buy_premium, 
                                                    step=0.05, key="buy_premium")
                else:
                    buy_strike = st.number_input("Strike Price", min_value=0.0, value=default_buy_strike, 
                                               step=0.5, key="buy_strike")
                    buy_premium = st.number_input("Premium Paid", min_value=0.0, value=default_buy_premium, 
                                                step=0.05, key="buy_premium")
            
            with calc_col3:
                st.markdown("**Analysis**")
                contracts = st.number_input("# Contracts", min_value=1, value=1, step=1)
            
            if st.button("Calculate Spread", type="primary"):
                # Validate spread type
                if sell_type == buy_type:
                    # Credit spread calculation
                    net_credit = sell_premium - buy_premium
                    max_profit = net_credit * 100 * contracts
                    
                    if sell_type == "Call":
                        # Call Credit Spread (Bear Call Spread)
                        if sell_strike < buy_strike:
                            spread_width = buy_strike - sell_strike
                            max_loss = (spread_width - net_credit) * 100 * contracts
                            breakeven = sell_strike + net_credit
                            spread_name = "Bear Call Spread"
                            valid_spread = True
                        else:
                            st.error("For a Call Credit Spread, sell strike must be lower than buy strike")
                            valid_spread = False
                    else:
                        # Put Credit Spread (Bull Put Spread)  
                        if sell_strike > buy_strike:
                            spread_width = sell_strike - buy_strike
                            max_loss = (spread_width - net_credit) * 100 * contracts
                            breakeven = sell_strike - net_credit
                            spread_name = "Bull Put Spread"
                            valid_spread = True
                        else:
                            st.error("For a Put Credit Spread, sell strike must be higher than buy strike")
                            valid_spread = False
                    
                    # Display results
                    if valid_spread:
                        result_col1, result_col2 = st.columns(2)
                        
                        with result_col1:
                            st.success(f"**{spread_name}**")
                            st.metric("Net Credit", f"${net_credit:.2f}")
                            st.metric("Max Profit", f"${max_profit:.2f}")
                            st.metric("Max Loss", f"-${abs(max_loss):.2f}")
                            st.metric("Breakeven", f"${breakeven:.2f}")
                            
                            if max_loss != 0:
                                risk_reward = abs(max_profit / max_loss)
                                st.metric("Risk/Reward Ratio", f"1:{risk_reward:.2f}")
                        
                        with result_col2:
                            # Create P&L diagram
                            if st.session_state.current_stock_price:
                                current_price = st.session_state.current_stock_price
                                price_range = np.linspace(
                                    min(sell_strike, buy_strike) * 0.9,
                                    max(sell_strike, buy_strike) * 1.1,
                                    100
                                )
                                
                                pnl = []
                                for price in price_range:
                                    if sell_type == "Call":
                                        # Bear Call Spread P&L
                                        sell_intrinsic = max(0, price - sell_strike)
                                        buy_intrinsic = max(0, price - buy_strike)
                                        position_pnl = (net_credit - sell_intrinsic + buy_intrinsic) * 100 * contracts
                                    else:  # Put
                                        # Bull Put Spread P&L
                                        sell_intrinsic = max(0, sell_strike - price)
                                        buy_intrinsic = max(0, buy_strike - price)
                                        position_pnl = (net_credit - sell_intrinsic + buy_intrinsic) * 100 * contracts
                                    
                                    pnl.append(position_pnl)
                                
                                # Create plot
                                fig = go.Figure()
                                
                                # Add P&L line
                                fig.add_trace(go.Scatter(
                                    x=price_range,
                                    y=pnl,
                                    mode='lines',
                                    name='P&L',
                                    line=dict(color='blue', width=3)
                                ))
                                
                                # Add breakeven line
                                fig.add_hline(y=0, line_dash="dash", line_color="gray", line_width=1)
                                fig.add_vline(x=breakeven, line_dash="dash", line_color="orange", 
                                            annotation_text=f"BE: ${breakeven:.2f}", annotation_position="top left")
                                
                                # Add current price line
                                if current_price:
                                    fig.add_vline(x=current_price, line_dash="dash", line_color="green",
                                                annotation_text=f"Current: ${current_price:.2f}", annotation_position="top right")
                                
                                # Add max profit and max loss lines
                                fig.add_hline(y=max_profit, line_dash="dot", line_color="green", 
                                            annotation_text=f"Max Profit: ${max_profit:.2f}", annotation_position="right")
                                fig.add_hline(y=-abs(max_loss), line_dash="dot", line_color="red",
                                            annotation_text=f"Max Loss: ${abs(max_loss):.2f}", annotation_position="right")
                                
                                fig.update_layout(
                                    title=f"{spread_name} P&L Diagram",
                                    xaxis_title="Stock Price",
                                    yaxis_title="Profit/Loss ($)",
                                    height=400,
                                    showlegend=True,
                                    hovermode='x unified'
                                )
                                
                                # Add shaded regions
                                fig.add_hrect(y0=0, y1=max_profit, fillcolor="green", opacity=0.1)
                                fig.add_hrect(y0=-abs(max_loss), y1=0, fillcolor="red", opacity=0.1)
                                
                                st.plotly_chart(fig, use_container_width=True)
                                
                                # Add legend explanation
                                st.markdown("**Chart Legend:**")
                                legend_col1, legend_col2 = st.columns(2)
                                with legend_col1:
                                    st.markdown("- **Blue Line**: P&L at expiration")
                                    st.markdown("- **Orange Dashed**: Breakeven price")
                                    st.markdown("- **Green Dashed**: Current stock price")
                                with legend_col2:
                                    st.markdown("- **Green Area**: Profit zone")
                                    st.markdown("- **Red Area**: Loss zone")
                                    st.markdown("- **Dotted Lines**: Max profit/loss levels")
                else:
                    st.error("Both legs must be the same type (both Calls or both Puts) for a credit spread")
        
        # Summary statistics - moved outside of credit spread calculator
        st.markdown("---")
        col1, col2, col3, col4 = st.columns(4)
        
        # Calculate totals from full option chain (not just displayed)
        if not option_chain.empty:
            total_call_volume = option_chain[option_chain['type'] == 'call']['volume'].sum()
            total_call_oi = option_chain[option_chain['type'] == 'call']['open_interest'].sum()
            total_put_volume = option_chain[option_chain['type'] == 'put']['volume'].sum()
            total_put_oi = option_chain[option_chain['type'] == 'put']['open_interest'].sum()
        else:
            total_call_volume = total_call_oi = total_put_volume = total_put_oi = 0
        
        with col1:
            st.markdown("##### Call Statistics")
            st.metric("Total Call Volume", f"{int(total_call_volume):,}")
            st.metric("Total Call OI", f"{int(total_call_oi):,}")
            
        with col2:
            st.markdown("##### Put Statistics")
            st.metric("Total Put Volume", f"{int(total_put_volume):,}")
            st.metric("Total Put OI", f"{int(total_put_oi):,}")
        
        with col3:
            st.markdown("##### Put/Call Ratios")
            if total_call_volume > 0:
                pc_ratio_volume = total_put_volume / total_call_volume
                st.metric("P/C Volume Ratio", f"{pc_ratio_volume:.2f}")
            else:
                st.metric("P/C Volume Ratio", "N/A")
                pc_ratio_volume = 0
                
            if total_call_oi > 0:
                pc_ratio_oi = total_put_oi / total_call_oi
                st.metric("P/C OI Ratio", f"{pc_ratio_oi:.2f}")
            else:
                st.metric("P/C OI Ratio", "N/A")
                pc_ratio_oi = 0
            
            # Add explanation tooltip
            st.caption("P/C Ratio = Put Volume ÷ Call Volume")
            st.caption("Higher ratio (>1) = More put activity")
        
        with col4:
            st.markdown("##### Trading Activity")
            # Simple activity indicator based on P/C ratio
            if pc_ratio_volume > 0 or pc_ratio_oi > 0:
                # Average non-zero ratios
                ratios = [r for r in [pc_ratio_volume, pc_ratio_oi] if r > 0]
                avg_pc_ratio = sum(ratios) / len(ratios) if ratios else 0
                
                if avg_pc_ratio > 1.2:
                    activity = "High Put Activity"
                elif avg_pc_ratio < 0.8:
                    activity = "High Call Activity"
                else:
                    activity = "Balanced Activity"
                st.metric("Options Flow", activity)
                if avg_pc_ratio > 0:
                    st.caption(f"Based on avg P/C: {avg_pc_ratio:.2f}")
            else:
                st.metric("Options Flow", "N/A")
        
        # Most Active Options
        if not option_chain.empty and option_chain['volume'].sum() > 0:
            st.markdown("---")
            st.markdown("### Most Active Options")
            
            active_calls = option_chain[option_chain['type'] == 'call'].nlargest(5, 'volume')
            active_puts = option_chain[option_chain['type'] == 'put'].nlargest(5, 'volume')
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### Top Active Calls")
                if not active_calls.empty:
                    for _, opt in active_calls.iterrows():
                        if 'bid' in opt and 'ask' in opt and pd.notna(opt['bid']) and pd.notna(opt['ask']):
                            bid_ask = f"Bid: ${opt['bid']:.2f}, Ask: ${opt['ask']:.2f}"
                        else:
                            bid_ask = f"Last: ${opt.get('last', 'N/A')}"
                        greeks = ""
                        if show_greeks and 'delta' in opt and pd.notna(opt['delta']):
                            greeks = f" | Δ={opt['delta']:.3f}, IV={opt.get('implied_volatility', 0):.3f}"
                        st.text(f"${opt['strike']:.0f} Strike: Vol={opt['volume']:,}, {bid_ask}{greeks}")
            
            with col2:
                st.markdown("#### Top Active Puts")
                if not active_puts.empty:
                    for _, opt in active_puts.iterrows():
                        if 'bid' in opt and 'ask' in opt and pd.notna(opt['bid']) and pd.notna(opt['ask']):
                            bid_ask = f"Bid: ${opt['bid']:.2f}, Ask: ${opt['ask']:.2f}"
                        else:
                            bid_ask = f"Last: ${opt.get('last', 'N/A')}"
                        greeks = ""
                        if show_greeks and 'delta' in opt and pd.notna(opt['delta']):
                            greeks = f" | Δ={opt['delta']:.3f}, IV={opt.get('implied_volatility', 0):.3f}"
                        st.text(f"${opt['strike']:.0f} Strike: Vol={opt['volume']:,}, {bid_ask}{greeks}")
        
    else:
        # Provide helpful message about why no data is available
        st.warning("No option data available for the selected parameters.")
        
        # Check common issues
        if selected_expiration and as_of_date:
            dte = date_difference_days(selected_expiration, as_of_date)
            if dte == 0:
                st.error("Options expiring on the same day (0 DTE) typically have no historical data.")
                st.info("**Solution**: Select an expiration date that's at least 1 day after your 'as of' date.")
            elif dte < 0:
                st.error("The expiration date is before the 'as of' date.")
            elif dte == 1:
                st.warning("Very short expiration (1 day) - limited strikes may be available.")
                st.info("**Try**: Select an expiration 5-30 days out for better strike coverage.")
        
        # Additional tips
        with st.expander("Troubleshooting Tips"):
            st.markdown("""
            **Common reasons for no data:**
            1. **Very short expiration**: Options with 0-2 days to expiration often have limited data
            2. **Weekend/Holiday**: Markets were closed on the selected date
            3. **Data availability**: Historical options data may be limited for certain dates
            4. **Strike availability**: Near expiration, many strikes are delisted
            
            **Recommended settings:**
            - **As Of Date**: A recent weekday when markets were open
            - **Expiration**: 7-30 days after the 'as of' date
            - **Popular tickers**: SPY, QQQ, AAPL tend to have the best data coverage
            
            **For best results:**
            - Use yesterday as the 'as of' date
            - Select monthly expirations (3rd Friday of the month)
            - These typically have the most strikes and liquidity
            """)

# Footer
st.markdown("---")
st.caption("Data provided by Polygon.io | Enhanced with S3 Flat Files | Built by Kshitij Singla")

# Debug info (hidden by default)
with st.expander("Debug Information", expanded=False):
    if 'option_chain' in st.session_state and st.session_state.option_chain is not None:
        st.write("**Option Chain Shape:**", st.session_state.option_chain.shape)
        st.write("**Columns:**", list(st.session_state.option_chain.columns))
        
        # Show strike distribution
        if 'strike' in st.session_state.option_chain.columns:
            strikes_in_data = sorted(st.session_state.option_chain['strike'].unique())
            st.write(f"\n**All Strikes in Data: {len(strikes_in_data)} total**")
            if len(strikes_in_data) > 20:
                st.write(f"First 10: {strikes_in_data[:10]}")
                st.write(f"Last 10: {strikes_in_data[-10:]}")
            else:
                st.write(f"Strikes: {strikes_in_data}")
        
        # Check data quality by source
        if 'data_source' in st.session_state.option_chain.columns:
            st.write("\n**Data Sources:**")
            source_counts = st.session_state.option_chain['data_source'].value_counts()
            for source, count in source_counts.items():
                st.write(f"  - {source}: {count} options")
        
        # Check Greeks availability
        if 'delta' in st.session_state.option_chain.columns:
            greeks_available = st.session_state.option_chain.dropna(subset=['delta'])
            st.write(f"\n**Greeks Available:** {len(greeks_available)}/{len(st.session_state.option_chain)} options ({len(greeks_available)/len(st.session_state.option_chain)*100:.1f}%)")
        
        # Check bid/ask data
        total_options = len(st.session_state.option_chain)
        if total_options > 0:
            if 'bid' in st.session_state.option_chain.columns and 'ask' in st.session_state.option_chain.columns:
                options_with_quotes = len(st.session_state.option_chain.dropna(subset=['bid', 'ask']))
                st.write(f"\n**Bid/Ask Coverage:** {options_with_quotes}/{total_options} options ({options_with_quotes/total_options*100:.1f}%)")
                
                # Show if bid/ask is estimated
                if options_with_quotes > 0 and 'data_source' in st.session_state.option_chain.columns:
                    if 's3_flatfiles' in st.session_state.option_chain['data_source'].values:
                        st.info("Bid/Ask prices are estimated based on last trade and volume")
            else:
                st.write("\n**Bid/Ask Coverage:** No bid/ask data available")
        else:
            st.write("\n**Data Status:** No options data found")
        
        st.write("\n**Sample Data:**")
        st.dataframe(st.session_state.option_chain.head())