# Playwright Web Scraper (FastAPI)

This project is a web scraper built with Playwright and FastAPI. It opens a Chrome browser, scrapes all links from a given webpage, and displays them. The purpose of this project is to educate users on how to deploy a web-scraping service on Leapcell.

## Features

- Uses Playwright for browser automation
- FastAPI for building the web service
- Extracts and displays all links from a webpage

## Project Structure

```
.
├── main.py                      # FastAPI application entry point
└── prepare_playwright_env.sh    # Script to set up Playwright and dependencies
```

## prepare_playwright_env.sh Explained

This script ensures all necessary dependencies are installed before running the scraper. It performs the following actions:

1. Installs required Python packages: `fastapi`, `uvicorn`, `pytest-playwright`, `python-multipart`, and `jinja2`.
2. Installs Playwright along with Chromium and its dependencies for proper browser automation.

### Script Content

```sh
#!/bin/sh

set -e
# Install FastAPI, Uvicorn, Pytest, and Playwright
pip install fastapi uvicorn pytest-playwright python-multipart jinja2

# Install Playwright and its dependencies
playwright install --with-deps chromium
```

## Deployment on Leapcell

This guide walks you through setting up and deploying the project on Leapcell.

### Prerequisites

Ensure you have the following:

- A Leapcell account
- Python installed (recommended: Python 3.9+)
- Playwright dependencies installed

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/leapcell/playwright-crawler-py
   cd playwright-crawler-py
   ```
2. Install dependencies and set up Playwright:
   ```bash
   chmod +x prepare_playwright_env.sh
   ./prepare_playwright_env.sh
   ```

### Running Locally

To start the FastAPI service, run:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

The application will be accessible at `http://localhost:8000`.

### Deploying on Leapcell

1. Push your code to a GitHub repository.
2. Log in to Leapcell and connect your repository.
3. Ensure `prepare_playwright_env.sh` is executed before running the service.
4. Deploy your application.

Once deployed, your application will be accessible via the Leapcell-generated domain.

## Contributing

Feel free to submit issues or pull requests to improve this project.

## Contact

For support, reach out via the Leapcell Discord community or email support@leapcell.io.
