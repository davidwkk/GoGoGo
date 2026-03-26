# Hooks System

## Hook Types

- **PreToolUse**: Before tool execution (validation, parameter modification)
- **PostToolUse**: After tool execution (auto-format, checks)
- **Stop**: When session ends (final verification)

## Auto-Accept Permissions

Use with caution:

- Enable for trusted, well-defined plans
- Disable for exploratory work
- Never use dangerously-skip-permissions flag
- Configure `allowedTools` in `~/.claude.json` instead

## Team PostToolUse Hooks

Add this to your `~/.claude/settings.json` (user-level) or project's `.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "cd /home/davidwsl/projects/GoGoGo && uv run ruff check --fix && uv run ruff format",
            "timeout": 30,
            "statusMessage": "Running ruff check/format..."
          },
          {
            "type": "command",
            "command": "cd /home/davidwsl/projects/GoGoGo/frontend && npm run lint && npm run format",
            "timeout": 30,
            "statusMessage": "Running frontend lint/format..."
          },
          {
            "type": "command",
            "command": "cd /home/davidwsl/projects/GoGoGo && npx prettier --write --ignore-unknown .",
            "timeout": 30,
            "statusMessage": "Running prettier..."
          },
          {
            "type": "command",
            "command": "cd /home/davidwsl/projects/GoGoGo/backend && uv run pyright app/",
            "timeout": 60,
            "statusMessage": "Running pyright type check..."
          }
        ]
      }
    ]
  }
}
```

## TodoWrite Best Practices

Use TodoWrite tool to:

- Track progress on multi-step tasks
- Verify understanding of instructions
- Enable real-time steering
- Show granular implementation steps

Todo list reveals:

- Out of order steps
- Missing items
- Extra unnecessary items
- Wrong granularity
- Misinterpreted requirements
