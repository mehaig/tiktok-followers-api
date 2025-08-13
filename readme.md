# TikTok Followers API for Leapcell.io

A simple TikTok followers API designed for easy deployment to Leapcell.io.

## Features

- Scrapes TikTok follower counts using Selenium WebDriver
- RESTful API endpoints
- No Docker required
- Optimized for Leapcell.io deployment

## API Endpoints

### Get Followers Count

```
GET /followers/<username>
```

Returns the follower count for the specified TikTok username.

**Example Response:**

```json
{
  "username": "mehaiscode",
  "followers": "708",
  "formatted_followers": "708",
  "status": "success"
}
```

### Health Check

```
GET /health
```

Returns the health status of the service.

## How It Works

The service uses Selenium WebDriver with Chrome in headless mode to:

1. Navigate to the TikTok profile page
2. Wait for JavaScript to render the content
3. Extract the follower count from the page
4. Return the data in JSON format

This approach is necessary because TikTok serves JavaScript-heavy content that cannot be scraped with simple HTTP requests.

## Requirements

- Python 3.9+
- Chrome browser (automatically installed by webdriver-manager)
- Selenium and Flask libraries

## Limitations

- Resource intensive (requires a full browser instance)
- May be rate-limited by TikTok
- Dependent on TikTok's page structure (selectors may need updating)
