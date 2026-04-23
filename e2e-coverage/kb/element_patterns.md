# UI Element Testing Patterns Knowledge Base

Common UI element types and the test scenarios they imply. When generating BDD scenarios, if a state contains these element types, the corresponding test patterns SHOULD be applied — even if the original flow did not exercise them.

This file evolves over time via post-generation reflection.

---

## SearchField / FilterInput

**How to identify**: `TextField` or `SearchField` in state, with label containing search/filter/find/query/搜索/検索/検索用語, or located inside a container with "Search" in its label (e.g., WebView "TabSearch").

**Test patterns**:
- **Valid query with results**: type a keyword that matches known content (use tab titles, page names, or element labels visible in the state) → verify the results list filters correctly and shows matching items
- **Query with no results**: type a query that won't match anything (e.g., "zzz_nonexistent_xyz") → verify an empty state or "no results" message appears
- **Clear search / restore full list**: type a query → clear the input → verify the full unfiltered list is restored
- **Partial match**: type only the first few characters of a known item → verify it appears in results
- **Special characters**: type `<script>alert(1)</script>` or `'; DROP TABLE` → verify no crash, results are empty or safe
- **Empty submit**: focus the search field and press Enter without typing → verify no crash, list unchanged or shows all

**Priority guidance**: valid-query-with-results is P0; no-results is P1; the rest are P2.

---

## Toggle / Switch

**How to identify**: `CheckBox`, `Switch`, or `Toggle` elements; also buttons with labels like "Turn On/Off", "Enable/Disable", "Pin/Unpin", "Mute/Unmute".

**Test patterns**:
- **Toggle on → verify functional effect**: don't just check the control's visual state; verify the feature is actually enabled (e.g., "Turn On Vertical Tabs" → tabs actually move to sidebar)
- **Toggle off → verify reverse**: toggle back and verify the feature is disabled / state is restored
- **Round-trip**: on → off → verify return to original state with no side effects
- **Persistence**: toggle on → close and reopen the app/panel → verify the setting persists

**Priority guidance**: toggle-on-functional-effect is P0; round-trip is P1; persistence is P1.

---

## Dropdown / ComboBox / PopUpButton

**How to identify**: `PopUpButton`, `ComboBox`, `Select`, or any element that opens a list of selectable options.

**Test patterns**:
- **Each option produces its expected effect**: at minimum, generate one scenario per option that verifies the functional outcome (not just that the dropdown label changed)
- **Default selection**: verify what option is selected by default on first open
- **Switch between options**: select option A → verify effect → select option B → verify effect changes

**Priority guidance**: each-option-effect is P0 for primary options; default-selection is P2.

---

## Text Input / Form Field

**How to identify**: `TextField`, `TextArea`, `SecureTextField`, or input elements that accept free-form user text (not search — those are covered above).

**Test patterns**:
- **Valid input**: enter expected content → submit → verify saved/applied correctly
- **Empty input**: submit without entering anything → verify error message or default behavior
- **Boundary length**: very long input (200+ chars) → verify truncation or acceptance
- **Unicode / emoji**: enter emoji or CJK characters → verify correct display
- **Whitespace-only**: enter spaces/tabs only → verify treated as empty or handled gracefully

**Priority guidance**: valid-input and empty-input are P0; boundary and unicode are P2.

---

## List / Table with Items

**How to identify**: `Table`, `List`, `OutlineView`, or a container with multiple similar child elements (e.g., repeated `Group` or `Cell` elements).

**Test patterns**:
- **Empty state**: if possible, get to a state where the list is empty → verify empty state message
- **Single item**: verify the list works correctly with exactly one item
- **Selection**: click an item → verify it becomes selected and detail/preview updates
- **Multi-selection** (if supported): select multiple items → verify bulk actions work

**Priority guidance**: selection is P0; empty-state is P1; multi-selection is P2.

---

## Context Menu (Right-Click)

**How to identify**: `RIGHT_CLICK` action in flow, or state with `MenuItem` elements.

**Test patterns**:
- **Every menu item gets its own scenario**: right-click → click menu item → verify the outcome based on the label's semantics
- **Dismiss without selecting**: right-click to open menu → press Escape or click elsewhere → verify nothing changed

**Priority guidance**: each-menu-item is P0 for destructive/important items (Delete, Close, Move), P1 for others; dismiss is P2.

---

## Dialog / Modal

**How to identify**: A state that is reached by an action and contains "Close", "Cancel", "OK", "Save", "Delete", "Confirm" buttons, or has a modal overlay.

**Test patterns**:
- **Every dismiss/action button**: generate a scenario for each button (Close, Cancel, Confirm, etc.)
- **Cancel preserves state**: click Cancel → verify no changes were made to the underlying data
- **Confirm/action button — infer and verify functional effect**: Do NOT just verify "dialog closes". Read the dialog's title, action button label, and contained controls (checkboxes, dropdowns, text fields) to **infer what the action actually does to the underlying data or system state**, then verify that concrete outcome. The reasoning process:
  1. What does the action button's label mean? (e.g., "Save" → persist data, "Remove" → delete something, "Apply" → change a setting)
  2. What do the dialog's controls specify? (e.g., checkboxes select which items are affected, dropdowns select scope/range, text fields provide input values)
  3. After clicking, what observable change should occur outside the dialog? (e.g., list becomes shorter, new item appears, file is created, setting takes effect)
  - Fill in concrete values in dialog controls before confirming, then verify the result reflects those values
  - If the action is destructive (removes data), verify the data is actually gone — not just that the dialog closed
- **Close via Escape key**: press Escape → verify dialog closes without applying changes

**Priority guidance**: confirm-with-functional-verification is P0; cancel-preserves is P0; escape-close is P2.

---

## Tab / Segmented Control

**How to identify**: `Tab`, `SegmentedControl`, `TabGroup`, or buttons that switch between views/panels (e.g., "Open Tabs" / "Recently Closed").

**Test patterns**:
- **Switch to each tab/segment**: click each tab → verify the correct content panel is displayed
- **Switch back and forth**: tab A → tab B → tab A → verify state is preserved (no data loss)
- **Default tab**: verify which tab is active by default on first open

**Priority guidance**: switch-each-tab is P0; back-and-forth-preservation is P1.
