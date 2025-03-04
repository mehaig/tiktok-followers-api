#!/bin/sh

set -e
# Install FastAPI, Uvicorn, Pytest, and Playwright
pip install fastapi uvicorn pytest-playwright python-multipart jinja2

# Install Playwright and its dependencies
playwright install --with-deps chromium