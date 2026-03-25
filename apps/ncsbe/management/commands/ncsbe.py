"""
NCSBE voter data management commands.

Usage:
    uv run manage.py ncsbe etl                  # download, load, and refresh views
    uv run manage.py ncsbe etl --refresh-only   # only refresh materialized views
    uv run manage.py ncsbe peek                 # inspect first 100 rows of each file
    uv run manage.py ncsbe comments             # print suggested db_comment values for view columns
"""

from pathlib import Path

import djclick as click
import polars as pl
from django.conf import settings

from apps.ncsbe.constants import NCVHIS_TXT_FILENAME, NCVOTER_TXT_FILENAME
from apps.ncsbe.etl.download import download_ncsbe_files
from apps.ncsbe.etl.loader import elapsed_timer, load_history_file, load_voter_file
from apps.ncsbe.models import VoterEventView, VoterView


def _refresh_views() -> None:
    for view_cls in (VoterView, VoterEventView):
        name = view_cls._meta.db_table
        click.echo(f"  Refreshing {name} …")
        view_cls.refresh(concurrently=False)
        click.secho(f"  ✓ {name} refreshed", fg="green")


@click.group()
def command() -> None:
    """NCSBE voter data management commands."""


@command.command()
@click.option(
    "--refresh-only", is_flag=True, default=False, help="Only refresh materialized views."
)
def etl(refresh_only: bool) -> None:
    """Download and load NCSBE voter data into PostgreSQL."""
    with elapsed_timer() as total:
        if not refresh_only:
            scratch_dir = settings.SCRATCH_DIR
            click.echo(f"=== Downloading NCSBE voter data (cache: {scratch_dir}) ===")
            ncvoter_path, ncvhis_path = download_ncsbe_files(scratch_dir)

            click.echo("\n=== Loading voter registration data ===")
            with elapsed_timer() as t:
                voter_count = load_voter_file(ncvoter_path)
            rps = voter_count / t[0] if t[0] else 0
            click.secho(f"  ✓ {voter_count:,} rows in {t[0]:.1f}s ({rps:,.0f} rows/s)", fg="green")

            click.echo("\n=== Loading voter history data ===")
            with elapsed_timer() as t:
                history_count = load_history_file(ncvhis_path)
            rps = history_count / t[0] if t[0] else 0
            click.secho(
                f"  ✓ {history_count:,} rows in {t[0]:.1f}s ({rps:,.0f} rows/s)", fg="green"
            )

        click.echo("\n=== Refreshing materialized views ===")
        _refresh_views()

    click.secho(f"\nDone in {total[0]:.1f}s total.", fg="green")


@command.command()
def peek() -> None:
    """Load the first 100 rows of each file and show column info."""
    scratch_dir = settings.SCRATCH_DIR
    ncvoter_path, ncvhis_path = download_ncsbe_files(scratch_dir)

    for path, label in [
        (ncvoter_path, NCVOTER_TXT_FILENAME),
        (ncvhis_path, NCVHIS_TXT_FILENAME),
    ]:
        click.secho(f"\n=== {label} (first 100 rows) ===", bold=True)
        for col, dtype, samples in peek_file(path):
            click.echo(f"  {col:<30} {dtype:<12} {samples}")


def peek_file(path: Path, n_rows: int = 100) -> list[tuple[str, str, list[str]]]:
    """
    Read *n_rows* from a tab-delimited NCSBE file and return column info.

    Returns a list of (column_name, dtype_str, sample_values) tuples.
    """
    df = pl.read_csv(
        path,
        separator="\t",
        quote_char='"',
        n_rows=n_rows,
        infer_schema_length=n_rows,
        truncate_ragged_lines=True,
        encoding="utf8-lossy",
    )
    return [
        (col, str(df[col].dtype), df[col].drop_nulls().cast(pl.String).head(3).to_list())
        for col in df.columns
    ]


def _distinct_values(model_cls: type, col: str, max_values: int) -> str:
    """Return a compact string of distinct values for a column, for use as db_comment."""
    qs = model_cls.objects.values_list(col, flat=True).distinct()
    total = qs.count()
    raw = [str(v) if v != "" else "(empty)" for v in qs[:max_values] if v is not None]
    values = ", ".join(raw)
    if total > max_values:
        return f"{values} ... ({total} distinct)"
    return f"{values} ({total} distinct)"


@command.command()
@click.option(
    "--max-values", default=20, show_default=True, help="Max distinct values to list per column."
)
def comments(max_values: int) -> None:
    """Print suggested db_comment values based on distinct column values in the views.

    Output can be copy-pasted as db_comment= kwargs into model field definitions.
    """
    for model_cls in (VoterView, VoterEventView):
        click.secho(f"\n=== {model_cls.__name__} ===", bold=True)
        for field in model_cls._meta.fields:
            col = field.column
            suggestion = _distinct_values(model_cls, col, max_values)
            click.echo(f"  {col:<30} db_comment={suggestion!r}")
