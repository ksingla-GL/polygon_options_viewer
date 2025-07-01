#!/bin/bash

# Historical Options Chain Viewer - Setup Script

echo "🚀 Setting up Historical Options Chain Viewer..."
echo "============================================"

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $python_version"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "📦 Installing requirements..."
pip install -r requirements.txt

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p data
mkdir -p logs

# Copy .env.sample to .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp .env.sample .env
    echo "⚠️  Please edit .env file with your Polygon.io credentials"
else
    echo "✓ .env file already exists"
fi

# Make test script executable
chmod +x tests/test_api.py

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your Polygon.io credentials:"
echo "   - POLYGON_API_KEY (required)"
echo "   - POLYGON_S3_ACCESS_KEY (optional but recommended)"
echo "   - POLYGON_S3_SECRET_KEY (optional but recommended)"
echo ""
echo "2. Test your setup:"
echo "   python tests/test_api.py"
echo ""
echo "3. Run the application:"
echo "   streamlit run app.py"
echo ""
echo "For more information, see README.md"