"""Shared helpers for touch tests."""
import json
from contextlib import asynccontextmanager
from playwright.async_api import async_playwright

PRE = "import sys, json\nT = sys.modules['__main__']\nfrom AnyQt.QtWidgets import *\nfrom AnyQt.QtCore import *\n"


class S:
    pass


@asynccontextmanager
async def session(port, page="orange.html", test="test_touch3.py"):
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        ctx = await b.new_context(viewport={"width": 1180, "height": 820}, has_touch=True, accept_downloads=True)
        pg = await ctx.new_page()
        cdp = await ctx.new_cdp_session(pg)
        await cdp.send("Emulation.setTouchEmulationEnabled", {"enabled": True, "maxTouchPoints": 5})
        s = S(); s.pg = pg; s.logs = []
        pg.on("console", lambda m: s.logs.append(m.text))

        async def touch(kind, x, y):
            pts = [] if kind == "touchEnd" else [{"x": x, "y": y, "id": 1}]
            await cdp.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": pts})

        async def tap(x, y, hold=60):
            await touch("touchStart", x, y); await pg.wait_for_timeout(hold); await touch("touchEnd", x, y)
            await pg.wait_for_timeout(350)

        async def dtap(x, y, wait=2500):
            await touch("touchStart", x, y); await pg.wait_for_timeout(50); await touch("touchEnd", x, y)
            await pg.wait_for_timeout(120)
            await touch("touchStart", x + 5, y + 4); await pg.wait_for_timeout(50); await touch("touchEnd", x + 5, y + 4)
            await pg.wait_for_timeout(wait)

        async def drag(a, b2, steps=20, hold=150):
            await touch("touchStart", *a); await pg.wait_for_timeout(hold)
            for i in range(1, steps + 1):
                await touch("touchMove", a[0] + (b2[0] - a[0]) * i / steps, a[1] + (b2[1] - a[1]) * i / steps)
                await pg.wait_for_timeout(16)
            await touch("touchEnd", *b2); await pg.wait_for_timeout(900)

        async def hold(x, y, ms=800):
            await touch("touchStart", x, y); await pg.wait_for_timeout(ms)
            await touch("touchEnd", x, y); await pg.wait_for_timeout(500)

        async def py(code):
            return json.loads(await pg.evaluate("(c) => py.runPython(c)", PRE + code))

        async def keyboard_up():
            return await pg.evaluate("""() => {
                let a = document.activeElement;
                while (a && a.shadowRoot && a.shadowRoot.activeElement) a = a.shadowRoot.activeElement;
                return !!(a && a.classList && a.classList.contains('qt-window-input-element') && a.inputMode !== 'none');
            }""")
        s.touch, s.tap, s.dtap, s.drag, s.hold, s.py, s.keyboard_up = touch, tap, dtap, drag, hold, py, keyboard_up
        await pg.goto(f"http://localhost:{port}/{page}?test={test}")
        for _ in range(160):
            await pg.wait_for_timeout(500)
            if any("[test] setup ok" in l for l in s.logs): break
        await pg.wait_for_timeout(800)
        s.node = {}
        for n in ("f", "t", "k", "ts", "sp", "ds"):
            s.node[n] = await py(f"n = T.nodes['{n}']\njson.dumps(T.g(n.position[0], n.position[1]))")
        try:
            yield s
        finally:
            await b.close()
