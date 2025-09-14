# Conversational AI CLI

Command-line interface for managing the Conversational AI system.

## Installation

```bash
cd cli
pip install -e .
```

## Configuration

Initialize the CLI configuration:

```bash
conversational config init --api-url http://localhost:8000/api/v1
```

## Authentication

Register a new account:
```bash
conversational auth register
```

Login to your account:
```bash
conversational auth login
```

Check current user:
```bash
conversational auth whoami
```

## Conversations

List conversations:
```bash
conversational conversation list
```

Create a new conversation:
```bash
conversational conversation create --title "My Chat" --model gpt-4o-mini
```

Start interactive chat:
```bash
conversational conversation chat <conversation-id>
```

View conversation history:
```bash
conversational conversation history <conversation-id>
```

## Admin Commands

Show system statistics (admin only):
```bash
conversational admin stats
```

View analytics dashboard:
```bash
conversational admin analytics --days 7
```

List system users:
```bash
conversational admin users --limit 10
```

## Configuration Management

Show current configuration:
```bash
conversational config show
```

Set configuration value:
```bash
conversational config set api_url http://api.example.com/v1
```

Reset configuration:
```bash
conversational config reset --confirm
```

## Service Status

Check service health:
```bash
conversational status --host localhost --port 8000
```

## Features

- **Authentication**: User registration, login, and session management
- **Conversations**: Create, list, and manage AI conversations
- **Interactive Chat**: Real-time chat with AI agents
- **Admin Tools**: System statistics and user management
- **Configuration**: Flexible configuration management
- **Rich Output**: Formatted tables and markdown rendering

## Environment Variables

You can also configure the CLI using environment variables:

- `CONVERSATIONAL_API_URL`: API base URL
- `CONVERSATIONAL_WS_URL`: WebSocket URL
- `CONVERSATIONAL_TOKEN`: Authentication token

## Development

Run the CLI in development mode:

```bash
python cli.py --help
```

## License

MIT