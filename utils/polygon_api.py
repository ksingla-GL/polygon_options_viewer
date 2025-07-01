"""
Polygon API utilities for fetching options data
Enhanced with S3 flat files support and Black-Scholes calculations
Save this file as: utils/polygon_api.py
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import time
import boto3
from botocore.config import Config
import gzip
import io
from scipy.stats import norm
import math

class PolygonOptionsAPI:
    """Enhanced wrapper for Polygon.io Options API with S3 flat files support"""
    
    def __init__(self, api_key: str, s3_access_key: Optional[str] = None, 
                 s3_secret_key: Optional[str] = None):
        """
        Initialize the API client with API key and optional S3 credentials
        
        Args:
            api_key: Polygon API key
            s3_access_key: S3 access key for flat files
            s3_secret_key: S3 secret key for flat files
        """
        self.api_key = api_key
        self.base_url = "https://api.polygon.io"
        self.session = requests.Session()
        self.session.headers.update({'Authorization': f'Bearer {api_key}'})
        
        # Initialize S3 client if credentials provided
        self.s3_client = None
        if s3_access_key and s3_secret_key:
            session = boto3.Session(
                aws_access_key_id=s3_access_key,
                aws_secret_access_key=s3_secret_key,
            )
            self.s3_client = session.client(
                's3',
                endpoint_url='https://files.polygon.io',
                config=Config(signature_version='s3v4'),
            )
            self.bucket_name = 'flatfiles'
    
    def calculate_greeks(self, S: float, K: float, T: float, r: float, 
                        sigma: float, option_type: str) -> Dict[str, float]:
        """
        Calculate Black-Scholes Greeks
        
        Args:
            S: Current stock price
            K: Strike price
            T: Time to expiration (in years)
            r: Risk-free rate (default 0.05)
            sigma: Implied volatility
            option_type: 'call' or 'put'
            
        Returns:
            Dictionary with delta, gamma, theta, vega, rho
        """
        # Avoid division by zero
        if T <= 0 or sigma <= 0:
            return {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0, 'rho': 0}
        
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        
        if option_type.lower() == 'call':
            delta = norm.cdf(d1)
            theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) - 
                     r * K * np.exp(-r * T) * norm.cdf(d2)) / 365
            rho = K * T * np.exp(-r * T) * norm.cdf(d2) / 100
        else:  # put
            delta = norm.cdf(d1) - 1
            theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) + 
                     r * K * np.exp(-r * T) * norm.cdf(-d2)) / 365
            rho = -K * T * np.exp(-r * T) * norm.cdf(-d2) / 100
        
        # Greeks that are same for calls and puts
        gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
        vega = S * norm.pdf(d1) * np.sqrt(T) / 100
        
        return {
            'delta': round(delta, 4),
            'gamma': round(gamma, 4),
            'theta': round(theta, 4),
            'vega': round(vega, 4),
            'rho': round(rho, 4)
        }
    
    def _black_scholes_price(self, S: float, K: float, T: float, r: float, 
                            sigma: float, option_type: str) -> float:
        """Calculate Black-Scholes option price"""
        if T <= 0:
            # Option has expired
            if option_type.lower() == 'call':
                return max(0, S - K)
            else:
                return max(0, K - S)
                
        d1 = self._d1(S, K, T, r, sigma)
        d2 = d1 - sigma * np.sqrt(T)
        
        if option_type.lower() == 'call':
            return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        else:
            return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    
    def _d1(self, S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate d1 for Black-Scholes"""
        if T <= 0 or sigma <= 0:
            return 0
        return (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    
    def get_s3_options_data(self, date: str, data_type: str = 'day_aggs_v1') -> pd.DataFrame:
        """
        Fetch options data from S3 flat files
        
        Args:
            date: Date in YYYY-MM-DD format
            data_type: Type of data ('day_aggs_v1', 'minute_aggs_v1', 'trades_v1')
            
        Returns:
            DataFrame with options data
        """
        if not self.s3_client:
            print("S3 client not initialized")
            return pd.DataFrame()
        
        # Convert date format for S3 path
        date_parts = date.split('-')
        year = date_parts[0]
        month = date_parts[1]
        
        # Construct S3 key
        s3_key = f'us_options_opra/{data_type}/{year}/{month}/{date}.csv.gz'
        
        try:
            # Download file from S3
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            
            # Read gzipped CSV
            with gzip.GzipFile(fileobj=io.BytesIO(response['Body'].read())) as gz:
                df = pd.read_csv(gz)
            
            print(f"Loaded {len(df)} records from S3: {s3_key}")
            return df
            
        except Exception as e:
            if '403' in str(e):
                print(f"Access denied for {data_type} - this data type may not be included in your subscription")
            else:
                print(f"Error fetching S3 data: {e}")
            return pd.DataFrame()
    
    def get_stock_price(self, ticker: str, date: str) -> Optional[float]:
        """Get stock price for a given date"""
        # Create cache key
        cache_key = f"price_{ticker}_{date}"
        
        # Check if we already have this data cached
        if not hasattr(self, '_price_cache'):
            self._price_cache = {}
        
        if cache_key in self._price_cache:
            return self._price_cache[cache_key]
        
        url = f"{self.base_url}/v2/aggs/ticker/{ticker}/range/1/day/{date}/{date}"
        params = {'adjusted': 'true', 'apiKey': self.api_key}
        
        try:
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                if data.get('results'):
                    price = data['results'][0]['c']  # closing price
                    self._price_cache[cache_key] = price
                    return price
        except Exception as e:
            print(f"Error fetching stock price: {e}")
        return None
    
    def get_previous_close(self, ticker: str) -> Optional[float]:
        """Get previous day's closing price"""
        url = f"{self.base_url}/v2/aggs/ticker/{ticker}/prev"
        params = {'apiKey': self.api_key}
        
        try:
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                if data.get('results'):
                    return data['results'][0]['c']
        except Exception as e:
            print(f"Error fetching previous close: {e}")
        return None
    
    def get_available_expirations(self, ticker: str, as_of_date: str) -> List[str]:
        """Get all available expiration dates for options on a ticker"""
        # Create cache key
        cache_key = f"{ticker}_{as_of_date}"
        
        # Check if we already have this data cached
        if not hasattr(self, '_expiration_cache'):
            self._expiration_cache = {}
        
        if cache_key in self._expiration_cache:
            return self._expiration_cache[cache_key]
        
        # First try S3 if available (faster)
        if self.s3_client:
            expirations = self._get_expirations_from_s3(ticker, as_of_date)
            if expirations:
                self._expiration_cache[cache_key] = expirations
                return expirations
        
        # Fallback to REST API
        url = f"{self.base_url}/v3/reference/options/contracts"
        params = {
            'underlying_ticker': ticker,
            'expiration_date.gte': as_of_date,
            'expired': 'false',
            'limit': 1000,
            'order': 'asc',
            'sort': 'expiration_date',
            'apiKey': self.api_key
        }
        
        expirations = set()
        next_url = url
        
        while next_url and len(expirations) < 50:
            try:
                if next_url == url:
                    response = requests.get(next_url, params=params)
                else:
                    response = requests.get(next_url)
                
                if response.status_code == 200:
                    data = response.json()
                    for contract in data.get('results', []):
                        expirations.add(contract['expiration_date'])
                    
                    next_url = data.get('next_url')
                    if next_url:
                        next_url += f"&apiKey={self.api_key}"
                else:
                    break
                    
                time.sleep(0.1)
            except Exception as e:
                print(f"Error fetching expirations: {e}")
                break
        
        result = sorted(list(expirations))
        self._expiration_cache[cache_key] = result
        return result
    
    def _get_expirations_from_s3(self, ticker: str, as_of_date: str) -> List[str]:
        """Get expirations from S3 flat files"""
        try:
            # Get aggregates data for the date
            df = self.get_s3_options_data(as_of_date, 'day_aggs_v1')
            if df.empty:
                return []
            
            # Filter for options of this ticker
            # Options tickers start with O:TICKER
            ticker_prefix = f"O:{ticker}"
            options_df = df[df['ticker'].str.startswith(ticker_prefix)]
            
            if options_df.empty:
                return []
            
            # Extract expiration dates from option symbols
            expirations = set()
            for opt_ticker in options_df['ticker'].unique():
                # Parse option symbol: O:AAPL240119C00175000
                # Format: O:TICKER + YYMMDD + C/P + STRIKE*1000
                parts = opt_ticker.replace(f"O:{ticker}", "")
                if len(parts) >= 6:
                    # Extract date part (YYMMDD)
                    date_str = parts[:6]
                    try:
                        # Convert to YYYY-MM-DD format
                        exp_date = datetime.strptime(date_str, "%y%m%d").strftime("%Y-%m-%d")
                        if exp_date >= as_of_date:
                            expirations.add(exp_date)
                    except:
                        continue
            
            return sorted(list(expirations))
        except Exception as e:
            print(f"Error getting expirations from S3: {e}")
            return []
    
    def get_option_chain(self, ticker: str, expiration: str, as_of_date: Optional[str] = None) -> pd.DataFrame:
        """
        Get complete option chain - prioritize S3 for historical data
        
        Args:
            ticker: Stock symbol
            expiration: Expiration date in YYYY-MM-DD format
            as_of_date: Historical date for the chain
            
        Returns:
            DataFrame with complete option chain
        """
        # For historical data, prioritize S3 (faster and more complete)
        if self.s3_client and as_of_date:
            try:
                s3_data = self._get_option_chain_from_s3(ticker, expiration, as_of_date)
                if not s3_data.empty:
                    return s3_data
            except Exception as e:
                print(f"S3 fetch failed, falling back to API: {e}")
        
        # Fallback to REST API only if S3 fails or not available
        api_data = self._get_option_chain_from_api(ticker, expiration, as_of_date)
        
        # Ensure basic columns exist even if empty
        if api_data.empty:
            api_data = pd.DataFrame(columns=['ticker', 'type', 'strike', 'expiration', 
                                            'bid', 'ask', 'last', 'volume', 'open_interest'])
        
        return api_data
    
    def _get_option_chain_from_s3(self, ticker: str, expiration: str, as_of_date: str) -> pd.DataFrame:
        """Get option chain from S3 flat files - optimized"""
        try:
            # Get daily aggregates only (skip trades)
            aggs_df = self.get_s3_options_data(as_of_date, 'day_aggs_v1')
            if aggs_df.empty:
                return pd.DataFrame()
            
            # Filter for this ticker and expiration
            exp_date_str = datetime.strptime(expiration, "%Y-%m-%d").strftime("%y%m%d")
            ticker_exp_prefix = f"O:{ticker}{exp_date_str}"
            
            options_aggs = aggs_df[aggs_df['ticker'].str.startswith(ticker_exp_prefix)].copy()
            
            if options_aggs.empty:
                return pd.DataFrame()
            
            # Get stock price once for all calculations
            stock_price = self.get_stock_price(ticker, as_of_date) or 100
            
            # Calculate time to expiration once
            exp_dt = datetime.strptime(expiration, "%Y-%m-%d")
            as_of_dt = datetime.strptime(as_of_date, "%Y-%m-%d")
            dte = (exp_dt - as_of_dt).days
            T = max(dte / 365.0, 0.001)
            
            # Parse option symbols and create structured data
            parsed_options = []
            
            for _, row in options_aggs.iterrows():
                opt_ticker = row['ticker']
                parts = opt_ticker.replace(f"O:{ticker}", "")
                
                if len(parts) < 15:
                    continue
                
                # Extract components
                opt_type = 'call' if parts[6] == 'C' else 'put'
                strike_str = parts[7:15]
                
                try:
                    strike = float(strike_str) / 1000
                except:
                    continue
                
                # Use close price as last traded price
                last_price = row.get('close', 0)
                volume = row.get('volume', 0)
                
                # Simple bid/ask estimation based on volume
                if last_price > 0:
                    if volume > 1000:
                        spread = 0.02  # 2% for liquid
                    elif volume > 100:
                        spread = 0.05  # 5% for semi-liquid  
                    else:
                        spread = 0.10  # 10% for illiquid
                    
                    half_spread = last_price * spread / 2
                    bid = max(0.01, last_price - half_spread)
                    ask = last_price + half_spread
                else:
                    bid = ask = 0
                
                # Simplified Greeks - only calculate for ITM/ATM options
                moneyness = abs(strike - stock_price) / stock_price
                
                if last_price > 0 and T > 0 and moneyness < 0.2:  # Within 20% of ATM
                    # Use simple IV estimate based on moneyness
                    if moneyness < 0.05:  # ATM
                        iv = 0.20
                    else:  # Near ATM
                        iv = 0.25
                    
                    # Quick Greeks calculation
                    greeks = self.calculate_greeks(stock_price, strike, T, 0.05, iv, opt_type)
                else:
                    # Skip Greeks for far OTM options
                    iv = 0.30
                    greeks = {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0, 'rho': 0}
                
                option_data = {
                    'ticker': opt_ticker,
                    'type': opt_type,
                    'strike': strike,
                    'expiration': expiration,
                    'bid': round(bid, 2),
                    'ask': round(ask, 2),
                    'last': last_price,
                    'volume': int(volume),
                    'open_interest': int(row.get('open', 0) * 100),  # Estimate
                    'high': row.get('high', 0),
                    'low': row.get('low', 0),
                    'vwap': row.get('vwap', 0),
                    'change': 0,
                    'implied_volatility': round(iv, 4),
                    **greeks,
                    'data_source': 's3_flatfiles'
                }
                
                parsed_options.append(option_data)
            
            return pd.DataFrame(parsed_options)
            
        except Exception as e:
            print(f"Error processing S3 option chain: {e}")
            return pd.DataFrame()
    
    def _get_option_chain_from_api(self, ticker: str, expiration: str, as_of_date: Optional[str]) -> pd.DataFrame:
        """Get option chain from REST API - optimized flow"""
        # Skip the slow contracts endpoint, go straight to snapshot
        timestamp = None
        if as_of_date and as_of_date != datetime.now().strftime('%Y-%m-%d'):
            timestamp = f"{as_of_date}T16:00:00Z"
        
        snapshot_data = self.get_options_snapshot(ticker, timestamp)
        
        if snapshot_data and snapshot_data.get('results'):
            results = snapshot_data.get('results', [])
            parsed_results = []
            
            for r in results:
                details = r.get('details', {})
                if details.get('expiration_date') == expiration:
                    day_data = r.get('day', {})
                    last_quote = r.get('last_quote', {})
                    
                    parsed = {
                        'ticker': details.get('ticker'),
                        'type': details.get('contract_type'),
                        'strike': details.get('strike_price'),
                        'expiration': details.get('expiration_date'),
                        'bid': last_quote.get('b'),
                        'ask': last_quote.get('a'),
                        'last': day_data.get('close'),
                        'volume': day_data.get('volume', 0),
                        'open_interest': r.get('open_interest', 0),
                        'high': day_data.get('high'),
                        'low': day_data.get('low'),
                        'vwap': day_data.get('vwap'),
                        'change': day_data.get('change'),
                        'data_source': 'rest_api'
                    }
                    parsed_results.append(parsed)
            
            df = pd.DataFrame(parsed_results)
            
            # Ensure required columns exist
            for col in ['bid', 'ask', 'last', 'volume', 'open_interest']:
                if col not in df.columns:
                    df[col] = None
                    
            return df
        
        # If snapshot fails, get basic contract structure
        return self._get_contracts_skeleton(ticker, expiration)
    
    def _get_contracts_with_quotes(self, ticker: str, expiration: str, as_of_date: Optional[str]) -> pd.DataFrame:
        """Get contracts with last quotes"""
        url = f"{self.base_url}/v3/reference/options/contracts"
        params = {
            'underlying_ticker': ticker,
            'expiration_date': expiration,
            'limit': 250,
            'apiKey': self.api_key
        }
        
        all_contracts = []
        next_url = url
        
        while next_url:
            try:
                if next_url == url:
                    response = requests.get(next_url, params=params)
                else:
                    response = requests.get(next_url)
                
                if response.status_code == 200:
                    data = response.json()
                    contracts = data.get('results', [])
                    
                    # Get quotes for each contract
                    for contract in contracts:
                        contract_ticker = contract['ticker']
                        
                        # Try to get last quote
                        quote_url = f"{self.base_url}/v2/last/trade/{contract_ticker}"
                        quote_params = {'apiKey': self.api_key}
                        
                        try:
                            quote_response = requests.get(quote_url, params=quote_params)
                            if quote_response.status_code == 200:
                                quote_data = quote_response.json()
                                last_trade = quote_data.get('results', {})
                                
                                all_contracts.append({
                                    'ticker': contract['ticker'],
                                    'type': contract['contract_type'],
                                    'strike': contract['strike_price'],
                                    'expiration': contract['expiration_date'],
                                    'bid': None,  # Will estimate from last
                                    'ask': None,  # Will estimate from last
                                    'last': last_trade.get('p', 0),
                                    'volume': last_trade.get('s', 0),
                                    'open_interest': 0,
                                    'data_source': 'rest_api_quotes'
                                })
                            else:
                                # Add contract without quote
                                all_contracts.append({
                                    'ticker': contract['ticker'],
                                    'type': contract['contract_type'],
                                    'strike': contract['strike_price'],
                                    'expiration': contract['expiration_date'],
                                    'bid': None,
                                    'ask': None,
                                    'last': None,
                                    'volume': 0,
                                    'open_interest': 0,
                                    'data_source': 'rest_api_no_quotes'
                                })
                        except:
                            pass
                        
                        time.sleep(0.05)  # Rate limiting
                    
                    next_url = data.get('next_url')
                    if next_url:
                        next_url += f"&apiKey={self.api_key}"
                else:
                    break
            except Exception as e:
                print(f"Error fetching contracts: {e}")
                break
        
        return pd.DataFrame(all_contracts)
    
    def _merge_option_data(self, s3_data: pd.DataFrame, api_data: pd.DataFrame) -> pd.DataFrame:
        """Merge S3 and API data, preferring S3 for pricing data"""
        # Ensure both dataframes have required columns
        required_cols = ['strike', 'type', 'ticker', 'bid', 'ask', 'last', 'volume', 'open_interest']
        
        for col in required_cols:
            if col not in s3_data.columns and col not in ['strike', 'type', 'ticker']:
                s3_data[col] = None
            if col not in api_data.columns and col not in ['strike', 'type', 'ticker']:
                api_data[col] = None
        
        # Use strike and type as merge keys
        merged = pd.merge(
            s3_data,
            api_data,
            on=['strike', 'type'],
            how='outer',
            suffixes=('', '_api')
        )
        
        # Prefer S3 data but fill missing with API data
        for col in ['bid', 'ask', 'last', 'volume', 'open_interest']:
            if col in merged.columns and f'{col}_api' in merged.columns:
                merged[col] = merged[col].fillna(merged[f'{col}_api'])
        
        # Keep the best ticker (from S3 if available)
        if 'ticker_api' in merged.columns:
            merged['ticker'] = merged['ticker'].fillna(merged['ticker_api'])
        
        # Clean up duplicate columns
        merged = merged[[col for col in merged.columns if not col.endswith('_api')]]
        
        # Add source indicator
        merged['data_source'] = 'merged'
        
        return merged
    
    def get_options_snapshot(self, ticker: str, timestamp: Optional[str] = None) -> Dict:
        """Get snapshot of all options for a ticker"""
        url = f"{self.base_url}/v3/snapshot/options/{ticker}"
        params = {'apiKey': self.api_key}
        
        if timestamp:
            params['timestamp'] = timestamp
        
        try:
            response = requests.get(url, params=params)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error fetching snapshot: {response.status_code}")
        except Exception as e:
            print(f"Error fetching snapshot: {e}")
        
        return {}
    
    def _get_contracts_skeleton(self, ticker: str, expiration: str) -> pd.DataFrame:
        """Get basic contract structure when snapshot has no data"""
        url = f"{self.base_url}/v3/reference/options/contracts"
        params = {
            'underlying_ticker': ticker,
            'expiration_date': expiration,
            'limit': 250,
            'apiKey': self.api_key
        }
        
        all_contracts = []
        next_url = url
        
        while next_url:
            try:
                if next_url == url:
                    response = requests.get(next_url, params=params)
                else:
                    response = requests.get(next_url)
                
                if response.status_code == 200:
                    data = response.json()
                    contracts = data.get('results', [])
                    
                    for contract in contracts:
                        all_contracts.append({
                            'ticker': contract['ticker'],
                            'type': contract['contract_type'],
                            'strike': contract['strike_price'],
                            'expiration': contract['expiration_date'],
                            'bid': None,
                            'ask': None,
                            'last': None,
                            'volume': 0,
                            'open_interest': 0,
                            'high': None,
                            'low': None,
                            'vwap': None,
                            'change': None,
                            'data_source': 'skeleton'
                        })
                    
                    next_url = data.get('next_url')
                    if next_url:
                        next_url += f"&apiKey={self.api_key}"
                else:
                    break
                    
            except Exception as e:
                print(f"Error fetching contracts: {e}")
                break
        
        df = pd.DataFrame(all_contracts)
        
        # Ensure all required columns exist
        required_cols = ['ticker', 'type', 'strike', 'expiration', 'bid', 'ask', 
                       'last', 'volume', 'open_interest']
        for col in required_cols:
            if col not in df.columns:
                df[col] = None if col not in ['volume', 'open_interest'] else 0
                
        return df