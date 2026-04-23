---
name: bdd-gen
description: Generate BDD Gherkin test cases from e2e-coverage flows. Reads flows.json + state detail files (with ui_tree) and outputs .feature files.
---

# BDD Test Case Generator

Generate BDD Gherkin `.feature` files from the flows and state data produced by `/e2e-coverage`.

**Trigger**: User says "generate test cases", "生成测试用例", "bdd", "/bdd-gen", or wants to convert flows to Gherkin format.

## Input (read-only — do NOT modify these files)

| File | Purpose |
|------|---------|
| `e2e_output/flows.json` | Flow definitions (path, steps, assertions) |
| `e2e_output/utg.json` | State graph (app_name, start_state, state titles, shortcuts, transitions) |
| `e2e_output/states/s_xxx.json` | Per-state detail: `ui_tree` + `interactive_elements` |
| `e2e_output/exploration_context.txt` | App name, feature scope, entry points, navigation shortcuts |
| `e2e-coverage/kb/element_patterns.md` | UI element testing patterns knowledge base |

## Output

```
e2e_output/features/
├── _plan.json               # Intermediate plan (deleted after generation)
└── <feature_name>.feature    # Gherkin BDD test cases
```

---

## Phase 1: Macro Planning

**Goal:** Group flows by functionality and plan expansion strategy — WITHOUT reading state detail files.

### Step 1.1: Read High-Level Data

1. Read `e2e_output/utg.json` — get `app_name`, `start_state`, state titles, `shortcuts`, `transitions`
2. Read `e2e_output/flows.json` — get all flow definitions
3. Read `e2e_output/exploration_context.txt` — get entry points and navigation shortcuts for reaching `start_state` from app launch
4. Read `e2e-coverage/kb/element_patterns.md` — load the element testing patterns knowledge base

**DO NOT read any `e2e_output/states/*.json` files in this phase.**

### Step 1.2: Group Flows & Write Plan

Analyze all flows and group them by functional area, then write `e2e_output/features/_plan.json`:

```json
{
  "app_name": "<from utg.json>",
  "feature_name": "<inferred or user-specified>",
  "groups": [
    {
      "group_name": "Human-readable group name",
      "flow_ids": ["flow_001", "flow_003"],
      "state_ids": ["s_045d1069", "s_1471d4fa"],
      "design_notes": "Free-form notes for Phase 2. What expansion strategies apply? Which element patterns from the knowledge base might be triggered?"
    }
  ]
}
```

- `state_ids`: ALL unique state IDs from the `path` arrays of flows in this group
- `design_notes`: Your prompt-to-self for Phase 2. Consider: positive paths, state-dependent scenarios, keyboard shortcuts, uncovered elements, and which knowledge base patterns (SearchField, Toggle, Dialog, etc.) might apply based on flow actions and state context

---

## Phase 2: Group-by-Group Generation

**Goal:** For each group, read relevant state files and generate Gherkin scenarios.

### Step 2.0: Write Feature File Header

```gherkin
Feature: <feature_name>
  As a user of <app_name>
  I want to verify the core workflows
  So that I can ensure the application works correctly
```

### Step 2.1: Process ONE Group at a Time

**CRITICAL: Do NOT delegate scenario generation to sub-agents (Agent tool).** You MUST process each group yourself in the main conversation. The only acceptable use of the Agent tool during Phase 2 is for reading large state files in parallel — never for generating or writing scenarios. This is because sub-agents lose context on knowledge base pattern matching rules, leading to coverage gaps.

**You MUST process groups one at a time. For each group, complete ALL steps below and write the output to the feature file BEFORE moving to the next group. Do NOT plan or generate scenarios for multiple groups in a single step.**

For the current group:

1. **Read state files** for this group's `state_ids` — get `ui_tree` and `interactive_elements`

2. **KB Pattern Scan (MANDATORY)** — Before generating any scenarios, scan every state in this group and output a structured KB match report. This step is NOT optional — you MUST output this scan before proceeding to scenario generation.

   For each state in the group, scan `interactive_elements` and `ui_tree` against the knowledge base patterns:
   - **SearchField**: `type in (TextField, SearchField)` AND label matches search/filter/find/query/搜索/検索, or inside a container with "Search" in its label
   - **Toggle**: `type in (CheckBox, Switch)` OR button label matches Turn On/Off, Enable/Disable, Pin/Unpin, Mute/Unmute
   - **Dropdown**: `type in (PopUpButton, ComboBox, Select)`
   - **TextInput**: `type in (TextField, TextArea, SecureTextField)` AND does NOT match SearchField
   - **List**: `type in (Table, List, OutlineView)` or repeated similar child elements
   - **ContextMenu**: `type == MenuItem` or state reached via RIGHT_CLICK
   - **Dialog**: state has buttons with label matching Close/Cancel/OK/Save/Delete/Confirm/Done/Remove/Apply
   - **Tab**: `type in (Tab, SegmentedControl, TabGroup)`

   Output the scan in this exact format (include it in your response text):

   ```
   KB Pattern Scan — Group "<group_name>":
   ┌─────────────────┬──────────────────────┬──────────────┬─────────────────────────────────┐
   │ State           │ Element              │ KB Pattern   │ Required Test Patterns           │
   ├─────────────────┼──────────────────────┼──────────────┼─────────────────────────────────┤
   │ s_bd2359bd      │ TextField "Search"   │ SearchField  │ valid_query, no_results, clear   │
   │ s_bd2359bd      │ Tab "Open Tabs"      │ Tab          │ switch_each, back_and_forth      │
   │ (no more matches for this state)                                                        │
   │ s_ef86e7dd      │ (no KB matches)      │ —            │ —                               │
   └─────────────────┴──────────────────────┴──────────────┴─────────────────────────────────┘
   Uncovered elements (contextually relevant, no KB pattern, no flow coverage):
   - s_bd2359bd: Button "Organize Tabs" — not covered by any flow in this group
   ```

   If a state has NO KB pattern matches and NO uncovered relevant elements, write `(no KB matches, no uncovered elements)`.

3. **Generate scenarios** using the flows, state data, AND the KB scan from step 2:

   **a) Positive path — with functional dedup**: Group flows by the functional action they test. Flows that perform the same action but differ only in precondition quantity (e.g., different item counts) are functionally equivalent — generate ONE scenario using the simplest precondition. Only generate separate scenarios when different preconditions cause **different behavior** (e.g., deleting the last item vs. deleting a non-last item).

   **b) State-dependent scenarios** — what if the precondition differs? (e.g., "add favorite" when already favorited); what if the action is repeated?

   **c) Keyboard shortcut scenarios** — if `utg.json` has `shortcuts` or a step has `shortcut_alternative`, generate a parallel scenario using the shortcut. Tag: `@shortcut`

   **d) KB-pattern-driven scenarios** — for every row in the KB scan table, generate scenarios for required test patterns that are **not already covered** by flow-based scenarios from step (a). If a flow scenario already exercises the same element with the same interaction pattern, that pattern is covered — do NOT generate a duplicate.

   **e) Uncovered element scenarios** — for each uncovered element listed in the KB scan (not generic browser chrome like Back, Refresh, Address bar), generate a scenario that exercises it based on the element's label and type.

4. **Write to file immediately** — append this group's scenarios to the `.feature` file using the Edit or Write tool NOW, before processing the next group. Use the group comment header:

```gherkin

  # ============================================================
  # Group Name (flows 001, 003)
  # ============================================================

  @P0 @happy
  Scenario: ...
```

**After writing this group's scenarios to the file, proceed to the next group. Do not go back to modify previous groups. Repeat steps 1-3 for each remaining group.**

---

## Phase 3: Finalize

1. Delete `e2e_output/features/_plan.json`
2. Regenerate the HTML report:

```bash
uv run --project e2e-coverage python3 e2e-coverage/scripts/report.py \
  --utg e2e_output/utg.json \
  --flows e2e_output/flows.json \
  --features e2e_output/features/ \
  --app-name "<app_name>" \
  -o e2e_output/report.html
```

3. **Reflection — knowledge base evolution (optional)**

Briefly reflect: were there element types in the states that the knowledge base did NOT cover, where you had to improvise test patterns? Did you discover a **generalizable** pattern (not app-specific)?

If yes: draft the proposed addition following the format in `element_patterns.md`, **ask the user for confirmation**, then append if approved.

Criteria for a valid knowledge base addition:
- Generalizable across apps (not "Edge's tab search should search by tab title")
- Non-obvious (experienced testers wouldn't naturally generate it without a hint)
- Not duplicating an existing pattern

---

## Tags & Priority

Every scenario MUST have both a priority tag and a category tag.

**Priority tags:**
- `@P0` — Core happy path. If it fails, the feature is broken.
- `@P1` — Important secondary: error handling, round-trip, negative cases, persistence. Feature works but has notable gaps.
- `@P2` — Edge cases, boundary, rare interactions. Feature works but may have rough edges.

**Category tags:**
- `@happy`, `@error`, `@boundary`, `@shortcut`, `@context-menu`, `@functional`

Tags are combinable: `@P0 @happy @shortcut`. Use priority guidance from the knowledge base when applicable.

---

## Gherkin Quality Rules

### Given (Precondition)

- **Every scenario starts with launching the app**: `Given I launch the Edge browser`
- **Reaching start_state**: Read `exploration_context.txt` for entry points. Convert them into explicit Given steps. NEVER write vague preconditions like `And the panel is open`.
- **Reaching states beyond start_state**: Use UTG transitions to find the **shortest path** (BFS) from start_state. Do NOT blindly follow the flow's path array.
- Chain all navigation actions as separate `And` steps.

### When/And (Actions)

- Read `ui_tree` to find element's container context
- If label is unique in the state: `When I click the "Pin favorites" button`
- If label appears multiple times, add container: `When I click the "More options" button in the Favorites toolbar`
- For TYPE actions, specify the text: `When I type "test query" in the "Search favorites" input field`

### Then (Assertions)

- Be specific and testable — no "should work correctly"
- Verify functional behavior, not UI styling
- End-to-end completeness: copy → verify by paste; save → verify file exists; toggle → verify effect persists

### Deduplication

Use semantic understanding to deduplicate, not just mechanical prefix matching. Before generating a scenario, ask: **"Does an existing scenario already test the same functional behavior through the same entry path?"**

Rules:
1. **Subsequence containment**: If scenario A's core action sequence is a subsequence of scenario B and both share the same entry path, keep only the more comprehensive one and merge unique assertions.
2. **Different entry paths — keep both**: If two scenarios test the same functional outcome but reach it via different navigation paths or entry points, keep BOTH. Different entry paths are valuable coverage.
3. **Lifecycle vs atomic — prefer atomic**: When a lifecycle flow (create → rename → use → cleanup) exists alongside individual atomic flows that each cover one step, **drop the lifecycle scenario** and keep the atomic ones. Each atomic scenario tests one clear behavior with focused assertions. Lifecycle scenarios dilute signal — if step 3 of 5 fails, it's unclear what broke.

---

## Examples

### Example 1 — Flow expansion with priority tags

Given this flow (exploration_context.txt says Entry point: `click "Compose" button in toolbar`):
```json
{
  "name": "Send email with attachment",
  "steps": [
    {"state": "s_compose", "action": "TYPE(To, recipient@example.com)", "assertion": null},
    {"state": "s_compose", "action": "CLICK(Attach file)", "assertion": null},
    {"state": "s_filepicker", "action": "CLICK(Select)", "assertion": null},
    {"state": "s_compose_attached", "action": "CLICK(Send)", "assertion": null},
    {"state": "s_inbox", "action": null, "assertion": "Email sent, returns to inbox"}
  ]
}
```

This ONE flow expands to MULTIPLE scenarios:

```gherkin
@P0 @happy
Scenario: Send email with a valid attachment
  Given I launch the Email app
  And I click the "Compose" button in the toolbar
  When I type "recipient@example.com" in the "To" input field
  And I click the "Attach file" button
  And I select "document.pdf" in the file picker
  And I click the "Select" button
  Then the compose window should show "document.pdf" as an attachment
  When I click the "Send" button
  Then the inbox should be displayed
  And the sent email should appear in the "Sent" folder with the attachment

@P1 @error
Scenario: Send email with invalid recipient address
  Given I launch the Email app
  And I click the "Compose" button in the toolbar
  When I type "not-an-email" in the "To" input field
  And I click the "Send" button
  Then an error message should indicate the recipient address is invalid

@P1 @happy
Scenario: Remove attachment before sending
  Given I launch the Email app
  And I click the "Compose" button in the toolbar
  When I click the "Attach file" button
  And I select "document.pdf" in the file picker
  And I click the "Select" button
  Then the compose window should show "document.pdf" as an attachment
  When I click the "Remove" button on the "document.pdf" attachment
  Then the attachment should be removed from the compose window
```

### Example 2 — Knowledge-base-driven: SearchField with no flow coverage

A state `s_bd2359bd` contains a `TextField` inside a `WebView` labeled "TabSearch", but NO flow has a TYPE action on it. The knowledge base's **SearchField** pattern matches. The state also shows open tabs titled "New Tab", "Settings", "History".

```gherkin
@P0 @happy
Scenario: Search tabs by keyword filters results to matching tabs
  Given I launch the Edge browser
  And I open three tabs: "New Tab", "Settings", "History"
  When I click the "Search tabs" button in the tab bar
  And I type "Settings" in the search field in the Search Tabs dropdown
  Then only the "Settings" tab should appear in the results list

@P1 @happy
Scenario: Search tabs with non-matching query shows no results
  Given I launch the Edge browser
  And I open two tabs
  When I click the "Search tabs" button in the tab bar
  And I type "zzz_nonexistent_xyz" in the search field in the Search Tabs dropdown
  Then the results list should show no matching tabs

@P1 @happy
Scenario: Clear search query restores full tab list
  Given I launch the Edge browser
  And I open three tabs
  When I click the "Search tabs" button in the tab bar
  And I type "Settings" in the search field
  Then filtered results should be displayed
  When I clear the search field
  Then all open tabs should be listed again
```

**Why this works:** The flow only covered `CLICK(Search tabs)` → dropdown opens. The knowledge base detected the SearchField and generated the real search scenarios that the flow missed.

### Example 3 — Bad scenario (what NOT to do)

```gherkin
@happy
Scenario: Test compose functionality
  Given the compose window is open
  When the user attaches a file
  And the user sends the email
  Then the email should be sent
```

Problems: no priority tag, vague precondition, third person, no concrete data, vague assertion.
