import asyncio
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from playwright.async_api import async_playwright
import base64
from jinja2 import Environment, BaseLoader

app = FastAPI()

# use tailwindcss for styling
htmlHeader = """
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Playwright Screenshot</title>
    <script src="https://unpkg.com/@tailwindcss/browser@4"></script>
    <style type="text/tailwindcss">
    </style>
</head>
"""

# Define an error template
error_template_str = """
<!DOCTYPE html>
<html lang="en">
{{ htmlHeader }}
<body class="bg-gray-100 min-h-screen flex items-center justify-center">
    <div class="bg-white p-8 rounded shadow-md w-full max-w-4xl">
        <h1 class="text-2xl font-bold mb-4">Error</h1>
        <p class="mb-4">An error occurred while taking the screenshot: {{ error_message }}</p>
        <a href="/" class="text-blue-500 underline">Go back</a>
    </div>
</body>
</html>
"""

# Define a success template
# The template will display the screenshot of the page, the page title, and all links on the page
success_template_str = """
<!DOCTYPE html>
<html lang="en">
   {{ htmlHeader }}
   <body class="bg-gray-100 min-h-screen flex items-center justify-center">
      <div class="bg-white p-8 rounded shadow-md w-full max-w-4xl">
         <h1 class="text-2xl font-bold mb-4">Web Page Screenshot By Playwright</h1>
         <p class="mb-4">Enter a URL to take a screenshot of the page. Default is <a href="https://news.ycombinator.com" class="text-blue-500 underline">Hacker News</a>.</p>
         <form method="post" class="space-y-4">
            <div>
               <label for="url" class="block text-sm font-medium text-gray-700">URL</label>
               <input type="text" id="url" name="url" class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm" placeholder="https://news.ycombinator.com">
            </div>
            <button type="submit" class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 cursor-pointer">
            Take Screenshot
            </button>
         </form>
         {% if page_title %}
         <h2 class="text-xl font-bold mt-4">Screenshot of the Page</h2>
         <p class="mb-4">URL: <a href="{{ url }}" class="text-blue-500 underline">{{ url }}</a></p>
         <p class="mb-4">Page Title: {{ page_title }}</p>
         <img src="data:image/png;base64,{{ screenshot_base64 }}" alt="Screenshot" class="w-full h-auto rounded-md mb-4">
         <h2 class="text-xl font-bold mb-2">All Links on the Page</h2>
         <ul class="list-disc pl-4">
            {% for link in links %}
            <li><a href="{{ link.href }}" class="text-blue-500 underline">
               {{ link.text }}
               <span class="text-gray-500 text-sm">({{ link.href }})</span>
               </a>
            </li>
            {% endfor %}
         </ul>
         {% endif %}
      </div>
   </body>
</html>
"""

# Create a Jinja2 environment
env = Environment(loader=BaseLoader())


@app.get("/", response_class=HTMLResponse)
async def index():
    # Render the success template with default values
    success_template = env.from_string(success_template_str)
    return success_template.render(
        url="https://news.ycombinator.com",
        screenshot_base64="",
        links=[],
        titles=[],
        htmlHeader=htmlHeader,
    )


@app.post("/", response_class=HTMLResponse)
async def take_screenshot(url: str = Form(default="https://news.ycombinator.com")):
    # Validate the URL
    if not url.startswith("http"):
        url = "https://" + url

    # Launch Playwright's Chromium browser asynchronously
    async with async_playwright() as p:
        # Launch Chromium browser with specific arguments
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--single-process',
                '--no-sandbox',
                '--disable-setuid-sandbox',
            ],
        )
        # Create a new browser page
        page = await browser.new_page()
        try:
            # Navigate to the specified URL
            await page.goto(url)
            # Take a screenshot of the page
            screenshot = await page.screenshot()
            # Get the page title
            page_title = await page.title()

            # Extract all <a> tags' links and text content
            links_and_texts = await page.evaluate(
                # JavaScript code to extract link and text info from <a> tags
                """() => {
                const anchors = document.querySelectorAll('a');
                return Array.from(anchors).map(anchor => {
                    const text = anchor.textContent.replace(/<[^>]*>/g, '').trim();
                    return {
                        href: anchor.href,
                        text: text
                    };
                });
            }"""
            )
            # Filter and format the links and texts
            links_and_texts = [
                {"href": link["href"], "text": link["text"]} for link in links_and_texts
            ]

        except Exception as e:
            # Close the browser in case of an error
            await browser.close()
            # Render the error page template
            error_template = env.from_string(error_template_str)
            return error_template.render(error_message=str(e), htmlHeader=htmlHeader)
        # Close the browser after successful operations
        await browser.close()

    # Encode the screenshot to base64 string
    screenshot_base64 = base64.b64encode(screenshot).decode("utf-8")

    # Render the success page template
    success_template = env.from_string(success_template_str)
    return success_template.render(
        url=url,
        page_title=page_title,
        screenshot_base64=screenshot_base64,
        links=links_and_texts,
        htmlHeader=htmlHeader,
    )
