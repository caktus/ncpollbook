"""ASGI web chat app for the voter SQL agent.

Run with:
    uv run uvicorn apps.agent.web:app --host 127.0.0.1 --port 7932

Then open http://127.0.0.1:7932 in your browser.
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

import concurrent.futures  # noqa: E402

from apps.agent.models import AgentTool, ToolModel  # noqa: E402
from apps.agent.sql_agent import resolve_model, voter_agent  # noqa: E402


def _get_web_model() -> str:
    record = (
        ToolModel.objects.filter(tool_name=AgentTool.VOTER_AGENT).select_related("model").first()
        or ToolModel.objects.filter(tool_name=None).select_related("model").first()
    )
    if record is None:
        raise ValueError(
            "No ToolModel configured for voter_agent and no default (tool_name=NULL) found. "
            "Add a ToolModel record in the Django admin."
        )
    return resolve_model(record.model.name)


with concurrent.futures.ThreadPoolExecutor(max_workers=1) as _pool:
    _web_model = _pool.submit(_get_web_model).result()

app = voter_agent.to_web(models=[_web_model])
