---
name: bdd-gen
description: Generate BDD Gherkin test cases from e2e-coverage flows. Reads flows.json + state detail files (with ui_tree) and outputs .feature files.
---

# BDD Test Case Generator

Generate BDD Gherkin `.feature` files from the flows and state data produced by `/e2e-coverage`.

**Trigger**: User says "generate test cases", "生成测试用例", "bdd", "/bdd-gen", or wants to convert flows to Gherkin format.

## Input

| File | Purpose |
|------|---------|
| `e2e_output/flows.json` | Flow definitions (path, steps, assertions) |
| `e2e_output/utg.json` | State graph overview (app_name, state titles) |
| `e2e_output/states/s_xxx.json` | Per-state detail: `ui_tree` (element hierarchy) + `interactive_elements` (flat list with coordinates) |

## Output

```
e2e_output/features/
└── <feature_name>.feature    # Gherkin BDD test cases
```

---

## Execution Flow

### Step 1: Read Data

1. Read `e2e_output/utg.json` — get `app_name`, `start_state`, and all state titles
2. Read `e2e_output/flows.json` — get all flow definitions
3. For each unique state ID referenced in flows, read `e2e_output/states/<state_id>.json` to get `ui_tree` and `interactive_elements`

### Step 2: Determine Feature Name

- If the user specified a feature name, use it
- Otherwise, infer from `app_name` + the flow content (e.g. "Edge Favorites")

### Step 3: Generate Gherkin Scenarios

For each flow in `flows.json`, apply **test case design techniques** to expand it into **multiple scenarios**. A single flow is NOT a single test case — it is a user journey that must be tested from multiple angles.

#### 3.1 Test Case Expansion Strategies

For each flow, generate scenarios using these strategies:

**Positive path (from the flow itself):**
- The happy path as described in the flow

**Negative / Error input:**
- For every input field (TYPE action) in the flow, generate at least one error scenario:
  - Invalid input (special characters, SQL injection strings, extremely long text)
  - Empty input (submit without entering anything)
- For every action that can fail, consider: what if the target element is missing or disabled?

**Boundary conditions:**
- For input fields: minimum length, maximum length, unicode/emoji, whitespace-only
- For search: query that returns no results, query that returns exactly one result
- For lists: empty list state, single item, many items

**State-dependent scenarios:**
- What if the precondition is different? (e.g., "add favorite" when the page is already favorited)
- What if the user repeats the action? (e.g., pin favorites twice)

**Keyboard shortcut scenarios:**
- If any step in the flow has a `shortcut_alternative` field (e.g., `"shortcut_alternative": "Command+D"`), generate an additional scenario that uses the keyboard shortcut instead of the UI click to perform that action
- The scenario should verify the same outcome as the original flow, but use `press "<shortcut>"` instead of `click`
- Example: if the flow clicks "Add This Page to Favorites..." and the step has `"shortcut_alternative": "Command+D"`, generate a scenario like:
  ```gherkin
  @happy
  Scenario: Add current page to favorites via keyboard shortcut
    Given the Favorites panel is open in Edge
    When I press "Command+D"
    Then a "Favorite Added" confirmation dialog should appear
  ```

**Example expansion for a "Search favorites" flow:**

The flow provides one path: enter search → exit search. But good test design expands to:
1. Search with a valid query that matches existing favorites
2. Search with a query that returns no results
3. Search with special characters (e.g., `<script>`, `' OR 1=1`)
4. Search with empty input (just press Enter)
5. Exit search and verify the full list is restored

#### 3.2 One Step = One Thing

Each Given/When/Then step must express exactly ONE action or ONE verification.

- NEVER: `Then a dialog should appear showing the page name and a folder selector` (two things)
- CORRECT:
  ```gherkin
  Then a "Favorite Added" confirmation dialog should appear
  And the dialog should show the current page name
  And the folder selector should default to "Favorites bar"
  ```

### Step 4: Write .feature File

Write all scenarios to `e2e_output/features/<feature_name>.feature`.

Use section comments in the .feature file to mark flow groups:
```gherkin
  # ============================================================
  # Group Name (flows 001, 028-032)
  # ============================================================
```

### Step 5: Group Flows and Update flows.json

After generating the .feature file:

1. For each flow in `flows.json`, assign a `group` field based on which section of the .feature file its scenarios belong to. The group name should match the comment headers in the .feature file.
2. Write the updated flows back to `e2e_output/flows.json` (preserving all existing fields, just adding `group`).

### Step 6: Regenerate Report

Regenerate the HTML report with the new `--features` flag to include test cases:

```bash
uv run --project e2e-coverage python3 e2e-coverage/scripts/report.py \
  --utg e2e_output/utg.json \
  --flows e2e_output/flows.json \
  --features e2e_output/features/ \
  --app-name "<app_name>" \
  -o e2e_output/report.html
```

The report will now show:
- Flow table with a "Group" column
- A "Test Cases" section with collapsible groups
- Each scenario with @happy/@error/@boundary tag badges
- Expandable Given/When/Then steps for each scenario

---

## Gherkin Generation Rules

### Structure

```gherkin
Feature: <feature_name>
  As a user of <app_name>
  I want to verify the core workflows
  So that I can ensure the application works correctly

  @<category>
  Scenario: <scenario name>
    Given <precondition based on start state>
    When <step 1 action>
    And <step 2 action>
    ...
    Then <verification 1>
    And <verification 2>
```

**Tags:**
- `@<category>`: one of `@happy`, `@error`, `@boundary` — based on what the scenario tests (NOT copied from flow.type — a happy flow can produce error/boundary scenarios through expansion)

### Given (Precondition)

- Derive from the **first state** in the flow's `path` array
- Use the state's `window_title` to describe the starting point
- Be specific: `Given the Favorites panel is open in Edge` not `Given the app is open`

### When/And (Action Steps)

For each step in `flow.steps` that has an `action`:

1. **Read the ui_tree** of the step's state to find the element's hierarchical context
2. Generate a precise action description using:
   - The element's `label` (from interactive_elements)
   - The element's **container context** from `ui_tree` (parent toolbar/panel/group)
   - An explicit action verb: `click`, `type`, `press`, `select`, `drag`

**Element precision rules:**
- If the label is unique in the state, use just the label: `When I click the "Pin favorites" button`
- If the label appears multiple times, add container context from ui_tree: `When I click the "More options" button in the Favorites toolbar`
- For TYPE actions, specify what to type: `When I type "test query" in the "Search favorites" input field`

### Then (Assertion)

- Convert the flow's last step `assertion` field into a testable Then statement
- Be specific about what to verify — no vague "should work correctly"
- Focus on functional behavior, not UI styling

### Content Quality Rules

These rules are adapted from the testCaseGenerator prompt and are critical for generating high-quality test cases:

1. **Use concrete actions, not vague statements**
   - Use `When I navigate to "https://bing.com"` instead of `When I open a webpage`
   - Use `Then the favorites list should show "GitHub", "Bing", "Microsoft"` instead of `Then the favorites should be sorted`

2. **Every step must be explicit — no pronouns or references**
   - NEVER: `Then the default save location should be correct` — specify the actual location
   - NEVER: `Then no changes should be made` — specify what to check
   - NEVER: `Then the deleted items should be restored` — specify which items
   - NEVER: `Then the sort order should be maintained` — specify the exact order

3. **One scenario = one focused functionality**
   - Do NOT combine multiple test goals into one scenario
   - If a flow tests "pin then unpin", that's one functionality (toggle behavior), keep it as one scenario

4. **One step = one thing**
   - Each Given/When/Then line must express exactly ONE action or ONE verification
   - NEVER combine two verifications in one Then line
   - NEVER: `Then the dialog should appear showing the name and the folder`
   - CORRECT: split into `Then the dialog should appear` + `And the dialog should show the name` + `And the folder selector should default to "Favorites bar"`

5. **Exclude UI style validations**
   - No: `Then the button should be highlighted`
   - No: `Then the icon should change`
   - Yes: `Then the favorites panel should be pinned as a sidebar`

5. **Ensure end-to-end completeness**
   - Copy to clipboard → must verify by pasting
   - Save/download → must verify file exists or content correct
   - Change setting → must verify it persists after reopen
   - Create/edit content → must verify changes are saved and displayed

6. **Maximize automation compatibility**
   - Use element labels that match the app's accessibility tree (these come from ui_tree)
   - Use clear action verbs: click, type, drag, select, press
   - Make verification steps objectively testable

## Examples

### Good Example — Expanding a flow into multiple scenarios

Given this flow:
```json
{
  "name": "Search favorites and exit search",
  "type": "happy",
  "steps": [
    {"state": "s_8b092bb2", "action": "CLICK(Search favorites)", "assertion": null},
    {"state": "s_53a4829e", "action": "TYPE(Search favorites, test)", "assertion": null},
    {"state": "s_53a4829e", "action": "CLICK(Exit search)", "assertion": null},
    {"state": "s_9e226d83", "action": null, "assertion": "Favorites panel returns to normal view"}
  ]
}
```

This ONE flow should expand to MULTIPLE scenarios:

```gherkin
@happy
Scenario: Search favorites with a matching keyword
  Given the Favorites panel is open in Edge
  When I click the "Search favorites" button in the Favorites toolbar
  And I type "GitHub" in the "Search favorites" input field
  Then the favorites list should show only items matching "GitHub"

@happy
Scenario: Exit search mode returns to full favorites list
  Given the Favorites panel is in search mode
  When I click the "Exit search" button
  Then the Favorites panel should show the full favorites list

@error
Scenario: Search favorites with special characters
  Given the Favorites panel is open in Edge
  When I click the "Search favorites" button in the Favorites toolbar
  And I type "<script>alert(1)</script>" in the "Search favorites" input field
  Then the search should complete without errors
  And no matching favorites should be found

@boundary
Scenario: Search favorites with no matching results
  Given the Favorites panel is open in Edge
  When I click the "Search favorites" button in the Favorites toolbar
  And I type "zzz_nonexistent_query" in the "Search favorites" input field
  Then the favorites list should show an empty state or "no results" message

@boundary
Scenario: Search favorites with empty input
  Given the Favorites panel is open in Edge
  When I click the "Search favorites" button in the Favorites toolbar
  And I type "" in the "Search favorites" input field
  Then the full favorites list should remain visible
```

**Why this is good:**
- One flow expands to 5 scenarios covering positive, error, and boundary cases
- Each scenario focuses on ONE test objective
- Each step does exactly ONE thing
- Element references include container context from ui_tree
- Assertions are specific and testable

### Bad Example

```gherkin
@happy @regression
Scenario: Test search functionality
  Given the user is on the favorites page
  When the user clicks search
  And the user exits search
  Then the page should return to normal
```

**Why this is bad:**
- One flow → one scenario (no test design expansion)
- Vague starting condition ("the user is on the favorites page")
- Third person ("the user") instead of first person
- No element context ("clicks search" — which search?)
- Vague assertion ("return to normal" — what does normal mean?)
- Missing error and boundary scenarios entirely
