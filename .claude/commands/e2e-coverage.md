---
name: e2e-coverage
description: "Black-box E2E coverage for macOS apps. LLM drives exploration via MCP tools while a Python advisor algorithm ensures completeness. Input: app name + bundle ID + optional constraints. Output: state graph + flows + interactive HTML report. Triggers on: 'explore app', 'build state graph', 'generate E2E flows', 'coverage report', 'auto-explore'."
---

# E2E Coverage Skill — LLM + Algorithm Advisor

You (Claude) drive the exploration loop via MCP tools. A Python advisor script tracks what's been explored and tells you what to try next. This combines LLM intelligence (semantic understanding, smart inputs, error recovery) with algorithmic completeness (never miss an element).

## Input

User provides:
1. **App name** — macOS application to explore (e.g. "Calculator", "Microsoft Edge")
2. **Bundle ID** — the app's bundleId (e.g. "com.apple.calculator", "com.microsoft.edgemac")
3. **Feature scope** (optional) — which feature/area to explore (e.g. "Copilot", "Settings panel"). If omitted, explore the entire app.
4. **Test constraints** (optional) — max states/actions

## Output

```
e2e_output/
├── states/
│   ├── s_xxx.png        # screenshot per discovered state
│   └── s_xxx.json       # per-state detail (elements + ui_tree)
├── blacklist.json       # global element blacklist (substring matching)
├── shortcuts_raw.json   # raw shortcuts discovered during exploration (auto + manual)
├── crawler_state.json   # exploration progress (lightweight, resumable)
├── utg.json             # final state transition graph (lightweight summary)
├── flows.json           # LLM-designed test flows
└── report.html          # interactive report
```

---

## Prerequisites

1. Appium Server running at `http://127.0.0.1:4723`
2. MCP server `auto-genesis-appium-mac` configured in `.mcp.json`
3. `uv` installed (manages Python deps via `e2e-coverage/pyproject.toml`)
4. Target app installed on this machine

---

## Key Rules

**MCP `page_source_file` parameter:** Every MCP tool call that accepts `page_source_file` (including `app_launch`, `click_element`, `press_key`, `get_page_source_tree`, `right_click_element`, `tap_coordinates`, `send_keys_on_macos`, `drag_element_to_element`, `find_element`, `time_sleep`, etc.) MUST pass `page_source_file=<absolute_path_to>/e2e_output/page_source_tmp.xml`. This saves the XML to disk and keeps your context clean. When you need to read the UI content (e.g., scope decisions, navigation checks), use the `Read` tool on the saved file.

**MCP `summary_only` parameter:** Most MCP action tools accept `summary_only=true`, which returns an agent-friendly summary instead of the full page source. Use this when you only need a quick status check (e.g., confirming navigation succeeded) and don't need the full XML for the advisor. When `summary_only=true`, `page_source_file` is still written if provided.

**Follow the advisor faithfully:** The advisor algorithm tracks exploration completeness. Always explore elements in the exact order the advisor provides. Do NOT skip elements, re-order, or try to "optimize" the exploration. Execute each element, record the result, and move on. The advisor handles prioritization — trust it.

---

## Execution Flow

### Phase 0: Feature Scoping (LLM — only if user specified a feature scope)

If the user specified a feature scope (e.g. "Copilot功能"), you must navigate to it before starting algorithmic exploration.

1. **Launch the app** via MCP `app_launch`
2. **Navigate to the feature**: identify the entry point from the page_source (returned by MCP tools) and click it to reach the feature's main UI state. This state becomes the starting point for the advisor.
3. **Persist the exploration context** to survive context compression:
   ```
   Write to e2e_output/exploration_context.txt:
   App: <app_name>
   Feature: <user's feature description in original language>
   Scope: <brief description of what's in/out of scope>
   Entry points: <list of entry point elements you identified>
   Navigation shortcuts: <list of shortcuts used to reach the feature, e.g. "⌘Y opens History panel">
   ```

If no feature scope is specified, skip this phase — explore the entire app starting from the initial state. Still write `exploration_context.txt` with just the app name.

### Phase 1: Explore App (LLM Main Loop + Algorithm Advisor)

**CRITICAL: The entire Phase 1 exploration loop must be executed by the main LLM directly. Do NOT delegate exploration to a sub-agent.** Sub-agents lack the full skill context and invariably take shortcuts (skipping elements instead of executing them, making incorrect scope judgments). The only place a sub-agent is used is Phase 1.5 (Evaluator).

The advisor is a Python script that maintains exploration state. You call it at checkpoints.

**Advisor CLI reference:**
```bash
ADVISOR="uv run --project e2e-coverage python3 e2e-coverage/scripts/advisor.py"
```

#### Step 1: Update Appium Config

Read `e2e-coverage/conf/appium_mac.json` and set `bundleId` to the user's value.

#### Step 2: Launch App + Initialize (or Resume)

**Check for existing state first:**
```bash
$ADVISOR status --output-dir e2e_output
```

- If this returns valid status (not error), **resume** — skip to Step 3. Launch the app via MCP `app_launch` before continuing.
- If no state exists, **start fresh**:

1. Call MCP tool `app_launch` with `caller=e2e-coverage`, `scenario=exploration`, `page_source_file=e2e_output/page_source_tmp.xml` (absolute path) — this launches the app and saves the initial page_source XML in one call
2. Call advisor to initialize:
```bash
$ADVISOR init --page-source e2e_output/page_source_tmp.xml --app-name "<app_name>" --output-dir e2e_output
```
3. Read the JSON output — it contains `start_state`, `interactive_elements`. The advisor also creates `states/<state_id>.json` with full element details + ui_tree.
4. Take a screenshot: call MCP `take_screenshot` with `save_path=e2e_output/states/<state_id>.png`
5. **Blacklist non-target elements** (only if feature scope is set): add elements that are clearly outside the target feature scope to the global blacklist. The blacklist uses **substring matching**, applies to **all states** automatically, and filters out **all action types** for matched elements.
   ```bash
   $ADVISOR blacklist --output-dir e2e_output --labels "Address and search bar,Copilot,Profile,Chat"
   ```
   - Only blacklist elements whose identity is unambiguously outside the feature scope. When in doubt, leave it in.
   - Substring matching means "Copilot" will match both "Copilot menu" and "Chat with Copilot".
   - Stored in `blacklist.json`, persists across explorations.

#### Step 3: Exploration Loop

Repeat until advisor returns `{"status": "done"}`:

**3a. Ask advisor what to explore:**
```bash
$ADVISOR next --output-dir e2e_output --max-actions <N> --max-states <N>
```

The response contains:
```json
{
  "status": "continue",
  "target_state": "s_abc123",
  "target_hash": "abc123def456",
  "navigate_path": [...],
  "elements": [
    {
      "label": "Settings",
      "type": "XCUIElementTypeButton",
      "action_type": "CLICK",
      "effective_key": "Settings",
      "x": 100, "y": 200, "width": 80, "height": 30
    },
    {
      "label": "Search",
      "type": "XCUIElementTypeTextField",
      "action_type": "TYPE",
      "effective_key": "Search",
      ...
    }
  ]
}
```

If `status` is `"done"`, go to **Phase 1.5** (Validate Exploration).

**3b. Navigate to target state (if not already there):**

Every MCP action returns `page_source_summary` — use it to judge whether you're at the target state. If not, restore by reversing your previous actions (e.g. Escape to dismiss a dialog, click the toolbar button that opened a panel), or follow `navigate_path` from the advisor. App restart is a last resort.

**3c. For EACH element in the advisor's list:**

1. **Execute action** (remember: `page_source_file` is set on every MCP call per Key Rules):
   - `CLICK`: call MCP `click_element` with `locator_value=<label>`
   - `TYPE`: call MCP `click_element` first to focus, wait 0.5s, then call MCP `send_keys_on_macos` with `locator_value=<label>` and a **semantically appropriate text** based on the label (e.g. "john@example.com" for an email field, "hello world" for a search box — use your judgment)
   - `RIGHT_CLICK`: call MCP `right_click_element` with `locator_value=<label>`. You must always execute it and record the result — whether a context menu exists is something you discover by trying, not by guessing.
   - `DRAG`: use your judgment to pick a meaningful drag target. Call MCP `drag_element_to_element` with `source_xpath` and `target_xpath`. You must always execute it and record the result. If the drag has no visible effect, record it as `same_state`.
   - If `use_coordinates` is true: call MCP `tap_coordinates` with `x=tap_x`, `y=tap_y`

2. **Record with advisor:**
   ```bash
   $ADVISOR record --output-dir e2e_output \
     --from-state <target_state> \
     --action "<ACTION_TYPE>(<label>)" \
     --effective-key "<effective_key>" \
     --action-type <ACTION_TYPE> \
     --page-source e2e_output/page_source_tmp.xml \
     --label "<label>"
   ```
   If the element used coordinates, add: `--tap-x <x> --tap-y <y>`
   Always pass: `--max-depth <N>` (default 6, or user-specified)

3. **Read the advisor's response:**
   - `result: "new_state"` → **Boundary check (only if feature scope is set):** Judge whether this new state is still within the feature scope. Look at the page_source elements — does this look like part of the target feature, or did we navigate away to an unrelated area?
     - **In scope**: Take a screenshot: MCP `take_screenshot` with `save_path=e2e_output/states/<state_id>.png`. Log: "NEW state discovered: <state_id> (in scope)"
     - **Out of scope**: Re-record with `--out-of-scope` flag:
       ```bash
       $ADVISOR record --output-dir e2e_output \
         --from-state <target_state> --action "CLICK(<label>)" \
         --effective-key "<effective_key>" \
         --page-source e2e_output/page_source_tmp.xml \
         --label "<label>" --out-of-scope
       ```
       Log: "NEW state <state_id> — OUT OF SCOPE, will not explore further"
     - If `depth_limited` is true: the state exceeded max depth. Log: "NEW state <state_id> — depth limit reached (depth N), will not explore further". No re-record needed — advisor handles this automatically.
   - `result: "known_state"` → Log: "→ known state <state_id>"
   - `result: "same_state"` → Log: "→ no effect"

4. **Restore to target state** before trying the next element (same strategy as 3b). If restore fails after retries, record it:
     ```bash
     $ADVISOR restore-failure --output-dir e2e_output --target-state <state_id>
     ```
     Then break out of this element loop and go back to step 3a.

#### LLM Enhancement Points

As the executor, you can apply intelligence that a pure algorithm cannot:

1. **Smart text input**: When typing into fields, generate semantically relevant text based on the field label and context (e.g., URLs for URL fields, emails for email fields)
2. **Error recovery**: If an MCP action fails or returns unexpected results, try alternative approaches (different click strategies, escape sequences)
3. **Unexpected dialogs**: If you encounter alert dialogs, permission prompts, or login walls that aren't part of the expected exploration, handle them intelligently (dismiss, accept, etc.) and record the transitions
5. **Directive compliance**: If the advisor's response contains a `directive` field, you MUST follow it. This is a hard constraint from the algorithm, not a suggestion.

### Phase 1.5: Validate Exploration (Sub-agent Evaluator)

After Phase 1 completes (advisor returns `status: "done"`), launch an **Evaluator sub-agent** to review the exploration before proceeding to Phase 2.

#### Step 1: Launch Evaluator sub-agent

Use the Agent tool with the following prompt (substitute actual file paths):

```
You are a strict QA reviewer auditing an automated UI exploration.
Your job is to find elements that were wrongly skipped or states that were missed.

Read these files:
1. e2e_output/exploration_context.txt — the feature scope definition
2. e2e_output/crawler_state.json — exploration progress (lightweight, no element details)
3. e2e_output/states/s_*.json — per-state detail files (interactive_elements + ui_tree)

In crawler_state.json, pay attention to:
- "skipped_pairs": elements that were skipped with reasons (separate from explored_pairs)
- "transitions": check if any in-scope state has zero outgoing transitions
- "state_index": list of all discovered state IDs

For each state in state_index, read its detail file (e2e_output/states/<state_id>.json)
to see interactive_elements and ui_tree.

For each skipped element, evaluate:
- Does the skip reason clearly justify skipping given the feature scope?
- Is this element likely part of the target feature?

For each state with zero outgoing transitions:
- Is it in-scope? If yes, its elements should have been explored.

Your default stance: a skip is WRONG unless the reason clearly proves the element
is outside the feature scope.

Output a JSON object:
{
  "verdict": "re-explore" or "pass",
  "elements_to_explore": [
    {"state": "<state_id>", "key": "<element_key>", "reason": "why it should be explored"}
  ]
}
```

#### Step 2: Handle Evaluator results

If the Evaluator returns `verdict: "re-explore"`:
1. For each element in `elements_to_explore`, call:
   ```bash
   $ADVISOR unskip --output-dir e2e_output --state <state_id> --effective-key "<element_key>"
   ```
2. Re-run Phase 1's exploration loop (Step 3) — the advisor will now recommend these elements
3. After re-exploration, run Phase 1.5 again to confirm

If the Evaluator returns `verdict: "pass"`, proceed to Phase 1.75.

### Phase 1.75: Name States (Claude)

After exploration is validated, give every state a meaningful title by reviewing its screenshot and context.

For each state in `crawler_state.json`'s `state_titles`:

1. Read the state's screenshot (`e2e_output/states/s_xxx.png`) and its JSON (`e2e_output/states/s_xxx.json`)
2. Look at the transitions in `crawler_state.json` to understand how the user got to this state (what action triggered it, from which parent state)
3. Assign a descriptive title that captures **what the user sees on screen**

**Naming rules:**
- Describe the visible UI state, not the action. Use noun phrases.
- Be specific enough to distinguish similar states. Include key differentiators like "with dialog open", "after deletion", "search results shown".
- Can be longer than typical (5-10 words is fine). Good: "History Full Page with Context Menu on Entry", "Pinned Sidebar After Deleting Entry". Bad: "State after click".
- Each title MUST be unique across all states.
- For out-of-scope or artifact states, prefix with `[OOS]` or `[Artifact]`.

After naming, update `crawler_state.json`'s `state_titles` by running:

```bash
$ADVISOR rename-state --output-dir e2e_output --state <state_id> --title "<new title>"
```

#### Curate Shortcuts

After naming all states, review and curate shortcuts for the final UTG:

1. Read `e2e_output/shortcuts_raw.json` — this contains all shortcuts automatically discovered from element labels during exploration (e.g., buttons with `(⌘D)` in their label)
2. Also check `exploration_context.txt`'s `Navigation shortcuts` line — these are shortcuts you noted during Phase 0 (e.g., `⌘Y opens History panel`)
3. **Deduplicate** — remove duplicates (same shortcut key appearing from multiple states)
4. **Judge scope** — only keep shortcuts that are relevant to the explored feature. Remove shortcuts that belong to unrelated UI elements (e.g., a Favorites shortcut `⌘D` when exploring History)
5. Write the curated list into `e2e_output/utg.json`'s `shortcuts` array (the finalize step leaves this empty for you to fill)

Each shortcut entry format:
```json
{"shortcut": "⌘Y", "label": "Show All History", "type": "XCUIElementTypeMenuItem", "source": "exploration_context"}
```

Then proceed to Phase 2.

### Phase 2: Design Flows (Claude)

Once the advisor returns `status: "done"`:

1. Run finalize:
```bash
$ADVISOR finalize --output-dir e2e_output
```

2. Read `e2e_output/utg.json`. Design test flows that cover all transitions.

**Requirements:**
- Every transition edge MUST appear in at least one flow
- Each flow = complete end-to-end path through the graph
- Last step includes an assertion (expected outcome to verify)
- Only use states and transitions that exist in utg.json
- Each flow MUST have a `flow_path` field: a natural language arrow chain describing the user journey, e.g. "Open sidebar → Click new chat → Enter new chat page"
- No `description` field needed — `flow_path` replaces it
- **Shortcuts** (MUST do — do not skip):
  1. Read `utg.json`'s `shortcuts` array (curated in Phase 1.75). For each shortcut, find flow steps whose action targets the same element (match by label). Set `shortcut_alternative` to the shortcut key on those steps.
  2. After writing flows.json, verify: count how many non-null `shortcut_alternative` values exist. If zero and `utg.json` has shortcuts, you missed something — go back and fix.

**Write `e2e_output/flows.json`:**

```json
[
  {
    "id": "flow_001",
    "name": "Basic addition 1+1=2",
    "flow_path": "Initial screen → Press 1 → Press + → Press 1 → Press = → Display shows 2",
    "steps": [
      {"state": "s_init", "action": "CLICK(1)", "assertion": null, "shortcut_alternative": null},
      {"state": "s_after_1", "action": "CLICK(+)", "assertion": null, "shortcut_alternative": null},
      {"state": "s_after_plus", "action": "CLICK(1)", "assertion": null, "shortcut_alternative": null},
      {"state": "s_after_1_2", "action": "CLICK(=)", "assertion": null, "shortcut_alternative": null},
      {"state": "s_result", "action": null, "assertion": "display shows 2", "shortcut_alternative": null}
    ],
    "path": ["s_init", "s_after_1", "s_after_plus", "s_after_1_2", "s_result"],
    "edges": [["s_init","s_after_1"], ["s_after_1","s_after_plus"], ["s_after_plus","s_after_1_2"], ["s_after_1_2","s_result"]]
  }
]
```

### Phase 3: Generate Report

```bash
uv run --project e2e-coverage python3 e2e-coverage/scripts/report.py \
  --utg e2e_output/utg.json \
  --flows e2e_output/flows.json \
  --app-name "<app_name>" \
  -o e2e_output/report.html
```

---

## Scripts

| Script | Purpose |
|--------|---------|
| `e2e-coverage/scripts/advisor.py` | Stateless advisor — tracks exploration state, saves per-state detail files (states/s_xxx.json), recommends next targets |
| `e2e-coverage/scripts/normalize.py` | State fingerprinting — parses page_source XML, computes hash, builds ui_tree |
| `e2e-coverage/scripts/report.py` | Report generation — reads utg.json + flows.json, outputs HTML |

## Advisor CLI Reference

```
# Initialize with first page_source
advisor.py init --page-source <xml_file> --app-name <name> --output-dir <dir>

# Get next exploration target
advisor.py next --output-dir <dir> [--max-actions 500] [--max-states 50]

# Record action result (--out-of-scope: don't explore new state; --max-depth: depth limit)
advisor.py record --output-dir <dir> --from-state <id> --action <desc> \
  --effective-key <key> --action-type <CLICK|TYPE|RIGHT_CLICK|DRAG> \
  --page-source <xml_file> [--label <label>] \
  [--tap-x <x> --tap-y <y>] [--out-of-scope] [--max-depth 6]

# Add labels to global blacklist (substring matching, applies to all states)
advisor.py blacklist --output-dir <dir> --labels "label1,label2,label3"

# Record restore failure
advisor.py restore-failure --output-dir <dir> --target-state <id> [--max-failures 3]

# Check progress (for debugging, not used during normal exploration)
advisor.py status --output-dir <dir>

# Generate utg.json
advisor.py finalize --output-dir <dir>

# Rename a state's title (used in Phase 1.75)
advisor.py rename-state --output-dir <dir> --state <state_id> --title "<descriptive title>"
```
