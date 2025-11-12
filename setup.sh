#!/bin/bash
# Setup script for LA Events Aggregator

echo "=================================="
echo "LA Events Aggregator - Setup"
echo "=================================="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Found Python $python_version"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo ""
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "✓ Created .env file"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and add your Google API keys!"
    echo "   - GOOGLE_MAPS_API_KEY"
    echo "   - GOOGLE_GEOCODING_API_KEY"
    echo ""
    echo "Get API keys from: https://console.cloud.google.com/apis/credentials"
else
    echo ""
    echo "✓ .env file already exists"
fi

# Create necessary directories
echo ""
echo "Creating directories..."
mkdir -p data logs

# Initialize database
echo ""
echo "Initializing database..."
python3 -c "from src.data.database import Database; db = Database('data/events.db'); print('✓ Database initialized')"

echo ""
echo "=================================="
echo "Setup Complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "1. Edit .env and add your Google API keys"
echo "2. Run scrapers: python run_scrapers.py"
echo "3. Start web server: python src/web/app.py"
echo "4. Open browser: http://localhost:8000"
echo ""
echo "For more information, see README.md"
echo ""
