# Historical Options Chain Viewer

A Streamlit application for viewing historical options chains using Polygon.io data.

## Quick Start
Note: Please ensure you have a new environment running with Python==3.11

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure API Keys
Create `.env` file with your credentials:
```
POLYGON_API_KEY=your_api_key_here
POLYGON_S3_ACCESS_KEY=your_s3_access_key_here  # Optional
POLYGON_S3_SECRET_KEY=your_s3_secret_key_here  # Optional
```

### 3. Run the App
```bash
streamlit run app.py
```

## Features

- **Historical Options Chains**: View complete option chains for any past date
- **S3 Flat Files Support**: Enhanced data coverage with Polygon's S3 files
- **Smart Strike Selection**: Automatically centers around ATM strikes
- **Credit Spread Calculator**: Analyze bull/bear spreads with P&L diagrams
- **Market Metrics**: Volume, open interest, put/call ratios

## Usage

1. **Select Parameters**:
   - Enter ticker (default: NVDA)
   - Choose historical date
   - Pick expiration from dropdown

2. **View Option Chain**:
   - Calls on left, strikes in center, puts on right
   - ITM options highlighted (green for calls, red for puts)
   - ATM strike highlighted in blue

3. **Analyze Spreads**:
   - Calculator auto-populates with actual option prices
   - Shows max profit/loss and breakeven
   - Interactive P&L diagram

## Data Sources

- **Primary**: S3 Flat Files (complete OHLC + volume)
- **Fallback**: REST API (limited strikes)
- **Estimates**: Bid/Ask spreads based on volume, Greeks via Black-Scholes

## Requirements

- Python 3.8+
- Polygon.io API key (free tier works)
- Optional: S3 credentials for enhanced data

## Notes

- Best results with dates after stock splits
- Use 7-30 day expirations for full strike coverage
- Weekend dates will show Friday's data

---

Built by Kshitij Singla | Data from Polygon.io
