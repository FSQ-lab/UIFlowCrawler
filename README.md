# UIFlowCrawler

LLM-driven black-box E2E coverage tool for macOS applications. An AI agent explores the app's UI states via Appium MCP tools while a Python advisor algorithm ensures completeness — then generates BDD Gherkin test cases from the discovered flows.

## Architecture

```
Claude Code (LLM)          Python Advisor
     │                          │
     ├── MCP tools ──► App      │
     │   (click, type, etc.)    │
     │                          │
     ├── advisor init/next ────►│  tracks states,
     ├── advisor record ───────►│  recommends targets,
     ├── advisor finalize ─────►│  computes coverage
     │                          │
     ▼                          ▼
  flows.json              utg.json + states/
     │
     ▼
  BDD .feature files + HTML report
```

## Components

| Path | Purpose |
|------|---------|
| `e2e-coverage/scripts/advisor.py` | Stateful exploration advisor — tracks coverage, recommends next targets |
| `e2e-coverage/scripts/normalize.py` | State fingerprinting — parses page source XML, computes hash, builds UI tree |
| `e2e-coverage/scripts/report.py` | Interactive HTML report generator (state graph + flows + test cases) |
| `.claude/commands/e2e-coverage.md` | Claude Code skill: drives the exploration loop |
| `.claude/commands/bdd-gen.md` | Claude Code skill: generates BDD Gherkin test cases from flows |

## Prerequisites

- macOS
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI
- [Appium](https://appium.io/) server running at `http://127.0.0.1:4723`
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- An MCP server for Appium (e.g. [AutoGenesis appium-mcp-server](https://github.com/anthropics/AutoGenesis))

## Quick Start

### 1. Configure MCP server

Create `.mcp.json` in the project root pointing to your Appium MCP server:

```json
{
  "mcpServers": {
    "auto-genesis-appium-mac": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "run", "--project", "<path-to-appium-mcp-server>",
        "python", "<path-to-appium-mcp-server>/simple_server.py",
        "--platform", "mac", "--transport", "stdio",
        "--config", "e2e-coverage/conf/appium_mac.json"
      ]
    }
  }
}
```

### 2. Set the target app

Edit `e2e-coverage/conf/appium_mac.json` and set the `bundleId` to your target app.

### 3. Run exploration

In Claude Code, use the `/e2e-coverage` command:

```
/e2e-coverage
> Explore the Favorites feature of Microsoft Edge (com.microsoft.edgemac)
```

The LLM will:
1. Launch the app via Appium
2. Explore UI states guided by the advisor algorithm
3. Generate a state transition graph (`utg.json`)
4. Design test flows covering all transitions (`flows.json`)
5. Produce an interactive HTML report (`report.html`)

### 4. Generate BDD test cases

```
/bdd-gen
```

This reads the flows and state data to generate Gherkin `.feature` files with expanded test scenarios (happy path, error, boundary), then updates the report.

## Output

All output goes to `e2e_output/`:

```
e2e_output/
├── states/           # Per-state screenshots + element data
├── utg.json          # State transition graph
├── flows.json        # LLM-designed test flows (with groups)
├── features/         # BDD Gherkin .feature files
└── report.html       # Interactive HTML report
```

## Report Features

- **State graph** — interactive SVG with hover tooltips and flow highlighting
- **Test cases** — collapsible groups with @happy/@error/@boundary badges, expandable steps
- **Flows** — grouped by feature area, click to highlight path on the graph
- **Summary** — state/transition/flow/test case counts at a glance

## License

MIT
