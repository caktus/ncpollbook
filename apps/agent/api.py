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

from apps.agent.models import AgentTool
from apps.agent.sql_agent import get_tool_model, voter_agent

_MODEL_ID = "voter-agent"

# Build auth from AGENT_API_KEY at startup. Bolt strips the "Bearer " prefix
# automatically when comparing Authorization header values, so api_keys holds the raw key.
_key = settings.AGENT_API_KEY
_auth = [APIKeyAuthentication(api_keys={_key}, header="Authorization")] if _key else []
_guards = [IsAuthenticated()] if _key else [AllowAny()]

api = BoltAPI(prefix="/v1")
register_health_checks(api)


# --- Request schemas ---


class Message(msgspec.Struct):
    role: str
    content: str | list


class ChatCompletionRequest(msgspec.Struct):
    messages: list[Message]
    stream: bool = False


# --- Helpers ---


def _extract_text(content: str | list) -> str:
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if p.get("type") == "text").strip()
    return str(content).strip()


def _build_question(messages: list[Message]) -> str | None:
    """Build a question from the message history.

    When there is only one user turn, returns it as-is.
    When there are multiple turns, prepends prior conversation as context so
    the agent can answer follow-up questions correctly.
    """
    question = None
    for msg in reversed(messages):
        if msg.role == "user":
            question = _extract_text(msg.content)
            break
    if not question:
        return None

    prior = messages[:-1]
    if not any(m.role == "user" for m in prior):
        return question

    context_lines = []
    for msg in prior:
        text = _extract_text(msg.content)
        if msg.role in ("user", "assistant") and text:
            label = "User" if msg.role == "user" else "Assistant"
            context_lines.append(f"{label}: {text}")

    if not context_lines:
        return question

    context = "\n".join(context_lines)
    return f"Conversation so far:\n{context}\n\nCurrent question: {question}"


def _completion_response(answer: str) -> dict:
    """Build an OpenAI-shaped chat.completion response dict."""
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": _MODEL_ID,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": answer},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


async def _sse_stream(question: str, model: str) -> AsyncGenerator[bytes]:
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
    async with voter_agent.iter(question, model=model) as agent_run:
        async for node in agent_run:
            if voter_agent.is_model_request_node(node):
                async with node.stream(agent_run.ctx) as stream:
                    async for delta in stream.stream_text(delta=True):
                        yield _chunk({"content": delta}, None)
    yield _chunk({}, "stop")
    yield b"data: [DONE]\n\n"


# --- Endpoints ---


@api.post("/chat/completions", auth=_auth, guards=_guards)
async def chat_completions(
    body: ChatCompletionRequest,
):
    """POST /v1/chat/completions — OpenAI-compatible chat completions."""

    question = _build_question(body.messages)
    if not question:
        raise BadRequest(detail="No user message found")

    model = await get_tool_model(AgentTool.VOTER_AGENT)

    if body.stream:
        return StreamingResponse(_sse_stream(question, model), media_type="text/event-stream")

    result = await voter_agent.run(question, model=model)
    return _completion_response(result.output)


@api.get("/models", auth=_auth, guards=_guards)
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
