# Roblox Rivals — Windows build

GitHub Actions builds this project as a Windows executable.

## Download
Open the Actions tab, select the latest successful build-rivals-aimbot run, and download the rivals-aimbot-exe artifact. Extract the ZIP to get rivals-aimbot.exe.

## Model note
The build bundles the generic yolov8n.pt fallback. For Roblox character detection, a compatible custom roblox.pt model should be placed beside the executable. The generic fallback is not trained specifically for Roblox Rivals, so it may not identify game characters reliably.

## Controls
- INSERT: toggle on/off
- Hold right mouse button: activate the aiming loop while enabled

The HUD is configured for monitor 2 and falls back to the last available monitor.
