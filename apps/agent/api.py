"""OpenAI-compatible Chat Completions endpoint for the voter agent.

Allows LibreChat (or any OpenAI-compatible client) to use the voter agent
as a backend by pointing it at http://<host>/v1 with model "voter-agent".

Served by django-bolt (manage.py runbolt --dev).

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

import msgspec
from django.conf import settings
from django_bolt import BoltAPI
from django_bolt.auth import AllowAny, APIKeyAuthentication, IsAuthenticated
from django_bolt.exceptions import BadRequest
from django_bolt.health import register_health_checks
from django_bolt.responses import StreamingResponse
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart

from apps.agent.models import AgentTool
from apps.agent.sql_agent import get_tool_model, voter_agent

_MODEL_ID = "voter-agent"

logger = logging.getLogger(__name__)

# Build auth from AGENT_API_KEY at startup. Bolt strips the "Bearer " prefix
# automatically when comparing Authorization header values, so api_keys holds the raw key.
_key = settings.AGENT_API_KEY
_auth = [APIKeyAuthentication(api_keys={_key}, header="Authorization")] if _key else []
_guards = [IsAuthenticated()] if _key else [AllowAny()]

api = BoltAPI()
register_health_checks(api)


# --- Request schemas ---


class Message(msgspec.Struct):
    role: str
    content: str | list


class ChatCompletionRequest(msgspec.Struct):
    messages: list[Message]


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


async def _sse_stream(
    question: str, model: str, history: list[ModelMessage]
) -> AsyncGenerator[bytes]:
    """Async generator yielding SSE chunks for real token streaming."""
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

    yield _chunk({"role": "assistant", "content": ""}, None)
    async with voter_agent.run_stream(
        question, model=model, message_history=history or None
    ) as result:
        async for delta in result.stream_text(delta=True):
            yield _chunk({"content": delta}, None)
    yield _chunk({}, "stop")
    yield b"data: [DONE]\n\n"


# --- Endpoints ---


@api.post("/v1/chat/completions", auth=_auth, guards=_guards)
async def chat_completions(body: ChatCompletionRequest) -> StreamingResponse:
    """POST /v1/chat/completions — OpenAI-compatible chat completions (streaming only)."""

    logger.debug("chat_completions messages: %s", body.messages)
    user_prompt, history = _parse_messages(body.messages)
    if not user_prompt:
        raise BadRequest(detail="No user message found")

    model = await get_tool_model(AgentTool.VOTER_AGENT)
    return StreamingResponse(
        _sse_stream(user_prompt, model, history), media_type="text/event-stream"
    )


@api.get("/v1/models", auth=_auth, guards=_guards)
async def models_list() -> dict:
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
