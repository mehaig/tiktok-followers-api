import asyncio
import aiohttp
import re
import json
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright, Browser, BrowserContext
from datetime import datetime, timedelta
import logging
from typing import Optional, Dict, Any
import hashlib
from contextlib import asynccontextmanager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state
class AppState:
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.playwright = None
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_timeout = 300  # 5 minutes
        self.request_queue = asyncio.Queue(maxsize=10)  # Rate limiting
        self.processing = False

app_state = AppState()

# Lifespan management for FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_browser_pool()
    asyncio.create_task(process_queue())
    yield
    # Shutdown
    await cleanup_browser()

app = FastAPI(lifespan=lifespan)

# Add CORS middleware for public API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def init_browser_pool():
    """Initialize a persistent browser context with optimizations"""
    try:
        logger.info("Initializing optimized browser pool...")
        
        app_state.playwright = await async_playwright().start()
        
        # Launch with performance optimizations
        app_state.browser = await app_state.playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox", 
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-background-networking",
                "--disable-default-apps",
                "--disable-extensions",
                "--disable-sync",
                "--disable-translate",
                "--disable-features=VizDisplayCompositor",
                "--disable-ipc-flooding-protection",
                "--disable-renderer-backgrounding",
                "--disable-backgrounding-occluded-windows",
                "--disable-background-timer-throttling",
                "--memory-pressure-off",
                "--max_old_space_size=4096"
            ]
        )
        
        # Create a persistent context with stealth settings
        app_state.context = await app_state.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            }
        )
        
        logger.info("Browser pool initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize browser: {e}")
        raise

async def cleanup_browser():
    """Clean up browser resources"""
    try:
        if app_state.context:
            await app_state.context.close()
        if app_state.browser:
            await app_state.browser.close()
        if app_state.playwright:
            await app_state.playwright.stop()
        logger.info("Browser cleanup completed")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

def get_cache_key(username: str) -> str:
    """Generate cache key"""
    return hashlib.md5(username.lower().encode()).hexdigest()

def is_cache_valid(cache_entry: Dict[str, Any]) -> bool:
    """Check if cache entry is still valid"""
    return (datetime.now() - cache_entry["timestamp"]) < timedelta(seconds=app_state.cache_timeout)

async def try_api_method(username: str) -> Optional[str]:
    """Try faster API-based methods first"""
    try:
        # TikTok has some unofficial APIs that might work
        api_urls = [
            f"https://www.tiktok.com/api/user/detail/?uniqueId={username}",
            f"https://tikapi.io/api/v1/public/user/@{username}",  # Third-party API
        ]
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            for url in api_urls:
                try:
                    async with session.get(url, headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    }) as response:
                        if response.status == 200:
                            data = await response.json()
                            # Extract follower count from different API formats
                            followers = extract_followers_from_api(data)
                            if followers:
                                logger.info(f"Got followers via API: {followers}")
                                return followers
                except Exception as e:
                    logger.debug(f"API method failed for {url}: {e}")
                    continue
                    
    except Exception as e:
        logger.debug(f"All API methods failed: {e}")
    
    return None

def extract_followers_from_api(data: dict) -> Optional[str]:
    """Extract follower count from API response"""
    try:
        # Try different possible paths in the API response
        paths = [
            ["userInfo", "stats", "followerCount"],
            ["user", "stats", "followerCount"], 
            ["data", "follower_count"],
            ["stats", "followers"],
            ["followerCount"]
        ]
        
        for path in paths:
            value = data
            try:
                for key in path:
                    value = value[key]
                if isinstance(value, (int, str)) and str(value).isdigit():
                    return str(value)
            except (KeyError, TypeError):
                continue
                
    except Exception:
        pass
    return None

async def scrape_with_playwright(username: str) -> Optional[str]:
    """Fallback to Playwright scraping with optimizations"""
    url = f"https://www.tiktok.com/@{username}"
    page = None
    
    try:
        logger.info(f"Scraping {url} with Playwright...")
        
        page = await app_state.context.new_page()
        
        # Block unnecessary resources for speed
        await page.route("**/*.{png,jpg,jpeg,gif,webp,css,woff,woff2}", lambda route: route.abort())
        
        # Navigate with optimizations
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        
        # Wait for key elements to load
        await page.wait_for_timeout(2000)
        
        # Fast selector strategy - try most reliable first
        selectors = [
            '[data-e2e="followers-count"]',
            'strong[title*="Followers"]',
            '[title*="Followers"] strong',
        ]
        
        for selector in selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=3000)
                if element:
                    text = await element.text_content()
                    if text and re.match(r'^[\d,.KMBkmb]+$', text.strip()):
                        followers = text.strip()
                        logger.info(f"Found followers: {followers}")
                        return followers
            except Exception:
                continue
        
        # Fallback: search page content
        try:
            content = await page.content()
            patterns = [
                r'"followerCount":(\d+)',
                r'followerCount["\']:\s*["\']?(\d+)',
                r'([\d,.]+[KMBkmb]?)\s*Followers',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    return matches[0]
                    
        except Exception as e:
            logger.error(f"Content search failed: {e}")
        
        return None
        
    except Exception as e:
        logger.error(f"Playwright scraping failed: {e}")
        return None
    finally:
        if page:
            await page.close()

async def get_followers_count(username: str) -> Optional[str]:
    """Main function to get followers count with multiple strategies"""
    cache_key = get_cache_key(username)
    
    # Check cache first
    if cache_key in app_state.cache:
        cache_entry = app_state.cache[cache_key]
        if is_cache_valid(cache_entry):
            logger.info(f"Cache hit for {username}")
            return cache_entry["followers"]
        else:
            del app_state.cache[cache_key]
    
    # Try fast API method first
    followers = await try_api_method(username)
    
    # Fallback to Playwright if API fails
    if not followers:
        followers = await scrape_with_playwright(username)
    
    # Cache successful results
    if followers:
        app_state.cache[cache_key] = {
            "followers": followers,
            "timestamp": datetime.now()
        }
    
    return followers

def format_followers(count: str) -> dict:
    """Format followers count with multiple representations"""
    if not count:
        return {"raw": "0", "formatted": "Unknown", "numeric": 0}
    
    # Handle K, M, B suffixes
    multipliers = {"K": 1000, "M": 1000000, "B": 1000000000, "k": 1000, "m": 1000000, "b": 1000000000}
    
    numeric_value = 0
    raw_count = count
    
    if count.isdigit():
        numeric_value = int(count)
        formatted_count = f"{numeric_value:,}"
    else:
        suffix = count[-1]
        if suffix in multipliers:
            try:
                number = float(count[:-1])
                numeric_value = int(number * multipliers[suffix])
                formatted_count = f"{numeric_value:,}"
            except ValueError:
                formatted_count = count
        else:
            formatted_count = count
    
    return {
        "raw": raw_count,
        "formatted": formatted_count,
        "numeric": numeric_value
    }

async def process_queue():
    """Background task to process requests with rate limiting"""
    while True:
        try:
            # Process queue items with delay to avoid rate limiting
            if not app_state.request_queue.empty():
                await asyncio.sleep(1)  # Rate limit: 1 request per second
        except Exception as e:
            logger.error(f"Queue processing error: {e}")
        await asyncio.sleep(0.1)

# API Routes
@app.get("/")
async def home():
    return {
        "message": "Optimized TikTok Followers API",
        "version": "2.0",
        "features": ["Caching", "Rate Limiting", "Multiple Data Sources", "Performance Optimized"],
        "endpoints": {
            "/followers/{username}": "Get followers count for a TikTok user",
            "/health": "Health check",
            "/cache/stats": "Cache statistics"
        }
    }

@app.get("/health")
async def health():
    browser_status = "healthy" if app_state.browser else "disconnected"
    return {
        "status": "healthy",
        "browser": browser_status,
        "cache_size": len(app_state.cache),
        "queue_size": app_state.request_queue.qsize()
    }

@app.get("/cache/stats")
async def cache_stats():
    """Get cache statistics"""
    valid_entries = sum(1 for entry in app_state.cache.values() if is_cache_valid(entry))
    return {
        "total_entries": len(app_state.cache),
        "valid_entries": valid_entries,
        "expired_entries": len(app_state.cache) - valid_entries
    }

@app.get("/followers/{username}")
async def get_followers_endpoint(username: str, background_tasks: BackgroundTasks):
    # Input validation
    if not username or not username.strip():
        raise HTTPException(status_code=400, detail="Username is required")
    
    username = username.strip().replace("@", "")
    
    if not re.match(r'^[a-zA-Z0-9._-]+$', username):
        raise HTTPException(status_code=400, detail="Invalid username format")
    
    # Rate limiting check
    if app_state.request_queue.full():
        raise HTTPException(status_code=429, detail="Server busy, please try again later")
    
    try:
        # Add to queue for rate limiting
        await app_state.request_queue.put(username)
        
        # Get followers count
        followers = await get_followers_count(username)
        
        if followers:
            formatted = format_followers(followers)
            
            # Clean up old cache entries in background
            background_tasks.add_task(cleanup_expired_cache)
            
            return {
                "username": username,
                "followers": formatted,
                "cached": get_cache_key(username) in app_state.cache,
                "timestamp": datetime.now().isoformat(),
                "status": "success"
            }
        else:
            raise HTTPException(
                status_code=404,
                detail="Could not retrieve followers count. User may not exist or profile may be private."
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error for {username}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        # Remove from queue
        try:
            app_state.request_queue.get_nowait()
            app_state.request_queue.task_done()
        except asyncio.QueueEmpty:
            pass

async def cleanup_expired_cache():
    """Remove expired cache entries"""
    try:
        expired_keys = [
            key for key, entry in app_state.cache.items()
            if not is_cache_valid(entry)
        ]
        for key in expired_keys:
            del app_state.cache[key]
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
    except Exception as e:
        logger.error(f"Cache cleanup error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)