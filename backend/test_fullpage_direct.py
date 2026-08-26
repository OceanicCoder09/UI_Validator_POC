import sys
import os
import cv2
import numpy as np

WORKSPACE_ROOT = r"f:\POC__"
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

os.chdir(WORKSPACE_ROOT)

from backend.main import capture_url_screenshot

def test_full_page_capture():
    url = "https://news.ycombinator.com"
    print(f"Testing capture for {url} with full_page=True...")
    
    img = capture_url_screenshot(url, width=1280, height=800, wait_seconds=1.5, full_page=True)
    if img is not None:
        h, w = img.shape[:2]
        print(f"Captured screenshot dimensions: {w}x{h}")
        cv2.imwrite("backend/test_fullpage_output.png", img)
        print("Saved to backend/test_fullpage_output.png")
    else:
        print("Capture returned None!")

if __name__ == "__main__":
    test_full_page_capture()
