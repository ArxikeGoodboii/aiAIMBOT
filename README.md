# aimbot

YOLOv8 screen-scan project. GitHub Actions builds a Windows executable.

## Build

Push to `main`, or run **Build Windows EXE** manually from the Actions tab. The output is uploaded as the `aimbot-exe` artifact.

## Controls

- `INSERT`: toggle the application on/off
- Hold right mouse button while enabled to activate its screen-targeting behavior

## Configuration

Edit the constants at the top of `aimbot/main.py`. The build downloads the standard YOLOv8n model weights during the workflow; the weights are not committed to the repository.
