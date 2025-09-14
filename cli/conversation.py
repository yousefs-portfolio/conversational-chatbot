"""Conversation management commands for the CLI."""

import click
import httpx
import asyncio
from typing import Optional
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
import json

console = Console()

@click.group(name="conversation")
def conversation_group():
    """Manage conversations and messages."""
    pass

@conversation_group.command(name="list")
@click.option("--limit", default=10, help="Number of conversations to show")
@click.pass_context
def list_conversations(ctx, limit: int):
    """List your conversations."""
    config = ctx.obj["config"]

    if "access_token" not in config:
        click.echo("❌ Not logged in. Use 'conversational auth login' first.")
        return

    try:
        headers = {"Authorization": f"Bearer {config['access_token']}"}
        response = httpx.get(
            f"{config['api_url']}/conversations",
            headers=headers,
            params={"limit": limit}
        )

        if response.status_code == 200:
            conversations = response.json()["conversations"]

            if not conversations:
                click.echo("No conversations found. Create one with 'conversational conversation create'")
                return

            table = Table(title="Your Conversations")
            table.add_column("ID", style="cyan", no_wrap=True)
            table.add_column("Title", style="green")
            table.add_column("Messages", justify="right")
            table.add_column("Created", style="yellow")

            for conv in conversations:
                table.add_row(
                    conv["id"][:8] + "...",
                    conv["title"],
                    str(conv.get("message_count", 0)),
                    conv["created_at"][:10]
                )

            console.print(table)
        else:
            click.echo(f"❌ Failed to list conversations: {response.text}")
    except Exception as e:
        click.echo(f"❌ Error: {e}")

@conversation_group.command()
@click.option("--title", prompt=True, help="Conversation title")
@click.option("--model", default="gpt-4o-mini", help="LLM model to use")
@click.option("--system-prompt", help="System prompt for the conversation")
@click.pass_context
def create(ctx, title: str, model: str, system_prompt: Optional[str]):
    """Create a new conversation."""
    config = ctx.obj["config"]

    if "access_token" not in config:
        click.echo("❌ Not logged in. Use 'conversational auth login' first.")
        return

    data = {
        "title": title,
        "model": model
    }
    if system_prompt:
        data["system_prompt"] = system_prompt

    try:
        headers = {"Authorization": f"Bearer {config['access_token']}"}
        response = httpx.post(
            f"{config['api_url']}/conversations",
            headers=headers,
            json=data
        )

        if response.status_code == 201:
            conv = response.json()
            click.echo(f"✅ Conversation created successfully!")
            click.echo(f"   ID: {conv['id']}")
            click.echo(f"   Title: {conv['title']}")
            click.echo(f"   Model: {conv['model']}")
        else:
            click.echo(f"❌ Failed to create conversation: {response.text}")
    except Exception as e:
        click.echo(f"❌ Error: {e}")

@conversation_group.command()
@click.argument("conversation_id")
@click.pass_context
def chat(ctx, conversation_id: str):
    """Interactive chat with a conversation."""
    config = ctx.obj["config"]

    if "access_token" not in config:
        click.echo("❌ Not logged in. Use 'conversational auth login' first.")
        return

    headers = {"Authorization": f"Bearer {config['access_token']}"}

    click.echo(f"Starting chat with conversation {conversation_id[:8]}...")
    click.echo("Type 'exit' or 'quit' to end the chat.")
    click.echo("-" * 50)

    while True:
        try:
            # Get user input
            message = click.prompt("You", type=str)

            if message.lower() in ["exit", "quit"]:
                click.echo("Ending chat session.")
                break

            # Send message
            response = httpx.post(
                f"{config['api_url']}/conversations/{conversation_id}/messages",
                headers=headers,
                json={"message": message, "use_tools": True, "use_memory": True}
            )

            if response.status_code == 200:
                result = response.json()
                # Display AI response
                click.echo(f"\nAI: {result['content']}\n")

                # Show tool usage if any
                if result.get("tool_calls"):
                    click.echo("🔧 Tools used:")
                    for tool in result["tool_calls"]:
                        click.echo(f"   - {tool['name']}: {tool.get('result', 'Processing...')}")
                    click.echo()
            else:
                click.echo(f"❌ Error: {response.text}")

        except KeyboardInterrupt:
            click.echo("\nEnding chat session.")
            break
        except Exception as e:
            click.echo(f"❌ Error: {e}")

@conversation_group.command()
@click.argument("conversation_id")
@click.option("--limit", default=20, help="Number of messages to show")
@click.pass_context
def history(ctx, conversation_id: str, limit: int):
    """Show conversation history."""
    config = ctx.obj["config"]

    if "access_token" not in config:
        click.echo("❌ Not logged in. Use 'conversational auth login' first.")
        return

    try:
        headers = {"Authorization": f"Bearer {config['access_token']}"}
        response = httpx.get(
            f"{config['api_url']}/conversations/{conversation_id}/messages",
            headers=headers,
            params={"limit": limit}
        )

        if response.status_code == 200:
            messages = response.json()["messages"]

            if not messages:
                click.echo("No messages in this conversation.")
                return

            for msg in messages:
                role = "You" if msg["role"] == "user" else "AI"
                click.echo(f"\n[{msg['created_at'][:19]}] {role}:")
                console.print(Markdown(msg["content"]))
        else:
            click.echo(f"❌ Failed to get history: {response.text}")
    except Exception as e:
        click.echo(f"❌ Error: {e}")

@conversation_group.command()
@click.argument("conversation_id")
@click.option("--confirm", is_flag=True, help="Skip confirmation")
@click.pass_context
def delete(ctx, conversation_id: str, confirm: bool):
    """Delete a conversation."""
    config = ctx.obj["config"]

    if "access_token" not in config:
        click.echo("❌ Not logged in. Use 'conversational auth login' first.")
        return

    if not confirm:
        if not click.confirm(f"Are you sure you want to delete conversation {conversation_id[:8]}?"):
            click.echo("Cancelled.")
            return

    try:
        headers = {"Authorization": f"Bearer {config['access_token']}"}
        response = httpx.delete(
            f"{config['api_url']}/conversations/{conversation_id}",
            headers=headers
        )

        if response.status_code == 204:
            click.echo(f"✅ Conversation deleted successfully")
        else:
            click.echo(f"❌ Failed to delete conversation: {response.text}")
    except Exception as e:
        click.echo(f"❌ Error: {e}")