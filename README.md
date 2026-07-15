# AutoAI QA Agents

A local-first foundation for specialized QA agents. It currently includes:

- a test planning agent that creates scope, strategy, environments, risks, entry/exit criteria, and
  deliverables from BRDs, PRDs, Figma, screenshots, or manual instructions
- a test design and test data agent that creates test design scenarios and synthetic test data
- a test-case generation agent that turns PRDs, Figma designs, screenshots, and requirement notes
  into structured test suites
- a QA automation agent that turns test cases plus a target URL into a downloadable Playwright
  Python automation project with generated test data where applicable
- a QA runner agent that executes generated Playwright projects and writes local JSON/Markdown
  execution reports
- a reporting agent that turns execution output into a concise run summary with follow-up findings
- a defect creation agent that turns failed runs or manual failure notes into draft defects
- a self-healing agent that flags locator failures and generated tests that retry likely fallback
  locators during execution

The test-case generation agent accepts:

- PRDs in PDF, DOCX, Markdown, text, JSON, YAML, or CSV
- local UI screenshots (`.png`, `.jpg`, `.jpeg`, `.webp`)
- Figma file or node URLs
- requirements supplied directly as text

Ollama keeps product material and generated test cases on your machine. Outputs are validated against
a Pydantic schema and can be exported as Markdown, JSON, or CSV.

## Architecture

```text
PRD / Figma / image
        |
        v
source adapter -> normalized source + optional images
        |
        v
TestCaseAgent -> Ollama /api/chat with JSON schema
        |
        v
validated suite -> Markdown / JSON / CSV / MCP response

The broader QA workflow is:

BRD / PRD / Figma / instruction
        |
        v
TestPlanningAgent -> TestDesignDataAgent -> TestCaseAgent
        |
        v
AutomationAgent -> RunnerAgent -> ReportingAgent -> DefectCreationAgent

Test URL + generated/manual test cases
        |
        v
AutomationAgent -> Ollama /api/chat with JSON schema
        |
        v
validated automation plan -> Playwright Python pytest project + generated data
        |
        v
RunnerAgent -> pytest / Playwright execution
        |
        v
ReportingAgent -> execution summary + findings + self-healing review
        |
        v
test-results/autoai-run-* + test-results/autoai-execution-report-*
```

The package is intentionally ready for more agents later. New agents can reuse `config.py`, the
Ollama client, source adapters, and MCP server.

## 1. Install Ollama

Install Ollama from [ollama.com/download](https://ollama.com/download), start it, then pull a model:

```bash
ollama pull qwen2.5-coder:7b
ollama pull qwen2.5vl:7b
```

`qwen2.5-coder:7b` is the default for text PRDs. `qwen2.5vl:7b` is selected automatically for screenshots and
rendered Figma frames.

Model quality and memory needs vary. Change `OLLAMA_MODEL` or `OLLAMA_VISION_MODEL` in `.env` without
changing application code. Use a smaller Qwen2.5 Coder variant if your machine has limited memory.

The first request to a 7B model can take several minutes. The default generation timeout is 15 minutes
and can be changed with `OLLAMA_TIMEOUT_SECONDS`.

## 2. Install this project

```bash
make install
cp .env.example .env
```

Or manually:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

Check that Ollama is reachable:

```bash
make check-ollama
```

## 3. Start the web UI

```bash
make run-ui
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The UI lets you:

- drag and drop multiple PRDs or design images
- paste a Figma file or selected-frame URL
- paste requirements or acceptance criteria directly
- add optional QA focus instructions
- generate a test plan
- generate test design scenarios and synthetic test data
- preview generated cases in the browser
- download the suite as Markdown, JSON, or CSV
- enter a test URL, paste/upload test cases, and download a generated Playwright automation project
- run UI-generated automation and inspect the execution report and self-healing review
- create draft defects from execution reports or failure notes

Generated downloads are stored locally under `output/web/`.
Automation downloads are stored locally under `output/automation-web/`.
Planning, design, and defect artifacts are stored locally under `output/artifacts-web/`.

## 4. Generate a test plan

```bash
.venv/bin/qa-planning-agent \
  --source examples/sample-prd.md \
  --instructions "Plan for web, mobile, accessibility, API dependencies, and release readiness." \
  --output output/test-plan.md
```

From manual instructions:

```bash
.venv/bin/qa-planning-agent \
  --text "Users can log out and cannot access protected pages afterward." \
  --output output/logout-plan.json
```

## 5. Generate test design and test data

```bash
.venv/bin/qa-design-agent \
  --source examples/sample-prd.md \
  --instructions "Use boundary analysis, negative testing, and state transitions." \
  --output output/test-design.md
```

## 6. Generate test cases from the CLI

From a PRD:

```bash
.venv/bin/qa-agent \
  --source examples/sample-prd.md \
  --output output/password-reset.md
```

Combine multiple sources:

```bash
.venv/bin/qa-agent \
  --source docs/checkout-prd.pdf \
  --source designs/checkout.png \
  --instructions "Prioritize mobile web, payment failure, and accessibility coverage" \
  --output output/checkout.json
```

From direct text:

```bash
.venv/bin/qa-agent \
  --text "A signed-in user can update their shipping address." \
  --output output/address.csv
```

## 7. Generate Playwright automation from test cases

The automation agent takes a target URL and test cases generated by the first agent, or manually
written cases in Markdown/JSON/text, then creates a Playwright Python pytest project.

```bash
.venv/bin/qa-automation-agent \
  --url "https://staging.example.com" \
  --test-cases output/password-reset.md \
  --instructions "Prefer data-testid locators when available. Use fake test data only." \
  --output-dir output/password-reset-automation
```

Run the generated project:

```bash
cd output/password-reset-automation
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/playwright install chromium
TEST_URL="https://staging.example.com" .venv/bin/python -m pytest
```

You can also install the browser runtime for local development from the root project:

```bash
make install-browsers
```

## 8. Run generated automated test cases

Use the runner agent to execute a generated Playwright project from this repository's Python
environment:

```bash
.venv/bin/qa-runner-agent \
  --project-dir output/password-reset-automation \
  --url "https://staging.example.com"
```

Run with a visible browser:

```bash
.venv/bin/qa-runner-agent \
  --project-dir output/password-reset-automation \
  --url "https://staging.example.com" \
  --headed
```

Pass extra pytest filters when you only want a subset:

```bash
.venv/bin/qa-runner-agent \
  --project-dir output/password-reset-automation \
  --url "https://staging.example.com" \
  --pytest-arg -k \
  --pytest-arg login
```

The runner writes reports inside the generated automation project:

```text
test-results/autoai-run-YYYYMMDD-HHMMSS.json
test-results/autoai-run-YYYYMMDD-HHMMSS.md
test-results/autoai-execution-report-YYYYMMDD-HHMMSS.json
test-results/autoai-execution-report-YYYYMMDD-HHMMSS.md
```

Generated Playwright projects include an `autoai_self_healing.py` helper. Locator-sensitive actions
and assertions first try the generated locator, then retry likely role, label, placeholder, text, and
test-id fallbacks. The reporting agent calls out locator-related failures so stable selectors can be
promoted back into the test code.

The runner also refreshes older generated projects with the latest runtime helpers before each run.
By default it uses a 45-second per-test timeout when `pytest-timeout` is installed, a 3-second
Playwright action timeout, a 15-second navigation timeout, and a bounded locator fallback search. You
can tune those without editing generated tests:

```bash
PLAYWRIGHT_ACTION_TIMEOUT_MS=5000 \
PLAYWRIGHT_NAVIGATION_TIMEOUT_MS=30000 \
AUTOAI_LOCATOR_TIMEOUT_MS=1200 \
AUTOAI_MAX_LOCATOR_CANDIDATES=12 \
.venv/bin/qa-runner-agent --project-dir output/password-reset-automation --url "https://staging.example.com"
```

## 9. Create defects from execution output

```bash
.venv/bin/qa-defect-agent \
  --report output/password-reset-automation/test-results/autoai-execution-report-YYYYMMDD-HHMMSS.md \
  --url "https://staging.example.com" \
  --context "QA environment, Chromium, build 1.2.3" \
  --output output/defects.md
```

## Figma setup

Create a Figma personal access token with `file_content:read` access, then set:

```bash
FIGMA_ACCESS_TOKEN=your_token
```

Generate from a whole file or a URL containing `node-id`:

```bash
.venv/bin/qa-agent \
  --figma-url "https://www.figma.com/design/FILE_KEY/Product?node-id=1-2" \
  --output output/figma-test-cases.md
```

The adapter extracts visible frames, controls, labels, component properties, and prototype actions. It
also sends rendered frame images when the configured Ollama model supports vision. Never commit the
Figma token; `.env` is ignored.

## MCP agent

Run the MCP server:

```bash
.venv/bin/qa-agent-mcp
```

Example client configuration:

```json
{
  "mcpServers": {
    "qa-agents": {
      "command": "/absolute/path/to/AutoAI/.venv/bin/qa-agent-mcp"
    }
  }
}
```

Available tools:

- `check_ollama`
- `generate_test_cases_from_text`
- `generate_test_cases_from_file`
- `generate_test_cases_from_figma`

## Test-case output

Each suite contains:

- source summary, assumptions, and open questions
- requirement-to-test coverage mapping
- priority and test type
- preconditions and test data
- numbered actions with expected results
- overall expected result, tags, and automation suitability

## Development

```bash
make test
make lint
```

Useful environment variables are documented in [.env.example](.env.example).

## Current boundaries

- Scanned PDFs need OCR before ingestion.
- Very large sources are truncated at `QA_AGENT_MAX_SOURCE_CHARS`; split large PRDs by feature for
  better results.
- A Figma token can only read files the token owner can access.
- Generated cases should receive human review before becoming a release gate.
- Generated automation is a strong starting point, but selectors may need adjustment unless the app
  exposes stable labels, roles, or `data-testid` attributes.
