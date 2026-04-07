import json
from unittest.mock import AsyncMock, patch

import pytest
from asgiref.sync import async_to_sync
from django.test import Client, override_settings

from apps.agent.views import _build_question


async def _collect_async(agen) -> list[bytes]:
    """Collect all chunks from an async generator into a list."""
    return [chunk async for chunk in agen]


@pytest.fixture
def client():
    return Client()


_MESSAGES = [{"role": "user", "content": "how many active voters are there?"}]


class TestBuildQuestion:
    def test_single_user_message(self):
        msgs = [{"role": "user", "content": "How many voters?"}]
        assert _build_question(msgs) == "How many voters?"

    def test_no_user_message_returns_none(self):
        msgs = [{"role": "system", "content": "You are an assistant."}]
        assert _build_question(msgs) is None

    def test_multi_turn_includes_context(self):
        msgs = [
            {"role": "user", "content": "How many people voted in Durham's 2026 primary?"},
            {"role": "assistant", "content": "66,154 people voted."},
            {"role": "user", "content": "What was the breakdown by party?"},
        ]
        result = _build_question(msgs)
        assert result is not None
        assert "Conversation so far:" in result
        assert "66,154 people voted" in result
        assert "Current question: What was the breakdown by party?" in result

    def test_multipart_content(self):
        msgs = [
            {
                "role": "user",
                "content": [{"type": "text", "text": "Hello"}, {"type": "text", "text": "world"}],
            }
        ]
        assert _build_question(msgs) == "Hello world"

    @pytest.mark.django_db
    def test_returns_openai_shape(self, client):
        with (
            patch(
                "apps.agent.views.voter_agent.run",
                AsyncMock(return_value=AsyncMock(output="There are 1000 active voters.")),
            ),
            patch(
                "apps.agent.views.get_tool_model",
                AsyncMock(return_value="openai:gpt-4o-mini"),
            ),
        ):
            resp = client.post(
                "/v1/chat/completions",
                data=json.dumps({"messages": _MESSAGES}),
                content_type="application/json",
            )
        assert resp.status_code == 200
        body = json.loads(resp.content)
        assert body["object"] == "chat.completion"
        assert body["choices"][0]["message"]["role"] == "assistant"
        assert "active voters" in body["choices"][0]["message"]["content"]

    @pytest.mark.django_db
    def test_streaming_returns_event_stream(self, client):
        with (
            patch(
                "apps.agent.views.voter_agent.run",
                AsyncMock(return_value=AsyncMock(output="42 active voters.")),
            ),
            patch(
                "apps.agent.views.get_tool_model",
                AsyncMock(return_value="openai:gpt-4o-mini"),
            ),
        ):
            resp = client.post(
                "/v1/chat/completions",
                data=json.dumps({"messages": _MESSAGES, "stream": True}),
                content_type="application/json",
            )
        assert resp.status_code == 200
        assert "text/event-stream" in resp["Content-Type"]
        # streaming_content is an async generator; collect it synchronously via Django's helper
        chunks = async_to_sync(lambda: _collect_async(resp.streaming_content))()
        body = b"".join(chunks).decode()
        assert "data:" in body
        assert "[DONE]" in body

    @pytest.mark.django_db
    def test_missing_user_message_returns_400(self, client):
        resp = client.post(
            "/v1/chat/completions",
            data=json.dumps({"messages": [{"role": "system", "content": "hi"}]}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    @pytest.mark.django_db
    def test_invalid_json_returns_400(self, client):
        resp = client.post(
            "/v1/chat/completions",
            data="not json",
            content_type="application/json",
        )
        assert resp.status_code == 400

    @pytest.mark.django_db
    @override_settings(AGENT_API_KEY="secret")
    def test_wrong_api_key_returns_401(self, client):
        resp = client.post(
            "/v1/chat/completions",
            data=json.dumps({"messages": _MESSAGES}),
            content_type="application/json",
            headers={"Authorization": "Bearer wrong"},
        )
        assert resp.status_code == 401

    @pytest.mark.django_db
    @override_settings(AGENT_API_KEY="secret")
    def test_correct_api_key_passes(self, client):
        with (
            patch(
                "apps.agent.views.voter_agent.run",
                AsyncMock(return_value=AsyncMock(output="answer")),
            ),
            patch(
                "apps.agent.views.get_tool_model",
                AsyncMock(return_value="openai:gpt-4o-mini"),
            ),
        ):
            resp = client.post(
                "/v1/chat/completions",
                data=json.dumps({"messages": _MESSAGES}),
                content_type="application/json",
                headers={"Authorization": "Bearer secret"},
            )
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_method_not_allowed(self, client):
        resp = client.get("/v1/chat/completions")
        assert resp.status_code == 405


class TestModelsList:
    @pytest.mark.django_db
    def test_returns_voter_agent_model(self, client):
        resp = client.get("/v1/models")
        assert resp.status_code == 200
        body = json.loads(resp.content)
        assert body["object"] == "list"
        assert body["data"][0]["id"] == "voter-agent"

    @pytest.mark.django_db
    @override_settings(AGENT_API_KEY="secret")
    def test_wrong_api_key_returns_401(self, client):
        resp = client.get("/v1/models", headers={"Authorization": "Bearer wrong"})
        assert resp.status_code == 401
