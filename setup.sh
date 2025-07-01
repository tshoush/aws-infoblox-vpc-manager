#!/bin/bash

# AWS to InfoBlox VPC Manager Setup Script
# This script creates a virtual environment and installs dependencies

echo "=========================================="
echo "AWS to InfoBlox VPC Manager Setup"
echo "=========================================="

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.7+ first."
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"

# Create virtual environment
echo ""
echo "🔧 Creating virtual environment..."
if [ -d "venv" ]; then
    echo "⚠️  Virtual environment already exists. Removing old one..."
    rm -rf venv
fi

python3 -m venv venv

if [ $? -ne 0 ]; then
    echo "❌ Failed to create virtual environment"
    exit 1
fi

echo "✅ Virtual environment created successfully"

# Activate virtual environment
echo ""
echo "🔧 Activating virtual environment..."
source venv/bin/activate

if [ $? -ne 0 ]; then
    echo "❌ Failed to activate virtual environment"
    exit 1
fi

echo "✅ Virtual environment activated"

# Upgrade pip
echo ""
echo "🔧 Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo ""
echo "🔧 Installing Python packages..."
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "❌ Failed to install requirements"
    exit 1
fi

echo "✅ All packages installed successfully"

# Create config file if it doesn't exist
echo ""
echo "🔧 Setting up configuration..."
if [ ! -f "config.env" ]; then
    cp config.env.template config.env
    echo "✅ Created config.env from template"
    echo "⚠️  Please edit config.env with your InfoBlox details before running the tool"
else
    echo "ℹ️  config.env already exists, skipping creation"
fi

echo ""
echo "=========================================="
echo "🎉 Setup Complete!"
echo "=========================================="
echo ""
echo "Next Steps:"
echo "1. Edit config.env with your InfoBlox Grid Master details:"
echo "   nano config.env"
echo ""
echo "2. Test the parsing functionality:"
echo "   source venv/bin/activate"
echo "   python example_usage.py"
echo ""
echo "3. Run the main tool in dry-run mode (safe, no changes made):"
echo "   python aws_infoblox_vpc_manager.py --dry-run"
echo ""
echo "4. Run with actual changes (after testing):"
echo "   python aws_infoblox_vpc_manager.py"
echo ""
echo "5. For help and options:"
echo "   python aws_infoblox_vpc_manager.py --help"
echo ""
echo "🔒 Remember: Always test with --dry-run first!"
echo ""
