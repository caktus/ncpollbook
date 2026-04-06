"""
Agent management commands.

Usage:
    uv run manage.py agent prompts                  # print all agent system prompts
    uv run manage.py agent prompts --name sql_gen   # print only the sql_gen_agent prompt
    uv run manage.py agent prompts --name voter     # print only the voter_agent prompt
    uv run manage.py agent cli                      # launch the interactive CLI
    uv run manage.py agent cli -q "..."            # ask a single question and exit
"""

import asyncio

import djclick as click

from apps.agent.cli import main as _cli_main
from apps.agent.sql_agent import _sql_system_prompt, voter_agent


@click.group()
def command() -> None:
    """Agent management commands."""


@command.command()
@click.option(
    "--name",
    type=click.Choice(["sql_gen", "voter"]),
    default=None,
    help="Print only the named agent's prompt (default: all).",
)
def prompts(name: str | None) -> None:
    """Print agent system prompts for inspection."""
    if name in (None, "sql_gen"):
        click.secho("=== sql_gen_agent system prompt ===", bold=True)
        click.echo(asyncio.run(_sql_system_prompt()))

    if name in (None, "voter"):
        if name is None:
            click.echo()
        click.secho("=== voter_agent instructions ===", bold=True)
        click.echo("\n".join(voter_agent._instructions))


@command.command()
@click.option("--question", "-q", default=None, help="Ask a single question and exit.")
@click.pass_context
def cli(ctx: click.Context, question: str | None) -> None:
    """Launch the interactive voter data agent CLI."""
    ctx.invoke(_cli_main, question=question)
