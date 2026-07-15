from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from importlib.util import find_spec
from pathlib import Path

from qa_agents.automation_exporters import write_runtime_support
from qa_agents.models import AutomationRunResult, AutomationRunStatus


class AutomationRunnerAgent:
    """Run generated Playwright pytest automation projects and write execution reports."""

    def run(
        self,
        project_dir: str | Path,
        target_url: str,
        headed: bool = False,
        timeout_seconds: int = 600,
        pytest_args: list[str] | None = None,
    ) -> AutomationRunResult:
        root = Path(project_dir).resolve()
        self._validate_project(root)
        if not target_url.strip():
            raise ValueError("Target URL is required.")

        write_runtime_support(root, target_url.strip())
        pytest_args = pytest_args or []
        timeout_args = _pytest_timeout_args(pytest_args)
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:rerunfailures",
            "--tb=short",
            *timeout_args,
            *pytest_args,
        ]
        env = os.environ.copy()
        env["TEST_URL"] = target_url.strip()
        env["HEADLESS"] = "false" if headed else "true"
        env.setdefault("PLAYWRIGHT_ACTION_TIMEOUT_MS", "3000")
        env.setdefault("PLAYWRIGHT_NAVIGATION_TIMEOUT_MS", "15000")
        env.setdefault("AUTOAI_LOCATOR_TIMEOUT_MS", "900")
        env.setdefault("AUTOAI_MAX_LOCATOR_CANDIDATES", "10")

        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            duration = time.monotonic() - started
            status = AutomationRunStatus.PASSED if completed.returncode == 0 else AutomationRunStatus.FAILED
            result = AutomationRunResult(
                project_dir=str(root),
                target_url=target_url.strip(),
                command=command,
                status=status,
                exit_code=completed.returncode,
                duration_seconds=round(duration, 2),
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.monotonic() - started
            result = AutomationRunResult(
                project_dir=str(root),
                target_url=target_url.strip(),
                command=command,
                status=AutomationRunStatus.TIMEOUT,
                exit_code=None,
                duration_seconds=round(duration, 2),
                stdout=_decode_timeout_output(exc.stdout),
                stderr=_decode_timeout_output(exc.stderr) or f"Timed out after {timeout_seconds} seconds.",
            )
        except OSError as exc:
            duration = time.monotonic() - started
            result = AutomationRunResult(
                project_dir=str(root),
                target_url=target_url.strip(),
                command=command,
                status=AutomationRunStatus.ERROR,
                exit_code=None,
                duration_seconds=round(duration, 2),
                stderr=str(exc),
            )

        return _write_reports(root, result)

    def _validate_project(self, root: Path) -> None:
        if not root.is_dir():
            raise FileNotFoundError(f"Automation project directory not found: {root}")
        tests_dir = root / "tests"
        if not tests_dir.is_dir():
            raise ValueError(
                f"{root} does not look like a generated automation project; missing tests/ folder."
            )
        if not any(tests_dir.glob("test_*.py")):
            raise ValueError(f"{root} does not contain pytest test files under tests/.")


def _write_reports(root: Path, result: AutomationRunResult) -> AutomationRunResult:
    report_dir = root / "test-results"
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = report_dir / f"autoai-run-{stamp}.json"
    markdown_path = report_dir / f"autoai-run-{stamp}.md"

    updated = result.model_copy(
        update={
            "report_json_path": str(json_path),
            "report_markdown_path": str(markdown_path),
        }
    )
    json_path.write_text(json.dumps(updated.model_dump(mode="json"), indent=2), encoding="utf-8")
    markdown_path.write_text(_to_markdown(updated), encoding="utf-8")
    return updated


def _pytest_timeout_args(pytest_args: list[str]) -> list[str]:
    if any(arg.startswith("--timeout") for arg in pytest_args):
        return []
    if find_spec("pytest_timeout") is None:
        return []
    return ["--timeout=45"]


def _to_markdown(result: AutomationRunResult) -> str:
    return f"""# AutoAI automation run

- Status: {result.status.value}
- Target URL: {result.target_url}
- Project: `{result.project_dir}`
- Command: `{" ".join(result.command)}`
- Exit code: {result.exit_code if result.exit_code is not None else "n/a"}
- Duration: {result.duration_seconds}s

## stdout

```text
{result.stdout.strip() or "No stdout."}
```

## stderr

```text
{result.stderr.strip() or "No stderr."}
```
"""


def _decode_timeout_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value
