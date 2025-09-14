#!/usr/bin/env python3
"""Main CLI entry point for Conversational AI system."""

import click
import asyncio
from typing import Optional
from pathlib import Path

from auth import auth_group
from conversation import conversation_group
from admin import admin_group
from config import config_group

@click.group()
@click.version_option(version="1.0.0", prog_name="conversational")
@click.pass_context
def cli(ctx):
    """Conversational AI CLI - Manage your AI conversations from the terminal."""
    ctx.ensure_object(dict)
    # Load configuration
    from config import load_config
    ctx.obj["config"] = load_config()

# Register command groups
cli.add_command(auth_group)
cli.add_command(conversation_group)
cli.add_command(admin_group)
cli.add_command(config_group)

@cli.command()
@click.option("--host", default="localhost", help="API host")
@click.option("--port", default=8000, help="API port")
def status(host: str, port: int):
    """Check the status of the Conversational AI service."""
    import httpx

    try:
        response = httpx.get(f"http://{host}:{port}/health")
        if response.status_code == 200:
            data = response.json()
            click.echo(f"✅ Service is {data['status']}")
            click.echo(f"   Database: {data['database']}")
            click.echo(f"   Version: {data['version']}")
        else:
            click.echo(f"❌ Service returned status code: {response.status_code}")
    except Exception as e:
        click.echo(f"❌ Could not connect to service: {e}")

def main():
    """Main entry point."""
    cli(obj={})

if __name__ == "__main__":
    main()