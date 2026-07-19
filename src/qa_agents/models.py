from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Priority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TestType(StrEnum):
    FUNCTIONAL = "functional"
    NEGATIVE = "negative"
    BOUNDARY = "boundary"
    UI = "ui"
    ACCESSIBILITY = "accessibility"
    SECURITY = "security"
    PERFORMANCE = "performance"
    COMPATIBILITY = "compatibility"
    API = "api"
    DATA = "data"
    RECOVERY = "recovery"


class TestStep(BaseModel):
    step: int = Field(ge=1)
    action: str = Field(min_length=1)
    expected_result: str = Field(min_length=1)


class TestCase(BaseModel):
    id: str = Field(description="Stable ID such as TC-001")
    title: str
    objective: str
    requirement_refs: list[str] = Field(default_factory=list)
    test_type: TestType
    priority: Priority
    preconditions: list[str] = Field(default_factory=list)
    test_data: list[str] = Field(default_factory=list)
    steps: list[TestStep] = Field(min_length=1)
    expected_result: str
    tags: list[str] = Field(default_factory=list)
    automation_candidate: bool = True


class CoverageItem(BaseModel):
    requirement: str
    test_case_ids: list[str]


class TestCaseSuite(BaseModel):
    feature: str
    source_summary: str
    assumptions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    coverage: list[CoverageItem] = Field(default_factory=list)
    test_cases: list[TestCase] = Field(min_length=1)


class SourceMaterial(BaseModel):
    name: str
    kind: str
    content: str
    images_base64: list[str] = Field(default_factory=list, exclude=True)


class TestScopeItem(BaseModel):
    area: str
    in_scope: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)


class TestRisk(BaseModel):
    risk: str
    impact: Priority = Priority.MEDIUM
    mitigation: str


class TestEnvironment(BaseModel):
    name: str
    purpose: str
    dependencies: list[str] = Field(default_factory=list)


class TestPlan(BaseModel):
    feature: str
    objective: str
    source_summary: str
    scope: list[TestScopeItem] = Field(default_factory=list)
    test_strategy: list[str] = Field(default_factory=list)
    test_levels: list[str] = Field(default_factory=list)
    test_types: list[TestType] = Field(default_factory=list)
    environments: list[TestEnvironment] = Field(default_factory=list)
    entry_criteria: list[str] = Field(default_factory=list)
    exit_criteria: list[str] = Field(default_factory=list)
    risks: list[TestRisk] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)


class TestDataRecord(BaseModel):
    id: str
    purpose: str
    data: dict[str, str] = Field(default_factory=dict)
    expected_usage: str
    sensitive: bool = False


class TestDesignScenario(BaseModel):
    id: str
    title: str
    requirement_refs: list[str] = Field(default_factory=list)
    design_technique: str
    priority: Priority = Priority.MEDIUM
    preconditions: list[str] = Field(default_factory=list)
    data_ids: list[str] = Field(default_factory=list)
    coverage_notes: list[str] = Field(default_factory=list)


class TestDesignSuite(BaseModel):
    feature: str
    source_summary: str
    design_approach: list[str] = Field(default_factory=list)
    scenarios: list[TestDesignScenario] = Field(default_factory=list)
    test_data: list[TestDataRecord] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class DefectSeverity(StrEnum):
    BLOCKER = "blocker"
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    TRIVIAL = "trivial"


class DefectStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"


class Defect(BaseModel):
    id: str
    title: str
    severity: DefectSeverity
    priority: Priority
    status: DefectStatus = DefectStatus.DRAFT
    environment: str
    source_test: str | None = None
    actual_result: str
    expected_result: str
    reproduction_steps: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    suspected_area: str | None = None
    labels: list[str] = Field(default_factory=list)


class DefectSuite(BaseModel):
    target_url: str | None = None
    execution_summary: str
    defects: list[Defect] = Field(default_factory=list)
    no_defect_notes: list[str] = Field(default_factory=list)


class BrowserAction(StrEnum):
    GOTO = "goto"
    CLICK = "click"
    FILL = "fill"
    SELECT = "select"
    CHECK = "check"
    EXPECT_VISIBLE = "expect_visible"
    EXPECT_TEXT = "expect_text"
    EXPECT_URL = "expect_url"
    CUSTOM = "custom"


class AutomationStep(BaseModel):
    step: int = Field(ge=1)
    action: BrowserAction
    description: str = Field(min_length=1)
    locator: str | None = Field(
        default=None,
        description="Preferred Playwright locator expression or user-facing target.",
    )
    value: str | None = Field(default=None, description="Value to type, select, or assert.")
    expected_result: str = Field(min_length=1)


class AutomationDataItem(BaseModel):
    name: str = Field(min_length=1)
    value: str = Field(min_length=1)
    description: str = Field(min_length=1)
    sensitive: bool = False


class AutomationTest(BaseModel):
    id: str = Field(description="Original test case ID when available, such as TC-001.")
    title: str
    source_test_case_id: str | None = None
    priority: Priority = Priority.MEDIUM
    preconditions: list[str] = Field(default_factory=list)
    test_data: list[AutomationDataItem] = Field(default_factory=list)
    steps: list[AutomationStep] = Field(min_length=1)
    notes: list[str] = Field(default_factory=list)


class AutomationSuite(BaseModel):
    target_url: str
    framework: str = "playwright-python-pytest"
    assumptions: list[str] = Field(default_factory=list)
    setup_notes: list[str] = Field(default_factory=list)
    tests: list[AutomationTest] = Field(min_length=1)


class AutomationRunStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    TIMEOUT = "timeout"


class AutomationRunResult(BaseModel):
    project_dir: str
    target_url: str
    command: list[str]
    status: AutomationRunStatus
    exit_code: int | None = None
    duration_seconds: float
    stdout: str = ""
    stderr: str = ""
    report_json_path: str | None = None
    report_markdown_path: str | None = None


class SelfHealingSuggestion(BaseModel):
    failed_locator: str | None = None
    failure_context: str
    suggested_locators: list[str] = Field(default_factory=list)
    recommendation: str


class ExecutionReport(BaseModel):
    status: AutomationRunStatus
    target_url: str
    project_dir: str
    command: list[str]
    exit_code: int | None = None
    duration_seconds: float
    total_tests: int | None = None
    passed_tests: int | None = None
    failed_tests: int | None = None
    summary: str
    findings: list[str] = Field(default_factory=list)
    self_healing: list[SelfHealingSuggestion] = Field(default_factory=list)


class DomSelectorCandidate(BaseModel):
    selector: str
    strategy: str
    stability: Priority = Priority.MEDIUM
    reason: str


class DomElement(BaseModel):
    tag: str
    role: str | None = None
    text: str | None = None
    label: str | None = None
    placeholder: str | None = None
    name: str | None = None
    element_type: str | None = None
    href: str | None = None
    selector_candidates: list[DomSelectorCandidate] = Field(default_factory=list)


class DomPage(BaseModel):
    url: str
    title: str | None = None
    elements: list[DomElement] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)


class DomInspectionReport(BaseModel):
    target_url: str
    pages: list[DomPage] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class PageObjectModelExport(BaseModel):
    target_url: str
    report: DomInspectionReport
    files: dict[str, str] = Field(default_factory=dict)


class TestManagementTool(StrEnum):
    XRAY = "xray"
    ZEPHYR = "zephyr"
    TESTRAIL = "testrail"


class TestManagementExport(BaseModel):
    tool: TestManagementTool
    source_summary: str
    row_count: int
    files: dict[str, str] = Field(default_factory=dict)
    run_report_markdown_path: str | None = None
    report_json_path: str | None = None
    report_markdown_path: str | None = None
