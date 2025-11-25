#!/bin/bash

# Local development setup script
# Usage: ./scripts/local-setup.sh

set -e

echo "🔧 Setting up local development environment..."

# Check Python version
echo "Checking Python version..."
python3 --version

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Copy .env.example if .env doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env with your configuration"
fi

echo "✅ Local setup completed!"
echo ""
echo "Next steps:"
echo "1. Edit .env with your GCP project configuration"
echo "2. Set up service account credentials"
echo "3. Run: source venv/bin/activate"
echo "4. Run: python main.py"
