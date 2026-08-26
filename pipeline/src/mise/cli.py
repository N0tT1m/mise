"""Pipeline entry point: `mise-pipeline <stage>`."""
from __future__ import annotations

import click

from . import STAGES, __version__, extract, ingest, publish, resolve
from .config import Config


@click.group(help="Mise offline pipeline. Stages run in order: " + " -> ".join(STAGES))
@click.version_option(__version__, prog_name="mise-pipeline")
def main() -> None:
    """Top-level CLI group."""


@main.command()
@click.option("--source", required=True, help="Source tag, e.g. 'dataset:indian'.")
@click.option("--path", required=True, help="Directory to ingest.")
def ingest_cmd(source: str, path: str) -> None:
    """Stage 1: load recipes with raw payloads intact."""
    click.echo(ingest.run(Config.from_env(), source, path))


@main.command()
@click.option("--limit", type=int, default=None, help="Cap lines processed.")
def extract_cmd(limit: int | None) -> None:
    """Stage 2: structure every ingredient line."""
    click.echo(extract.run(Config.from_env(), limit))


@main.command()
def resolve_cmd() -> None:
    """Stage 3: cluster names, resolve confident matches, queue the rest."""
    click.echo(resolve.run(Config.from_env()))


@main.command()
@click.option("--embed", is_flag=True, help="Also recompute embeddings.")
def publish_cmd(embed: bool) -> None:
    """Stage 4: rebuild derived columns the API reads."""
    click.echo(publish.run(Config.from_env(), embed))


main.add_command(ingest_cmd, "ingest")
main.add_command(extract_cmd, "extract")
main.add_command(resolve_cmd, "resolve")
main.add_command(publish_cmd, "publish")

if __name__ == "__main__":
    main()
