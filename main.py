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
playwright = None
browser = None
browser_initialized = False


async def init_browser():
    """
    Initialize the Playwright browser once for reuse across requests
    """
    global playwright, browser, browser_initialized

    if browser_initialized and browser:
        # Check if browser is still alive
        try:
            # Try to get browser contexts to test if browser is still alive
            await browser.contexts()
            return browser
        except Exception as e:
            logger.warning(f"Browser seems to be closed, reinitializing: {e}")
            browser_initialized = False
            browser = None
            playwright = None

    try:
        logger.info("Initializing Playwright browser...")

        # Start Playwright
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
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
                "--disable-web-security",  # Added for better compatibility
                "--no-first-run",
            ],
        )

        browser_initialized = True
        logger.info("Successfully initialized Playwright browser")
        return browser

    except Exception as e:
        logger.error(f"Error initializing browser: {e}")
        browser_initialized = False
        browser = None
        playwright = None
        raise e


async def cleanup_browser():
    """
    Clean up browser resources
    """
    global playwright, browser, browser_initialized

    try:
        if browser:
            await browser.close()
    except Exception as e:
        logger.warning(f"Error closing browser: {e}")

    try:
        if playwright:
            await playwright.stop()
    except Exception as e:
        logger.warning(f"Error stopping playwright: {e}")

    browser = None
    playwright = None
    browser_initialized = False


async def get_tiktok_followers_with_playwright(username):
    """
    Scrape TikTok followers count using Playwright to handle JavaScript rendering
    """
    page = None

    try:
        # Initialize browser if not already done or if it's been closed
        browser_instance = await init_browser()

        url = f"https://www.tiktok.com/@{username}"
        logger.info(f"Scraping followers count from: {url}")

        # Create a new browser context for isolation
        context = await browser_instance.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # Create a new page
        page = await context.new_page()

        # Navigate to the TikTok profile with longer timeout
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
        except Exception as e:
            logger.warning(f"Network idle timeout, continuing anyway: {e}")
            await page.goto(url, timeout=30000)

        # Wait for the page to load
        await page.wait_for_timeout(5000)

        followers_count = None

        # Try to find the followers count element with optimized selectors
        logger.info("Looking for followers count element...")

        # Optimized selectors - prioritize the most effective ones first
        selectors = [
            '[data-e2e="followers-count"]',
            'strong[data-e2e="followers-count"]',
            '[title*="Followers" i]',
            '.number[data-e2e="followers-count"]',
            '[data-testid="followers-count"]',
            'strong[title*="Followers"]',
        ]

        # Try each selector
        for selector in selectors:
            try:
                logger.info(f"Trying selector: {selector}")
                element = await page.wait_for_selector(selector, timeout=8000)
                if element:
                    text = await element.text_content()
                    text = text.strip() if text else ""
                    if text and re.match(r"^[\d,.KMBkmb]+$", text):
                        followers_count = text
                        logger.info(
                            f"Followers found with selector '{selector}': {followers_count}"
                        )
                        break
            except Exception as e:
                logger.info(f"Selector '{selector}' not found or timeout: {e}")
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
                    r'"followerCount"\s*:\s*(\d+)',
                    r"([\d,.]+[KMBkmb]?)\s*Followers",
                    r"Followers\s*([\d,.]+[KMBkmb]?)",
                    r'"stats".*?"followerCount"\s*:\s*"?(\d+)"?',
                ]

                for pattern in patterns:
                    matches = re.findall(pattern, page_source, re.IGNORECASE)
                    if matches:
                        followers_count = matches[0]
                        logger.info(
                            f"Followers found with pattern '{pattern}': {followers_count}"
                        )
                        break

            except Exception as e:
                logger.error(f"Error during general search: {e}")

        # Close the context (which closes all pages in it)
        await context.close()

        return followers_count

    except Exception as e:
        logger.error(f"Error in get_tiktok_followers_with_playwright: {e}")
        # Clean up in case of error
        try:
            if page:
                await page.close()
        except:
            pass
        return None


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

    # Remove any commas first
    count = str(count).replace(",", "")

    # If it's already a number, just return it formatted
    if count.isdigit():
        return f"{int(count):,}"

    # Check if it has a multiplier
    if len(count) > 0:
        suffix = count[-1]
        if suffix in multipliers:
            try:
                number = float(count[:-1])
                count_value = number * multipliers[suffix]
                return f"{int(count_value):,}"
            except ValueError:
                return count

    return count


@app.on_event("startup")
async def startup_event():
    """Initialize browser on startup"""
    await init_browser()


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up browser on shutdown"""
    await cleanup_browser()


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
    global browser, browser_initialized
    browser_status = (
        "initialized" if browser_initialized and browser else "not initialized"
    )
    return {"status": "healthy", "browser_status": browser_status}


@app.get("/followers/{username}")
async def get_followers(username: str):
    # Validate username
    if not username or len(username.strip()) == 0:
        raise HTTPException(status_code=400, detail="Username is required")

    # Clean username (remove @ if present)
    username = username.strip().lstrip("@")

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
                "timestamp": datetime.now().isoformat(),
            }
        else:
            raise HTTPException(
                status_code=404,
                detail="Could not retrieve followers count. The profile might be private, not exist, or TikTok might be blocking the request.",
            )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error for username '{username}': {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
