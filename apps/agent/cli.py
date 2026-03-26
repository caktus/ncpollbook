"""Interactive CLI for the NC voter data agent.

Run with:
    uv run python -m apps.agent.cli
    uv run python -m apps.agent.cli --question "how many active voters are in Durham?"
"""

import asyncio
import os
import time

import click
from pydantic_ai._agent_graph import CallToolsNode, ModelRequestNode
from pydantic_ai.messages import TextPart, ThinkingPart, ToolCallPart, ToolReturnPart
from pydantic_graph.nodes import End
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.status import Status
from rich.table import Table

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from apps.agent.sql_agent import voter_agent  # noqa: E402

console = Console()


def _fmt_elapsed(seconds: float) -> str:
    return f"{seconds:.2f}s"


async def _run_question(question: str) -> None:
    """Run voter_agent for one question, printing each step with rich formatting."""

    # Each entry: (label, elapsed, input_tok, output_tok, tok_per_sec)
    steps: list[tuple[str, float, int, int, float]] = []

    request_start: float = 0.0
    tool_starts: dict[str, float] = {}  # tool_call_id -> start time
    tool_call_names: dict[str, str] = {}  # tool_call_id -> tool name
    request_count = 0

    status = Status("[cyan]Calling model…[/]", console=console, spinner="dots")

    async with voter_agent.iter(question) as agent_run:
        async for node in agent_run:
            if isinstance(node, ModelRequestNode):
                # Show tool results that arrived with this request
                for part in node.request.parts:
                    if isinstance(part, ToolReturnPart):
                        tool_id = part.tool_call_id
                        elapsed = time.monotonic() - tool_starts.get(tool_id, time.monotonic())
                        name = tool_call_names.get(tool_id, part.tool_name)
                        steps.append((f"tool:{name}", elapsed, 0, 0, 0.0))
                        preview = (
                            part.content if isinstance(part.content, str) else str(part.content)
                        )
                        if len(preview) > 400:
                            preview = preview[:400] + "\n…"
                        console.print(
                            Panel(
                                preview,
                                title=f"[bold blue]↩ {name}[/] result",
                                border_style="blue",
                                padding=(0, 1),
                            )
                        )

                request_count += 1
                request_start = time.monotonic()
                status.start()

            elif isinstance(node, CallToolsNode):
                status.stop()
                elapsed = time.monotonic() - request_start
                response = node.model_response
                usage = response.usage
                tok_per_sec = usage.output_tokens / elapsed if elapsed > 0 else 0.0
                steps.append(
                    (
                        f"model:request-{request_count}",
                        elapsed,
                        usage.input_tokens,
                        usage.output_tokens,
                        tok_per_sec,
                    )
                )

                for part in response.parts:
                    if isinstance(part, ThinkingPart) and part.content.strip():
                        console.print(
                            Panel(
                                part.content,
                                title="[dim]Thinking[/]",
                                border_style="dim",
                                padding=(0, 1),
                            )
                        )
                    elif isinstance(part, ToolCallPart):
                        tool_starts[part.tool_call_id] = time.monotonic()
                        tool_call_names[part.tool_call_id] = part.tool_name
                        args = (
                            part.args_as_json_str()
                            if hasattr(part, "args_as_json_str")
                            else str(part.args)
                        )
                        console.print(f"[bold yellow]→ {part.tool_name}([/]{args}[bold yellow])[/]")
                    elif isinstance(part, TextPart) and part.content.strip():
                        console.print(Markdown(part.content))

            elif isinstance(node, End):
                result = agent_run.result
                if result and isinstance(result.output, str) and result.output.strip():
                    console.rule("[bold green]Answer[/]")
                    console.print(Markdown(result.output))

    # -----------------------------------------------------------------------
    # Summary table
    # -----------------------------------------------------------------------
    console.rule("[bold]Run summary[/]")
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("Step", style="cyan")
    table.add_column("Elapsed", justify="right")
    table.add_column("In tok", justify="right")
    table.add_column("Out tok", justify="right")
    table.add_column("tok/s", justify="right")

    total_elapsed = 0.0
    total_in = 0
    total_out = 0
    for label, elapsed, in_tok, out_tok, tps in steps:
        table.add_row(
            label,
            _fmt_elapsed(elapsed),
            str(in_tok) if in_tok else "—",
            str(out_tok) if out_tok else "—",
            f"{tps:.1f}" if tps else "—",
        )
        total_elapsed += elapsed
        total_in += in_tok
        total_out += out_tok

    total_tps = total_out / total_elapsed if total_elapsed > 0 else 0.0
    table.add_section()
    table.add_row(
        "[bold]Total[/]",
        f"[bold]{_fmt_elapsed(total_elapsed)}[/]",
        f"[bold]{total_in}[/]" if total_in else "—",
        f"[bold]{total_out}[/]" if total_out else "—",
        f"[bold]{total_tps:.1f}[/]" if total_tps else "—",
    )
    console.print(table)


@click.command()
@click.option("--question", "-q", default=None, help="Ask a single question and exit.")
def main(question: str | None) -> None:
    """Interactive CLI for the NC voter data agent."""
    console.rule("[bold cyan]NC Voter Data Agent[/]")

    if question:
        console.print(f"\n[bold]Question:[/] {question}\n")
        asyncio.run(_run_question(question))
        return

    # Interactive loop
    console.print("Type a question and press Enter. Type [bold]quit[/] or Ctrl-C to exit.\n")
    while True:
        try:
            q = click.prompt("You", prompt_suffix=" > ")
        except click.Abort, KeyboardInterrupt, EOFError:
            break
        if q.strip().lower() in {"quit", "exit", "q"}:
            break
        if q.strip():
            console.print()
            asyncio.run(_run_question(q.strip()))
            console.print()


if __name__ == "__main__":
    main()
