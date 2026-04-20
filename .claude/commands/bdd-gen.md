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
├── _plan.json               # Intermediate plan (deleted after generation)
└── <feature_name>.feature    # Gherkin BDD test cases
```

---

## Execution Flow — Two-Phase Generation

The generation process is split into two phases to avoid overloading the LLM context with too much information at once. Phase 1 does macro planning without reading state detail files. Phase 2 generates scenarios group by group, reading only the state files relevant to each group.

### Phase 1: Macro Planning

**Goal:** Understand all flows at a high level, group them by functionality, and plan the test design strategy for each group — WITHOUT reading any state detail files.

**Input:** Only `utg.json` and `flows.json`.

#### Step 1.1: Read High-Level Data

1. Read `e2e_output/utg.json` — get `app_name`, `start_state`, all state titles (window_title), and `shortcuts`
2. Read `e2e_output/flows.json` — get all flow definitions

**DO NOT read any `e2e_output/states/*.json` files in this phase.** State titles from utg.json provide enough context for grouping.

#### Step 1.2: Group Flows by Functionality

Analyze all flows and group them by functional area. Use your judgment to determine the grouping — there are no fixed rules on group count or group size. Consider:

- Flows that test the same UI area or feature belong together
- Flows that share the same starting state or action pattern may belong together
- Context menu flows from different entry points can be grouped if the menu is the same
- A group should be cohesive enough that you can reason about test expansion strategies within it

#### Step 1.3: Write the Plan

Write `e2e_output/features/_plan.json` with this structure:

```json
{
  "app_name": "<from utg.json>",
  "feature_name": "<inferred or user-specified>",
  "groups": [
    {
      "group_name": "Human-readable group name",
      "flow_ids": ["flow_001", "flow_003"],
      "state_ids": ["s_045d1069", "s_1471d4fa", "s_6039215b"],
      "design_notes": "Free-form notes on what test expansion strategies apply to this group. E.g.: 'Search flow needs error/boundary expansion for input field. The exit-search flow is a simple positive path.'"
    }
  ]
}
```

- `state_ids`: Collect ALL unique state IDs from the `path` arrays of the flows in this group. These are the states whose detail files will be read in Phase 2.
- `design_notes`: Your reasoning about what types of scenarios to generate for this group. This serves as a prompt-to-self for Phase 2. Consider which test design techniques apply (positive, negative, boundary, state-dependent, shortcut, context-menu) based on the flow actions and assertions.

#### Step 1.4: Update flows.json

Add a `group` field to each flow in `flows.json` matching the `group_name` from the plan. Preserve all existing fields.

---

### Phase 2: Group-by-Group Generation

**Goal:** For each group in `_plan.json`, read only the relevant state files and generate high-quality Gherkin scenarios.

#### Step 2.0: Initialize Feature File

Write the feature file header:

```gherkin
Feature: <feature_name>
  As a user of <app_name>
  I want to verify the core workflows
  So that I can ensure the application works correctly
```

#### Step 2.1: Iterate Over Groups

For each group in `_plan.json["groups"]`, sequentially:

1. **Read state files:** For each state_id in the group's `state_ids`, read `e2e_output/states/<state_id>.json` to get `ui_tree` and `interactive_elements`
2. **Re-read the flows** for this group from `flows.json` (just the flows matching `flow_ids`)
3. **Review the design_notes** from the plan to recall the intended test strategy
4. **Generate scenarios** for this group, applying the test case expansion strategies (see "Test Case Expansion Strategies" below)
5. **Append** the generated scenarios to the `.feature` file, preceded by a group comment header:

```gherkin

  # ============================================================
  # Group Name (flows 001, 003)
  # ============================================================

  @happy
  Scenario: ...
```

**IMPORTANT:** After finishing each group, move on to the next group. Do not go back and modify previously generated groups. Each group is self-contained.

---

### Phase 3: Finalize

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

---

## Test Case Expansion Strategies

For each flow, apply **test case design techniques** to expand it into **multiple scenarios**. A single flow is NOT a single test case — it is a user journey that must be tested from multiple angles. Use your judgment to decide which strategies apply and how many scenarios to generate — there is no fixed number.

### Positive path (from the flow itself)
- The happy path as described in the flow

### Negative / Error input
- For every input field (TYPE action) in the flow, consider error scenarios:
  - Invalid input (special characters, SQL injection strings, extremely long text)
  - Empty input (submit without entering anything)
- For every action that can fail, consider: what if the target element is missing or disabled?

### Boundary conditions
- For input fields: minimum length, maximum length, unicode/emoji, whitespace-only
- For search: query that returns no results, query that returns exactly one result
- For lists: empty list state, single item, many items

### State-dependent scenarios
- What if the precondition is different? (e.g., "add favorite" when the page is already favorited)
- What if the user repeats the action? (e.g., pin favorites twice)

### Keyboard shortcut scenarios
- If `utg.json` has a `shortcuts` array, or any step in the flow has a `shortcut_alternative` field, generate an additional scenario that uses the keyboard shortcut instead of the UI click
- The scenario should verify the same outcome but use `press "<shortcut>"` instead of `click`
- Tag: `@shortcut`

### Uncovered interactive elements in explored states
- For every state that appears in the group's flows, read its `interactive_elements` list
- Identify **all actionable elements** (buttons, menu items, checkboxes, dropdowns) that are contextually relevant to the state's purpose (ignore generic browser chrome like Back, Refresh, Address bar)
- Cross-reference with the flows: if an element exists in the state but NO flow clicks/interacts with it, generate a scenario that exercises that element
- Example: a dialog has "Cancel" and "Delete" buttons, but flows only cover "Cancel" → generate a scenario that clicks "Delete" and verifies the expected outcome
- Example: a menu has 4 items but flows only cover 3 → generate a scenario for the missing menu item
- For dialogs with multiple options (checkboxes, dropdowns), generate scenarios that exercise different combinations
- Tag: same as the parent flow's tag (e.g., `@happy` for a missing happy-path action)

### Right-click context menu scenarios
- If a flow contains a `RIGHT_CLICK` action that leads to a context menu state, read the target state's `interactive_elements` to find all `MenuItem` elements in the menu
- Generate a **separate scenario for each menu item**: right-click to open the menu, then click the menu item, and verify a reasonable outcome based on the menu item's label
- Tag: `@context-menu`

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
- `@happy`, `@error`, `@boundary` — based on what the scenario tests
- `@shortcut` — scenario uses keyboard shortcut instead of UI click
- `@context-menu` — scenario tests a right-click context menu item

Tags are combinable: a shortcut scenario is also `@happy`, so use `@happy @shortcut`.

### Given (Precondition)

- **Every scenario MUST start with launching the app**: `Given I launch the Edge browser`
- **Every precondition MUST be expressed as explicit, reproducible steps — NEVER as abstract state descriptions.** The tester must know exactly how to reach the starting state.
- Use the UTG transitions to derive the navigation path from `start_state` to the flow's first state. Write each navigation action as a separate `And` step.
- **NEVER** write vague preconditions like `And the Favorites panel is open` or `And the History full page is open`. Instead, write the exact actions:
  ```gherkin
  # BAD — abstract, tester doesn't know how to get there
  Given I launch the Edge browser
  And the Favorites panel is open

  # GOOD — explicit steps to reach the state
  Given I launch the Edge browser
  And I press "Ctrl+H" to open the History sidebar
  ```
  ```gherkin
  # BAD
  Given I launch the Edge browser
  And the History full page is open at "edge://history"

  # GOOD
  Given I launch the Edge browser
  And I press "Command+Y" to open the History full page
  ```
- If a scenario's precondition requires multiple navigations (e.g., reaching a pinned sidebar state), chain all the steps:
  ```gherkin
  Given I launch the Edge browser
  And I press "Ctrl+H" to open the History sidebar
  And I click the "Pin history" button in the History sidebar toolbar
  ```

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

6. **Ensure end-to-end completeness**
   - Copy to clipboard → must verify by pasting
   - Save/download → must verify file exists or content correct
   - Change setting → must verify it persists after reopen
   - Create/edit content → must verify changes are saved and displayed

7. **Maximize automation compatibility**
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
  Given I launch the Edge browser
  And the Favorites panel is open
  When I click the "Search favorites" button in the Favorites toolbar
  And I type "GitHub" in the "Search favorites" input field
  Then the favorites list should show only items matching "GitHub"

@happy
Scenario: Exit search mode returns to full favorites list
  Given I launch the Edge browser
  And the Favorites panel is in search mode
  When I click the "Exit search" button
  Then the Favorites panel should show the full favorites list

@error
Scenario: Search favorites with special characters
  Given I launch the Edge browser
  And the Favorites panel is open
  When I click the "Search favorites" button in the Favorites toolbar
  And I type "<script>alert(1)</script>" in the "Search favorites" input field
  Then the search should complete without errors
  And no matching favorites should be found

@boundary
Scenario: Search favorites with no matching results
  Given I launch the Edge browser
  And the Favorites panel is open
  When I click the "Search favorites" button in the Favorites toolbar
  And I type "zzz_nonexistent_query" in the "Search favorites" input field
  Then the favorites list should show an empty state or "no results" message

@boundary
Scenario: Search favorites with empty input
  Given I launch the Edge browser
  And the Favorites panel is open
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
