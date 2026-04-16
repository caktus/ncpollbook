"""OpenAI-compatible Chat Completions endpoint for the voter agent.

Allows LibreChat (or any OpenAI-compatible client) to use the voter agent
as a backend by pointing it at http://<host>/v1 with model "voter-agent".

Served by uvicorn (uv run uvicorn config.asgi:application).

Endpoints:
    POST /v1/chat/completions
    GET  /v1/models
    GET  /health
    GET  /ready
"""

import json
import logging
import time
import uuid
from collections.abc import AsyncGenerator

from django.conf import settings
from django.db import OperationalError, connection
from django.http import StreamingHttpResponse
from ninja import NinjaAPI, Schema
from ninja.security import HttpBearer
from pydantic import ConfigDict, field_validator
from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    UserPromptPart,
)
from pydantic_ai.run import AgentRunResultEvent

from apps.agent.models import AgentTool
from apps.agent.sql_agent import get_tool_model, voter_agent

# LibreChat sends a title-generation message through the same endpoint.
# Route these to a tool-less agent so the voter agent never tries to run queries.
_TITLE_REQUEST_PREFIX = "Provide a concise, 5-word-or-less title"
_title_agent: Agent[None, str] = Agent()


def _is_title_request(prompt: str) -> bool:
    return prompt.startswith(_TITLE_REQUEST_PREFIX)


_MODEL_ID = "voter-agent"

logger = logging.getLogger(__name__)


class _BearerAuth(HttpBearer):
    def authenticate(self, request, token):
        expected = settings.AGENT_API_KEY
        if not expected or token == expected:
            return token
        return None


api = NinjaAPI(urls_namespace="agent")


# --- Request schemas ---


class Message(Schema):
    role: str
    content: str | list

    @field_validator("content", mode="before")
    @classmethod
    def coerce_content(cls, v):
        return v


class ChatCompletionRequest(Schema):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "messages": [
                        {"role": "user", "content": "How many active voters are in Durham County?"}
                    ]
                }
            ]
        }
    )

    messages: list[Message]
    stream: bool = False


# --- Helpers ---


def _extract_text(content: str | list) -> str:
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if p.get("type") == "text").strip()
    return str(content).strip()


def _parse_messages(messages: list[Message]) -> tuple[str, list[ModelMessage]]:
    """Return (user_prompt, message_history) for pydantic-ai.

    The last user message becomes the prompt; prior user/assistant turns are
    passed as structured ModelMessage history so the model sees proper
    conversation turns rather than a flattened text blob.
    """
    last_user_idx = next(
        (i for i in range(len(messages) - 1, -1, -1) if messages[i].role == "user"),
        None,
    )
    if last_user_idx is None:
        return "", []

    user_prompt = _extract_text(messages[last_user_idx].content)

    history: list[ModelMessage] = []
    for msg in messages[:last_user_idx]:
        text = _extract_text(msg.content)
        if not text:
            continue
        if msg.role == "user":
            history.append(ModelRequest(parts=[UserPromptPart(content=text)]))
        elif msg.role == "assistant":
            history.append(ModelResponse(parts=[TextPart(content=text)]))

    return user_prompt, history


async def _complete_non_streaming(question: str, model: str, history: list[ModelMessage]) -> dict:
    """Run agent without streaming; return an OpenAI chat.completion JSON response."""
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    agent = _title_agent if _is_title_request(question) else voter_agent
    result = await agent.run(question, model=model, message_history=history or None)
    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": _MODEL_ID,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": str(result.output)},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


async def _sse_stream(
    question: str, model: str, history: list[ModelMessage]
) -> AsyncGenerator[bytes]:
    """Async generator yielding SSE chunks for real token streaming."""
    logger.debug("sse_stream start prompt=%r history_len=%d", question[:80], len(history))
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())

    def _chunk(delta: dict, finish_reason: str | None) -> bytes:
        data = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": _MODEL_ID,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }
        return f"data: {json.dumps(data)}\n\n".encode()

    agent = _title_agent if _is_title_request(question) else voter_agent
    yield _chunk({"role": "assistant", "content": ""}, None)
    async for event in agent.run_stream_events(
        question, model=model, message_history=history or None
    ):
        logger.debug("event_stream %s", event)
        if isinstance(event, AgentRunResultEvent):
            break
        if (
            isinstance(event, PartStartEvent)
            and isinstance(event.part, TextPart)
            and event.part.has_content()
        ):
            yield _chunk({"content": event.part.content}, None)
        elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
            yield _chunk({"content": event.delta.content_delta}, None)
    yield _chunk({}, "stop")
    yield b"data: [DONE]\n\n"


# --- Endpoints ---

# Apply bearer auth only when AGENT_API_KEY is configured.
_auth: _BearerAuth | None = _BearerAuth() if settings.AGENT_API_KEY else None


@api.post("/v1/chat/completions", auth=_auth)
async def chat_completions(request, body: ChatCompletionRequest):
    """POST /v1/chat/completions — OpenAI-compatible chat completions."""

    user_prompt, history = _parse_messages(body.messages)
    logger.info(
        "chat_completions prompt=%r stream=%s title=%s",
        user_prompt[:80],
        body.stream,
        _is_title_request(user_prompt),
    )
    if not user_prompt:
        return api.create_response(request, {"detail": "No user message found"}, status=400)

    model = await get_tool_model(AgentTool.VOTER_AGENT)
    if not body.stream:
        return await _complete_non_streaming(user_prompt, model, history)
    return StreamingHttpResponse(
        _sse_stream(user_prompt, model, history), content_type="text/event-stream"
    )


@api.get("/v1/models", auth=_auth)
async def models_list(request):
    """GET /v1/models — returns a static voter-agent model entry."""
    return {
        "object": "list",
        "data": [
            {
                "id": _MODEL_ID,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "ncpollbook",
            }
        ],
    }


@api.get("/health", auth=None)
def health(request):
    """Liveness probe."""
    return {"status": "ok"}


@api.get("/ready", auth=None)
def ready(request):
    """Readiness probe — checks database connectivity."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except OperationalError:
        return api.create_response(request, {"status": "error"}, status=503)
    return {"status": "ok"}
