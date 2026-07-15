from __future__ import annotations

import json
from pathlib import Path

from qa_agents.artifact_exporters import export_artifact
from qa_agents.config import Settings
from qa_agents.defect_agent import DefectCreationAgent
from qa_agents.design_agent import TestDesignDataAgent
from qa_agents.models import SourceMaterial
from qa_agents.planning_agent import TestPlanningAgent

PLAN = {
    "feature": "Logout",
    "objective": "Validate logout behavior.",
    "source_summary": "Users can sign out.",
    "scope": [{"area": "Session", "in_scope": ["Logout"], "out_of_scope": ["SSO"]}],
    "test_strategy": ["Risk-based testing"],
}

DESIGN = {
    "feature": "Logout",
    "source_summary": "Users can sign out.",
    "design_approach": ["State transition"],
    "scenarios": [
        {
            "id": "TD-001",
            "title": "Logout from active session",
            "design_technique": "state transition",
            "data_ids": ["DATA-001"],
        }
    ],
    "test_data": [
        {
            "id": "DATA-001",
            "purpose": "Valid user",
            "data": {"username": "standard_user", "password": "secret_sauce"},
            "expected_usage": "Login before logout.",
        }
    ],
}

DEFECTS = {
    "target_url": "https://example.test",
    "execution_summary": "One logout test failed.",
    "defects": [
        {
            "id": "DEF-001",
            "title": "Logout does not end session",
            "severity": "major",
            "priority": "high",
            "environment": "QA",
            "actual_result": "Inventory remains available.",
            "expected_result": "User is redirected to login.",
            "reproduction_steps": ["Login", "Logout", "Open inventory"],
        }
    ],
}


class FakeOllama:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def chat(self, system_prompt, user_prompt, response_schema, images_base64=None, model=None):
        return json.dumps(self.payload)


def test_planning_agent_generates_plan() -> None:
    agent = TestPlanningAgent(Settings(_env_file=None), FakeOllama(PLAN))
    plan = agent.generate([SourceMaterial(name="story", kind="text", content="User can logout.")])

    assert plan.feature == "Logout"
    assert plan.scope[0].area == "Session"


def test_design_agent_generates_design_and_data() -> None:
    agent = TestDesignDataAgent(Settings(_env_file=None), FakeOllama(DESIGN))
    design = agent.generate([SourceMaterial(name="story", kind="text", content="User can logout.")])

    assert design.scenarios[0].id == "TD-001"
    assert design.test_data[0].data["username"] == "standard_user"


def test_defect_agent_generates_defects() -> None:
    agent = DefectCreationAgent(Settings(_env_file=None), FakeOllama(DEFECTS))
    defects = agent.from_text("logout failed", "https://example.test")

    assert defects.defects[0].id == "DEF-001"
    assert defects.defects[0].severity.value == "major"


def test_exports_new_artifacts(tmp_path: Path) -> None:
    agent = TestPlanningAgent(Settings(_env_file=None), FakeOllama(PLAN))
    plan = agent.generate([SourceMaterial(name="story", kind="text", content="User can logout.")])

    md = export_artifact(plan, tmp_path / "plan.md")
    js = export_artifact(plan, tmp_path / "plan.json")

    assert md.is_file()
    assert js.is_file()
