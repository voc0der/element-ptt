#!/usr/bin/env python3
"""Cross-platform Element Desktop push-to-talk wrapper."""

import asyncio
import json
import os
import signal
import shutil
import subprocess
import sys
import time

from pynput import mouse
import requests
import websockets

# --- CONFIG ---
PTT_BUTTON_NAME = os.getenv("PTT_BUTTON", "mouse4").strip().lower()
DEBUG_PORT = int(os.getenv("DEBUG_PORT", "9222"))
GRACE_PERIOD = float(os.getenv("GRACE_PERIOD", "0.2"))

def resolve_ptt_button(raw_name):
    alias_map = {
        "mouse4": ("x1", "button8"),
        "mouse5": ("x2", "button9"),
        "btn_side": ("x1", "button8"),
        "btn_extra": ("x2", "button9"),
        "x1": ("x1", "button8"),
        "x2": ("x2", "button9"),
        "button8": ("button8", "x1"),
        "button9": ("button9", "x2"),
    }

    names = []
    if raw_name in alias_map:
        names.extend(alias_map[raw_name])
    names.append(raw_name)

    for name in names:
        if hasattr(mouse.Button, name):
            return getattr(mouse.Button, name), name

    if raw_name.isdigit():
        try:
            return mouse.Button(int(raw_name)), raw_name
        except Exception:
            pass

    available = ", ".join(sorted(mouse.Button.__members__.keys()))
    raise ValueError(
        f"Unsupported PTT_BUTTON '{raw_name}'. "
        f"Available for this platform: {available}."
    )


PTT_BUTTON, RESOLVED_PTT_BUTTON_NAME = resolve_ptt_button(PTT_BUTTON_NAME)

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
        self.loop = None
        self.stop_event = None
        self.listener = None
        self.shutting_down = False

    def get_element_cmd(self):
        debug_arg = f"--remote-debugging-port={DEBUG_PORT}"
        if sys.platform.startswith("win"):
            local = os.getenv("LOCALAPPDATA", "")
            candidates = [
                os.path.join(local, "Programs", "Element", "Element.exe"),
                os.path.join(os.getenv("ProgramFiles", ""), "Element", "Element.exe"),
                os.path.join(os.getenv("ProgramFiles(x86)", ""), "Element", "Element.exe"),
            ]
            for candidate in candidates:
                if candidate and os.path.exists(candidate):
                    return [candidate, debug_arg]
            for name in ("Element.exe", "element-desktop.exe", "element.exe"):
                path = shutil.which(name)
                if path:
                    return [path, debug_arg]
            raise RuntimeError("Could not find Element.exe. Install Element Desktop first.")

        for name in ("element-desktop", "element"):
            path = shutil.which(name)
            if path:
                return [path, debug_arg]
        return ["element-desktop", debug_arg]

    def get_ws_url(self):
        for _ in range(30):
            try:
                tabs = requests.get(f"http://localhost:{DEBUG_PORT}/json", timeout=1).json()
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

    def _on_listener_click(self, _x, _y, button, pressed):
        if button != PTT_BUTTON or not self.loop or self.shutting_down:
            return
        muted = not pressed
        try:
            future = asyncio.run_coroutine_threadsafe(self.set_mute(muted), self.loop)
            future.add_done_callback(self._on_mute_callback_done)
        except RuntimeError:
            pass

    @staticmethod
    def _on_mute_callback_done(future):
        try:
            future.result()
        except Exception as exc:
            print(f"PTT callback error: {exc}")

    def start_listener(self):
        self.listener = mouse.Listener(on_click=self._on_listener_click)
        self.listener.start()
        print(
            "Global listener active on mouse button: "
            f"{PTT_BUTTON_NAME} (resolved to {RESOLVED_PTT_BUTTON_NAME})"
        )

    def stop_listener(self):
        if self.listener:
            self.listener.stop()
            self.listener = None

    async def set_mute(self, muted: bool):
        if muted == self.is_muted:
            return
        if muted:
            await asyncio.sleep(GRACE_PERIOD)
        result = await self.send_js(JS_MUTE)
        if result == "toggled":
            self.is_muted = muted
            print(f"{'MUTED' if muted else 'LIVE'}")

    def _terminate_element(self):
        if not self.element_proc:
            return
        if self.element_proc.poll() is not None:
            return
        self.element_proc.terminate()
        try:
            self.element_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.element_proc.kill()
            self.element_proc.wait(timeout=5)

    async def run(self):
        self.stop_event = asyncio.Event()
        cmd = self.get_element_cmd()
        print("Starting Element Desktop...")
        self.element_proc = subprocess.Popen(cmd)
        print("Waiting for DevTools connection...")
        ws_url = self.get_ws_url()
        self.ws = await websockets.connect(ws_url)
        print("Connected! Hold Mouse4 to talk.")
        self.start_listener()
        try:
            while not self.stop_event.is_set():
                if self.element_proc and self.element_proc.poll() is not None:
                    print("Element exited; stopping listener.")
                    self.stop_event.set()
                    break
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        finally:
            self.shutting_down = True
            self.stop_listener()
            if self.ws:
                await self.ws.close()
            self._terminate_element()

    def start(self):
        loop = asyncio.new_event_loop()
        self.loop = loop

        def shutdown(*_):
            self.shutting_down = True
            if self.stop_event:
                loop.call_soon_threadsafe(self.stop_event.set)

        signal.signal(signal.SIGINT, shutdown)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, shutdown)

        try:
            loop.run_until_complete(self.run())
        finally:
            loop.close()

if __name__ == "__main__":
    PushToTalk().start()
