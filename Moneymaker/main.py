"""
Moneymaker – MVP Idea Engine v2
Entry point for the fully autonomous pipeline.

Usage
-----
    python main.py [--dry-run] [--sources reddit producthunt] [--limit 20]

Options
-------
    --dry-run        Run the pipeline without calling external APIs (uses mock data).
    --sources        Space-separated list of signal sources to enable.
                     Choices: reddit producthunt indiehackers jobboards
                     Default: all sources.
    --limit          Maximum number of pain signals to process (default: 10).
    --output         Path to write the JSON report (default: stdout).
    --platforms      Distribution platforms to post to (default: all).
                     Choices: reddit indiehackers twitter telegram
    --no-fulfill     Skip the manual fulfillment step.
    --no-distribute  Skip the distribution injection step.
"""

import argparse
import asyncio
import json
import sys

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.engine import Engine
from src.models import ConversionSummary, DistributionResult, FulfillmentResult, MVPPlan

load_dotenv()

console = Console()


def _build_mvp_table(plans: list[MVPPlan]) -> Table:
    table = Table(title="🚀 MVP Plans Ready for Launch", show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Problem", max_width=35)
    table.add_column("Target User", max_width=20)
    table.add_column("Format", max_width=15)
    table.add_column("Revenue Model", max_width=20)
    table.add_column("Build Time", justify="right", max_width=12)

    for i, plan in enumerate(plans, 1):
        table.add_row(
            str(i),
            plan.idea.problem[:120],
            plan.idea.target_user,
            plan.format,
            plan.revenue_model,
            plan.estimated_build_time,
        )
    return table


def _build_fulfillment_table(results: list[FulfillmentResult]) -> Table:
    table = Table(title="🔧 Manual Fulfillment Results", show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Title", max_width=25)
    table.add_column("Status", max_width=12)
    table.add_column("Simulated", max_width=10)
    table.add_column("Notes", max_width=50)

    for i, result in enumerate(results, 1):
        status_style = "green" if result.status.value == "completed" else "yellow"
        table.add_row(
            str(i),
            result.plan.title,
            f"[{status_style}]{result.status.value}[/{status_style}]",
            "✓" if result.simulated else "✗",
            result.notes[:100],
        )
    return table


def _build_distribution_table(results: list[DistributionResult]) -> Table:
    table = Table(title="📢 Distribution Posts", show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Plan", max_width=20)
    table.add_column("Platform", max_width=14)
    table.add_column("Posted", max_width=7)
    table.add_column("Tracking ID", max_width=20)
    table.add_column("URL", max_width=40)

    row_num = 1
    for dist_result in results:
        for post in dist_result.posts:
            posted_style = "green" if post.posted else "dim"
            table.add_row(
                str(row_num),
                dist_result.plan.title[:30],
                post.platform.value,
                f"[{posted_style}]{'✓' if post.posted else '✗'}[/{posted_style}]",
                post.tracking_id[:16] + "…",
                post.url[:38] if post.url else "—",
            )
            row_num += 1
    return table


def _build_conversion_table(summaries: list[ConversionSummary]) -> Table:
    table = Table(title="📊 Conversion Tracking", show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Platform", max_width=14)
    table.add_column("Clicks", justify="right", max_width=8)
    table.add_column("Signups", justify="right", max_width=8)
    table.add_column("Replies", justify="right", max_width=8)
    table.add_column("Payments", justify="right", max_width=9)
    table.add_column("Revenue", justify="right", max_width=10)

    for i, s in enumerate(summaries, 1):
        table.add_row(
            str(i),
            s.platform.value,
            str(s.clicks),
            str(s.signups),
            str(s.replies),
            str(s.payments),
            f"${s.total_revenue:.2f}",
        )
    return table


async def run(args: argparse.Namespace) -> list[MVPPlan]:
    engine = Engine(
        sources=args.sources,
        signal_limit=args.limit,
        dry_run=args.dry_run,
        platforms=getattr(args, "platforms", None),
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    ) as progress:
        task = progress.add_task("⛏  Mining pain signals…", total=None)
        signals = await engine.mine_signals()
        progress.update(task, description=f"⛏  Found {len(signals)} signals")

        progress.update(task, description="💡  Generating ideas…", total=None)
        ideas = await engine.generate_ideas(signals)
        progress.update(task, description=f"💡  Generated {len(ideas)} ideas")

        progress.update(task, description="💰  Filtering for money…", total=None)
        filtered = await engine.filter_ideas(ideas)
        progress.update(task, description=f"💰  {len(filtered)} ideas passed the money filter")

        progress.update(task, description="🔨  Building MVP plans…", total=None)
        plans = await engine.build_mvps(filtered)
        progress.update(task, description=f"🔨  {len(plans)} MVP plans ready")

        fulfill_results = []
        if not getattr(args, "no_fulfill", False) and plans:
            progress.update(task, description="🔧  Fulfilling MVP services…", total=None)
            fulfill_results = await engine.fulfill_mvps(plans)
            progress.update(
                task,
                description=f"🔧  {len(fulfill_results)} services fulfilled",
            )

        distribution_results = []
        if not getattr(args, "no_distribute", False) and plans:
            progress.update(task, description="📢  Distributing posts…", total=None)
            distribution_results = await engine.distribute_mvps(plans)
            total_posts = sum(len(r.posts) for r in distribution_results)
            progress.update(task, description=f"📢  {total_posts} posts generated")

    conversion_summaries = engine.conversion_tracker.summarize_all()

    console.print()
    console.print(
        Panel.fit(
            f"[bold green]Pipeline complete[/bold green]\n"
            f"  Signals mined  : [cyan]{len(signals)}[/cyan]\n"
            f"  Ideas generated: [cyan]{len(ideas)}[/cyan]\n"
            f"  Passed filter  : [cyan]{len(filtered)}[/cyan]\n"
            f"  MVP plans built: [cyan]{len(plans)}[/cyan]\n"
            f"  Services fulfilled: [cyan]{len(fulfill_results)}[/cyan]\n"
            f"  Distribution posts: [cyan]{sum(len(r.posts) for r in distribution_results)}[/cyan]",
            title="[bold]Moneymaker — MVP Idea Engine v2[/bold]",
        )
    )

    if plans:
        console.print(_build_mvp_table(plans))
    if fulfill_results:
        console.print(_build_fulfillment_table(fulfill_results))
    if distribution_results:
        console.print(_build_distribution_table(distribution_results))
    if conversion_summaries:
        console.print(_build_conversion_table(conversion_summaries))

    return plans


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Moneymaker — MVP Idea Engine v2: Fully Autonomous System",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use mock data; skip external API calls.",
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        default=["reddit", "producthunt", "indiehackers", "jobboards"],
        choices=["reddit", "producthunt", "indiehackers", "jobboards"],
        metavar="SOURCE",
        help="Signal sources to enable (default: all).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of pain signals to process (default: 10).",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="File path for JSON report, or '-' for stdout (default: -).",
    )
    parser.add_argument(
        "--platforms",
        nargs="+",
        default=None,
        choices=["reddit", "indiehackers", "twitter", "telegram"],
        metavar="PLATFORM",
        help="Distribution platforms to post to (default: all).",
    )
    parser.add_argument(
        "--no-fulfill",
        action="store_true",
        help="Skip the manual fulfillment step.",
    )
    parser.add_argument(
        "--no-distribute",
        action="store_true",
        help="Skip the distribution injection step.",
    )

    args = parser.parse_args()

    plans = asyncio.run(run(args))

    report = [p.model_dump() for p in plans]
    json_output = json.dumps(report, indent=2, default=str)

    if args.output == "-":
        sys.stdout.write(json_output + "\n")
    else:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(json_output + "\n")
        console.print(f"\n📄 Report written to [bold]{args.output}[/bold]")


if __name__ == "__main__":
    main()
