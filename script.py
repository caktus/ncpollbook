#!/usr/bin/env python3
# /// script
# dependencies = ["click", "polars"]
# ///
import click
import polars as pl

COLUMNS = [
    "election_lbl",
    "election_desc",
    "voting_method",
    "voted_party_cd",
    "voted_party_desc",
]


@click.command()
@click.argument("filepath", default="scratch/data/ncvhis_Statewide.txt")
def main(filepath):
    """Find unique values for key columns in the NC voter history file."""
    click.echo(f"Scanning {filepath} ...")

    unique_values = (
        pl.scan_csv(
            filepath,
            separator="\t",
            quote_char='"',
            infer_schema=False,
        )
        .select(COLUMNS)
        .unique()
        .collect()
    )

    for col in COLUMNS:
        values = sorted(unique_values[col].drop_nulls().unique().to_list())
        click.echo(f"\n{col} ({len(values)} unique):")
        for v in values:
            click.echo(f"  {v}")


if __name__ == "__main__":
    main()
