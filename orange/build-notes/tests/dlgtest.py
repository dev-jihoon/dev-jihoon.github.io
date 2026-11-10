import sys, asyncio, json, time
from playwright.async_api import async_playwright
PRE = "import sys, json\nT = sys.modules['__main__']\nfrom AnyQt.QtWidgets import *\nfrom AnyQt.QtCore import *\n"
res = []
def check(n, ok, info=""):
    res.append(ok); print(("PASS " if ok else "FAIL ") + n + (f"  | {info}" if info != "" else ""))
async def main():
    port = sys.argv[1]
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        ctx = await b.new_context(viewport={"width": 1280, "height": 800}, accept_downloads=True)
        pg = await ctx.new_page()
        logs = []; pg.on("console", lambda m: logs.append(m.text))
        await pg.goto(f"http://localhost:{port}/orange.html?test=test_touch3.py")
        for _ in range(160):
            await pg.wait_for_timeout(500)
            if any("[test] setup ok" in l for l in logs): break
        await pg.wait_for_timeout(800)
        async def py(c):
            return json.loads(await pg.evaluate("(c) => py.runPython(c)", PRE + c))
        vis = "json.dumps(sorted(w.windowTitle() for w in QApplication.topLevelWidgets() if w.isVisible()))"
        # 1. an error shows the box and Orange keeps working
        await py("QTimer.singleShot(0, lambda: 1/0)\njson.dumps(1)")
        await pg.wait_for_timeout(1500)
        t0 = time.time(); v = await py(vis); dt = time.time() - t0
        check("error box shown", "Error Encountered" in v, v)
        check("still responsive", dt < 2, round(dt, 2))
        await pg.screenshot(path="/home/claude/wasm/d1.png")
        await py("""bs = [w for w in QApplication.topLevelWidgets() if w.isVisible() and w.windowTitle() == 'Error Encountered']
[b.close() for b in bs]
json.dumps(1)""")
        # 2. Save Workflow Image as SVG downloads
        try:
            async with pg.expect_download(timeout=5000) as dl:
                await py("T._orange_main[1].save_as_svg_action.trigger()\njson.dumps(1)")
            d = await dl.value
            check("SVG download", d.suggested_filename.endswith(".svg"), d.suggested_filename)
        except Exception as e:
            check("SVG download", False, str(e)[:100])
        # 3. a question asked from a slot: answered by the user, the slot runs again with the answer
        await py("""
class Asker(QObject):
    def ask(self):
        r = QMessageBox.question(None, "Question", "Continue?")
        T.answers.append(r.name if hasattr(r, 'name') else str(r))
T.answers = []; T.asker = Asker()
T.asker.ask()
json.dumps(T.answers)""")
        print("first answers", await py("json.dumps(T.answers)"))
        await pg.wait_for_timeout(500)
        await py("""bs = [w for w in QApplication.topLevelWidgets() if w.isVisible() and w.windowTitle() == 'Question']
b = bs[0].button(QMessageBox.StandardButton.Yes); b.click()
json.dumps(1)""")
        await pg.wait_for_timeout(500)
        a = await py("json.dumps(T.answers)")
        check("question answer reaches the slot", a == ["No", "Yes"], a)
        # 4. CSV File Import: browse -> picker -> Import Options -> data
        await py("""from orangecanvas.registry import global_registry
d = T.doc.createNewNode(global_registry().widget('Orange.widgets.data.owcsvimport.OWCSVFileImport'), position=(600, 80))
T.csvnode = d
w = T.scheme.widget_manager.widget_for_node(d); w.show()
json.dumps(1)""")
        await pg.wait_for_timeout(800)
        try:
            async with pg.expect_file_chooser(timeout=5000) as fc:
                await py("T.scheme.widget_manager.widget_for_node(T.csvnode).browse()\njson.dumps(1)")
            ch = await fc.value
            await ch.set_files("/tmp/small.csv")
            await pg.wait_for_timeout(1500)
            v = await py(vis)
            check("Import Options dialog shown", "Import Options - Orange" in v or "Import Options" in v, v)
            await pg.screenshot(path="/home/claude/wasm/d2.png")
            await py("""bs = [w for w in QApplication.topLevelWidgets() if w.isVisible() and w.windowTitle() == 'Import Options']
bs[0].accept()
json.dumps(1)""")
            await pg.wait_for_timeout(3000)
            n = await py("w = T.scheme.widget_manager.widget_for_node(T.csvnode)\nfrom Orange.data import Table\njson.dumps(str(w.current_item().path()) if w.current_item() else None)")
            check("CSV file selected", n is not None and n.endswith("small.csv"), n)
        except Exception as e:
            check("CSV import chooser", False, str(e)[:120])
        # 5. Help > Example Workflows opens
        await py("T._orange_main[1].examples_dialog()\njson.dumps(1)")
        await pg.wait_for_timeout(1500)
        v = await py(vis)
        check("Example Workflows dialog", any("Example Workflows" in x for x in v), v)
        await pg.screenshot(path="/home/claude/wasm/d3.png")
        # 6. Save Data widget: Save As downloads the file
        await py("""from orangecanvas.registry import global_registry
from orangecanvas.scheme import SchemeLink
reg = global_registry()
n = T.doc.createNewNode(reg.widget('Orange.widgets.data.owsave.OWSave'), position=(700, 600))
f = T.nodes['f']
T.doc.addLink(SchemeLink(f, f.output_channel('Data'), n, n.input_channel('Data')))
T.savenode = n
json.dumps(1)""")
        await pg.wait_for_timeout(1500)
        try:
            async with pg.expect_download(timeout=8000) as dl:
                await py("T.scheme.widget_manager.widget_for_node(T.savenode).save_file_as()\njson.dumps(1)")
            d = await dl.value
            check("Save Data download", d.suggested_filename.endswith((".tab", ".csv", ".xlsx", ".pkl", ".gz")), d.suggested_filename)
        except Exception as e:
            check("Save Data download", False, str(e)[:120])
        print("SUMMARY %d/%d" % (sum(res), len(res)))
        for l in logs:
            if "Traceback" in l or "Error" in l[:40]: print("LOG", l[:300])
        await b.close()
asyncio.run(main())
