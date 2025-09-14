"""Authentication commands for the CLI."""

import click
import httpx
from typing import Optional
from pathlib import Path
import json

@click.group(name="auth")
def auth_group():
    """Authentication and user management commands."""
    pass

@auth_group.command()
@click.option("--email", prompt=True, help="Email address")
@click.option("--password", prompt=True, hide_input=True, help="Password")
@click.option("--username", prompt=True, help="Username")
@click.option("--full-name", help="Full name (optional)")
@click.pass_context
def register(ctx, email: str, password: str, username: str, full_name: Optional[str]):
    """Register a new user account."""
    config = ctx.obj["config"]

    data = {
        "email": email,
        "password": password,
        "username": username,
    }
    if full_name:
        data["full_name"] = full_name

    try:
        response = httpx.post(
            f"{config['api_url']}/auth/register",
            json=data
        )

        if response.status_code == 201:
            result = response.json()
            click.echo(f"✅ User registered successfully!")
            click.echo(f"   User ID: {result['id']}")
            click.echo(f"   Email: {result['email']}")
        else:
            click.echo(f"❌ Registration failed: {response.text}")
    except Exception as e:
        click.echo(f"❌ Error: {e}")

@auth_group.command()
@click.option("--email", prompt=True, help="Email address")
@click.option("--password", prompt=True, hide_input=True, help="Password")
@click.pass_context
def login(ctx, email: str, password: str):
    """Login to your account."""
    config = ctx.obj["config"]

    try:
        response = httpx.post(
            f"{config['api_url']}/auth/login",
            json={"email": email, "password": password}
        )

        if response.status_code == 200:
            result = response.json()
            # Save token to config file
            config_path = Path.home() / ".conversational" / "config.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)

            config_data = {}
            if config_path.exists():
                with open(config_path, "r") as f:
                    config_data = json.load(f)

            config_data["access_token"] = result["access_token"]
            config_data["user_id"] = result["user"]["id"]
            config_data["email"] = result["user"]["email"]

            with open(config_path, "w") as f:
                json.dump(config_data, f, indent=2)

            click.echo(f"✅ Logged in successfully as {email}")
            click.echo(f"   Token saved to {config_path}")
        else:
            click.echo(f"❌ Login failed: {response.text}")
    except Exception as e:
        click.echo(f"❌ Error: {e}")

@auth_group.command()
@click.pass_context
def logout(ctx):
    """Logout from your account."""
    config_path = Path.home() / ".conversational" / "config.json"

    if config_path.exists():
        with open(config_path, "r") as f:
            config_data = json.load(f)

        # Remove auth tokens
        config_data.pop("access_token", None)
        config_data.pop("user_id", None)
        config_data.pop("email", None)

        with open(config_path, "w") as f:
            json.dump(config_data, f, indent=2)

        click.echo("✅ Logged out successfully")
    else:
        click.echo("ℹ️ Not logged in")

@auth_group.command()
@click.pass_context
def whoami(ctx):
    """Show current user information."""
    config = ctx.obj["config"]

    if "access_token" not in config:
        click.echo("❌ Not logged in. Use 'conversational auth login' to authenticate.")
        return

    try:
        headers = {"Authorization": f"Bearer {config['access_token']}"}
        response = httpx.get(
            f"{config['api_url']}/auth/me",
            headers=headers
        )

        if response.status_code == 200:
            user = response.json()
            click.echo(f"✅ Logged in as:")
            click.echo(f"   Email: {user['email']}")
            click.echo(f"   Username: {user['username']}")
            click.echo(f"   User ID: {user['id']}")
            if user.get('full_name'):
                click.echo(f"   Name: {user['full_name']}")
        else:
            click.echo(f"❌ Failed to get user info: {response.text}")
    except Exception as e:
        click.echo(f"❌ Error: {e}")