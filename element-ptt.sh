#!/usr/bin/env python3
"""Element Desktop push-to-talk wrapper for Arch Linux."""

import asyncio
import json
import subprocess
import signal
import sys
import time
import requests
import evdev
import websockets

# --- CONFIG ---
PTT_KEY = evdev.ecodes.BTN_SIDE  # Mouse 4
DEBUG_PORT = 9222
ELEMENT_CMD = ["element-desktop", f"--remote-debugging-port={DEBUG_PORT}"]

JS_MUTE = """
(() => {
    const iframe = document.querySelector('iframe');
    if (!iframe || !iframe.contentDocument) return 'no_iframe';
    const btn = iframe.contentDocument.querySelector('[data-testid="incall_mute"]');
    if (btn) btn.click();
    return btn ? 'toggled' : 'not_found';
})()
"""

class PushToTalk:
    def __init__(self):
        self.ws = None
        self.is_muted = True
        self.element_proc = None

    def find_device(self):
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        for dev in devices:
            if evdev.ecodes.BTN_SIDE in dev.capabilities().get(evdev.ecodes.EV_KEY, []):
                print(f"Using input device: {dev.name} ({dev.path})")
                return dev
        raise RuntimeError("No mouse with side buttons found. Are you in the 'input' group?")

    def get_ws_url(self):
        for _ in range(30):
            try:
                tabs = requests.get(f"http://localhost:{DEBUG_PORT}/json").json()
                for tab in tabs:
                    if tab.get("type") == "page":
                        return tab["webSocketDebuggerUrl"]
            except Exception:
                time.sleep(1)
        raise RuntimeError("Couldn't connect to Element DevTools")

    async def send_js(self, expression):
        if not self.ws:
            return
        try:
            await self.ws.send(json.dumps({
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": expression}
            }))
            resp = json.loads(await asyncio.wait_for(self.ws.recv(), timeout=2))
            return resp.get("result", {}).get("result", {}).get("value")
        except Exception as e:
            print(f"CDP error: {e}")

    async def set_mute(self, muted: bool):
        if muted == self.is_muted:
            return
        if muted:
            await asyncio.sleep(0.2)  # 200ms grace period before muting
        result = await self.send_js(JS_MUTE)
        if result == "toggled":
            self.is_muted = muted
            print(f"{'MUTED' if muted else 'LIVE'}")

    async def run(self):
        print("Starting Element Desktop...")
        self.element_proc = subprocess.Popen(ELEMENT_CMD)
        print("Waiting for DevTools connection...")
        ws_url = self.get_ws_url()
        self.ws = await websockets.connect(ws_url)
        print("Connected! Hold Mouse4 to talk.")
        dev = self.find_device()
        try:
            async for event in dev.async_read_loop():
                if event.type == evdev.ecodes.EV_KEY and event.code == PTT_KEY:
                    if event.value == 1:
                        await self.set_mute(False)
                    elif event.value == 0:
                        await self.set_mute(True)
        except asyncio.CancelledError:
            pass
        finally:
            if self.ws:
                await self.ws.close()

    def start(self):
        loop = asyncio.new_event_loop()
        def shutdown(*_):
            if self.element_proc:
                self.element_proc.terminate()
            loop.stop()
            sys.exit(0)
        signal.signal(signal.SIGINT, shutdown)
        signal.signal(signal.SIGTERM, shutdown)
        loop.run_until_complete(self.run())

if __name__ == "__main__":
    PushToTalk().start()
