from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from django_bolt import BoltAPI
from django_bolt.auth import APIKeyAuthentication, IsAuthenticated
from django_bolt.testing import TestClient
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart

from apps.agent.api import Message, _parse_messages, api

_MESSAGES = [{"role": "user", "content": "how many active voters are there?"}]


class TestParseMessages:
    def test_single_user_message(self):
        msgs = [Message(role="user", content="How many voters?")]
        prompt, history = _parse_messages(msgs)
        assert prompt == "How many voters?"
        assert history == []

    def test_no_user_message_returns_empty(self):
        msgs = [Message(role="system", content="You are an assistant.")]
        prompt, history = _parse_messages(msgs)
        assert prompt == ""
        assert history == []

    def test_multi_turn_builds_history(self):
        msgs = [
            Message(role="user", content="How many people voted in Durham's 2026 primary?"),
            Message(role="assistant", content="66,154 people voted."),
            Message(role="user", content="What was the breakdown by party?"),
        ]
        prompt, history = _parse_messages(msgs)
        assert prompt == "What was the breakdown by party?"
        assert len(history) == 2
        assert isinstance(history[0], ModelRequest)
        assert isinstance(history[0].parts[0], UserPromptPart)
        assert isinstance(history[1], ModelResponse)
        assert isinstance(history[1].parts[0], TextPart)
        assert "66,154" in history[1].parts[0].content

    def test_multipart_content(self):
        msgs = [
            Message(
                role="user",
                content=[{"type": "text", "text": "Hello"}, {"type": "text", "text": "world"}],
            )
        ]
        prompt, history = _parse_messages(msgs)
        assert prompt == "Hello world"
        assert history == []


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
        mock_result = MagicMock()

        async def fake_deltas():
            return
            yield  # async generator that yields nothing

        mock_result.stream_text = MagicMock(return_value=fake_deltas())

        mock_run_stream_cm = MagicMock()
        mock_run_stream_cm.__aenter__ = AsyncMock(return_value=mock_result)
        mock_run_stream_cm.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("apps.agent.api.voter_agent.run_stream", return_value=mock_run_stream_cm),
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
    def test_streaming_yields_content_delta(self):
        """Agent token deltas from run_stream are forwarded as SSE chunks."""
        mock_result = MagicMock()

        async def fake_deltas():
            yield "Hello"

        mock_result.stream_text = MagicMock(return_value=fake_deltas())

        mock_run_stream_cm = MagicMock()
        mock_run_stream_cm.__aenter__ = AsyncMock(return_value=mock_result)
        mock_run_stream_cm.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("apps.agent.api.voter_agent.run_stream", return_value=mock_run_stream_cm),
            patch("apps.agent.api.get_tool_model", AsyncMock(return_value="openai:gpt-4o-mini")),
            TestClient(api) as client,
        ):
            resp = client.post(
                "/v1/chat/completions",
                json={"messages": _MESSAGES, "stream": True},
                stream=True,
            )
            assert resp.status_code == 200
            chunks = list(resp.iter_content(chunk_size=4096, decode_unicode=True))

        body = "".join(chunks)
        assert "Hello" in body
        assert "[DONE]" in body

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


class TestModelsList:
    @pytest.mark.django_db
    def test_returns_voter_agent_model(self):
        with TestClient(api) as client:
            resp = client.get("/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "list"
        assert data["data"][0]["id"] == "voter-agent"


class TestApiKeyAuth:
    """Verify APIKeyAuthentication rejects wrong keys and accepts correct ones."""

    def test_wrong_key_returns_401(self):
        auth = [APIKeyAuthentication(api_keys={"secret"}, header="Authorization")]
        guards = [IsAuthenticated()]
        test_api = BoltAPI()

        @test_api.get("/protected", auth=auth, guards=guards)
        async def protected():
            return {"ok": True}

        with TestClient(test_api) as client:
            assert (
                client.get("/protected", headers={"Authorization": "Bearer wrong"}).status_code
                == 401
            )
            assert (
                client.get("/protected", headers={"Authorization": "Bearer secret"}).status_code
                == 200
            )


class TestHealthChecks:
    def test_health_liveness(self):
        with TestClient(api) as client:
            resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
