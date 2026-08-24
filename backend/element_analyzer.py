"""
Element Analyzer module for UI Validation Engine.
Performs full DOM introspection in Playwright to discover and extract typed metadata,
unique CSS selectors, bounding boxes, visibility states, and interactivity metrics
for all relevant web elements.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Complete JavaScript DOM discovery and attribute extractor script
ELEMENT_EXTRACTION_SCRIPT = r"""
() => {
  // Helper: Generates a unique CSS selector for a DOM element
  function generateCssSelector(el) {
    if (!el || el.nodeType !== Node.ELEMENT_NODE) return '';
    if (el.id && !el.id.includes(' ') && !el.id.includes(':')) {
      return `#${el.id}`;
    }
    const parts = [];
    let curr = el;
    while (curr && curr.nodeType === Node.ELEMENT_NODE && curr !== document.documentElement) {
      let tag = curr.tagName.toLowerCase();
      if (curr.id && !curr.id.includes(' ') && !curr.id.includes(':')) {
        parts.unshift(`#${curr.id}`);
        break;
      }
      
      const name = curr.getAttribute('name');
      if (name && ['input', 'select', 'textarea', 'button'].includes(tag)) {
        parts.unshift(`${tag}[name="${name}"]`);
        break;
      }
      
      const role = curr.getAttribute('role');
      if (role) {
        tag += `[role="${role}"]`;
      }
      
      let siblingIndex = 1;
      let sibling = curr.previousElementSibling;
      while (sibling) {
        if (sibling.tagName === curr.tagName) {
          siblingIndex++;
        }
        sibling = sibling.previousElementSibling;
      }
      
      if (siblingIndex > 1) {
        tag += `:nth-of-type(${siblingIndex})`;
      }
      
      parts.unshift(tag);
      curr = curr.parentElement;
      if (parts.length >= 4) break;
    }
    return parts.join(' > ') || el.tagName.toLowerCase();
  }

  // Helper: Evaluates rendering and visibility properties
  function getVisibility(el) {
    const style = window.getComputedStyle(el);
    const r = el.getBoundingClientRect();
    const isDisplayNone = style.display === 'none';
    const isVisibilityHidden = style.visibility === 'hidden' || style.visibility === 'collapse';
    const isOpacityZero = parseFloat(style.opacity || '1') === 0;
    const hasHiddenAttr = el.hasAttribute('hidden');
    const ariaHidden = el.getAttribute('aria-hidden') === 'true';
    const inViewport = r.width > 0 && r.height > 0 &&
      r.bottom >= 0 && r.right >= 0 &&
      r.top <= (window.innerHeight || 0) && r.left <= (window.innerWidth || 0);

    const isVisible = !isDisplayNone && !isVisibilityHidden && !isOpacityZero && !hasHiddenAttr && r.width > 0 && r.height > 0;

    return {
      display: style.display,
      visibility: style.visibility,
      opacity: style.opacity,
      pointerEvents: style.pointerEvents,
      cursor: style.cursor,
      zIndex: style.zIndex,
      ariaHidden,
      hiddenAttr: hasHiddenAttr,
      inViewport,
      isVisible,
      width: Math.round(r.width),
      height: Math.round(r.height)
    };
  }

  // Helper: Classifies semantic element type
  function classifyElement(el) {
    const tag = (el.tagName || '').toLowerCase();
    const type = (el.getAttribute('type') || '').toLowerCase();
    const role = (el.getAttribute('role') || '').toLowerCase();
    const cls = (el.className && typeof el.className === 'string') ? el.className.toLowerCase() : '';

    if (tag === 'nav' || role === 'navigation') return 'navigation';
    if (tag === 'iframe') return 'iframe';
    if (tag === 'table') return 'table';
    if (tag === 'img' || role === 'img') return 'image';
    if (tag === 'a' || role === 'link') return 'link';
    if (tag === 'label') return 'label';
    if (tag === 'select' || role === 'combobox' || role === 'listbox') return 'dropdown';
    if (tag === 'textarea') return 'textarea';
    if (tag === 'input') {
      if (['checkbox'].includes(type) || role === 'checkbox') return 'checkbox';
      if (['radio'].includes(type) || role === 'radio') return 'radio';
      if (['button', 'submit', 'reset'].includes(type)) return 'button';
      return 'input';
    }
    if (tag === 'button' || role === 'button') return 'button';
    if (tag === 'svg' || tag === 'i' || cls.includes('icon') || el.getAttribute('data-icon')) return 'icon';
    if (el.hasAttribute('onclick') || el.getAttribute('tabindex') === '0' || ['tab', 'menuitem'].includes(role)) {
      return 'interactive';
    }
    return null;
  }

  // Collect all candidate DOM nodes
  const nodes = Array.from(document.querySelectorAll(
    'a, button, input, select, textarea, img, nav, iframe, table, label, svg, i, ' +
    '[role="button"], [role="link"], [role="combobox"], [role="listbox"], [role="navigation"], ' +
    '[role="checkbox"], [role="radio"], [role="img"], [role="tab"], [role="menuitem"], ' +
    '[class*="icon"], [onclick], [tabindex="0"]'
  ));

  const results = [];
  const seenSelectors = new Set();

  for (const el of nodes) {
    const kind = classifyElement(el);
    if (!kind) continue;

    const selector = generateCssSelector(el);
    const r = el.getBoundingClientRect();
    const dedupeKey = `${kind}|${selector}|${Math.round(r.x)}|${Math.round(r.y)}`;
    if (seenSelectors.has(dedupeKey)) continue;
    seenSelectors.add(dedupeKey);

    const vis = getVisibility(el);
    const style = window.getComputedStyle(el);

    const text = (
      el.innerText ||
      el.textContent ||
      el.getAttribute('aria-label') ||
      el.getAttribute('placeholder') ||
      el.getAttribute('alt') ||
      el.getAttribute('title') ||
      el.value ||
      ''
    ).trim().slice(0, 300);

    const isDisabled = el.disabled === true ||
      el.getAttribute('aria-disabled') === 'true' ||
      el.classList.contains('disabled') ||
      vis.pointerEvents === 'none';

    const isReadOnly = el.readOnly === true || el.getAttribute('aria-readonly') === 'true';
    const isRequired = el.required === true || el.getAttribute('aria-required') === 'true';

    const overflowX = el.scrollWidth - el.clientWidth;
    const overflowY = el.scrollHeight - el.clientHeight;

    const imgBroken = kind === 'image' && (el.complete && (el.naturalWidth === 0 || el.naturalHeight === 0));

    results.push({
      kind,
      tag: (el.tagName || '').toLowerCase(),
      type: (el.getAttribute('type') || '').toLowerCase(),
      role: (el.getAttribute('role') || '').toLowerCase(),
      id: el.id || '',
      name: el.getAttribute('name') || '',
      selector,
      text,
      href: el.getAttribute('href') || '',
      src: el.currentSrc || el.getAttribute('src') || '',
      alt: el.getAttribute('alt') || '',
      placeholder: el.getAttribute('placeholder') || '',
      title: el.getAttribute('title') || '',
      ariaLabel: el.getAttribute('aria-label') || '',
      accessKey: el.accessKey || el.getAttribute('accesskey') || '',
      disabled: isDisabled,
      readOnly: isReadOnly,
      required: isRequired,
      hasOnClick: Boolean(el.getAttribute('onclick') || el.onclick),
      bbox: {
        x: Math.round(r.x),
        y: Math.round(r.y),
        width: Math.round(r.width),
        height: Math.round(r.height)
      },
      visibility: vis,
      overflow: {
        x: overflowX,
        y: overflowY,
        textOverflow: style.textOverflow,
        whiteSpace: style.whiteSpace
      },
      imageBroken: imgBroken,
      naturalWidth: kind === 'image' ? (el.naturalWidth || 0) : 0,
      naturalHeight: kind === 'image' ? (el.naturalHeight || 0) : 0
    });
  }

  return results;
}
"""


class ElementAnalyzer:
    """
    Analyzes web page DOM and extracts structured elements.
    """

    @staticmethod
    def extract_elements(page) -> List[Dict[str, Any]]:
        """
        Executes JavaScript introspection on the Playwright page and returns element inventory.
        """
        try:
            elements = page.evaluate(ELEMENT_EXTRACTION_SCRIPT) or []
            return elements
        except Exception as exc:
            logger.warning(f"DOM element extraction failed on page: {exc}")
            return []

    @staticmethod
    def get_element_label(el: dict) -> str:
        """
        Formats a friendly, informative label for an element.
        """
        kind = (el.get("kind") or el.get("tag") or "ELEMENT").upper()
        text = (
            el.get("text") or
            el.get("ariaLabel") or
            el.get("placeholder") or
            el.get("alt") or
            el.get("id") or
            el.get("name") or
            el.get("href") or
            el.get("src") or
            el.get("selector") or
            ""
        ).strip()
        if len(text) > 60:
            text = text[:57] + "..."
        return f"{kind}: {text}" if text else kind

    @staticmethod
    def get_element_counts(elements: List[dict]) -> Dict[str, int]:
        """
        Computes summary counts categorized by element kind.
        """
        counts = {
            "button": 0,
            "input": 0,
            "dropdown": 0,
            "textarea": 0,
            "link": 0,
            "image": 0,
            "checkbox": 0,
            "radio": 0,
            "navigation": 0,
            "iframe": 0,
            "table": 0,
            "icon": 0,
            "interactive": 0,
            "total": len(elements),
        }
        for el in elements:
            k = el.get("kind")
            if k in counts:
                counts[k] += 1
        return counts
