from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from django.test import override_settings
from django_bolt.testing import TestClient

from apps.agent.api import Message, _build_question, api

_MESSAGES = [{"role": "user", "content": "how many active voters are there?"}]


class TestBuildQuestion:
    def test_single_user_message(self):
        msgs = [Message(role="user", content="How many voters?")]
        assert _build_question(msgs) == "How many voters?"

    def test_no_user_message_returns_none(self):
        msgs = [Message(role="system", content="You are an assistant.")]
        assert _build_question(msgs) is None

    def test_multi_turn_includes_context(self):
        msgs = [
            Message(role="user", content="How many people voted in Durham's 2026 primary?"),
            Message(role="assistant", content="66,154 people voted."),
            Message(role="user", content="What was the breakdown by party?"),
        ]
        result = _build_question(msgs)
        assert result is not None
        assert "Conversation so far:" in result
        assert "66,154 people voted" in result
        assert "Current question: What was the breakdown by party?" in result

    def test_multipart_content(self):
        msgs = [
            Message(
                role="user",
                content=[{"type": "text", "text": "Hello"}, {"type": "text", "text": "world"}],
            )
        ]
        assert _build_question(msgs) == "Hello world"


class TestChatCompletions:
    @pytest.mark.django_db
    def test_returns_openai_shape(self):
        with (
            patch(
                "apps.agent.api.voter_agent.run",
                AsyncMock(return_value=AsyncMock(output="There are 1000 active voters.")),
            ),
            patch("apps.agent.api.get_tool_model", AsyncMock(return_value="openai:gpt-4o-mini")),
            TestClient(api) as client,
        ):
            resp = client.post("/v1/chat/completions", json={"messages": _MESSAGES})
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "chat.completion"
        assert data["choices"][0]["message"]["role"] == "assistant"
        assert "active voters" in data["choices"][0]["message"]["content"]

    @pytest.mark.django_db
    def test_streaming_returns_event_stream(self):
        async def fake_nodes():
            return
            yield  # async generator that yields nothing

        mock_agent_run = MagicMock()
        mock_agent_run.__aiter__ = MagicMock(return_value=fake_nodes())
        mock_agent_run.ctx = MagicMock()

        mock_iter_cm = MagicMock()
        mock_iter_cm.__aenter__ = AsyncMock(return_value=mock_agent_run)
        mock_iter_cm.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("apps.agent.api.voter_agent.iter", return_value=mock_iter_cm),
            patch("apps.agent.api.get_tool_model", AsyncMock(return_value="openai:gpt-4o-mini")),
            TestClient(api) as client,
        ):
            resp = client.post(
                "/v1/chat/completions",
                json={"messages": _MESSAGES, "stream": True},
                stream=True,
            )
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")
            chunks = list(resp.iter_content(chunk_size=4096, decode_unicode=True))

        assert "[DONE]" in "".join(chunks)

    @pytest.mark.django_db
    def test_missing_user_message_returns_400(self):
        with TestClient(api) as client:
            resp = client.post(
                "/v1/chat/completions",
                json={"messages": [{"role": "system", "content": "hi"}]},
            )
        assert resp.status_code == 400

    @pytest.mark.django_db
    def test_invalid_body_returns_422(self):
        with TestClient(api) as client:
            resp = client.post("/v1/chat/completions", json={"bad": "field"})
        assert resp.status_code == 422

    @pytest.mark.django_db
    @override_settings(AGENT_API_KEY="secret")
    def test_wrong_api_key_returns_401(self):
        with TestClient(api) as client:
            resp = client.post(
                "/v1/chat/completions",
                json={"messages": _MESSAGES},
                headers={"Authorization": "Bearer wrong"},
            )
        assert resp.status_code == 401

    @pytest.mark.django_db
    @override_settings(AGENT_API_KEY="secret")
    def test_correct_api_key_passes(self):
        with (
            patch(
                "apps.agent.api.voter_agent.run",
                AsyncMock(return_value=AsyncMock(output="answer")),
            ),
            patch("apps.agent.api.get_tool_model", AsyncMock(return_value="openai:gpt-4o-mini")),
            TestClient(api) as client,
        ):
            resp = client.post(
                "/v1/chat/completions",
                json={"messages": _MESSAGES},
                headers={"Authorization": "Bearer secret"},
            )
        assert resp.status_code == 200


class TestModelsList:
    @pytest.mark.django_db
    def test_returns_voter_agent_model(self):
        with TestClient(api) as client:
            resp = client.get("/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "list"
        assert data["data"][0]["id"] == "voter-agent"

    @pytest.mark.django_db
    @override_settings(AGENT_API_KEY="secret")
    def test_wrong_api_key_returns_401(self):
        with TestClient(api) as client:
            resp = client.get("/v1/models", headers={"Authorization": "Bearer wrong"})
        assert resp.status_code == 401


class TestHealthChecks:
    def test_health_liveness(self):
        with TestClient(api) as client:
            resp = client.get("/v1/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
