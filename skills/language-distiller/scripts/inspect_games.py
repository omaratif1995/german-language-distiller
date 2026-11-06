#!/usr/bin/env python3
"""Play every game of a built study app in headless Chrome at phone size, the way a hurried thumb does.

usage: inspect_games.py STUDY_APP.html [--units L01,L02] [--answers 10] [--browser PATH] [--json]

It opens the app at 375 x 812 with touch, runs check_games.js on every unit (or the --units given) and reports a
right answer shown as wrong, a Hör-Bingo call with two right answers, a Satzbau sentence that makes no sense, two
equal meanings in Wortpaare, an option shown twice, a progress bar or streak that does not move, and a mistakes round
that does not bring back what was missed. Exit code 1 on any problem. Needs Chrome or Edge, and aiohttp (installed
with edge-tts); no Node.js.
"""
from __future__ import annotations

import argparse
import asyncio
import itertools
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

CHECKER = Path(__file__).with_name("check_games.js")
BROWSERS = ["chrome", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "msedge", "microsoft-edge",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
PHONE = {"width": 375, "height": 812, "deviceScaleFactor": 2, "mobile": True}
SECONDS_PER_UNIT = 300                       # a unit takes about a minute; this is the limit, not the plan


class InspectError(RuntimeError):
    pass


def find_browser(given=None):
    for name in ([given] if given else BROWSERS):
        found = shutil.which(name) or (name if Path(name).is_file() else None)
        if found:
            return found
    raise InspectError("no Chrome or Edge found: pass --browser PATH")


def start_browser(browser, profile):
    """Headless Chrome with a DevTools port of its own choosing; returns the process and the browser's websocket."""
    process = subprocess.Popen([browser, "--headless=new", "--no-first-run", "--no-default-browser-check",
                                "--disable-background-networking", "--disable-component-update", "--disable-sync",
                                "--autoplay-policy=no-user-gesture-required", "--mute-audio",
                                "--remote-debugging-port=0", f"--user-data-dir={profile}", "about:blank"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    port_file, end = Path(profile) / "DevToolsActivePort", time.time() + 30
    while time.time() < end:
        if port_file.is_file() and len(port_file.read_text().split()) >= 2:
            port, path = port_file.read_text().split()[:2]
            return process, f"ws://127.0.0.1:{port}{path}"
        if process.poll() is not None:
            raise InspectError(f"the browser exited at start ({process.returncode})")
        time.sleep(0.1)
    process.kill()
    raise InspectError("the browser did not open a DevTools port")


async def within(seconds, waiting, what):
    """Await `waiting`, or raise an InspectError that says what did not happen in time: a bare timeout says nothing."""
    try:
        return await asyncio.wait_for(waiting, seconds)
    except asyncio.TimeoutError:
        raise InspectError(f"{what} within {seconds:g} s") from None


async def inspect(app, browser, units=None, answers=10):
    import aiohttp
    checker = CHECKER.read_text(encoding="utf-8")
    profile = tempfile.mkdtemp(prefix="language-distiller-games-")
    process, endpoint = start_browser(browser, profile)
    try:
        async with aiohttp.ClientSession() as http, http.ws_connect(endpoint, max_msg_size=0) as socket:
            pending, loaded, ids = {}, asyncio.Event(), itertools.count(1)

            async def read():
                async for message in socket:
                    data = json.loads(message.data)
                    if data.get("id") in pending:
                        pending.pop(data["id"]).set_result(data)
                    elif data.get("method") == "Page.loadEventFired":
                        loaded.set()
            reader = asyncio.create_task(read())

            async def call(method, params=None, session=None, timeout=30, late=None):
                key = next(ids)
                pending[key] = asyncio.get_running_loop().create_future()
                await socket.send_json({"id": key, "method": method, "params": params or {},
                                        **({"sessionId": session} if session else {})})
                reply = await within(timeout, pending[key], late or f"the browser did not answer {method}")
                if "error" in reply:
                    raise InspectError(f"{method}: {reply['error'].get('message')}")
                return reply.get("result", {})

            target = (await call("Target.createTarget", {"url": "about:blank"}))["targetId"]
            page = (await call("Target.attachToTarget", {"targetId": target, "flatten": True}))["sessionId"]
            await call("Page.enable", session=page)
            await call("Emulation.setDeviceMetricsOverride", PHONE, page)
            await call("Emulation.setTouchEmulationEnabled", {"enabled": True, "maxTouchPoints": 5}, page)
            await call("Page.navigate", {"url": Path(app).resolve().as_uri()}, page)
            await within(120, loaded.wait(), "the app did not finish loading")    # a course with audio is 40-130 MB
            chosen = json.dumps(units) if units else "[...document.getElementById('pick').options].map(o => o.value)"
            count = len(units) if units else (await call("Runtime.evaluate", {
                "expression": "document.getElementById('pick').options.length", "returnByValue": True}, page))["result"]["value"]
            evaluated = await call("Runtime.evaluate", {
                "expression": f"window.GAME_CHECK = {{units: {chosen}, answers: {int(answers)}}};\n{checker}",
                "awaitPromise": True, "returnByValue": True}, page, timeout=60 + SECONDS_PER_UNIT * count,
                late=f"the games of {count} unit(s) did not finish")
            if evaluated.get("exceptionDetails"):
                raise InspectError(json.dumps(evaluated["exceptionDetails"])[:500])
            reader.cancel()
            return evaluated["result"]["value"]
    finally:
        process.kill()
        process.wait()
        shutil.rmtree(profile, ignore_errors=True)


def summary(result):
    """One line per unit: what was played and found."""
    lines = []
    for unit, games in result["units"].items():
        parts = [f"{key} " + ", ".join(f"{name} {value}" for name, value in stats.items())
                 for key, stats in games.items() if stats]
        lines.append(f"{unit}: " + " | ".join(parts))
    lines += [f"PROBLEM: {problem}" for problem in result["problems"]]
    lines.append(f"{'PASS' if result['passed'] else 'FAIL'}: {len(result['units'])} units, {len(result['problems'])} problems")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("app", type=Path)
    parser.add_argument("--units", help="comma-separated unit ids (default: every unit)")
    parser.add_argument("--answers", type=int, default=10, help="answers to give in the timed article game")
    parser.add_argument("--browser", help="path to Chrome or Edge")
    parser.add_argument("--json", action="store_true", help="print the full report as JSON")
    args = parser.parse_args(argv)
    try:
        if not args.app.is_file():
            raise InspectError(f"no such app: {args.app}")
        result = asyncio.run(inspect(args.app, find_browser(args.browser),
                                     args.units.split(",") if args.units else None, args.answers))
    except (InspectError, OSError, asyncio.TimeoutError) as error:
        print(f"FAIL: {str(error) or type(error).__name__}", file=sys.stderr)     # never an empty reason
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=1) if args.json else summary(result))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
