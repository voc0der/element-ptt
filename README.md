# Element PTT

Cross-platform push-to-talk wrapper for Element Desktop. Hold Mouse4 to unmute, release to mute.

## How it works

The wrapper launches Element Desktop with Chrome DevTools Protocol (CDP) debugging enabled, then uses `pynput` global mouse hooks to detect Mouse4 press/release. On press/release it reaches into Element's embedded call iframe and clicks the mute button via CDP.

## Install

### Linux (Arch example)

```bash
sudo pacman -S python python-pip element-desktop
pip install websockets requests pynput --break-system-packages
```

### Windows

```powershell
py -m pip install websockets requests pynput
# Install Element Desktop from https://element.io/download
```

## Setup

```bash
mkdir -p ~/.local/bin
cp element-ptt.py ~/.local/bin/element-ptt.py
chmod +x ~/.local/bin/element-ptt.py

# Run
python3 ~/.local/bin/element-ptt.py
```

Optional on Linux: `./element-ptt.sh` is a thin wrapper that just runs `element-ptt.py`.

On Windows, run:

```powershell
py .\element-ptt.py
```

## Configuration

Set environment variables:

| Variable | Default | Description |
|---|---|---|
| `PTT_BUTTON` | `mouse4` | Mouse button alias (`mouse4`, `mouse5`) or native name (`x1`, `x2`, `button8`, `button9`, etc.) |
| `DEBUG_PORT` | `9222` | CDP debugging port |
| `GRACE_PERIOD` | `0.2` | Seconds to wait before muting on release |

Examples:

```bash
PTT_BUTTON=mouse5 python3 element-ptt.py
```

```powershell
$env:PTT_BUTTON="x2"; py .\element-ptt.py
```

On Linux/X11, side buttons are often reported as `button8` and `button9`.

## Troubleshooting

**Element launch fails on Windows**
- Default path is `%LOCALAPPDATA%\Programs\Element\Element.exe`
- Reinstall Element Desktop if the executable is missing

**Button click not working / "not_found"**
- The mute button lives inside an iframe. If Element updates their DOM, you may need to update the selector. Open DevTools (`Ctrl+Shift+I`) in Element during a call and inspect the mic button.

**CDP connection failing**
- Check if the debug port is reachable: `curl http://localhost:9222/json`
- Make sure no other Electron app is already using port 9222

**Global input not detected**
- Some anti-cheat protected games can block all injected/global hooks.
- Outside those cases, `pynput` should work system-wide on both Linux and Windows.

## License

MIT
