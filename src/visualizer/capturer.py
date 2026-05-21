from playwright.sync_api import sync_playwright
import os

def capture_html_to_png(html_content: str, output_path: str):
    """
    Renders HTML content and captures it as a PNG image.
    Uses body element's bounding box for precision.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html_content)
        
        # Ensure the output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Take a screenshot of the body which contains our tables
        # full_page=True ensures we get the entire height if it scrolls
        temp_path = output_path + ".tmp"
        page.locator("body").screenshot(path=temp_path)
        os.replace(temp_path, output_path)
        
        browser.close()
