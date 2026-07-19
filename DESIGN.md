# AutoAI QA Agents Design Document

## 1. Purpose

AutoAI QA Agents is a local-first QA automation platform that uses Ollama-hosted LLMs to transform product inputs into QA deliverables and executable automation.

The system supports this end-to-end QA workflow:

```text
BRD / PRD / Figma / screenshot / manual instruction
        |
        v
Test Planning Agent
        |
        v
Test Design + Test Data Agent
        |
        v
Test Case Agent
        |
        v
Automation Agent
        |
        v
Automation Runner Agent
        |
        v
Reporting Agent + Self-Healing Agent
        |
        v
Defect Creation Agent
```

The key design goal is to keep each QA responsibility in a separate agent with validated structured output. This makes the pipeline easier to test, replace, and extend.

## 2. Goals

- Generate test plans from BRD, PRD, Figma, screenshots, or manual instructions.
- Generate test design scenarios and synthetic test data.
- Generate structured test cases.
- Inspect real application DOM and discover selector candidates before automation.
- Generate executable Playwright Python automation projects.
- Export Page Object Model scaffolds.
- Run generated automation from the UI or CLI.
- Produce execution reports in Markdown/JSON/CSV-compatible formats.
- Analyze failures and provide self-healing locator guidance.
- Create draft defects from failed execution reports or manual failure notes.
- Export test cases for Xray, Zephyr, and TestRail import workflows.
- Keep sensitive product material local by using Ollama.

## 3. Non-goals

- Full replacement for human QA review.
- Guaranteed automation success for every arbitrary website.
- Direct integration with Jira/Azure DevOps/GitHub Issues yet.
- Hosted/synchronized Xray, Zephyr, or TestRail API publishing. Current support is local import-file export.
- Production-grade distributed execution or CI orchestration.

## 4. Technology Stack

| Area | Technology |
|---|---|
| Language | Python 3.11+ |
| Web API/UI | FastAPI, Uvicorn, static HTML/CSS/JS |
| LLM runtime | Ollama |
| Data validation | Pydantic v2 |
| Browser automation | Playwright Python + pytest |
| Test execution safety | pytest-timeout, Playwright timeouts |
| Source parsing | pypdf, python-docx, YAML/JSON/CSV/text/image loaders |
| Agent protocol | MCP server support |
| Packaging | setuptools editable package |

## 5. High-level Architecture

```text
                      ┌────────────────────┐
                      │   Web UI / CLI /   │
                      │      MCP client    │
                      └─────────┬──────────┘
                                │
                                v
┌──────────────┐        ┌──────────────────┐        ┌───────────────┐
│ Source files │───────▶│ Source adapters  │───────▶│ SourceMaterial│
└──────────────┘        └──────────────────┘        └───────┬───────┘
                                                             │
                                                             v
                         ┌────────────────────────────────────────────┐
                         │            Specialized Agents              │
                         │ Planning / Design / Test Case / Automation │
                         │ Runner / Reporting / Defect / Self-Healing │
                         └────────────────────┬───────────────────────┘
                                              │
                                              v
                         ┌────────────────────────────────────────────┐
                         │ Pydantic validated artifacts + local files │
                         └────────────────────────────────────────────┘
```

## 6. Project Structure

```text
src/qa_agents/
  config.py                    Environment-backed settings
  ollama.py                    Ollama API client
  models.py                    Pydantic schemas for all agent outputs
  prompts.py                   System/user prompt templates
  source_utils.py              Shared source composition/truncation helpers
  input_loader.py              CLI source loading helper

  planning_agent.py            Test Planning Agent
  design_agent.py              Test Design + Test Data Agent
  test_case_agent.py           Test Case Agent
  dom_agent.py                 DOM Inspection + Page Object Model Agent
  automation_agent.py          Automation generation agent
  automation_runner_agent.py   Runner Agent
  reporting_agent.py           Reporting Agent
  self_healing_agent.py        Self-Healing analysis agent
  defect_agent.py              Defect Creation Agent
  test_management_agent.py     Xray/Zephyr/TestRail export agent

  exporters.py                 Test-case Markdown/JSON/CSV export
  artifact_exporters.py        Plan/design/defect Markdown/JSON export
  automation_exporters.py      Playwright project generation

  web.py                       FastAPI routes
  static/index.html            Browser UI
  mcp_server.py                MCP tools

  sources/
    files.py                   PDF/DOCX/text/JSON/YAML/CSV/image loader
    figma.py                   Figma loader

tests/
  test_*.py                    Unit/API tests
```

## 7. Agent Responsibilities

### 7.1 Test Planning Agent

File: `src/qa_agents/planning_agent.py`

Input:

- `SourceMaterial[]`
- optional planning instructions

Output:

- `TestPlan`

Responsibilities:

- Identify objective, scope, test strategy, test levels, test types.
- Define environments, entry criteria, exit criteria, risks, assumptions, open questions, and deliverables.
- Produce an execution-ready QA plan from product/design input.

### 7.2 Test Design and Test Data Agent

File: `src/qa_agents/design_agent.py`

Input:

- `SourceMaterial[]`
- optional design/data instructions

Output:

- `TestDesignSuite`

Responsibilities:

- Create test design scenarios.
- Apply design techniques such as boundary value analysis, equivalence partitioning, state transitions, negative testing, permissions, accessibility, and data integrity.
- Generate synthetic test data records and link them to scenarios.

### 7.3 Test Case Agent

File: `src/qa_agents/test_case_agent.py`

Input:

- source material from files, Figma, screenshots, or text
- optional QA focus instructions

Output:

- `TestCaseSuite`

Responsibilities:

- Generate structured test cases with steps, expected results, priority, test type, and traceability.
- Select vision model when image input is present.
- Retry malformed/truncated JSON with a compact prompt.
- Add compact-generation guidance for screenshot/PNG inputs.

### 7.4 Automation Agent

File: `src/qa_agents/automation_agent.py`

Input:

- target URL
- manual/generated test cases
- optional automation instructions

Output:

- `AutomationSuite`

Responsibilities:

- Convert test cases into a Playwright Python pytest automation plan.
- Generate test data where needed.
- Prefer accessibility-first Playwright locators.
- Capture assumptions and setup notes.

### 7.5 DOM Inspection + Page Object Model Agent

File: `src/qa_agents/dom_agent.py`

Input:

- target URL
- max pages to crawl
- optional headed browser mode

Output:

- `DomInspectionReport`
- `PageObjectModelExport`

Responsibilities:

- Use Playwright to crawl same-origin pages.
- Discover interactive DOM elements.
- Rank selector candidates such as `data-testid`, role/name, label, placeholder, text, and CSS fallbacks.
- Export a Python Page Object Model scaffold under `pages/`.
- Produce Markdown/JSON selector reports for review before automation generation.

### 7.6 Automation Exporter

File: `src/qa_agents/automation_exporters.py`

Output project structure:

```text
generated-project/
  README.md
  requirements.txt
  pytest.ini
  conftest.py
  autoai_self_healing.py
  test_data/generated_data.json
  tests/test_generated.py
```

Responsibilities:

- Render `AutomationSuite` into executable pytest files.
- Add Playwright fixtures and timeouts.
- Add runtime self-healing helpers.
- Refresh runtime support files before runner execution.

### 7.7 Automation Runner Agent

File: `src/qa_agents/automation_runner_agent.py`

Input:

- generated project directory
- target URL
- headed/headless option
- timeout seconds
- optional pytest arguments

Output:

- `AutomationRunResult`
- local runner reports:
  - `test-results/autoai-run-*.json`
  - `test-results/autoai-run-*.md`

Responsibilities:

- Validate project directory.
- Refresh runtime support files.
- Set Playwright/pytest timeout environment.
- Execute pytest.
- Capture stdout, stderr, exit code, status, duration, report paths.

### 7.7 Reporting Agent

File: `src/qa_agents/reporting_agent.py`

Input:

- `AutomationRunResult`

Output:

- `ExecutionReport`
- local execution reports:
  - `test-results/autoai-execution-report-*.json`
  - `test-results/autoai-execution-report-*.md`

Responsibilities:

- Summarize automation run.
- Parse passed/failed counts where possible.
- Add findings.
- Invoke Self-Healing Agent for locator-related recommendations.

### 7.8 Self-Healing Agent

Files:

- Static analysis: `src/qa_agents/self_healing_agent.py`
- Runtime helper generated into projects: `autoai_self_healing.py`

Responsibilities:

- Detect locator-related failures from runner output.
- Ignore low-value locator tokens such as stopwords.
- Suggest stable locator strategies.
- Runtime helper retries common role/label/placeholder/text/test-id locators.
- Runtime helper handles common generated-step patterns:
  - login credentials
  - logout
  - keyboard navigation
  - network outage simulation
  - post-logout protected route checks
  - unsupported profile/support/customer routes by skipping rather than hanging

### 7.9 Defect Creation Agent

File: `src/qa_agents/defect_agent.py`

Input:

- execution report file or raw failure text
- optional target URL
- optional defect context

Output:

- `DefectSuite`

Responsibilities:

- Convert execution failures into draft defects.
- Include severity, priority, expected result, actual result, reproduction steps, evidence, suspected area, and labels.
- Create investigation-style defect items when failures are likely automation/environment issues.

## 8. Data Models

All main artifacts are Pydantic models in `src/qa_agents/models.py`.

Core models:

- `SourceMaterial`
- `TestPlan`
- `TestDesignSuite`
- `TestCaseSuite`
- `AutomationSuite`
- `AutomationRunResult`
- `ExecutionReport`
- `DefectSuite`

This schema-first design provides:

- JSON validation.
- Safer LLM output handling.
- Easier API/CLI/UI reuse.
- Easier future integrations with test-management and defect-tracking tools.

## 9. Source Ingestion

Supported inputs:

- PDF
- DOCX
- Markdown
- TXT
- JSON
- YAML
- CSV
- PNG/JPG/JPEG/WebP screenshots
- Figma file or node URL
- pasted/manual text

Source ingestion normalizes input into `SourceMaterial`.

For image inputs:

- text content describes the image source
- base64 images are passed to the configured vision model
- compact-generation guidance is added to avoid JSON truncation

## 10. Ollama Integration

File: `src/qa_agents/ollama.py`

The `OllamaClient` calls `/api/chat` with:

- system prompt
- user prompt
- JSON schema response format
- optional images
- model override
- context window
- max output tokens
- temperature

Important settings:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:7b
OLLAMA_VISION_MODEL=qwen2.5vl:7b
OLLAMA_TIMEOUT_SECONDS=900
OLLAMA_CONTEXT_WINDOW=16384
OLLAMA_MAX_OUTPUT_TOKENS=12288
```

## 11. Web UI Design

File: `src/qa_agents/static/index.html`

The UI supports:

- source upload and Figma/manual input
- Test Plan generation
- Test Design + Test Data generation
- Test Case generation
- Automation project generation
- Automation runner execution
- execution report preview
- report downloads
- defect creation from report/failure text

FastAPI routes are defined in `src/qa_agents/web.py`.

Important routes:

| Route | Purpose |
|---|---|
| `GET /` | Web UI |
| `GET /health` | Ollama/config health |
| `POST /api/plan` | Generate test plan |
| `POST /api/design` | Generate test design/data |
| `POST /api/generate` | Generate test cases |
| `POST /api/dom-inspect` | Inspect DOM and export Page Object Model scaffold |
| `POST /api/automate` | Generate Playwright automation project |
| `POST /api/run-automation/{result_id}` | Run UI-generated automation |
| `POST /api/runner/run` | Run any workspace automation project |
| `POST /api/defects` | Generate draft defects |
| `POST /api/test-management-export` | Export test cases for Xray/Zephyr/TestRail |
| `GET /api/download/{result_id}/{file_type}` | Download test cases |
| `GET /api/dom-download/{result_id}/{file_type}` | Download DOM report or POM zip |
| `GET /api/automation-download/{result_id}` | Download automation zip |
| `GET /api/artifact-download/{kind}/{result_id}/{file_type}` | Download plan/design/defect artifacts |
| `GET /api/report-download` | Download runner reports |
| `GET /api/test-management-download/{result_id}/{tool}/{file_type}` | Download test management export |

## 12. CLI Design

Configured in `pyproject.toml`.

| Command | Purpose |
|---|---|
| `qa-planning-agent` | Generate test plan |
| `qa-design-agent` | Generate test design and test data |
| `qa-agent` | Generate test cases |
| `qa-dom-agent` | Inspect DOM and export Page Object Model scaffold |
| `qa-automation-agent` | Generate Playwright automation project |
| `qa-runner-agent` | Run generated automation |
| `qa-defect-agent` | Generate defects from reports/failure notes |
| `qa-test-management-agent` | Export test cases for Xray/Zephyr/TestRail |
| `qa-agent-mcp` | Run MCP server |
| `qa-agent-ui` | Run web UI |

## 13. MCP Design

File: `src/qa_agents/mcp_server.py`

The MCP server exposes selected QA tools for MCP-compatible clients. Existing tools focus on Ollama health and test-case generation. The architecture supports adding planning, design, automation, runner, and defect tools later.

## 14. Persistence and Outputs

Generated local outputs:

```text
output/web/                 Test-case downloads from UI
output/artifacts-web/       Plan/design/defect artifacts from UI
output/automation-web/      Generated automation projects from UI
output/*                    CLI outputs
```

Runner reports are stored inside each generated automation project:

```text
test-results/autoai-run-*.json
test-results/autoai-run-*.md
test-results/autoai-execution-report-*.json
test-results/autoai-execution-report-*.md
```

## 15. Error Handling

Major handled failure modes:

- Ollama unavailable.
- Ollama timeout.
- malformed/truncated LLM JSON.
- unsupported source file type.
- oversized uploads.
- automation project outside workspace.
- generated test timeouts.
- locator failures.
- mismatched generated test vs target URL.

For malformed test-case JSON, the Test Case Agent retries with a compact prompt and fewer cases.

For automation locator failures, the runtime helper retries likely fallback locators and skips unsupported generated routes instead of hanging.

## 16. Security and Privacy

- Product material stays local when using local Ollama.
- Figma token is read from environment and should not be committed.
- Uploaded files are stored temporarily during processing.
- Generated artifacts are written to local `output/` folders.
- Runner project path is restricted to the workspace.
- Report downloads are restricted to workspace `test-results` reports.

## 17. Testing Strategy

Automated tests cover:

- source loading
- test-case generation validation and retry
- exporters
- automation project generation
- automation runner
- reporting/self-healing
- planning/design/defect agents
- web endpoints

Run:

```bash
make test
make lint
```

## 18. Current Limitations

- Generated automation may need selector refinement for complex applications.
- CAPTCHA, MFA, OTP, SSO, email verification, payments, and admin-only flows need explicit setup.
- Vision-based generation can still produce large outputs; compact retry reduces but does not eliminate model truncation risk.
- Defect creation currently produces local draft defects only; no Jira/Azure DevOps integration yet.
- Test management support currently creates import files; it does not publish directly via vendor APIs.
- MCP currently exposes a subset of available agents.

## 19. Recommended Future Enhancements

1. Selector memory store per application.
2. Jira/Azure DevOps/GitHub Issues defect connectors.
3. Direct Xray/Zephyr/TestRail API publishing with authentication profiles.
4. CI runner profile for GitHub Actions.
5. Parallel runner and browser matrix.
6. Evidence capture: screenshots, traces, and videos on failure.
7. Authentication profile management for apps with login/SSO.
10. Expanded MCP tools for all agents.
