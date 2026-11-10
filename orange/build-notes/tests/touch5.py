import sys, asyncio
from th import session
res = []
def check(n, ok, info=""):
    res.append(ok); print(("PASS " if ok else "FAIL ") + n + (f"  | {info}" if info != "" else ""))
DLG = """from orangecanvas.document.editlinksdialog import EditLinksDialog
d = [w for w in QApplication.topLevelWidgets() if isinstance(w, EditLinksDialog) and w.isVisible()][0]
"""
async def main():
    async with session(sys.argv[1], page=(sys.argv[2] if len(sys.argv) > 2 else "orange.html")) as s:
        py = s.py
        await py("import webpatches\nwebpatches.open_link_editor(T.doc, T.scheme, T.nodes['f'], T.nodes['t'])\njson.dumps(1)")
        await s.pg.wait_for_timeout(1000)
        g = await py(DLG + "g = d.geometry()\njson.dumps([g.x(), g.y(), g.width(), g.height()])")
        # double tap the title bar: a fixed-size dialog must not maximize
        await s.dtap(g[0] + 80, g[1] - 14, wait=1200)
        st = await py(DLG + "json.dumps([str(d.windowState()), d.width()])")
        check("double tap on title keeps size", "Maximized" not in st[0] and st[1] == g[2], st)
        # drag from File 'Data' to Data Table 'Data Subset'
        pts = await py(DLG + """w = d.scene.editWidget
src = w.sourceNodeWidget.channelAnchors[0]
snk = w.sinkNodeWidget.channelAnchors[1]
def gp(it):
    p = d.view.mapFromScene(it.sceneBoundingRect().center())
    q = d.view.viewport().mapToGlobal(p)
    return [q.x(), q.y()]
json.dumps([gp(src), gp(snk)])""")
        await s.drag(tuple(pts[0]), tuple(pts[1]), steps=20, hold=120)
        links = await py(DLG + "json.dumps([[a.name, b.name] for a, b in d.links()])")
        check("touch drag adds a link in Edit Links", ["Data", "Data Subset"] in links, links)
        await s.pg.screenshot(path="/home/claude/wasm/t5.png")
        print("SUMMARY %d/%d" % (sum(res), len(res)))
asyncio.run(main())
