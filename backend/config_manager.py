"""
Configuration Manager for Web Page Crawling and UI Quality Validation Engine.
Centralizes default parameters, URL crawling boundaries, timeouts, and element validation policies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Set
from urllib.parse import urldefrag, urlparse


@dataclass
class CrawlConfig:
    """
    Configuration settings for recursive website crawling and UI element validation.
    """
    # Root target URL to start crawling from
    root_url: str
    
    # Optional baseline root URL (used for pairwise visual localization comparison against baseline)
    baseline_root_url: Optional[str] = None
    
    # Maximum recursion depth for link discovery (0 = root page only)
    max_depth: int = 2
    
    # Maximum total pages to crawl across the site
    max_pages: int = 10
    
    # If True, restrict crawl strictly to the same hostname / domain as root_url
    same_origin_only: bool = True
    
    # Viewport dimensions for headless browser
    viewport_width: int = 1280
    viewport_height: int = 800
    
    # Wait duration in seconds after page load before taking screenshot / running validation
    wait_seconds: float = 1.0
    
    # Navigation timeout in milliseconds
    timeout_ms: int = 25000
    
    # Validation feature flags
    check_links: bool = True
    check_images: bool = True
    check_interactions: bool = True
    
    # Safety settings: If True, only safely interact (hover/focus/click) with safe elements (tabs, accordions)
    # and strictly skip destructive elements (delete, remove, logout, checkout, purchase, etc.)
    safe_interactions_only: bool = True
    
    # User-Agent string to simulate standard desktop browser
    user_agent: Optional[str] = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36 UIValidator/2.0"
    )
    
    # File extensions to exclude from crawling
    skip_extensions: Set[str] = field(default_factory=lambda: {
        ".pdf", ".zip", ".tar", ".gz", ".7z", ".rar",
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp", ".tiff",
        ".mp4", ".mp3", ".avi", ".mov", ".wmv", ".webm", ".flv",
        ".css", ".js", ".mjs", ".json", ".xml",
        ".woff", ".woff2", ".ttf", ".eot", ".otf",
        ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".csv",
    })
    
    # Non-navigable URI protocols to ignore during link collection
    ignored_schemes: Set[str] = field(default_factory=lambda: {
        "mailto", "tel", "sms", "javascript", "data", "blob", "whatsapp", "callto"
    })

    def normalize_url(self, url: str) -> str:
        """
        Normalizes a URL by trimming whitespace, removing fragment hashes (#),
        lowercasing scheme and hostname, and removing redundant trailing slashes.
        """
        cleaned, _ = urldefrag((url or "").strip())
        if not cleaned:
            return ""
        parsed = urlparse(cleaned)
        if not parsed.scheme or not parsed.netloc:
            return cleaned
        
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path or "/"
        
        # Standardize non-root trailing slash: /about/ -> /about
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")
            
        query = f"?{parsed.query}" if parsed.query else ""
        return f"{scheme}://{netloc}{path}{query}"

    def is_same_origin(self, target_url: str) -> bool:
        """Checks whether target_url belongs to the same domain/origin as root_url."""
        pa = urlparse(self.normalize_url(self.root_url))
        pb = urlparse(self.normalize_url(target_url))
        return pa.scheme == pb.scheme and pa.netloc.lower() == pb.netloc.lower()

    def is_crawlable(self, candidate_url: str) -> bool:
        """
        Determines whether a URL is valid for crawling based on scheme,
        file extension exclusions, and origin constraints.
        """
        if not candidate_url:
            return False
        parsed = urlparse(candidate_url)
        
        # Check scheme
        if parsed.scheme.lower() not in ("http", "https"):
            return False
        
        # Check excluded static extensions
        path_lower = (parsed.path or "").lower()
        if any(path_lower.endswith(ext) for ext in self.skip_extensions):
            return False
            
        # Check origin boundary if same_origin_only is enabled
        if self.same_origin_only and not self.is_same_origin(candidate_url):
            return False
            
        return True
