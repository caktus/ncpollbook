import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from django.db import OperationalError
from django.test import Client
from ninja.testing import TestClient
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ThinkingPart,
    ThinkingPartDelta,
    UserPromptPart,
)

from apps.agent.api import Message, _is_title_request, _parse_messages, api

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


class TestIsTitleRequest:
    def test_title_request_detected(self):
        prompt = "Provide a concise, 5-word-or-less title for the conversation, using title case conventions. Only return the title itself."
        assert _is_title_request(prompt) is True

    def test_voter_question_not_title_request(self):
        assert _is_title_request("How many active voters are in Durham County?") is False

    def test_empty_string(self):
        assert _is_title_request("") is False


class TestChatCompletions:
    @pytest.mark.django_db
    def test_streams_event_stream(self):
        async def fake_events():
            yield PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="Hello"))

        client = Client()
        with (
            patch("apps.agent.api.voter_agent.run_stream_events", return_value=fake_events()),
            patch("apps.agent.api.get_tool_model", AsyncMock(return_value="openai:gpt-4o-mini")),
        ):
            resp = client.post(
                "/v1/chat/completions",
                data=json.dumps({"messages": _MESSAGES, "stream": True}),
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
    def test_part_start_event_content_is_streamed(self):
        """PartStartEvent initial TextPart content must not be dropped."""

        async def fake_events():
            yield PartStartEvent(index=0, part=TextPart(content="The "))
            yield PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="counties"))

        client = Client()
        with (
            patch("apps.agent.api.voter_agent.run_stream_events", return_value=fake_events()),
            patch("apps.agent.api.get_tool_model", AsyncMock(return_value="openai:gpt-4o-mini")),
        ):
            resp = client.post(
                "/v1/chat/completions",
                data=json.dumps({"messages": _MESSAGES, "stream": True}),
                content_type="application/json",
            )

            async def collect():
                return [chunk async for chunk in resp.streaming_content]

            body = b"".join(asyncio.run(collect())).decode()

        assert "The " in body
        assert "counties" in body
        assert "[DONE]" in body

    @pytest.mark.django_db
    def test_title_request_uses_title_agent(self):
        """Title generation requests must use _title_agent (no tools), not voter_agent."""

        async def fake_events():
            yield PartDeltaEvent(
                index=0, delta=TextPartDelta(content_delta="Counties Pre-1900 Voters")
            )

        title_messages = [
            {
                "role": "user",
                "content": "Provide a concise, 5-word-or-less title for the conversation, using title case conventions. Only return the title itself.\n\nConversation:\nUser: Which counties have voters born before 1900?\nAI: I'll query the data.",
            }
        ]
        client = Client()
        with (
            patch(
                "apps.agent.api._title_agent.run_stream_events", return_value=fake_events()
            ) as mock_title,
            patch("apps.agent.api.voter_agent.run_stream_events") as mock_voter,
            patch("apps.agent.api.get_tool_model", AsyncMock(return_value="openai:gpt-4o-mini")),
        ):
            resp = client.post(
                "/v1/chat/completions",
                data=json.dumps({"messages": title_messages, "stream": True}),
                content_type="application/json",
            )

            async def collect():
                return [chunk async for chunk in resp.streaming_content]

            b"".join(asyncio.run(collect()))

        mock_title.assert_called_once()
        mock_voter.assert_not_called()

    @pytest.mark.django_db
    def test_non_streaming_title_returns_json_completion(self):
        """Non-streaming title request returns chat.completion JSON with message format."""
        title_messages = [
            {
                "role": "user",
                "content": "Provide a concise, 5-word-or-less title for the conversation, using title case conventions. Only return the title itself.\n\nConversation:\nUser: q\nAI: r",
            }
        ]
        mock_result = MagicMock()
        mock_result.output = "Pre-1900 County Voters"
        client = Client()
        with (
            patch("apps.agent.api._title_agent.run", AsyncMock(return_value=mock_result)),
            patch("apps.agent.api.voter_agent.run") as mock_voter,
            patch("apps.agent.api.get_tool_model", AsyncMock(return_value="openai:gpt-4o-mini")),
        ):
            resp = client.post(
                "/v1/chat/completions",
                data=json.dumps({"messages": title_messages}),
                content_type="application/json",
            )

        assert resp.status_code == 200
        assert "application/json" in resp.get("content-type", "")
        data = json.loads(resp.content)
        assert data["object"] == "chat.completion"
        assert data["choices"][0]["message"]["content"] == "Pre-1900 County Voters"
        mock_voter.assert_not_called()

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


class TestChatCompletionsLogging:
    @pytest.mark.django_db
    def test_logs_prompt_info(self):
        mock_result = MagicMock()
        mock_result.output = "42 active voters"
        client = Client()
        with (
            patch("apps.agent.api.voter_agent.run", AsyncMock(return_value=mock_result)),
            patch("apps.agent.api.get_tool_model", AsyncMock(return_value="openai:gpt-4o-mini")),
            patch("apps.agent.api.logger") as mock_logger,
        ):
            client.post(
                "/v1/chat/completions",
                data=json.dumps({"messages": _MESSAGES}),
                content_type="application/json",
            )
        mock_logger.info.assert_called_once()
        logged_msg = mock_logger.info.call_args[0][0]
        assert "chat_completions" in logged_msg


class TestOpenAITypes:
    @pytest.mark.django_db
    def test_streaming_chunks_have_openai_object_type(self):
        """Each SSE data chunk must conform to the ChatCompletionChunk schema."""

        async def fake_events():
            yield PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="hi"))

        client = Client()
        with (
            patch("apps.agent.api.voter_agent.run_stream_events", return_value=fake_events()),
            patch("apps.agent.api.get_tool_model", AsyncMock(return_value="openai:gpt-4o-mini")),
        ):
            resp = client.post(
                "/v1/chat/completions",
                data=json.dumps({"messages": _MESSAGES, "stream": True}),
                content_type="application/json",
            )

            async def collect():
                return [chunk async for chunk in resp.streaming_content]

            body = b"".join(asyncio.run(collect())).decode()

        data_lines = [line[6:] for line in body.splitlines() if line.startswith("data: {")]
        assert data_lines, "no data chunks found"
        for raw in data_lines:
            chunk = json.loads(raw)
            assert chunk["object"] == "chat.completion.chunk"

    @pytest.mark.django_db
    def test_non_streaming_response_has_openai_object_type(self):
        """Non-streaming response must conform to the ChatCompletion schema."""
        mock_result = MagicMock()
        mock_result.output = "42 active voters"
        client = Client()
        with (
            patch("apps.agent.api.voter_agent.run", AsyncMock(return_value=mock_result)),
            patch("apps.agent.api.get_tool_model", AsyncMock(return_value="openai:gpt-4o-mini")),
        ):
            resp = client.post(
                "/v1/chat/completions",
                data=json.dumps({"messages": _MESSAGES}),
                content_type="application/json",
            )
        data = json.loads(resp.content)
        assert data["object"] == "chat.completion"
        assert data["choices"][0]["finish_reason"] == "stop"
        assert data["usage"]["total_tokens"] == 0


class TestThinkingStreaming:
    @pytest.mark.django_db
    def test_thinking_delta_emits_reasoning_content(self):
        """ThinkingPartDelta events must produce reasoning_content chunks."""

        async def fake_events():
            yield PartDeltaEvent(index=0, delta=ThinkingPartDelta(content_delta="thinking..."))
            yield PartDeltaEvent(index=1, delta=TextPartDelta(content_delta="answer"))

        client = Client()
        with (
            patch("apps.agent.api.voter_agent.run_stream_events", return_value=fake_events()),
            patch("apps.agent.api.get_tool_model", AsyncMock(return_value="openai:gpt-4o-mini")),
        ):
            resp = client.post(
                "/v1/chat/completions",
                data=json.dumps({"messages": _MESSAGES, "stream": True}),
                content_type="application/json",
            )

            async def collect():
                return [chunk async for chunk in resp.streaming_content]

            body = b"".join(asyncio.run(collect())).decode()

        data_lines = [
            json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: {")
        ]
        reasoning_chunks = [
            c for c in data_lines if c["choices"][0]["delta"].get("reasoning_content")
        ]
        text_chunks = [c for c in data_lines if c["choices"][0]["delta"].get("content")]
        assert reasoning_chunks, "no reasoning_content chunks found"
        assert reasoning_chunks[0]["choices"][0]["delta"]["reasoning_content"] == "thinking..."
        assert text_chunks[0]["choices"][0]["delta"]["content"] == "answer"

    @pytest.mark.django_db
    def test_thinking_part_start_emits_reasoning_content(self):
        """PartStartEvent with ThinkingPart content must also emit reasoning_content."""

        async def fake_events():
            yield PartStartEvent(index=0, part=ThinkingPart(content="initial thought"))

        client = Client()
        with (
            patch("apps.agent.api.voter_agent.run_stream_events", return_value=fake_events()),
            patch("apps.agent.api.get_tool_model", AsyncMock(return_value="openai:gpt-4o-mini")),
        ):
            resp = client.post(
                "/v1/chat/completions",
                data=json.dumps({"messages": _MESSAGES, "stream": True}),
                content_type="application/json",
            )

            async def collect():
                return [chunk async for chunk in resp.streaming_content]

            body = b"".join(asyncio.run(collect())).decode()

        data_lines = [
            json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: {")
        ]
        reasoning_chunks = [
            c for c in data_lines if c["choices"][0]["delta"].get("reasoning_content")
        ]
        assert reasoning_chunks
        assert reasoning_chunks[0]["choices"][0]["delta"]["reasoning_content"] == "initial thought"
