"""Extract a typed inventory of UI elements from the current Playwright page."""

from __future__ import annotations

EXTRACT_JS = r"""
() => {
  const visible = (el) => {
    const style = window.getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return {
      display: style.display,
      visibility: style.visibility,
      opacity: style.opacity,
      ariaHidden: el.getAttribute('aria-hidden'),
      hiddenAttr: el.hasAttribute('hidden'),
      width: r.width,
      height: r.height,
      inViewport: r.width > 0 && r.height > 0 && r.bottom >= 0 && r.right >= 0 &&
        r.top <= (window.innerHeight || 0) && r.left <= (window.innerWidth || 0)
    };
  };

  const classify = (el) => {
    const tag = (el.tagName || '').toLowerCase();
    const type = (el.getAttribute('type') || '').toLowerCase();
    const role = (el.getAttribute('role') || '').toLowerCase();
    const cls = (el.className && typeof el.className === 'string') ? el.className.toLowerCase() : '';

    if (tag === 'table') return 'table';
    if (tag === 'img' || role === 'img') return 'image';
    if (tag === 'a' && el.getAttribute('href')) return 'link';
    if (tag === 'label') return 'label';
    if (tag === 'select' || role === 'combobox' || role === 'listbox') return 'dropdown';
    if (tag === 'textarea' || role === 'textbox' || (tag === 'input' && ['text', 'email', 'search', 'password', 'tel', 'url', 'number', ''].includes(type)))
      return 'textbox';
    if ((tag === 'input' && type === 'checkbox') || role === 'checkbox') return 'checkbox';
    if ((tag === 'input' && type === 'radio') || role === 'radio') return 'radio';
    if (tag === 'button' || type === 'button' || type === 'submit' || type === 'reset' || role === 'button')
      return 'button';
    if (tag === 'svg' || tag === 'i' || cls.includes('icon') || el.getAttribute('data-icon'))
      return 'icon';
    return null;
  };

  const nodes = Array.from(document.querySelectorAll(
    'button, input, select, textarea, label, a, img, table, svg, i, [role="button"], [role="checkbox"], [role="radio"], [role="textbox"], [role="combobox"], [role="listbox"], [role="img"], [class*="icon"]'
  ));

  const seen = new Set();
  const items = [];

  for (const el of nodes) {
    const kind = classify(el);
    if (!kind) continue;

    const r = el.getBoundingClientRect();
    const key = `${kind}|${Math.round(r.x)}|${Math.round(r.y)}|${el.tagName}`;
    if (seen.has(key)) continue;
    seen.add(key);

    const vis = visible(el);
    const text = (el.innerText || el.textContent || el.getAttribute('aria-label') || el.getAttribute('alt') || el.value || '').trim().slice(0, 200);
    const overflowX = el.scrollWidth - el.clientWidth;
    const overflowY = el.scrollHeight - el.clientHeight;
    const style = window.getComputedStyle(el);

    items.push({
      kind,
      tag: (el.tagName || '').toLowerCase(),
      type: (el.getAttribute('type') || ''),
      id: el.id || '',
      name: el.getAttribute('name') || '',
      text,
      href: el.getAttribute('href') || '',
      src: el.currentSrc || el.getAttribute('src') || '',
      alt: el.getAttribute('alt') || '',
      accessKey: el.accessKey || el.getAttribute('accesskey') || '',
      ariaLabel: el.getAttribute('aria-label') || '',
      required: el.hasAttribute('required') || el.getAttribute('aria-required') === 'true',
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
      imageBroken: kind === 'image' ? (el.complete && (el.naturalWidth === 0 || el.naturalHeight === 0)) : false,
      naturalWidth: kind === 'image' ? (el.naturalWidth || 0) : 0
    });
  }
  return items;
}
"""


def extract_elements(page) -> list:
    try:
        return page.evaluate(EXTRACT_JS) or []
    except Exception:
        return []


def element_label(el: dict) -> str:
    kind = (el.get("kind") or "element").upper()
    text = (el.get("text") or el.get("ariaLabel") or el.get("alt") or el.get("id") or el.get("name") or el.get("src") or el.get("href") or "").strip()
    if len(text) > 80:
        text = text[:77] + "..."
    return f"{kind}: {text}" if text else kind
