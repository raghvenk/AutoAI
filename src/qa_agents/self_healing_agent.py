from __future__ import annotations

import re

from qa_agents.models import AutomationRunResult, SelfHealingSuggestion

LOCATOR_PATTERNS = [
    re.compile(r"waiting for (?P<locator>locator\(.+?\)|get_by_\w+\(.+?\))", re.IGNORECASE),
    re.compile(r"LocatorAssertions.+?(?P<locator>locator\(.+?\)|get_by_\w+\(.+?\))", re.IGNORECASE),
    re.compile(r"Error:.+?(?P<locator>locator\(.+?\)|get_by_\w+\(.+?\))", re.IGNORECASE),
]


class SelfHealingAgent:
    """Analyze locator-related execution failures and suggest safer alternatives."""

    def analyze(self, result: AutomationRunResult) -> list[SelfHealingSuggestion]:
        output = "\n".join(part for part in (result.stdout, result.stderr) if part)
        if not output.strip():
            return []

        suggestions: list[SelfHealingSuggestion] = []
        seen: set[str] = set()
        for line in output.splitlines():
            if not _looks_like_locator_failure(line):
                continue
            failed_locator = _extract_locator(line)
            if failed_locator is None:
                continue
            if _is_low_value_locator(failed_locator):
                continue
            key = failed_locator or line.strip()
            if key in seen:
                continue
            seen.add(key)
            recommendation, suggested = _recommendation_for(line, failed_locator)
            suggestions.append(
                SelfHealingSuggestion(
                    failed_locator=failed_locator,
                    failure_context=line.strip()[:500],
                    suggested_locators=suggested,
                    recommendation=recommendation,
                )
            )
        return suggestions


def _looks_like_locator_failure(line: str) -> bool:
    lowered = line.lower()
    return any(
        token in lowered
        for token in (
            "locator",
            "timeout",
            "strict mode violation",
            "waiting for",
            "to be visible",
            "to contain text",
        )
    ) and any(token in lowered for token in ("error", "timeout", "waiting", "visible", "strict"))


def _extract_locator(line: str) -> str | None:
    for pattern in LOCATOR_PATTERNS:
        match = pattern.search(line)
        if match:
            return match.group("locator")
    return None


def _suggest_locators(failed_locator: str | None) -> list[str]:
    if not failed_locator:
        return [
            "page.get_by_test_id('<stable-id>')",
            "page.get_by_role('<role>', name='<accessible name>')",
            "page.get_by_label('<field label>')",
        ]
    label = _quoted_text(failed_locator)
    if not label:
        return [
            "page.get_by_test_id('<stable-id>')",
            "page.get_by_role('<role>', name='<accessible name>')",
        ]
    safe_label = label.replace("'", "\\'")
    return [
        f"page.get_by_test_id('{_slug(label)}')",
        f"page.get_by_role('button', name='{safe_label}')",
        f"page.get_by_label('{safe_label}')",
        f"page.get_by_text('{safe_label}')",
    ]


def _recommendation_for(line: str, failed_locator: str | None) -> tuple[str, list[str]]:
    lowered = line.lower()
    if any(term in lowered for term in ("logged-in state", "after logging out", "after logout")):
        return (
            "This looks like a post-logout protected-action step, not a missing button. "
            "Verify it by navigating to the protected URL and asserting the login page or authorization "
            "error is shown.",
            [
                "page.goto(f'{base_url}/inventory.html')",
                "expect(page.locator(\"[data-test='login-button']\")).to_be_visible()",
                "expect(page.locator(\"[data-test='error']\")).to_be_visible()",
            ],
        )
    return (
        "Prefer a stable data-testid, role/name, label, or placeholder locator. "
        "If the generated self-healing helper found a fallback, promote that fallback "
        "into the generated test for long-term stability.",
        _suggest_locators(failed_locator),
    )


def _is_low_value_locator(failed_locator: str | None) -> bool:
    label = _quoted_text(failed_locator or "")
    if not label:
        return False
    return _is_stopword(label)


def _quoted_text(value: str) -> str | None:
    match = re.search(r"""['"]([^'"]{2,80})['"]""", value)
    return match.group(1) if match else None


def _is_stopword(value: str) -> bool:
    return value.lower() in {
        "a", "an", "and", "any", "as", "at", "be", "by", "can", "for", "from", "in",
        "into", "is", "it", "of", "on", "or", "perform", "that", "the", "then", "this",
        "to", "with",
    }


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "stable-id"
