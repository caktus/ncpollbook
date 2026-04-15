import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from django.db import OperationalError
from django.test import Client
from ninja.testing import TestClient
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
    def test_streams_event_stream(self):
        mock_result = MagicMock()

        async def fake_deltas():
            yield "Hello"

        mock_result.stream_text = MagicMock(return_value=fake_deltas())

        mock_run_stream_cm = MagicMock()
        mock_run_stream_cm.__aenter__ = AsyncMock(return_value=mock_result)
        mock_run_stream_cm.__aexit__ = AsyncMock(return_value=False)

        client = Client()
        with (
            patch("apps.agent.api.voter_agent.run_stream", return_value=mock_run_stream_cm),
            patch("apps.agent.api.get_tool_model", AsyncMock(return_value="openai:gpt-4o-mini")),
        ):
            resp = client.post(
                "/v1/chat/completions",
                data=json.dumps({"messages": _MESSAGES}),
                content_type="application/json",
            )

            assert resp.status_code == 200
            assert "text/event-stream" in resp.get("content-type", "")

            async def collect():
                return [chunk async for chunk in resp.streaming_content]

            body = b"".join(asyncio.run(collect())).decode()

        assert "Hello" in body
        assert "[DONE]" in body

    @pytest.mark.django_db
    def test_missing_user_message_returns_400(self):
        client = Client()
        resp = client.post(
            "/v1/chat/completions",
            data=json.dumps({"messages": [{"role": "system", "content": "hi"}]}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    @pytest.mark.django_db
    def test_invalid_body_returns_422(self):
        client = Client()
        resp = client.post(
            "/v1/chat/completions",
            data=json.dumps({"bad": "field"}),
            content_type="application/json",
        )
        assert resp.status_code == 422

    def test_health(self):
        client = TestClient(api)
        resp = client.get("/health")
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_ready(self):
        client = TestClient(api)
        assert client.get("/ready").status_code == 200

    def test_ready_db_failure_returns_503(self):
        client = TestClient(api)
        with patch("apps.agent.api.connection.cursor", side_effect=OperationalError("db down")):
            resp = client.get("/ready")
        assert resp.status_code == 503
