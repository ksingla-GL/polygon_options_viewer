# Quick Start Guide - Options Chain Viewer

## 🚀 Setup Instructions

### 1. Create Conda Environment
```bash
# Create new environment
conda create -n options_chain python=3.10 -y

# Activate environment
conda activate options_chain
```

### 2. Install Dependencies
```bash
# Install from requirements.txt
pip install -r requirements.txt
```

### 3. Test API Access
```bash
# Run the test script to verify everything works
python tests/test_api.py
```

### 4. Run the Application
```bash
# Start the Streamlit app
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

## 📱 Using the App

### Main Features:
1. **Ticker Input**: Enter any stock symbol (e.g., SPY, NVDA, AAPL)
2. **Date Selection**: Choose historical date to view option chains
3. **Expiration Dropdown**: Select from available expiration dates
4. **Strike Range**: Adjust how many strikes to show around ATM

### Credit Spread Calculator:
1. Select sell and buy legs
2. Enter strike prices and premiums
3. Click "Calculate Spread"
4. View P&L diagram and key metrics

## 🔧 Data Limitations

Based on your Polygon API tier:
- ✅ **Available**: Strikes, Volume, Open Interest, VWAP
- ⚠️ **Limited**: Bid/Ask (only for liquid options)
- ❌ **Not Available**: Individual trades

---

**Built by Kshitij Singla** | Data provided by Polygon.io
