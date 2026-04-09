"""OpenAI-compatible Chat Completions endpoint for the voter agent.

Allows LibreChat (or any OpenAI-compatible client) to use the voter agent
as a backend by pointing it at http://<host>/v1 with model "voter-agent".

Endpoints:
    POST /v1/chat/completions
    GET  /v1/models
"""

import json
import time
import uuid
from collections.abc import AsyncGenerator

from django.conf import settings
from django.http import HttpRequest, JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from apps.agent.models import AgentTool
from apps.agent.sql_agent import get_tool_model, voter_agent

_MODEL_ID = "voter-agent"


def _check_api_key(request: HttpRequest) -> JsonResponse | None:
    """Return a 401 response if AGENT_API_KEY is configured and the request doesn't match."""
    required = settings.AGENT_API_KEY
    if not required:
        return None
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {required}":
        return JsonResponse(
            {"error": {"message": "Invalid API key", "type": "invalid_request_error"}},
            status=401,
        )
    return None


def _extract_text(content: str | list) -> str:
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if p.get("type") == "text").strip()
    return str(content).strip()


def _build_question(messages: list[dict]) -> str | None:
    """Build a question from the message history.

    When there is only one user turn, returns it as-is.
    When there are multiple turns, prepends prior conversation as context so
    the agent can answer follow-up questions correctly.
    """
    # Find the last user message
    question = None
    for msg in reversed(messages):
        if msg.get("role") == "user":
            question = _extract_text(msg.get("content", ""))
            break
    if not question:
        return None

    # Single-turn: no context needed
    prior = messages[:-1]
    if not any(m.get("role") == "user" for m in prior):
        return question

    # Multi-turn: prepend conversation context
    context_lines = []
    for msg in prior:
        role = msg.get("role", "")
        text = _extract_text(msg.get("content", ""))
        if role in ("user", "assistant") and text:
            label = "User" if role == "user" else "Assistant"
            context_lines.append(f"{label}: {text}")

    if not context_lines:
        return question

    context = "\n".join(context_lines)
    return f"Conversation so far:\n{context}\n\nCurrent question: {question}"


def _completion_response(answer: str, stream: bool = False) -> dict:
    """Build an OpenAI-shaped chat.completion response dict."""
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())
    if stream:
        return {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": _MODEL_ID,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": answer},
                    "finish_reason": None,
                }
            ],
        }
    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
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


async def _sse_stream(question: str, model: str) -> AsyncGenerator[str]:
    """Async generator yielding SSE chunks for real token streaming."""
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())

    def _chunk(delta: dict, finish_reason: str | None) -> str:
        data = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": _MODEL_ID,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }
        return f"data: {json.dumps(data)}\n\n"

    yield _chunk({"role": "assistant", "content": ""}, None)
    async with voter_agent.run_stream(question, model=model) as run:
        async for delta in run.stream_text(delta=True):
            yield _chunk({"content": delta}, None)
    yield _chunk({}, "stop")
    yield "data: [DONE]\n\n"


@csrf_exempt
async def chat_completions(request: HttpRequest) -> JsonResponse | StreamingHttpResponse:
    """POST /v1/chat/completions — OpenAI-compatible chat completions."""
    if request.method != "POST":
        return JsonResponse({"error": {"message": "Method not allowed"}}, status=405)

    deny = _check_api_key(request)
    if deny:
        return deny

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse(
            {"error": {"message": "Invalid JSON body", "type": "invalid_request_error"}},
            status=400,
        )

    messages = body.get("messages", [])
    question = _build_question(messages)
    if not question:
        return JsonResponse(
            {"error": {"message": "No user message found", "type": "invalid_request_error"}},
            status=400,
        )

    stream = body.get("stream", False)
    model = await get_tool_model(AgentTool.VOTER_AGENT)

    if stream:
        return StreamingHttpResponse(
            _sse_stream(question, model),
            content_type="text/event-stream",
        )

    result = await voter_agent.run(question, model=model)
    answer = result.output
    return JsonResponse(_completion_response(answer))


@require_GET
def models_list(request: HttpRequest) -> JsonResponse:
    """GET /v1/models — returns a static voter-agent model entry."""
    deny = _check_api_key(request)
    if deny:
        return deny
    now = int(time.time())
    return JsonResponse(
        {
            "object": "list",
            "data": [
                {
                    "id": _MODEL_ID,
                    "object": "model",
                    "created": now,
                    "owned_by": "ncpollbook",
                }
            ],
        }
    )
