"""Admin commands for the CLI."""

import click
import httpx
from rich.console import Console
from rich.table import Table

console = Console()

@click.group(name="admin")
def admin_group():
    """Administrative commands (requires admin privileges)."""
    pass

@admin_group.command()
@click.pass_context
def stats(ctx):
    """Show system statistics."""
    config = ctx.obj["config"]

    if "access_token" not in config:
        click.echo("❌ Not logged in. Use 'conversational auth login' first.")
        return

    try:
        headers = {"Authorization": f"Bearer {config['access_token']}"}
        response = httpx.get(
            f"{config['api_url']}/admin/stats",
            headers=headers
        )

        if response.status_code == 200:
            stats = response.json()

            table = Table(title="System Statistics")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", justify="right")

            table.add_row("Total Users", str(stats.get("total_users", 0)))
            table.add_row("Active Conversations", str(stats.get("active_conversations", 0)))
            table.add_row("Total Messages", str(stats.get("total_messages", 0)))
            table.add_row("Total Memories", str(stats.get("total_memories", 0)))
            table.add_row("Active WebSocket Connections", str(stats.get("active_websocket_connections", 0)))

            console.print(table)
        elif response.status_code == 403:
            click.echo("❌ Admin privileges required")
        else:
            click.echo(f"❌ Failed to get stats: {response.text}")
    except Exception as e:
        click.echo(f"❌ Error: {e}")

@admin_group.command()
@click.option("--limit", default=10, help="Number of users to show")
@click.pass_context
def users(ctx, limit: int):
    """List system users (admin only)."""
    config = ctx.obj["config"]

    if "access_token" not in config:
        click.echo("❌ Not logged in. Use 'conversational auth login' first.")
        return

    try:
        headers = {"Authorization": f"Bearer {config['access_token']}"}
        response = httpx.get(
            f"{config['api_url']}/admin/users",
            headers=headers,
            params={"limit": limit}
        )

        if response.status_code == 200:
            users = response.json()["users"]

            table = Table(title="System Users")
            table.add_column("ID", style="cyan", no_wrap=True)
            table.add_column("Email", style="green")
            table.add_column("Username")
            table.add_column("Active", justify="center")
            table.add_column("Created", style="yellow")

            for user in users:
                table.add_row(
                    user["id"][:8] + "...",
                    user["email"],
                    user["username"],
                    "✅" if user["is_active"] else "❌",
                    user["created_at"][:10]
                )

            console.print(table)
        elif response.status_code == 403:
            click.echo("❌ Admin privileges required")
        else:
            click.echo(f"❌ Failed to list users: {response.text}")
    except Exception as e:
        click.echo(f"❌ Error: {e}")

@admin_group.command()
@click.option("--days", default=7, help="Number of days of history")
@click.pass_context
def analytics(ctx, days: int):
    """Show analytics dashboard."""
    config = ctx.obj["config"]

    if "access_token" not in config:
        click.echo("❌ Not logged in. Use 'conversational auth login' first.")
        return

    try:
        headers = {"Authorization": f"Bearer {config['access_token']}"}
        response = httpx.get(
            f"{config['api_url']}/analytics/dashboard",
            headers=headers,
            params={"time_range": "week" if days == 7 else "month"}
        )

        if response.status_code == 200:
            data = response.json()

            # Conversation metrics
            conv_metrics = data.get("conversation_metrics", {})
            table = Table(title="Conversation Metrics")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", justify="right")

            table.add_row("Total Conversations", str(conv_metrics.get("total_conversations", 0)))
            table.add_row("Active Conversations", str(conv_metrics.get("active_conversations", 0)))
            table.add_row("Avg Conversation Length", f"{conv_metrics.get('avg_conversation_length', 0):.1f}")
            table.add_row("Completion Rate", f"{conv_metrics.get('conversation_completion_rate', 0):.1%}")

            console.print(table)

            # Usage metrics
            usage = data.get("usage_metrics", {})
            table = Table(title="Usage Metrics")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", justify="right")

            table.add_row("Total Tokens", f"{usage.get('total_tokens', 0):,}")
            table.add_row("Total Cost", f"${usage.get('total_cost_cents', 0) / 100:.2f}")
            table.add_row("Avg Tokens/Conversation", f"{usage.get('avg_tokens_per_conversation', 0):.0f}")

            console.print(table)

            # Top tools
            if usage.get("top_tools"):
                table = Table(title="Top Tools Used")
                table.add_column("Tool", style="cyan")
                table.add_column("Usage Count", justify="right")

                for tool in usage.get("top_tools", [])[:5]:
                    table.add_row(tool["tool_name"], str(tool["usage_count"]))

                console.print(table)

        elif response.status_code == 403:
            click.echo("❌ Admin privileges required")
        else:
            click.echo(f"❌ Failed to get analytics: {response.text}")
    except Exception as e:
        click.echo(f"❌ Error: {e}")