"""ASGI web chat app for the voter SQL agent.

Run with:
    uv run uvicorn apps.agent.web:app --host 127.0.0.1 --port 7932

Then open http://127.0.0.1:7932 in your browser.
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.conf import settings  # noqa: E402

from apps.agent.sql_agent import voter_agent  # noqa: E402

app = voter_agent.to_web(models=settings.VOTER_REG_MODELS)
