from playwright.sync_api import sync_playwright
import cv2
import numpy as np

def capture_url(url_or_html, is_url=True):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        if is_url:
            page.goto(url_or_html, wait_until="networkidle", timeout=15000)
        else:
            page.set_content(url_or_html)
        screenshot_bytes = page.screenshot()
        browser.close()
        
        # Convert bytes to cv2 BGR image
        nparr = np.frombuffer(screenshot_bytes, np.uint8)
        img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img_bgr

if __name__ == "__main__":
    html = "<html><body style='background:#0696D7;color:white;display:flex;align-items:center;justify-content:center;height:100vh;font-family:sans-serif;'><h1>Autodesk Automated Screenshot Capture Test</h1></body></html>"
    img = capture_url(html, is_url=False)
    print("Automated Screenshot Captured Successfully! Shape:", img.shape)
