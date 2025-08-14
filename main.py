import asyncio
from fastapi import FastAPI, HTTPException
from playwright.async_api import async_playwright
import re
from datetime import datetime, timedelta
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Global variables for browser instance reuse and caching
browser = None
browser_initialized = False


async def init_browser():
    """
    Initialize the Playwright browser once for reuse across requests
    """
    global browser, browser_initialized

    if browser_initialized:
        return browser

    try:
        logger.info("Initializing Playwright browser...")

        # Launch Playwright's Chromium browser asynchronously
        p = await async_playwright().start()
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--single-process",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-background-networking",
                "--disable-default-apps",
                "--disable-extensions",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-ipc-flooding-protection",
                "--disable-background-timer-throttling",
                "--disable-features=TranslateUI",
            ],
        )

        browser_initialized = True
        logger.info("Successfully initialized Playwright browser")
        return browser

    except Exception as e:
        logger.error(f"Error initializing browser: {e}")
        raise e


async def get_tiktok_followers_with_playwright(username):
    """
    Scrape TikTok followers count using Playwright to handle JavaScript rendering
    """
    global browser

    current_time = datetime.now()

    # Initialize browser if not already done
    if not browser_initialized:
        await init_browser()

    url = f"https://www.tiktok.com/@{username}"

    try:
        logger.info(f"Scraping followers count from: {url}")

        # Create a new browser page
        page = await browser.new_page()

        # Set user agent to avoid detection
        await page.set_extra_http_headers(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )

        # Navigate to the TikTok profile
        await page.goto(url, wait_until="networkidle")

        # Wait for the page to load
        await page.wait_for_timeout(3000)

        followers_count = None

        # Try to find the followers count element with optimized selectors
        logger.info("Looking for followers count element...")

        # Optimized selectors - prioritize the most effective ones first
        selectors = [
            '[data-e2e="followers-count"]',
            'strong[data-e2e="followers-count"]',
            '[title*="Followers" i]',
            '.number[data-e2e="followers-count"]',
        ]

        # Try each selector
        for selector in selectors:
            try:
                logger.info(f"Trying selector: {selector}")
                element = await page.wait_for_selector(selector, timeout=5000)
                if element:
                    text = await element.text_content()
                    text = text.strip()
                    if text and re.match(r"^[\d,.KMBkmb]+$", text):
                        followers_count = text
                        logger.info(
                            f"Followers found with selector '{selector}': {followers_count}"
                        )
                        break
            except Exception as e:
                logger.info(f"Timeout waiting for selector: {selector}, error: {e}")
                continue

        # If we still haven't found it, try a more general approach
        if not followers_count:
            logger.info("Trying general text search...")
            try:
                # Get page source
                page_source = await page.content()

                # Look for patterns in the page source
                patterns = [
                    r'"followerCount"\s*:\s*"(\d+)"',
                    r"([\d,.]+[KMBkmb]?)\s*Followers",
                    r"Followers\s*([\d,.]+[KMBkmb]?)",
                ]

                for pattern in patterns:
                    matches = re.findall(pattern, page_source, re.IGNORECASE)
                    if matches:
                        followers_count = matches[0]
                        logger.info(
                            f"Followers found with pattern '{pattern}': {followers_count}"
                        )
                        break

                # If still not found, look for any large numbers
                if not followers_count:
                    numbers = re.findall(r"\b\d{3,}\b", page_source)
                    for number in numbers:
                        if int(number) > 1000:
                            followers_count = number
                            logger.info(
                                f"Potential followers count found (large number): {followers_count}"
                            )
                            break
            except Exception as e:
                logger.error(f"Error during general search: {e}")

        # Close the page
        await page.close()

        return followers_count

    except Exception as e:
        logger.error(f"Error: {e}")
        # Close the page in case of an error
        try:
            await page.close()
        except:
            pass
        return False


def format_followers_count(count):
    """
    Format the followers count for better readability
    """
    if not count:
        return "Unknown"

    # Handle formatted numbers like 1.2M, 3.4K, etc.
    multipliers = {
        "K": 1000,
        "M": 1000000,
        "B": 1000000000,
        "k": 1000,
        "m": 1000000,
        "b": 1000000000,
    }

    # If it's already a number, just return it formatted
    if count.isdigit():
        return f"{int(count):,}"

    # Check if it has a multiplier
    suffix = count[-1]
    if suffix in multipliers:
        try:
            number = float(count[:-1])
            count_value = number * multipliers[suffix]
            return f"{int(count_value):,}"
        except ValueError:
            return count

    return count


@app.get("/")
async def home():
    return {
        "message": "TikTok Followers API",
        "endpoints": {
            "/followers/{username}": "Get followers count for a TikTok user",
            "/health": "Health check",
        },
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/followers/{username}")
async def get_followers(username: str):
    # Validate username
    if not username or len(username) == 0:
        raise HTTPException(status_code=400, detail="Username is required")

    try:
        # Get followers count
        followers = await get_tiktok_followers_with_playwright(username)

        if followers:
            formatted_count = format_followers_count(followers)
            return {
                "username": username,
                "followers": followers,
                "formatted_followers": formatted_count,
                "status": "success",
            }
        else:
            raise HTTPException(
                status_code=404, detail="Could not retrieve followers count"
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
