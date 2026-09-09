# Build the Windows EXE

This project includes a GitHub Actions workflow that builds a single Windows executable on a Windows runner. No Python is needed on your PC to run the finished EXE.

## Easiest method
1. Open the GitHub repository and click **Actions**.
2. Select **Build Windows EXE**.
3. Click the latest workflow run.
4. When it finishes with a green check, scroll to **Artifacts**.
5. Download **OSRSQuestNavigator-Windows**.
6. Extract the downloaded ZIP.
7. Double-click **OSRSQuestNavigator.exe**.

The workflow uses PyInstaller's `--onefile --windowed` mode.

## Important
The current project is the starter external overlay. It does not yet have full live OSRS map-coordinate tracking or the complete quest database. Those are subsequent development steps.
