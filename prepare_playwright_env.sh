#!/bin/sh
set -e

echo "Installing Python dependencies..."
# Install from requirements.txt for better version control
pip install -r requirements.txt

echo "Installing Playwright browsers..."
# Install Playwright and its dependencies
playwright install --with-deps chromium

echo "Setting up environment variables for Playwright..."
# Set environment variables for better performance in containers
export PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=false

echo "Playwright environment setup complete!"