Feature: Edge History
  As a user of Microsoft Edge
  I want to verify the core history workflows
  So that I can ensure the application works correctly

  # ============================================================
  # Sidebar Navigation and Tabs (flows 001, 012)
  # ============================================================

  @happy
  Scenario: Switch to Recently Closed tab in History sidebar
    Given I launch the Edge browser
    And I press "Ctrl+H" to open the History sidebar
    When I click the "Recently Closed" tab in the History sidebar
    Then the "Recently Closed" tab should be active
    And the list should show recently closed browser entries

  @happy
  Scenario: Switch to Tabs From Other Devices tab in History sidebar
    Given I launch the Edge browser
    And I press "Ctrl+H" to open the History sidebar
    When I click the "Tabs From Other Devices" tab in the History sidebar
    Then the "Tabs From Other Devices" tab should be active
    And a sign-in prompt should be displayed for syncing tabs

  @happy
  Scenario: Switch back to All tab from Recently Closed
    Given I launch the Edge browser
    And I press "Ctrl+H" to open the History sidebar
    And I click the "Recently Closed" tab in the History sidebar
    When I click the "All" tab in the History sidebar
    Then the "All" tab should be active
    And the browsing history entries should be displayed grouped by date

  @happy
  Scenario: Pin the History sidebar
    Given I launch the Edge browser
    And I press "Ctrl+H" to open the History sidebar
    When I click the "Pin history" button in the History sidebar toolbar
    Then the History sidebar should be pinned to the side of the browser window
    And the browser page content should resize to accommodate the pinned sidebar

  @happy
  Scenario: Navigate tabs and pin sidebar in sequence
    Given I launch the Edge browser
    And I press "Ctrl+H" to open the History sidebar
    When I click the "Recently Closed" tab in the History sidebar
    And I click the "All" tab in the History sidebar
    And I click the "Tabs From Other Devices" tab in the History sidebar
    And I click the "Pin history" button in the History sidebar toolbar
    Then the History sidebar should be pinned to the side of the browser window

  @happy
  Scenario: Click a history entry to open it in the browser
    Given I launch the Edge browser
    And I press "Ctrl+H" to open the History sidebar
    When I click a history entry in the "All" tab
    Then the clicked page should open in the current browser tab

  @boundary
  Scenario: Rapidly switch between all History sidebar tabs
    Given I launch the Edge browser
    And I press "Ctrl+H" to open the History sidebar
    When I click the "Recently Closed" tab in the History sidebar
    And I click the "Tabs From Other Devices" tab in the History sidebar
    And I click the "All" tab in the History sidebar
    And I click the "Recently Closed" tab in the History sidebar
    Then the "Recently Closed" tab should be active
    And the recently closed entries should be displayed without errors

  # ============================================================
  # Sidebar More Options Menu (flows 013, 014, 015)
  # ============================================================

  @happy
  Scenario: Open History Page from More options menu
    Given I launch the Edge browser
    And I press "Ctrl+H" to open the History sidebar
    When I click the "More options" button in the History sidebar toolbar
    And I click "Open History Page" in the More options menu
    Then the full History page should open at "edge://history"

  @happy
  Scenario: Hide History Button from Toolbar via More options menu
    Given I launch the Edge browser
    And I press "Ctrl+H" to open the History sidebar
    When I click the "More options" button in the History sidebar toolbar
    And I click "Hide History Button from Toolbar" in the More options menu
    Then the History button should be removed from the browser toolbar

  @happy
  Scenario: Hide Duplicate Pages via More options menu
    Given I launch the Edge browser
    And I press "Ctrl+H" to open the History sidebar
    When I click the "More options" button in the History sidebar toolbar
    And I click "Hide Duplicate Pages" in the More options menu
    Then duplicate history entries should be hidden from the list

  @happy
  Scenario: Export Browsing Data from More options menu
    Given I launch the Edge browser
    And I press "Ctrl+H" to open the History sidebar
    When I click the "More options" button in the History sidebar toolbar
    And I click "Export Browsing Data" in the More options menu
    Then the "Export Browsing Data" dialog should appear with "Cancel" and "Export" buttons

  @happy
  Scenario: Toggle Hide Duplicate Pages on and off
    Given I launch the Edge browser
    And I press "Ctrl+H" to open the History sidebar
    When I click the "More options" button in the History sidebar toolbar
    And I click "Hide Duplicate Pages" in the More options menu
    And I click the "More options" button in the History sidebar toolbar
    And I click "Hide Duplicate Pages" in the More options menu
    Then all history entries including duplicates should be displayed again

  # ============================================================
  # Sidebar Context Menu (flows 005, 006, 007, 008, 009, 010)
  # ============================================================

  @happy @context-menu
  Scenario: Right-click history entry and open in new tab
    Given I launch the Edge browser
    And I press "Ctrl+H" to open the History sidebar
    When I right-click a history entry in the "All" tab
    And I click "Open in New Tab" in the context menu
    Then the history entry URL should open in a new background tab

  @happy @context-menu
  Scenario: Right-click history entry and open in new window
    Given I launch the Edge browser
    And I press "Ctrl+H" to open the History sidebar
    When I right-click a history entry in the "All" tab
    And I click "Open in New Window" in the context menu
    Then the history entry URL should open in a separate new browser window

  @happy @context-menu
  Scenario: Right-click history entry and open in InPrivate window
    Given I launch the Edge browser
    And I press "Ctrl+H" to open the History sidebar
    When I right-click a history entry in the "All" tab
    And I click "Open in New InPrivate Window" in the context menu
    Then the history entry URL should open in a new InPrivate browsing window

  @happy @context-menu
  Scenario: Right-click history entry and copy link
    Given I launch the Edge browser
    And I press "Ctrl+H" to open the History sidebar
    When I right-click a history entry in the "All" tab
    And I click "Copy Link" in the context menu
    Then the URL of the history entry should be copied to the clipboard
    And I should be able to paste the URL into the address bar

  @happy @context-menu
  Scenario: Right-click history entry, select Delete, then cancel
    Given I launch the Edge browser
    And I press "Ctrl+H" to open the History sidebar
    When I right-click a history entry in the "All" tab
    And I click "Delete" in the context menu
    Then a delete confirmation dialog should appear with "Cancel" and "Delete" buttons
    When I click the "Cancel" button in the delete confirmation dialog
    Then the history entry should remain in the list

  @happy @context-menu
  Scenario: Right-click history entry, select Delete, then confirm
    Given I launch the Edge browser
    And I press "Ctrl+H" to open the History sidebar
    When I right-click a history entry in the "All" tab
    And I click "Delete" in the context menu
    Then a delete confirmation dialog should appear
    When I click the "Delete" button in the delete confirmation dialog
    Then the history entry should be removed from the list

  @happy @context-menu
  Scenario: Right-click history entry and filter by same site
    Given I launch the Edge browser
    And I press "Ctrl+H" to open the History sidebar
    When I right-click a history entry in the "All" tab
    And I click "More from the Same Site" in the context menu
    Then the History sidebar should show only entries from the same domain
    And a "Clear search" button should be visible

  # ============================================================
  # Sidebar Pin/Unpin/Close (flows 025, 026)
  # ============================================================

  @happy
  Scenario: Unpin a pinned History sidebar
    Given I launch the Edge browser
    And I press "Ctrl+H" to open the History sidebar
    And I click the "Pin history" button in the History sidebar toolbar
    When I click the "Unpin history" button in the pinned History sidebar
    Then the History sidebar should return to overlay panel mode
    And the browser page content should expand to full width

  @happy
  Scenario: Close a pinned History sidebar
    Given I launch the Edge browser
    And I press "Ctrl+H" to open the History sidebar
    And I click the "Pin history" button in the History sidebar toolbar
    When I click the "Close history" button in the pinned History sidebar
    Then the History sidebar should be completely closed
    And the browser page should be shown without the sidebar

  @happy
  Scenario: Pin, unpin, then pin again (toggle)
    Given I launch the Edge browser
    And I press "Ctrl+H" to open the History sidebar
    And I click the "Pin history" button in the History sidebar toolbar
    When I click the "Unpin history" button in the pinned History sidebar
    And I click the "Pin history" button in the History sidebar toolbar
    Then the History sidebar should be pinned to the side of the browser window

  # ============================================================
  # Delete Browsing Data (flows 011, 022)
  # ============================================================

  @happy
  Scenario: Open Delete Browsing Data settings from History sidebar
    Given I launch the Edge browser
    And I press "Ctrl+H" to open the History sidebar
    When I click the "Delete Browsing Data" button in the History sidebar toolbar
    Then the Clear browsing data settings page should open at "edge://settings/privacy/clearBrowsingData"

  @happy
  Scenario: Open Delete Browsing Data dialog from History full page
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    When I click the "Delete Browsing Data" button on the History full page
    Then the Delete browsing data dialog should appear
    And the dialog should show a "Time range" dropdown defaulting to "Last hour"
    And the dialog should show checkboxes for "Browsing history", "Download history", "Cookies and other site data", "Cached images and files", "Autofill form data (includes forms and cards)", and "Site permissions"
    And the dialog should show "Cancel" and "Clear now" buttons

  @happy
  Scenario: Cancel Delete Browsing Data dialog on full page
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    And I click the "Delete Browsing Data" button on the History full page
    When I click the "Cancel" button in the Delete browsing data dialog
    Then the dialog should close
    And the history entries should remain unchanged

  @happy
  Scenario: Clear browsing data using Clear now button
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    And I click the "Delete Browsing Data" button on the History full page
    When I click the "Clear now" button in the Delete browsing data dialog
    Then the dialog should close
    And the browsing history entries should be cleared based on the selected time range

  @boundary
  Scenario: Toggle individual checkboxes in Delete Browsing Data dialog
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    And I click the "Delete Browsing Data" button on the History full page
    When I uncheck "Browsing history" in the Delete browsing data dialog
    And I uncheck "Download history" in the Delete browsing data dialog
    And I check "Cookies and other site data" in the Delete browsing data dialog
    Then only checked data types should be selected for deletion

  @boundary
  Scenario: Change time range in Delete Browsing Data dialog
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    And I click the "Delete Browsing Data" button on the History full page
    When I click the "Time range" dropdown in the Delete browsing data dialog
    And I select a different time range
    Then the "Time range" dropdown should reflect the selected value

  # ============================================================
  # Full Page Navigation and Search (flows 002, 003, 004, 030)
  # ============================================================

  @happy
  Scenario: Open History full page and view Filter By Date dropdown
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    When I click the "Filter By Date" dropdown on the History full page
    Then the dropdown should show options: "Date Range", "Today", "Yesterday", "Last Week"

  @happy @shortcut
  Scenario: Open History full page using Command+Y shortcut
    Given I launch the Edge browser
    When I press "Command+Y"
    Then the History full page should open at "edge://history"
    And the page should show all browsing history entries

  @happy
  Scenario: Open Export Browsing Data dialog from History full page
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    When I click the "Export Browsing Data" button on the History full page
    Then the "Export Browsing Data" dialog should appear
    And the dialog should contain a privacy warning
    And the dialog should show "Cancel" and "Export" buttons

  @happy
  Scenario: Search history on full page with matching keyword
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    When I type "github" in the "Search history" text field
    Then the history list should show only entries matching "github"
    And matching text should be highlighted in the results

  @happy
  Scenario: Search history and clear search to restore full list
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    And I type "github" in the "Search history" text field
    When I click the "Clear search" button
    Then the search field should be cleared
    And all history entries should be displayed again

  @error
  Scenario: Search history with special characters
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    When I type "<script>alert(1)</script>" in the "Search history" text field
    Then the search should complete without errors
    And no matching history entries should be found

  @boundary
  Scenario: Search history with empty input
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    When I click the "Search history" text field
    And I type "" in the "Search history" text field
    Then the full history list should remain visible

  @boundary
  Scenario: Search history with no matching results
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    When I type "zzz_nonexistent_query_12345" in the "Search history" text field
    Then an empty state or "no results" message should be displayed

  @boundary
  Scenario: Search history with very long query
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    When I type a 500-character string in the "Search history" text field
    Then the search should complete without errors
    And no matching history entries should be found

  # ============================================================
  # Full Page Context Menu (flows 016, 017, 018, 019, 020, 021)
  # ============================================================

  @happy @context-menu
  Scenario: Full page: right-click entry and open in new tab
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    When I right-click a history entry on the full page
    And I click "Open in New Tab" in the context menu
    Then the history entry URL should open in a new tab

  @happy @context-menu
  Scenario: Full page: right-click entry and open in new window
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    When I right-click a history entry on the full page
    And I click "Open in New Window" in the context menu
    Then the history entry URL should open in a separate new browser window

  @happy @context-menu
  Scenario: Full page: right-click entry and open in InPrivate window
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    When I right-click a history entry on the full page
    And I click "Open in New InPrivate Window" in the context menu
    Then the history entry URL should open in a new InPrivate browsing window

  @happy @context-menu
  Scenario: Full page: right-click entry and copy link
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    When I right-click a history entry on the full page
    And I click "Copy Link" in the context menu
    Then the URL of the history entry should be copied to the clipboard
    And I should be able to paste the URL into the address bar to verify

  @happy @context-menu
  Scenario: Full page: right-click entry, select Delete, then cancel
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    When I right-click a history entry on the full page
    And I click "Delete" in the context menu
    Then a "Delete these pages?" confirmation dialog should appear with "Cancel" and "Delete" buttons
    When I click the "Cancel" button in the confirmation dialog
    Then the history entry should remain in the list

  @happy @context-menu
  Scenario: Full page: right-click entry, select Delete, then confirm
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    When I right-click a history entry on the full page
    And I click "Delete" in the context menu
    Then a "Delete these pages?" confirmation dialog should appear
    When I click the "Delete" button in the confirmation dialog
    Then the history entry should be removed from the full page list

  @happy @context-menu
  Scenario: Full page: right-click entry and filter by same site
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    When I right-click a history entry on the full page
    And I click "More from the Same Site" in the context menu
    Then the full page should show only entries from the same domain
    And a "Clear search" button should be visible

  @happy @context-menu
  Scenario: Full page: clear site filter after filtering by same site
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    And I right-click a history entry on the full page
    And I click "More from the Same Site" in the context menu
    When I click the "Clear search" button
    Then all history entries should be displayed again on the full page

  # ============================================================
  # Full Page Filter By Date (flows 023, 027, 028)
  # ============================================================

  @happy
  Scenario: Open Filter By Date dropdown on full page
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    When I click the "Filter By Date" dropdown on the History full page
    Then the dropdown should show "Date Range", "Today", "Yesterday", "Last Week" options

  @happy
  Scenario: Filter history by Today
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    When I click the "Filter By Date" dropdown on the History full page
    And I click "Today" in the Filter By Date dropdown
    Then the history full page should show only today's entries
    And a date header for today should be displayed

  @happy
  Scenario: Filter history by Yesterday
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    When I click the "Filter By Date" dropdown on the History full page
    And I click "Yesterday" in the Filter By Date dropdown
    Then the history full page should show only yesterday's entries
    And a date header for yesterday should be displayed

  @happy
  Scenario: Filter history by Last Week
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    When I click the "Filter By Date" dropdown on the History full page
    And I click "Last Week" in the Filter By Date dropdown
    Then the history full page should show entries from the last week

  @happy
  Scenario: Open Date Range picker and cancel
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    And I click the "Filter By Date" dropdown on the History full page
    When I click "Date Range" in the Filter By Date dropdown
    Then the Date Range picker should appear with "Start Time" and "End Time" fields
    And the picker should show two "Show date picker" buttons
    And the picker should show "Cancel" and "Apply" buttons
    When I click the "Cancel" button in the Date Range picker
    Then the Date Range picker should be dismissed
    And the history list should be displayed

  @happy
  Scenario: Apply a date range filter
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    And I click the "Filter By Date" dropdown on the History full page
    When I click "Date Range" in the Filter By Date dropdown
    And I set the Start Time using the "Show date picker" button
    And I set the End Time using the "Show date picker" button
    And I click the "Apply" button in the Date Range picker
    Then the history full page should show only entries within the selected date range

  # ============================================================
  # Full Page Recently Closed and Other Devices (flow 024)
  # ============================================================

  @happy
  Scenario: Navigate to Recently Closed section on full page
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    When I click the "Recently Closed" row in the left sidebar
    Then the Recently Closed section should be displayed
    And the section should show a list of recently closed tabs and windows
    And a "Search history" text field should be visible

  @happy
  Scenario: Navigate to Tabs From Other Devices section on full page
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    When I click the "Tabs From Other Devices" row in the left sidebar
    Then the Tabs From Other Devices section should be displayed
    And the section should show synced tabs from other devices or a sign-in prompt

  @happy
  Scenario: Switch between Recently Closed and Tabs From Other Devices
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    When I click the "Recently Closed" row in the left sidebar
    And I click the "Tabs From Other Devices" row in the left sidebar
    Then the Tabs From Other Devices section should be displayed

  # ============================================================
  # Full Page Export Browsing Data (flow 029)
  # ============================================================

  @happy
  Scenario: Open Export Browsing Data dialog and cancel
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    When I click the "Export Browsing Data" button on the History full page
    Then the Export Browsing Data dialog should appear with a privacy warning
    And the dialog should show "Cancel" and "Export" buttons
    When I click the "Cancel" button in the Export Browsing Data dialog
    Then the dialog should be dismissed
    And the history list should be displayed

  @happy
  Scenario: Export browsing data by clicking Export
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    When I click the "Export Browsing Data" button on the History full page
    And I click the "Export" button in the Export Browsing Data dialog
    Then a file save dialog should appear to save the exported browsing data

  # ============================================================
  # Keyboard Shortcuts (flows 031, 032, 033)
  # ============================================================

  @happy @shortcut
  Scenario: Ctrl+H opens History sidebar
    Given I launch the Edge browser
    When I press "Ctrl+H"
    Then the History sidebar panel should open
    And the "All" tab should be active
    And browsing history entries should be displayed

  @happy @shortcut
  Scenario: Command+Y opens History full page
    Given I launch the Edge browser
    When I press "Command+Y"
    Then the History full page should open at "edge://history"
    And all browsing history entries should be displayed

  @happy @shortcut
  Scenario: Shift+Command+T opens Clear Browsing Data settings
    Given I launch the Edge browser
    When I press "Shift+Command+T"
    Then the Clear browsing data settings page should open at "edge://settings/privacy/clearBrowsingData"

  @boundary @shortcut
  Scenario: Press Ctrl+H when History sidebar is already open
    Given I launch the Edge browser
    And I press "Ctrl+H" to open the History sidebar
    When I press "Ctrl+H" again
    Then the History sidebar should close or toggle visibility

  @boundary @shortcut
  Scenario: Press Command+Y when History full page is already open
    Given I launch the Edge browser
    And I press "Command+Y" to open the History full page
    When I press "Command+Y" again
    Then the History full page should remain open or a new tab should not be created
