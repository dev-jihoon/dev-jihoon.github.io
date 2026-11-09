import sys, asyncio, base64
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        pg = await b.new_page(viewport={"width": 1180, "height": 820})
        logs = []
        pg.on("console", lambda m: logs.append(m.text))
        await pg.goto(f"http://localhost:{sys.argv[1]}/orange.html")
        for _ in range(120):
            await pg.wait_for_timeout(1000)
            if any("[boot] ready" in l for l in logs): break
        r = await pg.evaluate("""() => py.runPython(`
import base64, os
from orangecanvas import config
p = os.path.join(config.cache_dir(), "widget-registry.pck")
base64.b64encode(open(p, "rb").read()).decode()
`)""")
        open(sys.argv[2], "wb").write(base64.b64decode(r))
        print("saved", len(base64.b64decode(r)))
        await b.close()
asyncio.run(main())
