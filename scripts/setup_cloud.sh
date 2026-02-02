#!/bin/bash
# ============================================================================
# FLIGHT ARBITRAGE - CLOUD VM SETUP SCRIPT
# ============================================================================
# This script sets up everything you need to run the flight scraper on a
# cloud virtual machine (VM).
#
# WHAT THIS SCRIPT DOES:
# 1. Updates the system packages
# 2. Installs Python and pip
# 3. Installs the project dependencies
# 4. Installs Playwright browsers
# 5. Tests that everything works
#
# HOW TO USE:
# 1. Create a VM on your cloud provider (see README for options)
# 2. SSH into your VM
# 3. Clone your repository
# 4. Run this script: bash scripts/setup_cloud.sh
# ============================================================================

set -e  # Exit immediately if a command fails

echo "=============================================="
echo "Flight Arbitrage - Cloud Setup"
echo "=============================================="
echo ""

# ----------------------------------------------------------------------------
# Step 1: Update system packages
# ----------------------------------------------------------------------------
echo "[1/5] Updating system packages..."
sudo apt-get update -y
sudo apt-get upgrade -y

# ----------------------------------------------------------------------------
# Step 2: Install Python and pip
# ----------------------------------------------------------------------------
echo ""
echo "[2/5] Installing Python..."
sudo apt-get install -y python3 python3-pip python3-venv

# ----------------------------------------------------------------------------
# Step 3: Create virtual environment and install dependencies
# ----------------------------------------------------------------------------
echo ""
echo "[3/5] Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# ----------------------------------------------------------------------------
# Step 4: Install Playwright browsers and dependencies
# ----------------------------------------------------------------------------
echo ""
echo "[4/5] Installing Playwright browsers..."
# Install system dependencies needed by Playwright
sudo apt-get install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libatspi2.0-0

# Install Playwright browsers
playwright install chromium
playwright install-deps chromium

# ----------------------------------------------------------------------------
# Step 5: Test the installation
# ----------------------------------------------------------------------------
echo ""
echo "[5/5] Testing installation..."
python3 -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('https://www.google.com')
    title = page.title()
    browser.close()
    print(f'✓ Browser test passed! Page title: {title}')
"

# ----------------------------------------------------------------------------
# Done!
# ----------------------------------------------------------------------------
echo ""
echo "=============================================="
echo "✓ Setup complete!"
echo "=============================================="
echo ""
echo "To run the scraper:"
echo "  1. Activate the virtual environment:"
echo "     source venv/bin/activate"
echo ""
echo "  2. Run the test script:"
echo "     python src/scraper/google_flights.py"
echo ""
echo "  3. Or import and use in your own code:"
echo "     from src.scraper import search_google_flights"
echo ""
