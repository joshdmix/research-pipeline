"""CLI entry point for the research pipeline."""

from __future__ import annotations

from pathlib import Path

import click
import structlog

from research_pipeline.config import Config
from research_pipeline.orchestrator import Orchestrator

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ],
)


@click.group()
@click.version_option()
def cli():
    """Research-to-Prototype Pipeline: discover papers, extract algorithms, generate code."""
    pass


@cli.command()
@click.option("--topic", "-t", help="Research topic to explore")
@click.option("--paper", "-p", help="Single arxiv paper ID (e.g., 2301.12345)")
@click.option("--output", "-o", default="./output", help="Output directory")
@click.option("--config", "-c", "config_path", default=None, help="Path to config.yaml")
def run(topic: str | None, paper: str | None, output: str, config_path: str | None):
    """Run the research pipeline."""
    if not topic and not paper:
        raise click.UsageError("Either --topic or --paper must be specified")

    config = Config.load(Path(config_path) if config_path else None)
    orchestrator = Orchestrator(config)
    output_dir = Path(output)

    if paper:
        click.echo(f"Running pipeline for paper: {paper}")
        ctx = orchestrator.run_paper(paper, output_dir)
    else:
        click.echo(f"Running pipeline for topic: {topic}")
        ctx = orchestrator.run_topic(topic, output_dir)

    click.echo(f"\nPipeline finished: {ctx.state.value}")
    click.echo(f"Output directory: {ctx.output_dir}")

    if ctx.implementations:
        click.echo(f"\nImplementations:")
        for impl in ctx.implementations:
            status = "OK" if impl.success else "FAIL"
            click.echo(f"  [{status}] {impl.algorithm_name} → {impl.module_path}")

    if ctx.test_results:
        click.echo(f"\nTests:")
        for test in ctx.test_results:
            status = "PASS" if test.success else "FAIL"
            click.echo(f"  [{status}] {test.algorithm_name}: {test.passed}p/{test.failed}f")

    if ctx.errors:
        click.echo(f"\nErrors:")
        for err in ctx.errors:
            click.echo(f"  - {err}")


@cli.command()
@click.option("--output", "-o", default="./output", help="Output directory to check")
def status(output: str):
    """Check pipeline status from saved state."""
    import json

    output_dir = Path(output)
    state_files = list(output_dir.rglob("pipeline_state.json"))

    if not state_files:
        click.echo("No pipeline runs found.")
        return

    for state_file in state_files:
        data = json.loads(state_file.read_text())
        click.echo(f"\n{state_file.parent.name}:")
        click.echo(f"  State: {data['state']}")
        click.echo(f"  Papers: {data.get('papers_fetched', 0)}")
        click.echo(f"  Analyses: {data.get('analyses', 0)}")
        if data.get("implementations"):
            ok = sum(1 for i in data["implementations"] if i["success"])
            click.echo(f"  Implementations: {ok}/{len(data['implementations'])} succeeded")
        if data.get("budget"):
            click.echo(f"  Budget: input {data['budget'].get('input_pct', '?')}, "
                       f"output {data['budget'].get('output_pct', '?')}")


if __name__ == "__main__":
    cli()
