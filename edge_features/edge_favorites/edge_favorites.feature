Feature: Edge Favorites
  As a user of Microsoft Edge
  I want to verify the favorites management workflows
  So that I can ensure bookmarking and organizing favorites works correctly

  # ============================================================
  # Edit Favorite Dialog (flows 001, 028-032)
  # ============================================================

  @happy
  Scenario: Open Edit Favorite dialog by clicking the star button
    Given the New Tab page is open in Microsoft Edge
    When I click the "Edit favorite for this page" button in the App bar
    Then the "Edit favorite" dialog should appear
    And the "Favorite Name" text field should be visible
    And the "Folder" dropdown should be visible
    And the "Done" button should be visible
    And the "Remove" button should be visible

  @happy
  Scenario: Open Edit Favorite dialog via keyboard shortcut Command+D
    Given the New Tab page is open in Microsoft Edge
    When I press "Command+D"
    Then the "Edit favorite" dialog should appear
    And the "Favorite Name" text field should be visible

  @happy
  Scenario: Edit the favorite name in the Edit Favorite dialog
    Given the "Edit favorite" dialog is open in Microsoft Edge
    When I clear the "Favorite Name" text field
    And I type "My Custom Bookmark" in the "Favorite Name" text field
    Then the "Favorite Name" text field should contain "My Custom Bookmark"

  @happy
  Scenario: Change the folder for a favorite
    Given the "Edit favorite" dialog is open in Microsoft Edge
    When I click the "Folder" dropdown in the Edit favorite dialog
    Then a list of available folders should appear

  @happy
  Scenario: Expand the Edit Favorite dialog with More button
    Given the "Edit favorite" dialog is open in Microsoft Edge
    When I click the "More" button in the Edit favorite dialog
    Then the expanded Edit favorite view should appear with additional options

  @happy
  Scenario: Save a favorite by clicking Done
    Given the "Edit favorite" dialog is open in Microsoft Edge
    When I type "Test Bookmark" in the "Favorite Name" text field
    And I click the "Done" button in the Edit favorite dialog
    Then the "Edit favorite" dialog should close
    And the page should be saved to favorites

  @happy
  Scenario: Remove a favorite from the Edit Favorite dialog
    Given the "Edit favorite" dialog is open in Microsoft Edge
    When I click the "Remove" button in the Edit favorite dialog
    Then the "Edit favorite" dialog should close
    And the page should no longer be in favorites

  @error
  Scenario: Edit favorite name with special characters
    Given the "Edit favorite" dialog is open in Microsoft Edge
    When I clear the "Favorite Name" text field
    And I type "<script>alert('xss')</script>" in the "Favorite Name" text field
    And I click the "Done" button in the Edit favorite dialog
    Then the favorite should be saved without executing any scripts
    And the favorite name should be stored as literal text

  @boundary
  Scenario: Edit favorite name with empty input
    Given the "Edit favorite" dialog is open in Microsoft Edge
    When I clear the "Favorite Name" text field
    And I click the "Done" button in the Edit favorite dialog
    Then the dialog should either prevent saving or save with a default name

  @boundary
  Scenario: Edit favorite name with very long text
    Given the "Edit favorite" dialog is open in Microsoft Edge
    When I clear the "Favorite Name" text field
    And I type a 500-character string in the "Favorite Name" text field
    And I click the "Done" button in the Edit favorite dialog
    Then the favorite should be saved
    And the name should be displayed without breaking the UI

  @boundary
  Scenario: Edit favorite name with unicode and emoji characters
    Given the "Edit favorite" dialog is open in Microsoft Edge
    When I clear the "Favorite Name" text field
    And I type "Favorito estrella" in the "Favorite Name" text field
    And I click the "Done" button in the Edit favorite dialog
    Then the favorite should be saved with the unicode name intact

  # ============================================================
  # Open Favorites Panel (flows 002, 007)
  # ============================================================

  @happy
  Scenario: Open the Favorites panel from the toolbar
    Given the New Tab page is open in Microsoft Edge
    When I click the "Favorites" button in the App bar
    Then the Favorites panel should appear
    And the Favorites toolbar should show "Add This Page to Favorites...", "Add folder", "Search favorites", "More options", and "Pin favorites" buttons
    And the "Favorites Bar" folder should be visible in the favorites list

  @happy
  Scenario: Navigate to Favorites full page from the panel
    Given the Favorites panel is open in Microsoft Edge
    When I click the "Favorites" heading button in the Favorites panel
    Then the Favorites full page should open in a new tab

  # ============================================================
  # Add Favorite (flows 008, 016)
  # ============================================================

  @happy
  Scenario: Add current page to favorites via panel toolbar
    Given the Favorites panel is open in Microsoft Edge
    When I click the "Add This Page to Favorites..." button in the Favorites toolbar
    Then a new favorite entry should appear inline in the Favorites list
    And an inline text field should be active for editing the favorite name

  @happy
  Scenario: Add current page to favorites via More Options menu
    Given the Favorites panel is open in Microsoft Edge
    When I click the "More options" button in the Favorites toolbar
    And I click the "Add This Page to Favorites..." menu item
    Then the current page should be added to favorites

  # ============================================================
  # Add Folder (flows 009, 018, 033)
  # ============================================================

  @happy
  Scenario: Add a new folder via panel toolbar
    Given the Favorites panel is open in Microsoft Edge
    When I click the "Add folder" button in the Favorites toolbar
    Then a new "New folder" row should appear in the Favorites list
    And an inline text field should be active for entering the folder name

  @happy
  Scenario: Type a folder name in the Add Folder inline editor
    Given a new folder inline editor is active in the Favorites panel
    When I type "Work Bookmarks" in the folder name text field
    Then the folder name text field should contain "Work Bookmarks"

  @happy
  Scenario: Add a new folder via More Options menu
    Given the Favorites panel is open in Microsoft Edge
    When I click the "More options" button in the Favorites toolbar
    And I click the "Add Folder..." menu item
    Then a new folder inline editor should appear in the Favorites list

  @error
  Scenario: Add folder with special characters in the name
    Given a new folder inline editor is active in the Favorites panel
    When I type "Folder/With\\Special<Chars>" in the folder name text field
    And I press "Return"
    Then the folder should be created without errors
    And the folder name should be displayed as entered

  @boundary
  Scenario: Add folder with empty name
    Given a new folder inline editor is active in the Favorites panel
    When I leave the folder name text field empty
    And I press "Return"
    Then the folder should either use a default name or prevent creation

  @boundary
  Scenario: Add folder with very long name
    Given a new folder inline editor is active in the Favorites panel
    When I type a 300-character string in the folder name text field
    And I press "Return"
    Then the folder should be created
    And the folder name should be displayed without breaking the panel layout

  # ============================================================
  # Search Favorites (flows 010, 034, 035)
  # ============================================================

  @happy
  Scenario: Activate search mode in the Favorites panel
    Given the Favorites panel is open in Microsoft Edge
    When I click the "Search favorites" button in the Favorites toolbar
    Then the search mode should activate
    And the "Search favorites" input field should be visible
    And the "Exit search" button should be visible

  @happy
  Scenario: Search favorites with a matching keyword
    Given the Favorites search mode is active in Microsoft Edge
    When I type "Test" in the "Search favorites" input field
    Then the favorites list should show only items matching "Test"

  @happy
  Scenario: Exit search mode and return to full favorites list
    Given the Favorites search mode is active in Microsoft Edge
    When I click the "Exit search" button
    Then the Favorites panel should return to the normal list view
    And the Favorites toolbar buttons should be visible again

  @error
  Scenario: Search favorites with HTML injection attempt
    Given the Favorites search mode is active in Microsoft Edge
    When I type "<img src=x onerror=alert(1)>" in the "Search favorites" input field
    Then the search should complete without errors
    And no scripts should execute

  @boundary
  Scenario: Search favorites with no matching results
    Given the Favorites search mode is active in Microsoft Edge
    When I type "zzz_nonexistent_query_12345" in the "Search favorites" input field
    Then the favorites list should show no results or an empty state message

  @boundary
  Scenario: Search favorites with empty input
    Given the Favorites search mode is active in Microsoft Edge
    When I type "" in the "Search favorites" input field
    Then the full favorites list should remain visible

  @boundary
  Scenario: Search favorites with whitespace-only input
    Given the Favorites search mode is active in Microsoft Edge
    When I type "   " in the "Search favorites" input field
    Then the favorites list should show no results or the full list

  # ============================================================
  # More Options Menu (flow 011)
  # ============================================================

  @happy
  Scenario: Open the More Options menu in the Favorites panel
    Given the Favorites panel is open in Microsoft Edge
    When I click the "More options" button in the Favorites toolbar
    Then the More Options menu should appear
    And the menu should contain "Open Favorites Page"
    And the menu should contain "Add This Page to Favorites..."
    And the menu should contain "Add Open Pages to Favorites..."
    And the menu should contain "Add Folder..."
    And the menu should contain "Import favorites"
    And the menu should contain "Export favorites"
    And the menu should contain "Remove Duplicate Favorites"
    And the menu should contain "Show Favorites Bar"
    And the menu should contain "Hide Favorites Button from Toolbar"

  # ============================================================
  # Pin Favorites (flow 012)
  # ============================================================

  @happy
  Scenario: Pin the Favorites panel as a sidebar
    Given the Favorites panel is open in Microsoft Edge
    When I click the "Pin favorites" button in the Favorites toolbar
    Then the Favorites panel should be pinned as a persistent sidebar

  @happy
  Scenario: Pin favorites panel and verify it persists after clicking elsewhere
    Given the Favorites panel is open in Microsoft Edge
    When I click the "Pin favorites" button in the Favorites toolbar
    And I click on the web page content area
    Then the Favorites sidebar should remain visible

  # ============================================================
  # Expand Favorites Bar folder (flow 013)
  # ============================================================

  @happy
  Scenario: Expand the Favorites Bar folder
    Given the Favorites panel is open in Microsoft Edge
    When I click the "Favorites Bar" folder in the favorites list
    Then the Favorites Bar folder should expand
    And the child favorites should be visible

  # ============================================================
  # Click a Favorite item (flow 014)
  # ============================================================

  @happy
  Scenario: Open a favorite by clicking on it
    Given the Favorites panel is open in Microsoft Edge
    When I click the "Test Favorite" item in the favorites list
    Then the "Test Favorite" page should load in the browser

  # ============================================================
  # Open Favorites Page via More Options (flows 015, 036)
  # ============================================================

  @happy
  Scenario: Open Favorites Page via More Options menu
    Given the Favorites panel is open in Microsoft Edge
    When I click the "More options" button in the Favorites toolbar
    And I click the "Open Favorites Page" menu item
    Then the Favorites full page should open in a new tab

  @happy
  Scenario: Access More Options from the Favorites full page
    Given the Favorites full page is open in Microsoft Edge
    When I click the "More options" button on the Favorites full page
    Then a context menu with favorites management options should appear

  # ============================================================
  # Add Open Pages to Favorites (flow 017)
  # ============================================================

  @happy
  Scenario: Add all open pages to favorites via More Options
    Given the Favorites panel is open in Microsoft Edge
    When I click the "More options" button in the Favorites toolbar
    And I click the "Add Open Pages to Favorites..." menu item
    Then the "Add Open Pages to Favorites" dialog should appear

  # ============================================================
  # Import Favorites (flows 003, 019)
  # ============================================================

  @happy
  Scenario: Import favorites from the Favorites bar
    Given the New Tab page is open in Microsoft Edge
    When I click the "Import favorites" button in the Favorites bar
    Then the import favorites action should be triggered

  @happy
  Scenario: Import favorites via More Options menu
    Given the Favorites panel is open in Microsoft Edge
    When I click the "More options" button in the Favorites toolbar
    And I click the "Import favorites" menu item
    Then the "Import browser data" settings page should open

  # ============================================================
  # Export Favorites (flow 020)
  # ============================================================

  @happy
  Scenario: Export favorites via More Options menu
    Given the Favorites panel is open in Microsoft Edge
    When I click the "More options" button in the Favorites toolbar
    And I click the "Export favorites" menu item
    Then the "Export Favorites" save dialog should appear
    And the default file format should be HTML

  # ============================================================
  # Remove Duplicate Favorites (flow 021)
  # ============================================================

  @happy
  Scenario: Remove duplicate favorites via More Options menu
    Given the Favorites panel is open in Microsoft Edge
    When I click the "More options" button in the Favorites toolbar
    And I click the "Remove Duplicate Favorites" menu item
    Then the "Remove Duplicate Favorites" page should open

  @boundary
  Scenario: Remove duplicate favorites when no duplicates exist
    Given the Favorites panel is open in Microsoft Edge
    And there are no duplicate favorites
    When I click the "More options" button in the Favorites toolbar
    And I click the "Remove Duplicate Favorites" menu item
    Then the page should indicate that no duplicate favorites were found

  # ============================================================
  # Show Favorites Bar (flows 022, 024, 025, 026, 027)
  # ============================================================

  @happy
  Scenario: Open Show Favorites Bar submenu
    Given the Favorites panel is open in Microsoft Edge
    When I click the "More options" button in the Favorites toolbar
    And I hover over the "Show Favorites Bar" menu item
    Then the Show Favorites Bar submenu should appear
    And the submenu should contain "Always", "Never", and "Only on New Tabs"

  @happy
  Scenario: Set Favorites Bar to show always
    Given the Show Favorites Bar submenu is open in Microsoft Edge
    When I click the "Always" menu item
    Then the Favorites Bar should be visible on all pages
    And the Favorites panel should remain accessible

  @happy
  Scenario: Set Favorites Bar to never show
    Given the Show Favorites Bar submenu is open in Microsoft Edge
    When I click the "Never" menu item
    Then the Favorites Bar should be hidden on all pages

  @happy
  Scenario: Set Favorites Bar to show only on new tabs
    Given the Show Favorites Bar submenu is open in Microsoft Edge
    When I click the "Only on New Tabs" menu item
    Then the Favorites Bar should be visible only on new tab pages

  # ============================================================
  # Hide Favorites Button from Toolbar (flow 023)
  # ============================================================

  @happy
  Scenario: Hide the Favorites button from the toolbar
    Given the Favorites panel is open in Microsoft Edge
    When I click the "More options" button in the Favorites toolbar
    And I click the "Hide Favorites Button from Toolbar" menu item
    Then the "Favorites" button should be removed from the App bar

  # ============================================================
  # Right-click Context Menus (flows 004, 005, 006)
  # ============================================================

  @happy
  Scenario: Right-click on the Edit Favorite button shows context menu
    Given the New Tab page is open in Microsoft Edge
    When I right-click the "Edit favorite for this page" button in the App bar
    Then a context menu should appear with customization options

  @happy
  Scenario: Right-click on the Favorites button shows context menu
    Given the New Tab page is open in Microsoft Edge
    When I right-click the "Favorites" button in the App bar
    Then the Favorites context menu should appear

  @happy
  Scenario: Right-click on Import Favorites button shows context menu
    Given the New Tab page is open in Microsoft Edge
    When I right-click the "Import favorites" button in the Favorites bar
    Then the Import Favorites context menu should appear

  # ============================================================
  # State-dependent / Repeated action scenarios
  # ============================================================

  @happy
  Scenario: Pin favorites when already pinned (toggle unpin)
    Given the Favorites panel is pinned as a sidebar in Microsoft Edge
    When I click the "Unpin favorites" button in the Favorites toolbar
    Then the Favorites panel should return to overlay mode

  @happy
  Scenario: Add a favorite when the page is already favorited
    Given the current page is already in favorites in Microsoft Edge
    When I click the "Edit favorite for this page" button in the App bar
    Then the "Edit favorite" dialog should appear with the existing favorite name pre-filled
    And the "Remove" button should be available to delete the favorite

  @happy
  Scenario: Remove a favorite and verify it is no longer in the list
    Given the "Edit favorite" dialog is open in Microsoft Edge
    When I click the "Remove" button in the Edit favorite dialog
    Then the dialog should close
    And the removed favorite should no longer appear in the Favorites panel list
