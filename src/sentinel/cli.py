"""CLI entry point for Sentinel SRE Agent."""

from __future__ import annotations

import json
import sys
import os

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.table import Table

from sentinel.tracing import setup_tracing
from sentinel.agent import SentinelAgent
from sentinel.mcp import PhoenixMCPClient
from sentinel.tools import (
    QueryMetrics,
    QueryTraces,
    GetAlerts,
    AnalyzeDrift,
    CorrelateSignals,
    CreateAlert,
    SuggestRemediation,
    SelfIntrospect,
    QueryPhoenixTraces,
    QueryPhoenixSpans,
    QueryPhoenixSessions,
)
from sentinel.evaluation import LLMJudge
from sentinel.scenarios import SCENARIOS, run_demo_scenario, list_scenarios

console = Console()


@click.group()
def cli():
    """Sentinel SRE Agent - AI-powered ML model observability."""
    pass


@cli.command()
@click.option("--demo", is_flag=True, help="Run in demo mode with seeded data")
@click.option("--model", default=None, help="Gemini model to use")
@click.option("--live", is_flag=True, help="Force live Phoenix MCP (requires Phoenix server running)")
def interactive(demo: bool, model: str | None, live: bool):
    """Interactive chat with the Sentinel agent."""
    load_dotenv()

    if demo and not live:
        os.environ["SENTINEL_DEMO_MODE"] = "true"
        console.print(Panel("[yellow]Demo Mode[/yellow] - Using seeded data. Add --live for real Phoenix MCP.", border_style="yellow"))

    setup_tracing()
    agent = _create_agent(model=model, demo=demo and not live)

    _print_banner()

    phoenix_url = os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006")
    if "app.phoenix.arize.com" in phoenix_url:
        console.print(f"[dim]Phoenix: [link]{phoenix_url}[/link][/dim]")
    else:
        console.print(f"[dim]Phoenix: [link]{phoenix_url}[/link] (open in browser to view traces)[/dim]")
    console.print("[dim]Type a mission. Try 'scenarios' to see demos, 'run <id>' to execute one.[/dim]")

    session_count = 0
    while True:
        mission = Prompt.ask("\n[bold green]Mission[/bold green]")

        if mission.lower() in ("quit", "exit", "q"):
            console.print("[dim]Goodbye![/dim]")
            break

        if mission.lower() == "scenarios":
            _print_scenarios()
            continue

        if mission.lower().startswith("run "):
            scenario_id = mission.split(" ", 1)[1].strip()
            _run_scenario_by_id(scenario_id, agent)
            continue

        if not mission.strip():
            continue

        session_count += 1
        session_id = f"session-{session_count:03d}"

        console.print()
        console.print("[bold yellow]Sentinel is investigating...[/bold yellow]")
        console.print()

        try:
            response = agent.run(mission, session_id=session_id)
            console.print(Panel(Markdown(response.content), title="Sentinel Response", border_style="blue"))

            if response.tool_calls:
                console.print()
                console.print("[dim]Tools used:[/dim]")
                for tc in response.tool_calls:
                    status = "[green]✓[/green]" if tc["success"] else "[red]✗[/red]"
                    console.print(f"  {status} {tc['tool']}")

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


@cli.command()
@click.option("--demo", is_flag=True, help="Run demo scenarios with seeded data")
@click.option("--evaluate/--no-evaluate", default=True, help="Run LLM-as-a-judge evaluation")
@click.option("--scenario", default=None, help="Run a specific scenario ID")
def demo_scenarios(demo: bool, evaluate: bool, scenario: str | None):
    """Run through demo scenarios showcasing agent capabilities."""
    load_dotenv()

    if demo:
        os.environ["SENTINEL_DEMO_MODE"] = "true"

    setup_tracing()
    agent = _create_agent(demo=demo)
    evaluator = LLMJudge() if evaluate else None

    _print_banner()
    console.print("[bold cyan]Running Demo Scenarios[/bold cyan]")
    console.print()

    results = []

    if scenario:
        s = next((s for s in SCENARIOS if s.id == scenario), None)
        if s:
            result = run_demo_scenario(agent, s, evaluator)
            results.append(result)
    else:
        for s in SCENARIOS:
            result = run_demo_scenario(agent, s, evaluator)
            results.append(result)

    _print_summary(results)


@cli.command()
def scenarios():
    """List available demo scenarios."""
    _print_scenarios()


@cli.command()
def status():
    """Check agent configuration and dependencies."""
    load_dotenv()

    console.print(Panel("[bold]Sentinel SRE Agent[/bold] - Status Check", border_style="cyan"))

    table = Table()
    table.add_column("Component", style="cyan")
    table.add_column("Status")
    table.add_column("Details")

    # Gemini
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if gemini_key and gemini_key != "your-gemini-api-key-here":
        table.add_row("Gemini API", "[green]Configured[/green]", os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"))
    else:
        table.add_row("Gemini API", "[red]Not configured[/red]", "Set GEMINI_API_KEY in .env")

    # Phoenix
    phoenix_url = os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006")
    phoenix_key = os.environ.get("PHOENIX_API_KEY", "")
    if phoenix_key and phoenix_key != "your-phoenix-api-key-here":
        table.add_row("Phoenix", "[green]Configured[/green]", phoenix_url)
    else:
        mode = "Cloud" if "app.phoenix.arize.com" in phoenix_url else "Local"
        table.add_row("Phoenix", f"[yellow]{mode} (no API key)[/yellow]", phoenix_url)

    # npx
    import shutil
    npx_path = shutil.which("npx")
    if npx_path:
        table.add_row("npx (for MCP)", "[green]Available[/green]", npx_path)
    else:
        table.add_row("npx (for MCP)", "[red]Not found[/red]", "Install Node.js")

    # Demo mode
    demo_mode = os.environ.get("SENTINEL_DEMO_MODE", "false")
    table.add_row("Demo Mode", "[green]ON[/green]" if demo_mode == "true" else "[yellow]OFF[/yellow]", "Set SENTINEL_DEMO_MODE=true")

    console.print(table)


def _create_agent(model: str | None = None, demo: bool = True) -> SentinelAgent:
    """Create the Sentinel agent with all tools."""
    phoenix_client = PhoenixMCPClient()

    tools = [
        SelfIntrospect(phoenix_client),
        QueryPhoenixTraces(phoenix_client),
        QueryPhoenixSpans(phoenix_client),
        QueryPhoenixSessions(phoenix_client),
        QueryMetrics(),
        QueryTraces(),
        GetAlerts(),
        AnalyzeDrift(),
        CorrelateSignals(),
        SuggestRemediation(),
        CreateAlert(),
    ]

    return SentinelAgent(model=model, tools=tools)


def _print_banner():
    console.print(Panel(
        "[bold cyan]Sentinel SRE Agent[/bold cyan]\n"
        "[dim]Self-improving ML Model Observability & Incident Response[/dim]\n\n"
        "Powered by [bold]Gemini[/bold] + [bold]Arize Phoenix[/bold] + MCP",
        border_style="cyan",
    ))


def _print_scenarios():
    table = Table(title="Available Demo Scenarios")
    table.add_column("ID", style="cyan")
    table.add_column("Title")
    table.add_column("Complexity")
    table.add_column("Mission", style="dim")

    for s in SCENARIOS:
        table.add_row(s.id, s.title, s.complexity, s.mission[:60] + "...")

    console.print(table)
    console.print("\n[dim]Run a scenario: run <scenario_id>[/dim]")


def _run_scenario_by_id(scenario_id: str, agent: SentinelAgent):
    from sentinel.scenarios import get_scenario

    scenario = get_scenario(scenario_id)
    if not scenario:
        console.print(f"[red]Scenario '{scenario_id}' not found[/red]")
        return

    console.print()
    console.print(f"[bold]Running: {scenario.title}[/bold]")
    console.print(f"[dim]{scenario.mission}[/dim]")
    console.print()

    try:
        response = agent.run(scenario.mission, session_id=scenario.id)
        console.print(Panel(Markdown(response.content), title="Sentinel Response", border_style="blue"))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


def _print_summary(results: list[dict]):
    console.print()
    table = Table(title="Demo Results Summary")
    table.add_column("Scenario", style="cyan")
    table.add_column("Tools Used")
    table.add_column("Score", justify="right")
    table.add_column("Status")

    for r in results:
        tools = ", ".join(t["tool"] for t in r.get("tools_used", []))
        eval_data = r.get("evaluation", {})
        score = f"{eval_data.get('overall_score', 'N/A'):.1f}/5.0" if eval_data else "N/A"
        status = "[green]Passed[/green]" if (eval_data and eval_data.get("overall_score", 0) >= 3.0) else "[yellow]Needs Review[/yellow]"

        table.add_row(r["title"], tools, score, status)

    console.print(table)


def main():
    cli()


if __name__ == "__main__":
    main()
