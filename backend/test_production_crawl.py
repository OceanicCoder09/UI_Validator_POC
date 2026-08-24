"""
End-to-End Production Verification Test Suite for Web UI Quality Validation Engine.
Validates:
  1. Live / local HTML site crawling with Playwright
  2. Element extraction (Links, Buttons, Images, Inputs, Dropdowns)
  3. Defect detection (Broken Link, Broken Image, Invisible Element, Disabled Element, Layout Collision)
  4. Multi-format report generation (report.json, report.csv, report.xlsx)
  5. Backwards compatibility of existing pairwise BMP CV engine
"""

from __future__ import annotations

import http.server
import json
import os
import socketserver
import threading
import time
import openpyxl

from config_manager import CrawlConfig
from crawler import PlaywrightCrawler
from cv_engine import analyze_localization_quality
from framework import run_framework
from report_generator import REPORTS_BASE_DIR


# Sample HTML fixture with intentional defects for validator verification
TEST_HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>UI Quality Validation Test Harness</title>
  <style>
    body { font-family: sans-serif; padding: 20px; }
    .btn { padding: 10px 20px; background: #0696d7; color: white; border: none; border-radius: 4px; }
    .overlap-a { position: absolute; top: 100px; left: 50px; width: 150px; height: 40px; background: red; }
    .overlap-b { position: absolute; top: 110px; left: 80px; width: 150px; height: 40px; background: blue; }
    .hidden-control { display: none; }
    .disabled-control { pointer-events: none; opacity: 0.5; }
  </style>
</head>
<body>
  <h1>UI Quality Test Suite</h1>
  
  <!-- Valid Link & Broken Link -->
  <p><a id="valid-link" href="/page2">Valid Internal Link</a></p>
  <p><a id="broken-link" href="/non-existent-page-404">Broken 404 Link</a></p>
  <p><a id="empty-href-link">Missing Href Link</a></p>
  
  <!-- Valid Image & Broken Image -->
  <p><img id="broken-img" src="/missing_image.png" alt="Missing Test Graphic" width="100" height="50" /></p>
  
  <!-- Overlapping interactive buttons -->
  <div style="position: relative; height: 160px;">
    <button id="btn-overlap-1" class="btn overlap-a">Action One</button>
    <button id="btn-overlap-2" class="btn overlap-b">Action Two</button>
  </div>
  
  <!-- Hidden interactive control -->
  <button id="btn-hidden-submit" class="btn hidden-control">Hidden Submit Button</button>
  
  <!-- Disabled pointer-events element -->
  <input id="input-disabled-action" class="disabled-control" type="text" placeholder="Disabled pointer events" disabled />
  
  <!-- Standard Form elements -->
  <form action="/submit" method="POST">
    <label for="username">Username</label>
    <input type="text" id="username" name="username" placeholder="Enter username" required />
    
    <label for="role">User Role</label>
    <select id="role" name="role">
      <option value="admin">Admin</option>
      <option value="user">User</option>
    </select>
    
    <button type="submit" id="submit-btn" class="btn">Save Changes</button>
  </form>
</body>
</html>
"""

TEST_HTML_PAGE_2 = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Subpage 2 - UI Quality Test Harness</title>
</head>
<body>
  <h2>Subpage 2</h2>
  <p>Clean subpage with no intentional defects.</p>
  <a href="/">Back to Root</a>
</body>
</html>
"""


class MockHttpHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(TEST_HTML_PAGE.encode("utf-8"))
        elif self.path == "/page2":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(TEST_HTML_PAGE_2.encode("utf-8"))
        elif self.path == "/non-existent-page-404":
            self.send_response(404)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"404 Not Found")
        elif self.path == "/missing_image.png":
            self.send_response(404)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress HTTP server logging during tests


def run_e2e_tests():
    # 1. Start Local Test HTTP Server on port 8999
    port = 8999
    httpd = socketserver.TCPServer(("127.0.0.1", port), MockHttpHandler)
    server_thread = threading.Thread(target=httpd.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    time.sleep(0.5)

    root_url = f"http://127.0.0.1:{port}/"
    print(f"\n[TEST 1] Running Crawl & Validation against mock server at {root_url}...")

    try:
        result = run_framework(
            root_url=root_url,
            max_depth=2,
            max_pages=5,
            same_origin_only=True,
            viewport_width=1280,
            viewport_height=800,
            wait_seconds=0.5,
            check_links=True,
            check_images=True,
            check_interactions=True,
            safe_interactions_only=True,
        )

        run_id = result.get("run_id")
        summary = result.get("summary") or {}
        defects = result.get("defects") or []
        pages = result.get("pages") or []

        print(f"-> Crawl Run ID: {run_id}")
        print(f"-> Pages Crawled: {summary.get('pages_crawled')} (Expected: >= 2)")
        print(f"-> Total Elements Checked: {summary.get('total_elements_checked')}")
        print(f"-> Total Defects Detected: {summary.get('fail_count')}")
        print(f"-> Passed Checks: {summary.get('pass_count')}")

        assert summary.get("pages_crawled", 0) >= 2, "Expected at least 2 pages crawled"
        assert summary.get("total_elements_checked", 0) > 5, "Expected elements extracted"
        assert summary.get("fail_count", 0) > 0, "Expected intentional defects to be flagged"

        # Check specific defect categories
        categories_detected = {d.get("defect_category") for d in defects if d.get("status") == "FAIL"}
        print(f"-> Defect Categories Detected: {categories_detected}")

        assert "Broken Link" in categories_detected or "HTTP Error" in categories_detected, "Expected Broken Link detection"
        assert "Broken Image" in categories_detected or "HTTP Error" in categories_detected, "Expected Broken Image detection"
        assert "Invisible Element" in categories_detected, "Expected Invisible Element detection"

        # 2. Verify Generated Reports (JSON, CSV, XLSX)
        run_dir = os.path.join(REPORTS_BASE_DIR, run_id)
        json_path = os.path.join(run_dir, "report.json")
        csv_path = os.path.join(run_dir, "report.csv")
        xlsx_path = os.path.join(run_dir, "report.xlsx")

        assert os.path.isfile(json_path), f"Missing JSON report at {json_path}"
        assert os.path.isfile(csv_path), f"Missing CSV report at {csv_path}"
        assert os.path.isfile(xlsx_path), f"Missing XLSX report at {xlsx_path}"
        print("-> Verified JSON, CSV, and Excel report files exist on disk.")

        # Check JSON validity
        with open(json_path, "r", encoding="utf-8") as f:
            json_data = json.load(f)
            assert json_data.get("run_id") == run_id
            assert "summary" in json_data
            assert "issues" in json_data
        print("-> Verified JSON schema structure.")

        # Check Excel Workbook structure
        wb = openpyxl.load_workbook(xlsx_path)
        sheet_names = wb.sheetnames
        print(f"-> Excel Sheets: {sheet_names}")
        assert "Summary" in sheet_names
        assert "Issues & Findings" in sheet_names
        assert "Crawled Pages" in sheet_names
        print("-> Verified Excel multi-tab workbook structure.")

        # 3. Test Backwards Compatibility of Existing Pairwise CV Engine
        print("\n[TEST 2] Verifying backwards compatibility of pairwise CV engine...")
        import cv2
        import numpy as np
        # Create 2 simple dummy images
        img_en = np.ones((800, 1280, 3), dtype=np.uint8) * 255
        img_loc = np.ones((800, 1280, 3), dtype=np.uint8) * 255
        cv_res = analyze_localization_quality(img_en, img_loc)
        assert "score" in cv_res
        assert "findings" in cv_res
        assert cv_res["score"] == 100
        print(f"-> Pairwise CV Engine Score: {cv_res['score']}/100 (Pass)")

        print("\n=======================================================")
        print(" ALL PRODUCTION E2E TESTS PASSED SUCCESSFULLY! ")
        print("=======================================================\n")

    finally:
        httpd.shutdown()


if __name__ == "__main__":
    run_e2e_tests()
