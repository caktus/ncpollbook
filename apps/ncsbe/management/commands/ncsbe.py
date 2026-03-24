"""
NCSBE voter data management commands.

Usage:
    uv run manage.py ncsbe etl     # download and load data (default)
    uv run manage.py ncsbe peek    # inspect first 100 rows of each file
"""

import time
from pathlib import Path

import djclick as click
import polars as pl
from django.conf import settings

from apps.ncsbe.constants import NCVHIS_TXT_FILENAME, NCVOTER_TXT_FILENAME
from apps.ncsbe.etl.download import download_ncsbe_files
from apps.ncsbe.etl.loader import load_history_file, load_voter_file
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
def etl() -> None:
    """Download and load NCSBE voter data into PostgreSQL."""
    scratch_dir = settings.SCRATCH_DIR
    click.echo(f"=== Downloading NCSBE voter data (cache: {scratch_dir}) ===")
    ncvoter_path, ncvhis_path = download_ncsbe_files(scratch_dir)

    t_start = time.monotonic()

    click.echo("\n=== Loading voter registration data ===")
    voter_count, voter_elapsed = load_voter_file(ncvoter_path)
    voter_rps = voter_count / voter_elapsed if voter_elapsed else 0
    click.secho(
        f"  ✓ {voter_count:,} rows in {voter_elapsed:.1f}s ({voter_rps:,.0f} rows/s)",
        fg="green",
    )

    click.echo("\n=== Loading voter history data ===")
    history_count, history_elapsed = load_history_file(ncvhis_path)
    history_rps = history_count / history_elapsed if history_elapsed else 0
    click.secho(
        f"  ✓ {history_count:,} rows in {history_elapsed:.1f}s ({history_rps:,.0f} rows/s)",
        fg="green",
    )

    total = time.monotonic() - t_start
    click.echo("\n=== Refreshing materialized views ===")
    _refresh_views()
    click.secho(f"\nDone in {total:.1f}s total.", fg="green")


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
