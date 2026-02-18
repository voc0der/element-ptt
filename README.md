# Element PTT

Push-to-talk wrapper for Element Desktop on Arch Linux (KDE). Hold Mouse4 to unmute, release to mute — works globally, even during Moonlight game streaming.

## How it works

The wrapper launches Element Desktop with Chrome DevTools Protocol (CDP) debugging enabled, then uses `evdev` to listen for a global key press at the kernel level. On press/release it reaches into Element's embedded call iframe and clicks the mute button via CDP.

## Install

```bash
# Dependencies
sudo pacman -S python python-pip element-desktop
pip install websockets requests evdev --break-system-packages

# Add yourself to the input group (required for global key capture)
sudo usermod -aG input $USER
# Log out and back in for this to take effect
```

## Setup

```bash
# Install the script
mkdir -p ~/.local/bin
cp element-ptt ~/.local/bin/element-ptt
chmod +x ~/.local/bin/element-ptt

# Install the .desktop file for KDE
cp element-ptt.desktop ~/.local/share/applications/
kbuildsycoca6 --noincremental
```

Search "Element PTT" in your KDE app launcher.

## Configuration

Edit `~/.local/bin/element-ptt` to change these values at the top of the file:

| Variable | Default | Description |
|---|---|---|
| `PTT_KEY` | `BTN_SIDE` (Mouse 4) | Key or button to hold for push-to-talk |
| `DEBUG_PORT` | `9222` | CDP debugging port |
| `GRACE_PERIOD` | `0.2` | Seconds to wait before muting on release |

### Common key alternatives

```python
PTT_KEY = evdev.ecodes.BTN_SIDE     # Mouse 4
PTT_KEY = evdev.ecodes.BTN_EXTRA    # Mouse 5
PTT_KEY = evdev.ecodes.KEY_SCROLLLOCK
PTT_KEY = evdev.ecodes.KEY_PAUSE
```

Run `evtest` to find the keycode for any key or button on your devices.

## Troubleshooting

**"No mouse with side buttons found"**
- Make sure you're in the `input` group: `groups | grep input`
- Log out and back in after adding yourself to the group

**Button click not working / "not_found"**
- The mute button lives inside an iframe. If Element updates their DOM, you may need to update the selector. Open DevTools (`Ctrl+Shift+I`) in Element during a call and inspect the mic button.

**CDP connection failing**
- Check if the debug port is reachable: `curl http://localhost:9222/json`
- Make sure no other Electron app is already using port 9222

**Moonlight / game streaming**
- Works as long as Moonlight doesn't exclusively grab your input device. If Discord PTT works during streaming, this will too.

## How it compares to Discord PTT

Discord uses the same `evdev` approach on Linux. This wrapper is functionally equivalent — global capture, grace period on release, works during game streaming.

## License

MIT