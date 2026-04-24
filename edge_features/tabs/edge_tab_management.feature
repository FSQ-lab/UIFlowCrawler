Feature: edge_tab_management
  As a user of Microsoft Edge
  I want to verify the core tab management workflows
  So that I can ensure the application works correctly

  # ============================================================
  # Basic Tab Creation and Closure (flows 001, 002, 004, 030, 031, 032)
  # flow_003 dropped: lifecycle superseded by atomic flows
  # ============================================================

  @P0 @happy
  Scenario: Open a new tab from single tab state
    Given I launch the Edge browser
    When I click the "New Tab" button in the tab bar
    Then a second tab should appear in the tab bar
    And the new tab should be the active tab

  @P0 @happy @shortcut
  Scenario: Open a new tab using keyboard shortcut
    Given I launch the Edge browser
    When I press "⌘T"
    Then a second tab should appear in the tab bar
    And the new tab should be the active tab

  @P0 @happy
  Scenario: Close a tab returns to single tab
    Given I launch the Edge browser
    And I click the "New Tab" button in the tab bar
    When I click the "Close tab" button on the active tab
    Then only one tab should remain in the tab bar

  @P0 @happy @shortcut
  Scenario: Close a tab using keyboard shortcut
    Given I launch the Edge browser
    And I press "⌘T"
    When I press "⌘W"
    Then only one tab should remain in the tab bar

  @P0 @boundary
  Scenario: Close the last tab closes the browser window
    Given I launch the Edge browser
    And only one tab is open
    When I click the "Close tab" button on the active tab
    Then the browser window should close

  @P0 @boundary @shortcut
  Scenario: Close the last tab using keyboard shortcut closes the window
    Given I launch the Edge browser
    And only one tab is open
    When I press "⌘W"
    Then the browser window should close

  @P1 @happy
  Scenario: Open multiple tabs sequentially increases tab count
    Given I launch the Edge browser
    When I click the "New Tab" button in the tab bar
    Then two tabs should be visible in the tab bar
    When I click the "New Tab" button in the tab bar
    Then three tabs should be visible in the tab bar
    When I click the "New Tab" button in the tab bar
    Then four tabs should be visible in the tab bar
    When I click the "New Tab" button in the tab bar
    Then five tabs should be visible in the tab bar

  @P1 @happy
  Scenario: Click an existing tab keeps the same tab count
    Given I launch the Edge browser
    And I click the "New Tab" button in the tab bar
    And two tabs are visible in the tab bar
    When I click the first tab in the tab bar
    Then two tabs should still be visible in the tab bar
    And the first tab should become the active tab

  @P1 @happy @shortcut
  Scenario: Reopen closed tab using keyboard shortcut
    Given I launch the Edge browser
    And I click the "New Tab" button in the tab bar
    And two tabs are visible in the tab bar
    When I press "⌘W" to close the active tab
    Then only one tab should remain
    When I press "⌘⇧T"
    Then two tabs should be visible again in the tab bar

  # ============================================================
  # Search Tabs Dropdown (flows 005, 006, 007, 008)
  # flows 005/006/007 deduplicated: same action from different tab counts
  # ============================================================

  @P0 @happy
  Scenario: Open Search Tabs dropdown from tab bar
    Given I launch the Edge browser
    When I click the "Search tabs" button in the tab bar
    Then the Search Tabs dropdown should appear
    And the dropdown should show "Turn On Vertical Tabs" menu item
    And the dropdown should show "Organize Tabs" menu item
    And the dropdown should show "Open Tabs" and "Recently Closed" tabs

  @P0 @happy
  Scenario: Switch between Open Tabs and Recently Closed tabs
    Given I launch the Edge browser
    And I click the "New Tab" button in the tab bar
    And I click the "Search tabs" button in the tab bar
    When I click the "Open Tabs" button in the Search Tabs dropdown
    Then the Open Tabs list should be displayed
    When I click the "Recently Closed" button in the Search Tabs dropdown
    Then the Recently Closed tab list should be displayed

  @P1 @happy
  Scenario: Switch back and forth between Open Tabs and Recently Closed preserves state
    Given I launch the Edge browser
    And I click the "New Tab" button in the tab bar
    And I click the "Search tabs" button in the tab bar
    When I click the "Recently Closed" button in the Search Tabs dropdown
    Then the Recently Closed tab list should be displayed
    When I click the "Open Tabs" button in the Search Tabs dropdown
    Then the Open Tabs list should be displayed with the same tabs as before

  @P0 @happy
  Scenario: Search tabs by keyword filters results to matching tabs
    Given I launch the Edge browser
    And I open two tabs: "New Tab" and another page
    And I click the "Search tabs" button in the tab bar
    When I type "New Tab" in the search field in the Search Tabs dropdown
    Then only tabs matching "New Tab" should appear in the results list

  @P1 @happy
  Scenario: Search tabs with non-matching query shows no results
    Given I launch the Edge browser
    And I click the "New Tab" button in the tab bar
    And I click the "Search tabs" button in the tab bar
    When I type "zzz_nonexistent_xyz" in the search field in the Search Tabs dropdown
    Then the results list should show no matching tabs

  @P1 @happy
  Scenario: Clear search query restores full tab list
    Given I launch the Edge browser
    And I click the "New Tab" button in the tab bar
    And I click the "Search tabs" button in the tab bar
    When I type "New Tab" in the search field in the Search Tabs dropdown
    Then filtered results should be displayed
    When I clear the search field in the Search Tabs dropdown
    Then all open tabs should be listed again

  @P2 @boundary
  Scenario: Dismiss Search Tabs dropdown by pressing Escape
    Given I launch the Edge browser
    And I click the "Search tabs" button in the tab bar
    And the Search Tabs dropdown is visible
    When I press "Escape"
    Then the Search Tabs dropdown should close
    And no changes should be made to the tabs

  # ============================================================
  # Vertical Tabs (flows 009, 010, 012, 013, 014, 015)
  # flow_011 dropped: same as 010 with different tab count
  # flow_009 partially covered by atomics 013/014
  # ============================================================

  @P0 @happy
  Scenario: Turn on vertical tabs moves tabs to sidebar
    Given I launch the Edge browser
    And I click the "New Tab" button in the tab bar
    And I click the "Search tabs" button in the tab bar
    When I click the "Turn On Vertical Tabs" menu item in the Search Tabs dropdown
    Then the tabs should move from the top bar to a vertical sidebar on the left
    And the sidebar should show the open tabs in a vertical list

  @P0 @happy
  Scenario: Turn off vertical tabs returns to horizontal layout
    Given I launch the Edge browser
    And I click the "New Tab" button in the tab bar
    And I click the "Search tabs" button in the tab bar
    And I click the "Turn On Vertical Tabs" menu item in the Search Tabs dropdown
    When I click the "Turn Off Vertical Tabs" menu item in the vertical tabs sidebar
    Then the tabs should return to the horizontal tab bar at the top
    And the vertical sidebar should disappear

  @P1 @happy
  Scenario: Vertical tabs round-trip preserves tabs
    Given I launch the Edge browser
    And I click the "New Tab" button in the tab bar
    And I click the "Search tabs" button in the tab bar
    And I click the "Turn On Vertical Tabs" menu item in the Search Tabs dropdown
    And the vertical tabs sidebar is displayed
    When I click the "Turn Off Vertical Tabs" menu item in the vertical tabs sidebar
    Then the horizontal tab bar should display the same two tabs as before

  @P0 @happy
  Scenario: Collapse vertical tabs sidebar to icon-only view
    Given I launch the Edge browser
    And I click the "New Tab" button in the tab bar
    And I click the "Search tabs" button in the tab bar
    And I click the "Turn On Vertical Tabs" menu item in the Search Tabs dropdown
    When I click the "Collapse pane" button in the vertical tabs sidebar
    Then the vertical tabs sidebar should collapse to an icon-only view
    And the tab icons should still be visible in the collapsed sidebar

  @P1 @happy
  Scenario: Pin vertical tabs sidebar keeps it permanently expanded
    Given I launch the Edge browser
    And I click the "New Tab" button in the tab bar
    And I click the "Search tabs" button in the tab bar
    And I click the "Turn On Vertical Tabs" menu item in the Search Tabs dropdown
    And I click the "New Tab" button in the vertical tabs sidebar
    When I click the "Pin pane" button in the vertical tabs sidebar
    Then the sidebar should remain permanently expanded
    And a "Collapse pane" button should be visible instead of "Pin pane"

  @P1 @happy
  Scenario: Add new tab in collapsed vertical tabs sidebar
    Given I launch the Edge browser
    And I click the "New Tab" button in the tab bar
    And I click the "Search tabs" button in the tab bar
    And I click the "Turn On Vertical Tabs" menu item in the Search Tabs dropdown
    And I click the "Collapse pane" button in the vertical tabs sidebar
    And I click the "New Tab" button in the collapsed vertical tabs sidebar
    When a new tab icon appears in the collapsed sidebar
    Then the collapsed sidebar should show three tab icons

  # ============================================================
  # Organize Tabs Dialog (flows 016, 017, 018, 019, 021, 022)
  # flow_020 dropped: Cancel to variant state is same action as 017
  # flow_023 dropped: clicking New Tab in dialog triggering feedback is edge case subsumed by 022
  # ============================================================

  @P0 @happy
  Scenario: Open Organize Tabs dialog from Search Tabs dropdown
    Given I launch the Edge browser
    And I click the "New Tab" button in the tab bar
    And I click the "Search tabs" button in the tab bar
    When I click the "Organize Tabs" menu item in the Search Tabs dropdown
    Then the Organize Tabs dialog should appear
    And the dialog should show suggested tab groups
    And the dialog should have "Close", "Cancel", and "Group Tabs" buttons

  @P0 @happy
  Scenario: Group Tabs applies suggested groupings
    Given I launch the Edge browser
    And I click the "New Tab" button in the tab bar
    And I click the "Search tabs" button in the tab bar
    And I click the "Organize Tabs" menu item in the Search Tabs dropdown
    When I click the "Group Tabs" button in the Organize Tabs dialog
    Then the dialog should close
    And the tabs should be organized into the suggested groups

  @P0 @happy
  Scenario: Cancel Organize Tabs preserves original tab state
    Given I launch the Edge browser
    And I click the "New Tab" button in the tab bar
    And I click the "Search tabs" button in the tab bar
    And I click the "Organize Tabs" menu item in the Search Tabs dropdown
    When I click the "Cancel" button in the Organize Tabs dialog
    Then the dialog should close
    And the tabs should remain ungrouped and unchanged

  @P1 @happy
  Scenario: Close Organize Tabs dialog without changes
    Given I launch the Edge browser
    And I click the "New Tab" button in the tab bar
    And I click the "Search tabs" button in the tab bar
    And I click the "Organize Tabs" menu item in the Search Tabs dropdown
    When I click the "Close" button in the Organize Tabs dialog
    Then the dialog should close
    And the tabs should remain ungrouped and unchanged

  @P1 @functional
  Scenario: Submit satisfied feedback for Organize Tabs suggestions
    Given I launch the Edge browser
    And I click the "New Tab" button in the tab bar
    And I click the "Search tabs" button in the tab bar
    And I click the "Organize Tabs" menu item in the Search Tabs dropdown
    When I click the "I'm Satisfied With The Suggestions" button in the Organize Tabs dialog
    Then the satisfaction feedback should be recorded

  @P1 @functional
  Scenario: Submit not satisfied feedback with reason
    Given I launch the Edge browser
    And I click the "New Tab" button in the tab bar
    And I click the "Search tabs" button in the tab bar
    And I click the "Organize Tabs" menu item in the Search Tabs dropdown
    When I click the "I'm Not Satisfied With The Suggestions" button in the Organize Tabs dialog
    Then the feedback options should appear
    When I click the "Not All Of My Tabs Are Grouped" option
    Then the feedback should be submitted

  @P2 @boundary
  Scenario: Dismiss Organize Tabs dialog with Escape key
    Given I launch the Edge browser
    And I click the "New Tab" button in the tab bar
    And I click the "Search tabs" button in the tab bar
    And I click the "Organize Tabs" menu item in the Search Tabs dropdown
    When I press "Escape"
    Then the Organize Tabs dialog should close
    And the tabs should remain ungrouped and unchanged

  # ============================================================
  # Tab Context Menus (flows 024, 025, 026, 033, 034)
  # flows 027/028/029 dropped: tab switching/self-loop covered in Group 1
  # ============================================================

  @P0 @happy @context-menu
  Scenario: Right-click tab opens context menu with all options
    Given I launch the Edge browser
    And I open five tabs
    When I right-click a tab in the tab bar
    Then a context menu should appear with options including "New Tab to the Right", "Add Tab to New Group", "Duplicate Tab", "Pin Tab", "Mute Tab", "Close Tab", "Close Other Tabs", and "Close Tabs to the Right"

  @P0 @happy @context-menu
  Scenario: New Tab to the Right from tab context menu
    Given I launch the Edge browser
    And I open five tabs
    When I right-click a tab in the tab bar
    And I click the "New Tab to the Right" menu item
    Then a new tab should appear immediately to the right of the right-clicked tab
    And the total tab count should increase by one

  @P0 @happy @context-menu
  Scenario: Close Tab from tab context menu
    Given I launch the Edge browser
    And I open five tabs
    When I right-click a tab in the tab bar
    And I click the "Close Tab" menu item
    Then the right-clicked tab should be closed
    And four tabs should remain in the tab bar

  @P0 @happy @context-menu
  Scenario: Close Other Tabs from tab context menu
    Given I launch the Edge browser
    And I open five tabs
    When I right-click a tab in the tab bar
    And I click the "Close Other Tabs" menu item
    Then all tabs except the right-clicked tab should be closed
    And only one tab should remain in the tab bar

  @P1 @happy @context-menu
  Scenario: Close Tabs to the Right from tab context menu
    Given I launch the Edge browser
    And I open five tabs
    When I right-click the third tab in the tab bar
    And I click the "Close Tabs to the Right" menu item
    Then all tabs to the right of the third tab should be closed
    And three tabs should remain in the tab bar

  @P1 @happy @context-menu
  Scenario: Duplicate Tab from tab context menu
    Given I launch the Edge browser
    And I open two tabs
    When I right-click a tab in the tab bar
    And I click the "Duplicate Tab" menu item
    Then a new tab should appear with the same page content as the right-clicked tab
    And the total tab count should increase by one

  @P1 @happy @context-menu
  Scenario: Pin Tab from tab context menu
    Given I launch the Edge browser
    And I open two tabs
    When I right-click a tab in the tab bar
    And I click the "Pin Tab" menu item
    Then the tab should be pinned to the left side of the tab bar
    And the pinned tab should display as a smaller icon-only tab

  @P1 @happy @context-menu
  Scenario: Mute Tab from tab context menu
    Given I launch the Edge browser
    And I open two tabs
    When I right-click a tab in the tab bar
    And I click the "Mute Tab" menu item
    Then the tab should be muted
    And a muted icon should appear on the tab

  @P2 @happy @context-menu
  Scenario: Switch to Last Active Tab from tab context menu
    Given I launch the Edge browser
    And I open three tabs
    And I click the second tab in the tab bar
    And I click the third tab in the tab bar
    When I right-click the third tab
    And I click the "Switch to Last Active Tab" menu item
    Then the second tab should become the active tab

  @P2 @boundary @context-menu
  Scenario: Dismiss tab context menu by pressing Escape
    Given I launch the Edge browser
    And I open two tabs
    When I right-click a tab in the tab bar
    And the context menu is visible
    And I press "Escape"
    Then the context menu should close
    And no changes should be made to the tabs

  @P0 @happy @context-menu
  Scenario: Right-click blank tab bar area opens context menu
    Given I launch the Edge browser
    When I right-click the blank area of the tab bar
    Then a context menu should appear with options including "New Tab", "Restore Window", "Name Window", "Turn On Vertical Tabs", "Customize Toolbar", and "Browser Task Manager"

  @P0 @happy @context-menu
  Scenario: New Tab from blank tab bar context menu
    Given I launch the Edge browser
    When I right-click the blank area of the tab bar
    And I click the "New Tab" menu item
    Then a new tab should be created
    And two tabs should be visible in the tab bar

  @P2 @happy @context-menu
  Scenario: Name Window from blank tab bar context menu
    Given I launch the Edge browser
    When I right-click the blank area of the tab bar
    And I click the "Name Window" menu item
    Then a dialog or input should appear to name the current window

  # ============================================================
  # Tab Groups (flows 035, 036, 037, 038, 039)
  # flow_040 dropped: lifecycle superseded by atomic flows 035-038
  # ============================================================

  @P0 @happy
  Scenario: Create a new tab group via right-click context menu
    Given I launch the Edge browser
    And I open five tabs
    When I right-click a tab in the tab bar
    And I click the "Add Tab to New Group" menu item
    Then the Edit Tab Group dialog should appear
    And the dialog should show a "Tab-group title" text field
    And the dialog should show 9 color options: Blue, Pink, Violet, Purple, Royal blue, Teal, Orange, Yellow, and Gray
    And the dialog should show "New Tab in Group", "Ungroup", and "Move to new window" buttons

  @P0 @happy
  Scenario: Rename a tab group
    Given I launch the Edge browser
    And I open five tabs
    And I right-click a tab in the tab bar
    And I click the "Add Tab to New Group" menu item
    When I type "MyGroup" in the "Tab-group title" text field
    Then the tab group header in the tab bar should display "MyGroup"

  @P1 @happy
  Scenario: Change tab group color
    Given I launch the Edge browser
    And I open five tabs
    And I right-click a tab in the tab bar
    And I click the "Add Tab to New Group" menu item
    And I type "MyGroup" in the "Tab-group title" text field
    When I click the "Pink" color option
    Then the tab group color should change to Pink
    And the group header in the tab bar should reflect the new color

  @P0 @happy
  Scenario: Add a new tab inside an existing group
    Given I launch the Edge browser
    And I open five tabs
    And I right-click a tab in the tab bar
    And I click the "Add Tab to New Group" menu item
    And I type "MyGroup" in the "Tab-group title" text field
    When I click the "New Tab in Group" button
    Then a new tab should be created inside the "MyGroup" group
    And the new tab should appear under the group header in the tab bar

  @P0 @happy
  Scenario: Ungroup a tab group dissolves grouped tabs
    Given I launch the Edge browser
    And I open five tabs
    And I right-click a tab in the tab bar
    And I click the "Add Tab to New Group" menu item
    And I type "MyGroup" in the "Tab-group title" text field
    When I click the "Ungroup" button
    Then the tab group should be dissolved
    And all tabs should remain open but no longer grouped
    And the group header should disappear from the tab bar

  @P1 @happy
  Scenario: Move tab group to a new window
    Given I launch the Edge browser
    And I open five tabs
    And I right-click a tab in the tab bar
    And I click the "Add Tab to New Group" menu item
    When I click the "Move to new window" button
    Then the grouped tab should move to a new browser window
    And the original window should retain the remaining ungrouped tabs

  @P1 @boundary
  Scenario: Create tab group with empty name
    Given I launch the Edge browser
    And I open five tabs
    And I right-click a tab in the tab bar
    And I click the "Add Tab to New Group" menu item
    When I leave the "Tab-group title" text field empty
    And I click the "New Tab in Group" button
    Then the tab group should be created with a default or empty name
    And the new tab should be added to the group

  @P2 @happy
  Scenario: Add Tab Group to a New Collection
    Given I launch the Edge browser
    And I open five tabs
    And I right-click a tab in the tab bar
    And I click the "Add Tab to New Group" menu item
    And I type "MyGroup" in the "Tab-group title" text field
    When I click the "Add Tab Group to a New Collection" button
    Then the tab group should be saved to a new collection
