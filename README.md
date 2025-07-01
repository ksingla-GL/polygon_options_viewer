# Historical Options Chain Viewer

A Streamlit application for viewing historical options chains using Polygon.io's REST API and S3 flat files. This tool provides a comprehensive view of options data similar to major trading platforms like NSE India and NASDAQ.

## Features

### Core Features
- 📊 **Historical Options Chain Display**: View complete option chains for any date
- 🎯 **Smart Strike Selection**: Automatically centers around ATM (At-The-Money) strikes
- 📈 **Greeks Calculation**: Black-Scholes based Greeks (Delta, Gamma, Theta, Vega, Rho)
- 💾 **S3 Flat Files Integration**: Enhanced data coverage using Polygon's S3 flat files
- 🔄 **Hybrid Data Source**: Seamlessly combines REST API and S3 data

### Display Features
- **Side-by-side Layout**: Calls on the left, puts on the right
- **ITM/OTM Highlighting**: Visual indicators for in-the-money options
- **Market Sentiment Analysis**: Put/Call ratios and sentiment indicators
- **Most Active Options**: Quick view of high-volume contracts
- **Data Quality Indicators**: Shows data source and completeness

### Analysis Tools
- 💰 **Credit Spread Calculator**: Analyze bull put and bear call spreads
- 📊 **P&L Visualization**: Interactive profit/loss diagrams
- 📈 **Risk/Reward Analysis**: Calculate max profit, max loss, and breakeven points

## Installation

1. Clone the repository:
```bash
git clone <your-repo-url>
cd polygon_options_viewer
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.sample .env
# Edit .env with your credentials
```

4. Configure your Polygon.io credentials in `.env`:
```
POLYGON_API_KEY=your_api_key_here
POLYGON_S3_ACCESS_KEY=your_s3_access_key_here  # Optional but recommended
POLYGON_S3_SECRET_KEY=your_s3_secret_key_here  # Optional but recommended
```

## Usage

### Running the Application

```bash
streamlit run app.py
```

### Testing the Setup

Before running the main app, test your configuration:

```bash
python tests/test_api.py
```

This will verify:
- API key validity
- S3 credentials (if provided)
- Data access and quality

### Using the Application

1. **Select Parameters**:
   - Enter a ticker symbol (e.g., SPY, AAPL)
   - Choose the "as of" date for historical data
   - Select an expiration date from available options

2. **Configure Display**:
   - Adjust number of strikes to show around ATM
   - Toggle ITM highlighting
   - Enable/disable Greeks display

3. **Analyze Options**:
   - View bid/ask spreads (or estimated values from trades)
   - Check volume and open interest
   - Review Greeks for risk assessment
   - Use the credit spread calculator for strategy analysis

## Data Sources

### REST API
- Real-time quotes (when available)
- Contract specifications
- Basic chain structure

### S3 Flat Files
- Daily aggregates (OHLC data)
- Trade-level data
- Historical volume
- Enhanced coverage for all strikes

### Data Limitations & Workarounds

When using flat files, some data may not be available:
- **Bid/Ask Quotes**: Estimated from last traded price and typical spreads
- **Greeks**: Calculated using Black-Scholes model
- **Open Interest**: Estimated from opening values when not directly available

## Project Structure

```
polygon_options_viewer/
├── app.py                  # Main Streamlit application
├── utils/
│   └── polygon_api.py      # Enhanced API wrapper with S3 support
├── tests/
│   └── test_api.py         # API functionality tests
├── requirements.txt        # Python dependencies
├── .env.sample            # Environment variables template
└── README.md              # This file
```

## Key Components

### PolygonOptionsAPI Class

Enhanced wrapper for Polygon.io that:
- Manages both REST API and S3 access
- Calculates Black-Scholes Greeks
- Estimates implied volatility
- Merges data from multiple sources
- Handles data quality issues gracefully

### Data Processing

- **Strike Parsing**: Extracts strike prices and types from option symbols
- **Data Merging**: Combines S3 and API data for completeness
- **Greeks Calculation**: Real-time Greeks using market data
- **Spread Estimation**: Intelligent bid/ask spread estimation based on liquidity

## Troubleshooting

### Common Issues

1. **403 Forbidden Error with S3**:
   - Ensure you have the correct subscription tier (Options Starter or higher)
   - Verify S3 credentials are correct
   - Check that you're accessing the right data type (aggregates vs trades)

2. **No Data Available**:
   - Check if markets were open on the selected date
   - Verify the ticker has options available
   - Try a more recent date

3. **Missing Bid/Ask Data**:
   - This is normal for historical data
   - The app will show estimated values based on trades
   - Use the "Last" price as a reference

### Data Quality Tips

- **Best Data**: Recent dates and liquid options (high volume)
- **Limited Data**: Older dates or illiquid strikes
- **S3 Benefits**: More complete strike coverage and historical depth

## Future Enhancements

- [ ] Add more Greeks (Charm, Vanna, etc.)
- [ ] Support for multi-leg strategies
- [ ] Historical volatility charts
- [ ] Options flow analysis
- [ ] Export functionality
- [ ] Real-time data integration

## Contributing

Feel free to submit issues, fork the repository, and create pull requests for any improvements.

## License

MIT License - See LICENSE file for details

## Acknowledgments

- Built with [Streamlit](https://streamlit.io/)
- Data provided by [Polygon.io](https://polygon.io/)
- Greeks calculations using scipy and numpy
- Charts powered by Plotly

## Author

Kshitij Singla

---

**Note**: This tool is for educational and analytical purposes. Always verify data and calculations before making trading decisions.