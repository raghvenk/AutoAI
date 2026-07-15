from __future__ import annotations

import csv
import json
import re
import shlex
import tempfile
import uuid
import zipfile
from io import StringIO
from pathlib import Path
from typing import Annotated

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response

from qa_agents.artifact_exporters import artifact_to_markdown, export_artifact
from qa_agents.automation_agent import AutomationAgent
from qa_agents.automation_exporters import export_automation_project
from qa_agents.automation_runner_agent import AutomationRunnerAgent
from qa_agents.config import get_settings
from qa_agents.defect_agent import DefectCreationAgent
from qa_agents.design_agent import TestDesignDataAgent
from qa_agents.exporters import export_suite, suite_to_markdown
from qa_agents.models import SourceMaterial
from qa_agents.ollama import OllamaError
from qa_agents.planning_agent import TestPlanningAgent
from qa_agents.progress import ConsoleProgress
from qa_agents.reporting_agent import ReportingAgent
from qa_agents.sources import FigmaSourceLoader, FileSourceLoader
from qa_agents.sources.files import UnsupportedSourceError
from qa_agents.test_case_agent import TestCaseAgent

PACKAGE_DIR = Path(__file__).parent
PROJECT_ROOT = Path.cwd()
OUTPUT_ROOT = PROJECT_ROOT / "output" / "web"
AUTOMATION_OUTPUT_ROOT = PROJECT_ROOT / "output" / "automation-web"
ARTIFACT_OUTPUT_ROOT = PROJECT_ROOT / "output" / "artifacts-web"
SAFE_RESULT_ID = re.compile(r"^[a-f0-9]{32}$")
DOWNLOAD_NAMES = {
    "md": "test-cases.md",
    "json": "test-cases.json",
    "csv": "test-cases.csv",
}
ARTIFACT_DOWNLOAD_NAMES = {
    "md": "artifact.md",
    "json": "artifact.json",
}

app = FastAPI(title="AutoAI QA Agent", docs_url="/api/docs", redoc_url=None)


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(PACKAGE_DIR / "static" / "index.html", media_type="text/html")


@app.get("/health")
def health() -> dict[str, str | bool]:
    settings = get_settings()
    try:
        TestCaseAgent().llm.health()
        ollama_ready = True
    except OllamaError:
        ollama_ready = False
    return {
        "status": "ok",
        "ollama_ready": ollama_ready,
        "text_model": settings.ollama_model,
        "vision_model": settings.ollama_vision_model,
        "figma_ready": bool(settings.figma_access_token),
    }


@app.post("/api/plan")
async def generate_test_plan(
    files: Annotated[list[UploadFile] | None, File()] = None,
    figma_url: Annotated[str, Form()] = "",
    requirements: Annotated[str, Form()] = "",
    instructions: Annotated[str, Form()] = "",
) -> dict[str, object]:
    sources = await _sources_from_web_inputs(files, figma_url, requirements, "planning")
    progress = ConsoleProgress("TestPlanningAgent")
    try:
        progress.update(35, "Generating test plan")
        plan = await run_in_threadpool(TestPlanningAgent().generate, sources, instructions.strip() or None)
    except (ValueError, FileNotFoundError, UnsupportedSourceError, OllamaError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _store_artifact_response("plan", plan)


@app.post("/api/design")
async def generate_test_design(
    files: Annotated[list[UploadFile] | None, File()] = None,
    figma_url: Annotated[str, Form()] = "",
    requirements: Annotated[str, Form()] = "",
    instructions: Annotated[str, Form()] = "",
) -> dict[str, object]:
    sources = await _sources_from_web_inputs(files, figma_url, requirements, "design")
    progress = ConsoleProgress("TestDesignDataAgent")
    try:
        progress.update(35, "Generating test design and data")
        design = await run_in_threadpool(
            TestDesignDataAgent().generate,
            sources,
            instructions.strip() or None,
        )
    except (ValueError, FileNotFoundError, UnsupportedSourceError, OllamaError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _store_artifact_response("design", design)


@app.post("/api/defects")
async def generate_defects(
    report_file: Annotated[UploadFile | None, File()] = None,
    report_text: Annotated[str, Form()] = "",
    target_url: Annotated[str, Form()] = "",
    context: Annotated[str, Form()] = "",
) -> dict[str, object]:
    settings = get_settings()
    progress = ConsoleProgress("DefectCreationAgent")
    with tempfile.TemporaryDirectory(prefix="autoai-defect-uploads-") as temp_dir:
        temp_root = Path(temp_dir)
        text = report_text.strip()
        if report_file and report_file.filename:
            progress.update(15, "Reading uploaded execution report")
            saved_paths = await _save_uploads([report_file], temp_root, settings.qa_agent_max_upload_mb)
            text = saved_paths[0].read_text(encoding="utf-8")
        if not text:
            raise HTTPException(status_code=400, detail="Add an execution report or failure notes.")
        try:
            progress.update(35, "Creating draft defects")
            defects = await run_in_threadpool(
                DefectCreationAgent().from_text,
                text,
                target_url.strip() or None,
                context.strip() or None,
            )
        except (ValueError, FileNotFoundError, OllamaError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _store_artifact_response("defects", defects)


@app.post("/api/automate")
async def generate_automation(
    target_url: Annotated[str, Form()],
    test_cases: Annotated[str, Form()] = "",
    instructions: Annotated[str, Form()] = "",
    test_cases_file: Annotated[UploadFile | None, File()] = None,
) -> dict[str, object]:
    settings = get_settings()
    progress = ConsoleProgress("AutomationAgent")
    if not target_url.strip():
        raise HTTPException(status_code=400, detail="Add the target test URL.")

    with tempfile.TemporaryDirectory(prefix="autoai-automation-uploads-") as temp_dir:
        temp_root = Path(temp_dir)
        progress.update(5, "Preparing automation inputs")
        saved_text = test_cases.strip()
        if test_cases_file and test_cases_file.filename:
            progress.update(15, "Reading uploaded test cases")
            saved_paths = await _save_uploads([test_cases_file], temp_root, settings.qa_agent_max_upload_mb)
            saved_text = saved_paths[0].read_text(encoding="utf-8")
        if not saved_text.strip():
            raise HTTPException(status_code=400, detail="Add test cases as a file or pasted text.")
        try:
            progress.update(30, "Generating Playwright automation plan")
            suite = await run_in_threadpool(
                AutomationAgent().from_text,
                target_url.strip(),
                saved_text,
                instructions.strip() or None,
            )
        except (ValueError, FileNotFoundError, OllamaError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Automation generation failed: {exc}") from exc

    result_id = uuid.uuid4().hex
    result_dir = AUTOMATION_OUTPUT_ROOT / result_id / "project"
    result_dir.mkdir(parents=True, exist_ok=False)
    progress.update(85, "Exporting Playwright project")
    export_automation_project(suite, result_dir)
    zip_path = AUTOMATION_OUTPUT_ROOT / result_id / "playwright-automation.zip"
    _zip_directory(result_dir, zip_path)
    progress.complete("Automation project ready")

    return {
        "result_id": result_id,
        "suite": suite.model_dump(mode="json"),
        "download": f"/api/automation-download/{result_id}",
    }


@app.post("/api/generate")
async def generate_test_cases(
    files: Annotated[list[UploadFile] | None, File()] = None,
    figma_url: Annotated[str, Form()] = "",
    requirements: Annotated[str, Form()] = "",
    instructions: Annotated[str, Form()] = "",
) -> dict[str, object]:
    settings = get_settings()
    progress = ConsoleProgress("TestCaseAgent")
    uploads = [upload for upload in (files or []) if upload.filename]
    if not uploads and not figma_url.strip() and not requirements.strip():
        raise HTTPException(status_code=400, detail="Add a PRD, image, Figma URL, or requirements text.")

    with tempfile.TemporaryDirectory(prefix="autoai-uploads-") as temp_dir:
        temp_root = Path(temp_dir)
        progress.update(5, "Preparing source material")
        saved_paths = await _save_uploads(uploads, temp_root, settings.qa_agent_max_upload_mb)
        try:
            progress.update(20, "Loading sources")
            sources = await run_in_threadpool(
                _load_sources,
                saved_paths,
                figma_url.strip(),
                requirements.strip(),
            )
            progress.update(35, "Generating test cases")
            suite = await run_in_threadpool(
                TestCaseAgent().generate,
                sources,
                instructions.strip() or None,
            )
        except (ValueError, FileNotFoundError, UnsupportedSourceError, OllamaError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Generation failed: {exc}") from exc

    result_id = uuid.uuid4().hex
    result_dir = OUTPUT_ROOT / result_id
    result_dir.mkdir(parents=True, exist_ok=False)
    progress.update(85, "Exporting test-case files")
    export_suite(suite, result_dir / DOWNLOAD_NAMES["md"])
    export_suite(suite, result_dir / DOWNLOAD_NAMES["json"])
    export_suite(suite, result_dir / DOWNLOAD_NAMES["csv"])
    progress.complete("Test cases ready")

    return {
        "result_id": result_id,
        "suite": suite.model_dump(mode="json"),
        "markdown": suite_to_markdown(suite),
        "downloads": {
            file_type: f"/api/download/{result_id}/{file_type}" for file_type in DOWNLOAD_NAMES
        },
    }


@app.get("/api/download/{result_id}/{file_type}")
def download(result_id: str, file_type: str) -> FileResponse:
    if not SAFE_RESULT_ID.fullmatch(result_id) or file_type not in DOWNLOAD_NAMES:
        raise HTTPException(status_code=404, detail="Download not found.")
    path = OUTPUT_ROOT / result_id / DOWNLOAD_NAMES[file_type]
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Download not found.")
    media_types = {
        "md": "text/markdown",
        "json": "application/json",
        "csv": "text/csv",
    }
    return FileResponse(path, media_type=media_types[file_type], filename=DOWNLOAD_NAMES[file_type])


@app.get("/api/automation-download/{result_id}")
def download_automation(result_id: str) -> FileResponse:
    if not SAFE_RESULT_ID.fullmatch(result_id):
        raise HTTPException(status_code=404, detail="Download not found.")
    path = AUTOMATION_OUTPUT_ROOT / result_id / "playwright-automation.zip"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Download not found.")
    return FileResponse(path, media_type="application/zip", filename="playwright-automation.zip")


@app.get("/api/artifact-download/{kind}/{result_id}/{file_type}")
def download_artifact(kind: str, result_id: str, file_type: str) -> FileResponse:
    if kind not in {"plan", "design", "defects"}:
        raise HTTPException(status_code=404, detail="Download not found.")
    if not SAFE_RESULT_ID.fullmatch(result_id) or file_type not in ARTIFACT_DOWNLOAD_NAMES:
        raise HTTPException(status_code=404, detail="Download not found.")
    path = ARTIFACT_OUTPUT_ROOT / kind / result_id / ARTIFACT_DOWNLOAD_NAMES[file_type]
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Download not found.")
    media_type = "application/json" if file_type == "json" else "text/markdown"
    filename = f"{kind}.{file_type}"
    return FileResponse(path, media_type=media_type, filename=filename)


@app.get("/api/report-download")
def download_runner_report(path: str, file_type: str = "md"):
    report_path = _resolve_report_path(path)
    file_type = file_type.lower()
    if file_type not in {"md", "json", "csv"}:
        raise HTTPException(status_code=404, detail="Report download not found.")

    if file_type == "md":
        markdown_path = report_path if report_path.suffix.lower() == ".md" else report_path.with_suffix(".md")
        if markdown_path.is_file():
            return FileResponse(markdown_path, media_type="text/markdown", filename=markdown_path.name)
    if file_type == "json":
        json_path = report_path if report_path.suffix.lower() == ".json" else report_path.with_suffix(".json")
        if json_path.is_file():
            return FileResponse(json_path, media_type="application/json", filename=json_path.name)
    if file_type == "csv":
        csv_text = _report_to_csv(report_path)
        return Response(
            csv_text,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="autoai-execution-report.csv"'},
        )
    raise HTTPException(status_code=404, detail="Report download not found.")


@app.post("/api/run-automation/{result_id}")
async def run_generated_automation(
    result_id: str,
    target_url: Annotated[str, Form()],
    headed: Annotated[bool, Form()] = False,
) -> dict[str, object]:
    progress = ConsoleProgress("RunnerAgent")
    if not SAFE_RESULT_ID.fullmatch(result_id):
        raise HTTPException(status_code=404, detail="Automation project not found.")
    project_dir = AUTOMATION_OUTPUT_ROOT / result_id / "project"
    if not project_dir.is_dir():
        raise HTTPException(status_code=404, detail="Automation project not found.")
    try:
        progress.update(10, "Starting generated automation run")
        result = await run_in_threadpool(
            AutomationRunnerAgent().run,
            project_dir,
            target_url,
            headed,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    progress.update(80, "Generating execution report")
    report = ReportingAgent().generate(result)
    progress.complete("Runner and report complete")
    return {"result": result.model_dump(mode="json"), "report": report.model_dump(mode="json")}


async def _sources_from_web_inputs(
    files: list[UploadFile] | None,
    figma_url: str,
    requirements: str,
    prefix: str,
) -> list[SourceMaterial]:
    settings = get_settings()
    uploads = [upload for upload in (files or []) if upload.filename]
    if not uploads and not figma_url.strip() and not requirements.strip():
        raise HTTPException(status_code=400, detail="Add a BRD, PRD, image, Figma URL, or instructions.")
    with tempfile.TemporaryDirectory(prefix=f"autoai-{prefix}-uploads-") as temp_dir:
        saved_paths = await _save_uploads(uploads, Path(temp_dir), settings.qa_agent_max_upload_mb)
        return await run_in_threadpool(_load_sources, saved_paths, figma_url.strip(), requirements.strip())


@app.post("/api/runner/run")
async def run_automation_runner(
    project_dir: Annotated[str, Form()],
    target_url: Annotated[str, Form()],
    headed: Annotated[bool, Form()] = False,
    timeout_seconds: Annotated[int, Form()] = 600,
    pytest_args: Annotated[str, Form()] = "",
) -> dict[str, object]:
    progress = ConsoleProgress("RunnerAgent")
    project = _resolve_runner_project(project_dir)
    if not target_url.strip():
        raise HTTPException(status_code=400, detail="Add the target test URL.")
    try:
        parsed_pytest_args = shlex.split(pytest_args)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid pytest arguments: {exc}") from exc
    try:
        progress.update(10, "Starting automation runner")
        result = await run_in_threadpool(
            AutomationRunnerAgent().run,
            project,
            target_url.strip(),
            headed,
            min(max(timeout_seconds, 30), 3600),
            parsed_pytest_args,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    progress.update(80, "Generating execution report")
    report = ReportingAgent().generate(result)
    progress.complete("Runner and report complete")
    return {"result": result.model_dump(mode="json"), "report": report.model_dump(mode="json")}


async def _save_uploads(
    uploads: list[UploadFile],
    temp_root: Path,
    max_upload_mb: int,
) -> list[Path]:
    max_bytes = max_upload_mb * 1024 * 1024
    saved: list[Path] = []
    for index, upload in enumerate(uploads):
        safe_name = Path(upload.filename or f"upload-{index}").name
        destination = temp_root / f"{index}-{safe_name}"
        size = 0
        with destination.open("wb") as handle:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    destination.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"{safe_name} exceeds the {max_upload_mb} MB upload limit.",
                    )
                handle.write(chunk)
        await upload.close()
        saved.append(destination)
    return saved


def _load_sources(
    saved_paths: list[Path],
    figma_url: str,
    requirements: str,
) -> list[SourceMaterial]:
    settings = get_settings()
    loader = FileSourceLoader()
    sources = [loader.load(path) for path in saved_paths]
    if requirements:
        sources.append(SourceMaterial(name="Pasted requirements", kind="text", content=requirements))
    if figma_url:
        sources.append(FigmaSourceLoader(settings.figma_access_token or "").load(figma_url))
    return sources


def _resolve_runner_project(project_dir: str) -> Path:
    if not project_dir.strip():
        raise HTTPException(status_code=400, detail="Add a generated automation project directory.")
    raw_path = Path(project_dir.strip()).expanduser()
    resolved = raw_path.resolve() if raw_path.is_absolute() else (PROJECT_ROOT / raw_path).resolve()
    if resolved != PROJECT_ROOT and PROJECT_ROOT not in resolved.parents:
        raise HTTPException(status_code=422, detail="Project directory must be inside this workspace.")
    return resolved


def _resolve_report_path(path: str) -> Path:
    if not path.strip():
        raise HTTPException(status_code=400, detail="Report path is required.")
    raw_path = Path(path.strip()).expanduser()
    resolved = raw_path.resolve() if raw_path.is_absolute() else (PROJECT_ROOT / raw_path).resolve()
    if resolved != PROJECT_ROOT and PROJECT_ROOT not in resolved.parents:
        raise HTTPException(status_code=422, detail="Report path must be inside this workspace.")
    if "test-results" not in resolved.parts:
        raise HTTPException(status_code=422, detail="Only runner test-results reports can be downloaded.")
    if resolved.suffix.lower() not in {".md", ".json"}:
        raise HTTPException(status_code=422, detail="Report path must be a Markdown or JSON report.")
    return resolved


def _report_to_csv(report_path: Path) -> str:
    json_path = report_path if report_path.suffix.lower() == ".json" else report_path.with_suffix(".json")
    if not json_path.is_file():
        raise HTTPException(status_code=404, detail="JSON report not found for CSV conversion.")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    buffer = StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "status",
            "target_url",
            "project_dir",
            "exit_code",
            "duration_seconds",
            "total_tests",
            "passed_tests",
            "failed_tests",
            "summary",
            "findings",
            "self_healing",
        ],
    )
    writer.writeheader()
    writer.writerow(
        {
            "status": payload.get("status", ""),
            "target_url": payload.get("target_url", ""),
            "project_dir": payload.get("project_dir", ""),
            "exit_code": payload.get("exit_code", ""),
            "duration_seconds": payload.get("duration_seconds", ""),
            "total_tests": payload.get("total_tests", ""),
            "passed_tests": payload.get("passed_tests", ""),
            "failed_tests": payload.get("failed_tests", ""),
            "summary": payload.get("summary", ""),
            "findings": " | ".join(payload.get("findings") or []),
            "self_healing": json.dumps(payload.get("self_healing") or [], ensure_ascii=False),
        }
    )
    return buffer.getvalue()


def _zip_directory(source_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in source_dir.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(source_dir))


def _store_artifact_response(kind: str, artifact) -> dict[str, object]:
    result_id = uuid.uuid4().hex
    result_dir = ARTIFACT_OUTPUT_ROOT / kind / result_id
    result_dir.mkdir(parents=True, exist_ok=False)
    export_artifact(artifact, result_dir / ARTIFACT_DOWNLOAD_NAMES["md"])
    export_artifact(artifact, result_dir / ARTIFACT_DOWNLOAD_NAMES["json"])
    return {
        "result_id": result_id,
        "artifact": artifact.model_dump(mode="json"),
        "markdown": artifact_to_markdown(artifact),
        "downloads": {
            file_type: f"/api/artifact-download/{kind}/{result_id}/{file_type}"
            for file_type in ARTIFACT_DOWNLOAD_NAMES
        },
    }


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    AUTOMATION_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    ARTIFACT_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    uvicorn.run("qa_agents.web:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
