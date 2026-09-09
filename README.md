# OSRS Quest Navigator — External Windows Overlay

A standalone companion overlay for Old School RuneScape. It does **not** inject into the game, automate clicks, or control the character.

## What this build does
- Runs as a normal Windows desktop app.
- Always-on-top, borderless overlay window that can be moved/resized.
- Quest checklist with prerequisite-aware ordering.
- Ironman-friendly profile flag.
- Searchable quest list.
- Route cards with next objective, destination, and notes.
- Manual waypoint editor so you can place a route over the OSRS client/map.
- Saves settings locally.

## Important limitation
A completely external app cannot reliably obtain OSRS world coordinates, quest-state variables, NPC/object IDs, and collision/pathing data from the official client without a supported data bridge. This build therefore does not pretend to have invisible game-state access. The overlay is ready for a future bridge/import layer and provides manual route calibration.

## Install
Use the GitHub Actions artifact. Open **Actions** -> **Build Windows EXE** -> open the completed run -> download **OSRSQuestNavigator-Windows**. Extract it and double-click `OSRSQuestNavigator.exe`.

## Controls
- `F8`: show/hide overlay
- `F9`: toggle click-through mode
- Drag the title bar to move the overlay.
- Use the sidebar to select a quest.
- Waypoints can be added from the Waypoints tab.

## Extending it
The data format is in `data/quests.json`. Each quest has prerequisites and route steps. The route engine can later be connected to a coordinate/collision provider without changing the UI.
