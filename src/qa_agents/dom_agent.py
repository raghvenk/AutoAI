from __future__ import annotations

import re
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Page, TimeoutError, sync_playwright

from qa_agents.models import (
    DomElement,
    DomInspectionReport,
    DomPage,
    DomSelectorCandidate,
    PageObjectModelExport,
    Priority,
)


class DomInspectionAgent:
    """Inspect reachable pages and export stable selector guidance plus a POM scaffold."""

    def inspect(
        self,
        target_url: str,
        max_pages: int = 3,
        headed: bool = False,
        timeout_ms: int = 15_000,
    ) -> DomInspectionReport:
        target_url = target_url.strip()
        if not target_url:
            raise ValueError("Target URL is required.")
        if not target_url.startswith(("http://", "https://")):
            raise ValueError("Target URL must start with http:// or https://.")

        max_pages = min(max(max_pages, 1), 10)
        visited: set[str] = set()
        queue: deque[str] = deque([target_url])
        pages: list[DomPage] = []
        origin = _origin(target_url)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not headed)
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(2_500)
            page.set_default_navigation_timeout(timeout_ms)
            while queue and len(pages) < max_pages:
                url = queue.popleft()
                normalized = _normalize_url(url)
                if normalized in visited:
                    continue
                visited.add(normalized)
                try:
                    page.goto(normalized, wait_until="domcontentloaded", timeout=timeout_ms)
                    try:
                        page.wait_for_load_state("networkidle", timeout=2_000)
                    except TimeoutError:
                        pass
                    dom_page = _inspect_page(page)
                except Exception as exc:
                    dom_page = DomPage(
                        url=normalized,
                        title="Inspection failed",
                        elements=[],
                        links=[],
                    )
                    dom_page.elements.append(
                        DomElement(
                            tag="error",
                            text=f"Unable to inspect page: {exc}",
                            selector_candidates=[],
                        )
                    )
                pages.append(dom_page)
                for link in dom_page.links:
                    absolute = _normalize_url(urljoin(normalized, link))
                    if _origin(absolute) == origin and absolute not in visited:
                        queue.append(absolute)
            context.close()
            browser.close()

        return DomInspectionReport(
            target_url=target_url,
            pages=pages,
            recommendations=[
                "Prefer data-testid/data-test/data-qa attributes for critical flows.",
                "Use role/name, label, and placeholder selectors before text or CSS fallbacks.",
                "Promote verified selectors into generated automation before making tests a release gate.",
            ],
        )

    def export_page_objects(
        self,
        report: DomInspectionReport,
        output_dir: str | Path,
    ) -> PageObjectModelExport:
        root = Path(output_dir)
        pages_dir = root / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)

        files = {
            "pages/base_page.py": _base_page_py(),
            "pages/app_page.py": _app_page_py(report),
            "README.md": _pom_readme(report),
        }
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return PageObjectModelExport(target_url=report.target_url, report=report, files=files)


def _inspect_page(page: Page) -> DomPage:
    payload = page.evaluate(
        """() => {
          const interesting = Array.from(document.querySelectorAll(
            'a,button,input,textarea,select,[role],[data-testid],[data-test],[data-qa]'
          ));
          const labelFor = new Map(Array.from(document.querySelectorAll('label[for]')).map(
            label => [label.getAttribute('for'), label.innerText.trim()]
          ));
          const cssPath = (element) => {
            const parts = [];
            let node = element;
            while (node && node.nodeType === Node.ELEMENT_NODE && parts.length < 5) {
              let part = node.tagName.toLowerCase();
              if (node.id) {
                part += `#${CSS.escape(node.id)}`;
                parts.unshift(part);
                break;
              }
              const testId = node.getAttribute('data-testid')
                || node.getAttribute('data-test')
                || node.getAttribute('data-qa');
              if (testId) {
                part += `[data-testid="${testId}"]`;
                parts.unshift(part);
                break;
              }
              const parent = node.parentElement;
              if (parent) {
                const same = Array.from(parent.children).filter(child => child.tagName === node.tagName);
                if (same.length > 1) part += `:nth-of-type(${same.indexOf(node) + 1})`;
              }
              parts.unshift(part);
              node = parent;
            }
            return parts.join(' > ');
          };
          return {
            url: location.href,
            title: document.title,
            links: Array.from(document.querySelectorAll('a[href]'))
              .map(a => a.getAttribute('href'))
              .filter(Boolean)
              .slice(0, 40),
            elements: interesting.slice(0, 160).map((el) => {
              const id = el.getAttribute('id');
              const wrappedLabel = el.closest('label')?.innerText?.trim();
              return {
                tag: el.tagName.toLowerCase(),
                role: el.getAttribute('role'),
                text: (el.innerText || el.value || '').trim().slice(0, 120),
                label: labelFor.get(id) || el.getAttribute('aria-label') || wrappedLabel || '',
                placeholder: el.getAttribute('placeholder') || '',
                name: el.getAttribute('name') || '',
                type: el.getAttribute('type') || '',
                href: el.getAttribute('href') || '',
                testid: el.getAttribute('data-testid')
                  || el.getAttribute('data-test')
                  || el.getAttribute('data-qa')
                  || '',
                css: cssPath(el)
              };
            })
          };
        }"""
    )
    return DomPage(
        url=payload.get("url") or page.url,
        title=payload.get("title") or None,
        links=payload.get("links") or [],
        elements=[_element_from_payload(item) for item in payload.get("elements", [])],
    )


def _element_from_payload(item: dict[str, str]) -> DomElement:
    candidates: list[DomSelectorCandidate] = []
    testid = item.get("testid", "").strip()
    role = item.get("role", "").strip() or _implicit_role(item)
    label = item.get("label", "").strip()
    placeholder = item.get("placeholder", "").strip()
    text = _clean_text(item.get("text", ""))
    css = item.get("css", "").strip()

    if testid:
        candidates.append(
            DomSelectorCandidate(
                selector=f"page.get_by_test_id({testid!r})",
                strategy="test-id",
                stability=Priority.HIGH,
                reason="Stable test id attribute found.",
            )
        )
    if role and text:
        candidates.append(
            DomSelectorCandidate(
                selector=f"page.get_by_role({role!r}, name={text!r})",
                strategy="role-name",
                stability=Priority.HIGH,
                reason="Accessible role/name selector.",
            )
        )
    if label:
        candidates.append(
            DomSelectorCandidate(
                selector=f"page.get_by_label({label!r})",
                strategy="label",
                stability=Priority.HIGH,
                reason="Form label or aria-label found.",
            )
        )
    if placeholder:
        candidates.append(
            DomSelectorCandidate(
                selector=f"page.get_by_placeholder({placeholder!r})",
                strategy="placeholder",
                stability=Priority.MEDIUM,
                reason="Placeholder can locate the field but may change with copy.",
            )
        )
    if text and len(text) <= 80:
        candidates.append(
            DomSelectorCandidate(
                selector=f"page.get_by_text({text!r})",
                strategy="text",
                stability=Priority.MEDIUM,
                reason="Visible text fallback.",
            )
        )
    if css:
        candidates.append(
            DomSelectorCandidate(
                selector=f"page.locator({css!r})",
                strategy="css",
                stability=Priority.LOW,
                reason="CSS fallback; verify before relying on it.",
            )
        )
    return DomElement(
        tag=item.get("tag", ""),
        role=role or None,
        text=text or None,
        label=label or None,
        placeholder=placeholder or None,
        name=item.get("name") or None,
        element_type=item.get("type") or None,
        href=item.get("href") or None,
        selector_candidates=candidates[:5],
    )


def _implicit_role(item: dict[str, str]) -> str:
    tag = item.get("tag", "")
    element_type = item.get("type", "")
    if tag == "button" or element_type in {"button", "submit", "reset"}:
        return "button"
    if tag == "a":
        return "link"
    if tag in {"input", "textarea"}:
        return "textbox"
    if tag == "select":
        return "combobox"
    return ""


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _normalize_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed._replace(fragment="").geturl()


def _origin(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _base_page_py() -> str:
    return '''from __future__ import annotations

from playwright.sync_api import Page, expect


class BasePage:
    def __init__(self, page: Page, base_url: str) -> None:
        self.page = page
        self.base_url = base_url.rstrip("/")

    def goto(self, path: str = "") -> None:
        self.page.goto(f"{self.base_url}/{path.lstrip('/')}" if path else self.base_url)

    def expect_url_contains(self, text: str) -> None:
        expect(self.page).to_have_url(lambda url: text in url)
'''


def _app_page_py(report: DomInspectionReport) -> str:
    lines = [
        "from __future__ import annotations",
        "",
        "from playwright.sync_api import Locator",
        "",
        "from .base_page import BasePage",
        "",
        "",
        "class AppPage(BasePage):",
        '    """Page object scaffold generated from DOM inspection."""',
        "",
    ]
    seen: set[str] = set()
    for page_index, dom_page in enumerate(report.pages, start=1):
        lines.append(f"    # Page {page_index}: {dom_page.url}")
        for element in dom_page.elements:
            if not element.selector_candidates:
                continue
            name = _method_name(element)
            if name in seen:
                continue
            seen.add(name)
            selector = element.selector_candidates[0].selector
            lines.extend(
                [
                    "    @property",
                    f"    def {name}(self) -> Locator:",
                    f"        return {selector.replace('page.', 'self.page.')}",
                    "",
                ]
            )
    if not seen:
        lines.extend(
            [
                "    @property",
                "    def page_body(self) -> Locator:",
                "        return self.page.locator('body')",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _pom_readme(report: DomInspectionReport) -> str:
    lines = [
        "# AutoAI Page Object Model Export",
        "",
        f"Target URL: `{report.target_url}`",
        "",
        "Use `pages/app_page.py` as a reviewed scaffold. "
        "Promote the best selectors into your generated tests.",
        "",
        "## Inspected pages",
    ]
    for page in report.pages:
        lines.extend(["", f"### {page.title or 'Untitled'}", "", f"- URL: `{page.url}`"])
        for element in page.elements[:25]:
            if element.selector_candidates:
                lines.append(
                    f"- `{element.selector_candidates[0].selector}` — {element.tag}"
                    f"{': ' + element.text if element.text else ''}"
                )
    return "\n".join(lines).strip() + "\n"


def _method_name(element: DomElement) -> str:
    source = element.label or element.placeholder or element.text or element.name or element.tag
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", source.lower()).strip("_") or element.tag
    return f"{slug[:48]}_locator"
