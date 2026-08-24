"""
Report Generator module for UI Validation Engine.
Generates comprehensive JSON, CSV, and professionally formatted Excel (.xlsx) reports
containing complete defect audits, executive summaries, and element diagnostics.
"""

from __future__ import annotations

import csv
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

REPORTS_BASE_DIR = os.path.join(os.path.dirname(__file__), "reports")

REPORT_HEADERS = [
    ("root_url", "Root URL", 32),
    ("crawled_url", "Crawled URL", 40),
    ("page_title", "Page Title", 25),
    ("element_type", "Element Type", 16),
    ("element_identifier", "Element Identifier / Text", 30),
    ("element_selector", "Element Selector", 35),
    ("expected_behavior", "Expected Behavior", 45),
    ("actual_behavior", "Actual Behavior", 45),
    ("status", "Status", 12),
    ("defect_category", "Defect Category", 22),
    ("http_status", "HTTP Status", 14),
    ("error_message", "Error Message", 40),
    ("screenshot_path", "Screenshot Path", 30),
    ("timestamp", "Timestamp", 24),
]


class ReportGenerator:
    """
    Builds and saves JSON, CSV, and Excel reports for a completed crawl and validation run.
    """

    @staticmethod
    def ensure_run_dir(run_id: str) -> str:
        """Creates and returns the dedicated report directory for run_id."""
        run_dir = os.path.join(REPORTS_BASE_DIR, run_id)
        os.makedirs(run_dir, exist_ok=True)
        os.makedirs(os.path.join(run_dir, "evidence"), exist_ok=True)
        return run_dir

    @staticmethod
    def generate_json_report(run_dir: str, payload: dict) -> str:
        """Writes the structured JSON audit report."""
        file_path = os.path.join(run_dir, "report.json")
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.error(f"Failed to generate JSON report: {exc}")
        return file_path

    @staticmethod
    def generate_csv_report(run_dir: str, defects: List[dict]) -> str:
        """Writes the standard CSV audit report."""
        file_path = os.path.join(run_dir, "report.csv")
        try:
            with open(file_path, "w", encoding="utf-8", newline="") as f:
                fieldnames = [col[0] for col in REPORT_HEADERS]
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                
                # Write header row with readable labels
                writer.writerow({col[0]: col[1] for col in REPORT_HEADERS})
                
                for d in defects:
                    row = dict(d)
                    # Don't dump huge base64 into CSV cells
                    if str(row.get("screenshot_path") or "").startswith("data:"):
                        row["screenshot_path"] = "(embedded evidence; see JSON/images)"
                    writer.writerow(row)
        except Exception as exc:
            logger.error(f"Failed to generate CSV report: {exc}")
        return file_path

    @staticmethod
    def generate_excel_report(run_dir: str, payload: dict, defects: List[dict], pages: List[dict]) -> str:
        """
        Creates a styled, multi-tab Excel workbook using openpyxl.
        Tabs:
          1. Summary (Executive Dashboard KPIs)
          2. Defects & Issues (Color-coded audit finding records)
          3. Crawled Pages (Hierarchy and status)
        """
        file_path = os.path.join(run_dir, "report.xlsx")
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
            from openpyxl.utils import get_column_letter

            wb = Workbook()

            # --- TAB 1: EXECUTIVE SUMMARY ---
            ws_summary = wb.active
            ws_summary.title = "Summary"
            ws_summary.views.sheetView[0].showGridLines = True

            # Header Banner
            ws_summary.merge_cells("A1:D1")
            title_cell = ws_summary["A1"]
            title_cell.value = "Web UI Quality & Crawl Validation Audit Report"
            title_cell.font = Font(name="Segoe UI", size=15, bold=True, color="FFFFFF")
            title_cell.fill = PatternFill("solid", fgColor="0696D7")
            title_cell.alignment = Alignment(horizontal="center", vertical="center")
            ws_summary.row_dimensions[1].height = 36

            summary_meta = payload.get("summary") or {}
            config = payload.get("config") or {}

            kpi_rows = [
                ("Root Target URL", payload.get("root_url", "")),
                ("Baseline Root URL", payload.get("baseline_root_url") or "(None - Single Site Mode)"),
                ("Audit Run ID", payload.get("run_id", "")),
                ("Audit Timestamp", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")),
                ("Overall Audit Status", summary_meta.get("status", "PASS")),
                ("Total Pages Crawled", summary_meta.get("pages_crawled", len(pages))),
                ("Total Elements Checked", summary_meta.get("total_elements_checked", 0)),
                ("Total Links Checked", summary_meta.get("total_links_checked", 0)),
                ("Total Images Checked", summary_meta.get("total_images_checked", 0)),
                ("Total Interactions Checked", summary_meta.get("total_interactions_checked", 0)),
                ("Total Defects Detected", summary_meta.get("fail_count", 0)),
                ("Passed Checks", summary_meta.get("pass_count", 0)),
            ]

            thin_border = Border(
                left=Side(style="thin", color="E2E8F0"),
                right=Side(style="thin", color="E2E8F0"),
                top=Side(style="thin", color="E2E8F0"),
                bottom=Side(style="thin", color="E2E8F0"),
            )

            for i, (label, val) in enumerate(kpi_rows, start=3):
                cell_lbl = ws_summary.cell(row=i, column=1, value=label)
                cell_val = ws_summary.cell(row=i, column=2, value=str(val))
                cell_lbl.font = Font(name="Segoe UI", size=10, bold=True, color="334155")
                cell_lbl.fill = PatternFill("solid", fgColor="F8FAFC")
                cell_lbl.border = thin_border
                cell_val.font = Font(name="Segoe UI", size=10, color="0F172A")
                cell_val.border = thin_border
                ws_summary.row_dimensions[i].height = 22

                if label == "Overall Audit Status":
                    is_pass = str(val).upper() == "PASS"
                    cell_val.font = Font(name="Segoe UI", size=11, bold=True, color="166534" if is_pass else "991B1B")
                    cell_val.fill = PatternFill("solid", fgColor="DCFCE7" if is_pass else "FEE2E2")

            ws_summary.column_dimensions["A"].width = 28
            ws_summary.column_dimensions["B"].width = 50

            # --- TAB 2: DEFECTS & ISSUES ---
            ws_issues = wb.create_sheet(title="Issues & Findings")
            ws_issues.views.sheetView[0].showGridLines = True

            header_fill = PatternFill("solid", fgColor="0696D7")
            header_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")

            # Write header row
            for col_idx, (key, label, col_w) in enumerate(REPORT_HEADERS, start=1):
                c = ws_issues.cell(row=1, column=col_idx, value=label)
                c.fill = header_fill
                c.font = header_font
                c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                ws_issues.column_dimensions[get_column_letter(col_idx)].width = col_w
            ws_issues.row_dimensions[1].height = 28

            fail_fill = PatternFill("solid", fgColor="FEF2F2")
            pass_fill = PatternFill("solid", fgColor="F0FDF4")
            fail_badge = PatternFill("solid", fgColor="FEE2E2")
            pass_badge = PatternFill("solid", fgColor="DCFCE7")

            for r_idx, defect in enumerate(defects, start=2):
                status = str(defect.get("status") or "FAIL").upper()
                row_fill = fail_fill if status == "FAIL" else pass_fill

                for c_idx, (key, label, col_w) in enumerate(REPORT_HEADERS, start=1):
                    val = defect.get(key)
                    if val is None:
                        val = ""
                    if key == "screenshot_path" and str(val).startswith("data:"):
                        val = "(see evidence/ folder)"

                    cell = ws_issues.cell(row=r_idx, column=c_idx, value=str(val))
                    cell.font = Font(name="Segoe UI", size=9)
                    cell.border = thin_border
                    cell.alignment = Alignment(vertical="top", wrap_text=True)
                    cell.fill = row_fill

                    if key == "status":
                        cell.alignment = Alignment(horizontal="center", vertical="top")
                        cell.font = Font(name="Segoe UI", size=9, bold=True, color="166534" if status == "PASS" else "991B1B")
                        cell.fill = pass_badge if status == "PASS" else fail_badge

                ws_issues.row_dimensions[r_idx].height = 28

            # --- TAB 3: CRAWLED PAGES INVENTORY ---
            ws_pages = wb.create_sheet(title="Crawled Pages")
            ws_pages.views.sheetView[0].showGridLines = True

            page_headers = [
                ("url", "Page URL", 45),
                ("title", "Page Title", 30),
                ("depth", "Crawl Depth", 14),
                ("http_status", "HTTP Status", 14),
                ("elements_count", "Elements Discovered", 20),
                ("screenshot", "Screenshot Evidence File", 35),
                ("error", "Error / Exception", 35),
            ]

            for col_idx, (key, label, col_w) in enumerate(page_headers, start=1):
                c = ws_pages.cell(row=1, column=col_idx, value=label)
                c.fill = header_fill
                c.font = header_font
                c.alignment = Alignment(horizontal="center", vertical="center")
                ws_pages.column_dimensions[get_column_letter(col_idx)].width = col_w
            ws_pages.row_dimensions[1].height = 26

            for r_idx, page in enumerate(pages, start=2):
                counts = page.get("element_counts") or {}
                total_els = counts.get("total", 0)

                row_vals = [
                    page.get("url", ""),
                    page.get("title", ""),
                    page.get("depth", 0),
                    page.get("http_status", 0),
                    total_els,
                    page.get("screenshot", ""),
                    page.get("error", ""),
                ]

                for c_idx, val in enumerate(row_vals, start=1):
                    cell = ws_pages.cell(row=r_idx, column=c_idx, value=val)
                    cell.font = Font(name="Segoe UI", size=9)
                    cell.border = thin_border
                    cell.alignment = Alignment(vertical="center")

                ws_pages.row_dimensions[r_idx].height = 20

            wb.save(file_path)
        except Exception as exc:
            logger.error(f"Failed to generate Excel report: {exc}")

        return file_path
