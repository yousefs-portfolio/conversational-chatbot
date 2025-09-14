"""Configuration management for the CLI."""

import click
import json
from pathlib import Path
from typing import Dict, Any

@click.group(name="config")
def config_group():
    """Manage CLI configuration."""
    pass

def load_config() -> Dict[str, Any]:
    """Load configuration from file."""
    config_path = Path.home() / ".conversational" / "config.json"
    default_config = {
        "api_url": "http://localhost:8000/api/v1",
        "ws_url": "ws://localhost:8000/ws"
    }

    if config_path.exists():
        with open(config_path, "r") as f:
            file_config = json.load(f)
            default_config.update(file_config)

    return default_config

def save_config(config: Dict[str, Any]):
    """Save configuration to file."""
    config_path = Path.home() / ".conversational" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

@config_group.command()
@click.pass_context
def show(ctx):
    """Show current configuration."""
    config = ctx.obj["config"]

    click.echo("Current Configuration:")
    click.echo("-" * 40)

    # Hide sensitive values
    display_config = config.copy()
    if "access_token" in display_config:
        display_config["access_token"] = "***hidden***"

    for key, value in display_config.items():
        click.echo(f"  {key}: {value}")

@config_group.command()
@click.argument("key")
@click.argument("value")
@click.pass_context
def set(ctx, key: str, value: str):
    """Set a configuration value."""
    config = load_config()
    config[key] = value
    save_config(config)

    click.echo(f"✅ Configuration updated: {key} = {value}")

@config_group.command()
@click.argument("key")
@click.pass_context
def get(ctx, key: str):
    """Get a configuration value."""
    config = ctx.obj["config"]

    if key in config:
        # Hide sensitive values
        if key == "access_token":
            click.echo("***hidden***")
        else:
            click.echo(config[key])
    else:
        click.echo(f"❌ Configuration key '{key}' not found")

@config_group.command()
@click.option("--confirm", is_flag=True, help="Skip confirmation")
@click.pass_context
def reset(ctx, confirm: bool):
    """Reset configuration to defaults."""
    if not confirm:
        if not click.confirm("Are you sure you want to reset all configuration?"):
            click.echo("Cancelled.")
            return

    config_path = Path.home() / ".conversational" / "config.json"

    if config_path.exists():
        config_path.unlink()
        click.echo("✅ Configuration reset to defaults")
    else:
        click.echo("ℹ️ No configuration file found")

@config_group.command()
@click.option("--api-url", help="API base URL")
@click.option("--ws-url", help="WebSocket URL")
@click.pass_context
def init(ctx, api_url: str, ws_url: str):
    """Initialize configuration with custom settings."""
    config = load_config()

    if api_url:
        config["api_url"] = api_url
    if ws_url:
        config["ws_url"] = ws_url

    save_config(config)

    click.echo("✅ Configuration initialized:")
    click.echo(f"   API URL: {config['api_url']}")
    click.echo(f"   WebSocket URL: {config['ws_url']}")
    click.echo(f"   Config saved to: {Path.home() / '.conversational' / 'config.json'}")