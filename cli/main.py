"""
DAI CLI — Command-line interface for the Decision Authority Infrastructure.

Commands:
    dai verify   — Verify hash chain integrity over a time range
    dai query    — Query decision records with filters
    dai export   — Generate EU AI Act Article 19 compliance export
    dai status   — Check server connectivity and ledger health
    dai init     — Interactive setup wizard
"""

import asyncio
import csv
import io
import json
import os
import sys
from datetime import UTC, datetime

import httpx
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

app = typer.Typer(
    name="dai",
    help="Decision Authority Infrastructure — decision ledger CLI",
    add_completion=False,
)
console = Console()
err_console = Console(stderr=True)


def _get_client(endpoint: str | None, api_key: str | None) -> httpx.AsyncClient:
    ep = endpoint or os.environ.get("DAI_ENDPOINT", "http://localhost:8080")
    key = api_key or os.environ.get("DAI_API_KEY", "")
    return httpx.AsyncClient(
        base_url=ep,
        headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
        timeout=10.0,
    )


def _parse_dt(value: str) -> datetime:
    """Parse ISO8601 date or datetime string to UTC-aware datetime."""
    try:
        if "T" in value or " " in value:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(f"{value}T00:00:00+00:00")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except ValueError as exc:
        err_console.print(f"[red]Invalid datetime: {value!r}. Use ISO8601 format.[/red]")
        raise typer.Exit(1) from exc


# ── dai verify ────────────────────────────────────────────────────────────────


@app.command("verify")
def verify(
    from_: str = typer.Option(..., "--from", help="Start of period (ISO8601)"),
    to: str = typer.Option(..., "--to", help="End of period (ISO8601)"),
    agent: str | None = typer.Option(None, "--agent", help="Filter by agent_id"),
    type_: str | None = typer.Option(None, "--type", help="Filter by decision_type"),
    endpoint: str | None = typer.Option(None, "--endpoint", help="DAI server URL"),
    api_key: str | None = typer.Option(None, "--api-key", help="API key"),
) -> None:
    """Verify hash chain integrity over a time range. Exits 0=valid, 1=broken."""
    from_ts = _parse_dt(from_)
    to_ts = _parse_dt(to)

    async def _run() -> dict:
        async with _get_client(endpoint, api_key) as client:
            params: dict = {
                "from_timestamp": from_ts.isoformat(),
                "to_timestamp": to_ts.isoformat(),
            }
            if agent:
                params["agent_id"] = agent
            if type_:
                params["decision_type"] = type_
            resp = await client.get("/verify", params=params)
            resp.raise_for_status()
            return resp.json()

    try:
        with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as prog:
            prog.add_task("Verifying chain...", total=None)
            import time

            t0 = time.monotonic()
            result = asyncio.run(_run())
            elapsed = (time.monotonic() - t0) * 1000

        table = Table(title="Chain Verification Result", show_header=True)
        table.add_column("Field", style="bold")
        table.add_column("Value")
        table.add_row("Period", f"{from_} → {to}")
        table.add_row("Total records", str(result.get("total_records", 0)))

        if result.get("valid"):
            table.add_row("Status", "[bold green]✓ VERIFIED[/bold green]")
        else:
            broken = result.get("broken_at", "unknown")
            table.add_row("Status", f"[bold red]✗ BROKEN at {broken}[/bold red]")

        table.add_row("Time", f"{elapsed:.0f}ms")
        console.print(table)

        if not result.get("valid"):
            raise typer.Exit(1)

    except httpx.HTTPError as e:
        err_console.print(f"[red]Server error: {e}[/red]")
        raise typer.Exit(1) from e


# ── dai query ─────────────────────────────────────────────────────────────────


@app.command("query")
def query(
    agent: str | None = typer.Option(None, "--agent"),
    type_: str | None = typer.Option(None, "--type"),
    from_: str | None = typer.Option(None, "--from"),
    to: str | None = typer.Option(None, "--to"),
    outcome: str | None = typer.Option(None, "--outcome"),
    exception_only: bool = typer.Option(False, "--exception-only", is_flag=True),
    override_only: bool = typer.Option(False, "--override-only", is_flag=True),
    limit: int = typer.Option(20, "--limit"),
    format_: str = typer.Option("table", "--format", help="table | json | csv"),
    endpoint: str | None = typer.Option(None, "--endpoint"),
    api_key: str | None = typer.Option(None, "--api-key"),
) -> None:
    """Query decision records with optional filters."""

    async def _run() -> list:
        params: dict = {"limit": limit}
        if agent:
            params["agent_id"] = agent
        if type_:
            params["decision_type"] = type_
        if from_:
            params["from_timestamp"] = _parse_dt(from_).isoformat()
        if to:
            params["to_timestamp"] = _parse_dt(to).isoformat()
        if outcome:
            params["outcome"] = outcome
        if exception_only:
            params["exception_applied"] = "true"
        if override_only:
            params["override_applied"] = "true"

        async with _get_client(endpoint, api_key) as client:
            resp = await client.get("/decisions", params=params)
            resp.raise_for_status()
            return resp.json().get("records", [])

    try:
        records = asyncio.run(_run())

        if format_ == "json":
            console.print_json(json.dumps(records))
            return

        if format_ == "csv":
            if not records:
                console.print("No records found.")
                return
            fields = [
                "decision_id",
                "decision_timestamp",
                "agent_id",
                "decision_type",
                "outcome",
                "confidence",
                "exception_applied",
                "override_applied",
            ]
            writer_io = io.StringIO()
            writer = csv.DictWriter(writer_io, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(records)
            sys.stdout.write(writer_io.getvalue())
            return

        # Table output
        table = Table(title=f"Decision Records ({len(records)} results)")
        table.add_column("ID (short)", style="dim")
        table.add_column("Timestamp")
        table.add_column("Agent")
        table.add_column("Type")
        table.add_column("Outcome")
        table.add_column("Conf.")
        table.add_column("Exc.")
        table.add_column("OVR.")

        for r in records:
            exc_marker = "[yellow]✓[/yellow]" if r.get("exception_applied") else ""
            ovr_marker = "[blue]✓[/blue]" if r.get("override_applied") else ""
            outcome_val = r.get("outcome", "")
            outcome_styled = (
                f"[green]{outcome_val}[/green]"
                if outcome_val == "approved"
                else (f"[red]{outcome_val}[/red]" if outcome_val == "denied" else outcome_val)
            )
            table.add_row(
                r.get("decision_id", "")[:8] + "…",
                r.get("decision_timestamp", "")[:19],
                r.get("agent_id", ""),
                r.get("decision_type", ""),
                outcome_styled,
                f"{r.get('confidence', 0):.2f}",
                exc_marker,
                ovr_marker,
            )
        console.print(table)

    except httpx.HTTPError as e:
        err_console.print(f"[red]Server error: {e}[/red]")
        raise typer.Exit(1) from e


# ── dai export ────────────────────────────────────────────────────────────────


@app.command("export")
def export(
    from_: str = typer.Option(..., "--from"),
    to: str = typer.Option(..., "--to"),
    output: str | None = typer.Option(None, "--output", help="Output file path"),
    format_: str = typer.Option("json", "--format", help="json | text"),
    agent: str | None = typer.Option(None, "--agent"),
    type_: str | None = typer.Option(None, "--type"),
    endpoint: str | None = typer.Option(None, "--endpoint"),
    api_key: str | None = typer.Option(None, "--api-key"),
) -> None:
    """Generate an EU AI Act Article 19 compliance export."""
    from_ts = _parse_dt(from_)
    to_ts = _parse_dt(to)

    async def _run() -> str:
        body: dict = {
            "from_timestamp": from_ts.isoformat(),
            "to_timestamp": to_ts.isoformat(),
            "include_chain_proof": True,
        }
        if agent:
            body["agent_ids"] = [agent]
        if type_:
            body["decision_types"] = [type_]
        async with _get_client(endpoint, api_key) as client:
            resp = await client.post(
                "/export/article19",
                json=body,
                params={"format": format_},
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            return resp.text

    try:
        content = asyncio.run(_run())
        if output:
            with open(output, "w") as f:
                f.write(content)
            console.print(f"[green]Export written to {output}[/green]")
        else:
            sys.stdout.write(content)
            sys.stdout.write("\n")
    except httpx.HTTPError as e:
        err_console.print(f"[red]Server error: {e}[/red]")
        raise typer.Exit(1) from e


# ── dai status ────────────────────────────────────────────────────────────────


@app.command("status")
def status(
    endpoint: str | None = typer.Option(None, "--endpoint"),
    api_key: str | None = typer.Option(None, "--api-key"),
) -> None:
    """Check server connectivity and ledger health."""
    ep = endpoint or os.environ.get("DAI_ENDPOINT", "http://localhost:8080")

    async def _run() -> dict:
        async with _get_client(endpoint, api_key) as client:
            health = await client.get("/health")
            health.raise_for_status()
            latest = await client.get("/decisions/latest-hash")
            records = await client.get("/decisions", params={"limit": 1})
            return {
                "health": health.json(),
                "latest_hash": latest.json().get("hash", ""),
                "total": records.json().get("total", 0),
            }

    try:
        info = asyncio.run(_run())
        table = Table(title="DAI Server Status")
        table.add_column("Field", style="bold")
        table.add_column("Value")
        table.add_row("Server", ep)
        table.add_row("Status", "[green]✓ Connected[/green]")
        table.add_row("Version", info["health"].get("version", "?"))
        table.add_row("Latest hash", info["latest_hash"][:16] + "…" if info["latest_hash"] else "—")
        console.print(table)
    except httpx.HTTPError as e:
        table = Table(title="DAI Server Status")
        table.add_column("Field", style="bold")
        table.add_column("Value")
        table.add_row("Server", ep)
        table.add_row("Status", "[red]✗ Unreachable[/red]")
        console.print(table)
        raise typer.Exit(1) from e


# ── dai init ──────────────────────────────────────────────────────────────────


@app.command("init")
def init() -> None:
    """Interactive setup wizard — configure DAI and write .env file."""
    console.print("[bold]DAI Setup Wizard[/bold]")
    console.print("This will create a .env file in the current directory.\n")

    ep = typer.prompt("DAI server endpoint", default="http://localhost:8080")
    key = typer.prompt("API key", hide_input=True)

    # Test connection
    async def _test() -> bool:
        try:
            async with httpx.AsyncClient(base_url=ep, timeout=5.0) as client:
                resp = await client.get("/health")
                return resp.status_code == 200
        except Exception:
            return False

    console.print("Testing connection...", end=" ")
    ok = asyncio.run(_test())
    if ok:
        console.print("[green]✓ Connected[/green]")
    else:
        console.print("[yellow]⚠ Could not connect (server may not be running yet)[/yellow]")

    env_content = (
        f"DAI_ENDPOINT={ep}\nDAI_API_KEY={key}\nDAI_ENVIRONMENT=production\nDAI_LOG_LEVEL=INFO\n"
    )
    with open(".env", "w") as f:
        f.write(env_content)

    console.print("\n[green]✓ Written .env[/green]")
    console.print("\nNext steps:")
    console.print("  [bold]dai status[/bold]   — verify connection")
    console.print("  [bold]dai query[/bold]    — browse decision records")
    console.print("  [bold]dai verify --from 2025-01-01 --to 2026-12-31[/bold]   — verify chain")


if __name__ == "__main__":
    app()
