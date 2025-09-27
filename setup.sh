#!/bin/bash
# Quick setup script for Teensy LED Matrix project

echo "==================================="
echo "Teensy LED Matrix Setup"
echo "==================================="

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or later."
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"

# Check for PlatformIO
if ! command -v platformio &> /dev/null; then
    echo "⚠️  PlatformIO not found. Installing..."
    pip3 install --user platformio
    export PATH=$PATH:~/.local/bin
fi

echo "✓ PlatformIO found"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Build firmware
echo ""
echo "Building Teensy firmware..."
platformio run

if [ $? -eq 0 ]; then
    echo ""
    echo "==================================="
    echo "✓ Setup complete!"
    echo "==================================="
    echo ""
    echo "Quick Start:"
    echo "1. Upload firmware:  platformio run --target upload"
    echo "2. Test connection:  source venv/bin/activate && python3 python_utils/test_serial.py"
    echo "3. Run demo:         python3 python_utils/test_serial.py --pattern"
    echo ""
    echo "For more commands, see README.md"
else
    echo ""
    echo "❌ Firmware build failed. Please check the error messages above."
    exit 1
fi