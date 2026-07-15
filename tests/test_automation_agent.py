from __future__ import annotations

import json

from qa_agents.automation_agent import AutomationAgent
from qa_agents.config import Settings

VALID_AUTOMATION = {
    "target_url": "https://staging.example.test",
    "framework": "playwright-python-pytest",
    "assumptions": ["Login page exposes accessible labels."],
    "setup_notes": ["Install Playwright browsers before running."],
    "tests": [
        {
            "id": "TC-001",
            "title": "Successful login",
            "source_test_case_id": "TC-001",
            "priority": "high",
            "preconditions": ["A registered user exists."],
            "test_data": [
                {
                    "name": "email",
                    "value": "qa.user@example.test",
                    "description": "Synthetic registered user email.",
                    "sensitive": False,
                }
            ],
            "steps": [
                {
                    "step": 1,
                    "action": "fill",
                    "description": "Enter email.",
                    "locator": "get_by_label('Email')",
                    "value": "{{email}}",
                    "expected_result": "Email is entered.",
                },
                {
                    "step": 2,
                    "action": "click",
                    "description": "Submit login.",
                    "locator": "get_by_role('button', name='Log in')",
                    "expected_result": "Dashboard opens.",
                },
            ],
            "notes": [],
        }
    ],
}


class FakeOllama:
    def __init__(self) -> None:
        self.calls = []

    def chat(self, system_prompt, user_prompt, response_schema, images_base64=None, model=None):
        self.calls.append((system_prompt, user_prompt, response_schema, images_base64, model))
        return json.dumps(VALID_AUTOMATION)


def test_generates_automation_from_text() -> None:
    llm = FakeOllama()
    agent = AutomationAgent(Settings(_env_file=None), llm=llm)

    suite = agent.from_text("https://staging.example.test", "TC-001: Successful login")

    assert suite.tests[0].id == "TC-001"
    assert suite.tests[0].test_data[0].name == "email"
    assert "https://staging.example.test" in llm.calls[0][1]
