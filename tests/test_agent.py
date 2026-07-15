from __future__ import annotations

import json

from qa_agents.config import Settings
from qa_agents.models import SourceMaterial
from qa_agents.test_case_agent import TestCaseAgent as Agent

VALID_SUITE = {
    "feature": "Login",
    "source_summary": "A user can log in.",
    "assumptions": [],
    "open_questions": [],
    "coverage": [{"requirement": "User login", "test_case_ids": ["TC-001"]}],
    "test_cases": [
        {
            "id": "TC-001",
            "title": "Successful login",
            "objective": "Confirm a registered user can log in.",
            "requirement_refs": ["User login"],
            "test_type": "functional",
            "priority": "critical",
            "preconditions": ["A registered user exists"],
            "test_data": ["Valid username and password"],
            "steps": [
                {
                    "step": 1,
                    "action": "Submit valid credentials",
                    "expected_result": "The account home page is displayed",
                }
            ],
            "expected_result": "The user is authenticated.",
            "tags": ["login"],
            "automation_candidate": True,
        }
    ],
}


class FakeOllama:
    def __init__(self) -> None:
        self.calls = []

    def chat(self, system_prompt, user_prompt, response_schema, images_base64=None, model=None):
        self.calls.append((system_prompt, user_prompt, response_schema, images_base64, model))
        return json.dumps(VALID_SUITE)


class RetryOllama:
    def __init__(self) -> None:
        self.calls = []

    def chat(self, system_prompt, user_prompt, response_schema, images_base64=None, model=None):
        self.calls.append((system_prompt, user_prompt, response_schema, images_base64, model))
        if len(self.calls) == 1:
            return '{"feature": "Login", "source_summary": "truncated'
        return json.dumps(VALID_SUITE)


def test_generates_valid_suite_from_text() -> None:
    llm = FakeOllama()
    agent = Agent(Settings(_env_file=None), llm=llm)

    suite = agent.from_text("Registered users can log in.")

    assert suite.feature == "Login"
    assert suite.test_cases[0].id == "TC-001"
    assert "Registered users can log in." in llm.calls[0][1]


def test_truncates_large_source() -> None:
    llm = FakeOllama()
    settings = Settings(_env_file=None, qa_agent_max_source_chars=5_000)
    agent = Agent(settings, llm=llm)

    agent.from_text("x" * 6_000)

    assert "[Source truncated" in llm.calls[0][1]


def test_retries_truncated_json_with_compact_prompt() -> None:
    llm = RetryOllama()
    agent = Agent(Settings(_env_file=None), llm=llm)

    suite = agent.from_text("Registered users can log in.", instructions="Use Gherkin format.")

    assert suite.feature == "Login"
    assert len(llm.calls) == 2
    assert "Generate at most 8 concise test cases" in llm.calls[1][1]
    assert "Given/When/Then" in llm.calls[1][1]


def test_image_inputs_add_compact_generation_guidance() -> None:
    llm = FakeOllama()
    agent = Agent(Settings(_env_file=None), llm=llm)

    agent.generate(
        [
            SourceMaterial(
                name="screen.png",
                kind="image",
                content="Screenshot input.",
                images_base64=["abc123"],
            )
        ]
    )

    assert "For image-only or screenshot inputs" in llm.calls[0][1]
    assert llm.calls[0][4] == "qwen2.5vl:7b"
