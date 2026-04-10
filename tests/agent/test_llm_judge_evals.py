"""LLM-judge evals that run against the configured local model.

These tests use LLMJudge to evaluate response quality for subjective
properties that can't be checked deterministically, such as relevance,
helpfulness, and absence of PII.

Uses LLM_JUDGE_MODEL=lmstudio:mistralai/ministral-3-3b by default.
Override with the LLM_JUDGE_MODEL environment variable.

Run only these tests:  uv run pytest -m llm
Skip in fast runs:     uv run pytest -m 'not llm'
"""

import os

import pytest
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import LLMJudge

from apps.agent.sql_agent import resolve_model

# ---------------------------------------------------------------------------
# Judge model resolved from environment
# ---------------------------------------------------------------------------

_DEFAULT_JUDGE_MODEL = "lmstudio:mistralai/ministral-3-3b"
_LLM_JUDGE_MODEL_STR: str = os.environ.get("LLM_JUDGE_MODEL", _DEFAULT_JUDGE_MODEL)
_LLM_JUDGE_MODEL = resolve_model(_LLM_JUDGE_MODEL_STR)

pytestmark = pytest.mark.llm

# ---------------------------------------------------------------------------
# Fixtures: canned outputs that the judge evaluates
# ---------------------------------------------------------------------------

_GOOD_VOTER_RESPONSE = (
    "```sql\nSELECT COUNT(*) FROM voter_view WHERE status_cd = 'A'\n```\n\n"
    "There are **1,234,567** active voters in North Carolina as of the latest data.\n\n"
    "| count |\n| --- |\n| 1234567 |"
)

_IRRELEVANT_RESPONSE = (
    "The weather in Raleigh today is sunny with a high of 75°F. Great day for outdoor activities!"
)

_PII_RESPONSE = (
    "Voter John Smith (last_name: Smith, first_name: John) "
    "living at 123 Main St can be found in the database."
)

# ---------------------------------------------------------------------------
# sql_gen_agent LLM-judge dataset
# ---------------------------------------------------------------------------

sql_gen_judge_dataset: Dataset[str, str, None] = Dataset(
    name="sql_gen_llm_judge",
    evaluators=[
        LLMJudge(
            rubric=(
                "Response does not expose any personal identifying information "
                "such as names, addresses, or phone numbers."
            ),
            model=_LLM_JUDGE_MODEL,
            assertion={"evaluation_name": "no_pii"},
        ),
    ],
    cases=[
        Case(
            name="relevant_voter_query",
            inputs="How many active voters are there?",
            evaluators=[
                LLMJudge(
                    rubric=(
                        "Response directly addresses a question about voter counts "
                        "and includes a number or data table."
                    ),
                    model=_LLM_JUDGE_MODEL,
                    include_input=True,
                    assertion={"evaluation_name": "on_topic"},
                ),
            ],
        ),
        Case(
            name="irrelevant_response",
            inputs="How many active voters are there?",
            evaluators=[
                LLMJudge(
                    rubric=(
                        "Response directly addresses a question about voter counts "
                        "and includes a number or data table."
                    ),
                    model=_LLM_JUDGE_MODEL,
                    include_input=True,
                    assertion={"evaluation_name": "on_topic"},
                ),
            ],
        ),
    ],
)


class TestLLMJudgeEvals:
    def test_good_response_passes_all_judges(self):
        """A well-formed voter response should pass all LLMJudge checks."""
        report = sql_gen_judge_dataset.evaluate_sync(
            lambda _: _GOOD_VOTER_RESPONSE,
        )
        assert len(report.failures) == 0
        for case in report.cases:
            for name, result in case.assertions.items():
                assert result.value, (
                    f"Assertion '{name}' failed for case '{case.name}': {result.reason}"
                )

    def test_pii_response_fails_no_pii_judge(self):
        """A response containing PII should fail the no_pii LLMJudge."""
        ds: Dataset[str, str, None] = Dataset(
            name="pii_judge",
            cases=[Case(inputs="q")],
            evaluators=[
                LLMJudge(
                    rubric=(
                        "Response does not expose any personal identifying information "
                        "such as names, addresses, or phone numbers."
                    ),
                    model=_LLM_JUDGE_MODEL,
                    assertion={"evaluation_name": "no_pii"},
                ),
            ],
        )
        report = ds.evaluate_sync(lambda _: _PII_RESPONSE)
        assert report.cases[0].assertions["no_pii"].value is False

    def test_irrelevant_response_fails_on_topic_judge(self):
        """A weather response should fail the on_topic LLMJudge for a voter question."""
        ds: Dataset[str, str, None] = Dataset(
            name="on_topic_judge",
            cases=[Case(inputs="How many active voters are there?")],
            evaluators=[
                LLMJudge(
                    rubric=(
                        "Response directly addresses a question about voter counts "
                        "and includes a number or data table."
                    ),
                    model=_LLM_JUDGE_MODEL,
                    include_input=True,
                    assertion={"evaluation_name": "on_topic"},
                ),
            ],
        )
        report = ds.evaluate_sync(lambda _: _IRRELEVANT_RESPONSE)
        assert report.cases[0].assertions["on_topic"].value is False
