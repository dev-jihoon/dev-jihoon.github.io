import sys, asyncio
from th import session
res = []
def check(n, ok, info=""):
    res.append(ok); print(("PASS " if ok else "FAIL ") + n + (f"  | {info}" if info != "" else ""))
W = "T.scheme.widget_manager.widget_for_node(T.nodes['{}'])"
async def main():
    async with session(sys.argv[1], page=(sys.argv[2] if len(sys.argv) > 2 else "orange.html"), test="test_touch4.py") as s:
        py, tap, dtap, drag = s.py, s.tap, s.dtap, s.drag
        async def close(n):
            xy = await py(f"w = {W.format(n)}\ng_ = w.geometry()\njson.dumps([g_.right() - 10, g_.top() - 14])")
            await tap(*xy)
        # quick taps on two different widgets are not a double tap
        async def vis():
            return await py("json.dumps(sorted(w.windowTitle() for w in QApplication.topLevelWidgets() if w.isVisible()))")
        v0 = await vis()
        await s.touch("touchStart", *s.node["t"]); await s.pg.wait_for_timeout(50); await s.touch("touchEnd", *s.node["t"])
        await s.pg.wait_for_timeout(150)
        await s.touch("touchStart", *s.node["f"]); await s.pg.wait_for_timeout(50); await s.touch("touchEnd", *s.node["f"])
        await s.pg.wait_for_timeout(1500)
        sel = await py("json.dumps([n.title for n in T.doc.selectedNodes()])")
        check("two quick taps on different widgets open nothing", await vis() == v0, await vis())
        check("the second tapped widget is selected", sel == ["File"], sel)
        await tap(*s.node["k"])
        await dtap(*s.node["ts"])
        check("tap one widget, then double tap another opens the other", any(x.startswith("Data Table") for x in await vis()) and len(await vis()) == len(v0) + 1, await vis())
        await close('ts')
        # Data Table: scroll with a finger, then tap a row selects it
        await dtap(*s.node["t"])
        v = await py(f"w = {W.format('t')}\nv = [v for v in w.findChildren(QTableView) if v.isVisible()][0]\nr = v.viewport().rect()\np = v.viewport().mapToGlobal(r.center())\njson.dumps([p.x(), p.y(), v.verticalScrollBar().value()])")
        await drag((v[0], v[1] + 100), (v[0], v[1] - 100), steps=15, hold=30)
        sb = await py(f"w = {W.format('t')}\nv = [v for v in w.findChildren(QTableView) if v.isVisible()][0]\njson.dumps([v.verticalScrollBar().value(), len(v.selectionModel().selectedRows())])")
        check("finger drag scrolls the table", sb[0] > v[2] + 100, (v[2], sb))
        check("scrolling does not select rows", sb[1] == 0, sb)
        await tap(v[0], v[1])
        sel = await py(f"w = {W.format('t')}\nv = [v for v in w.findChildren(QTableView) if v.isVisible()][0]\njson.dumps(len(v.selectionModel().selectedRows()))")
        check("tap selects a row", sel == 1, sel)
        await s.pg.screenshot(path="/home/claude/wasm/t4_1.png")
        await close('t')
        # Select Columns: tap a feature, tap the move button -> it is removed from features
        await dtap(*s.node["k"])
        await s.pg.wait_for_timeout(500)
        it = await py(f"""w = {W.format('k')}
v = w.used_attrs_view
m = v.model()
r = v.visualRect(m.index(0, 0)); p = v.viewport().mapToGlobal(r.center())
json.dumps([p.x(), p.y(), m.rowCount()])""")
        await tap(it[0], it[1])
        btn = await py(f"""w = {W.format('k')}
b = w.move_attr_button
p = b.mapToGlobal(b.rect().center()); json.dumps([p.x(), p.y()])""")
        await tap(*btn)
        n2 = await py(f"w = {W.format('k')}\njson.dumps(w.used_attrs_view.model().rowCount())")
        check("Select Columns: tap item + arrow moves it", n2 == it[2] - 1, (it[2], n2))
        await s.pg.screenshot(path="/home/claude/wasm/t4_2.png")
        await close('k')
        # Scatter plot: drag a rectangle to select points
        await dtap(*s.node["sp"])
        await s.pg.wait_for_timeout(800)
        pr = await py(f"""w = {W.format('sp')}
gv = w.graph.plot_widget
r = gv.rect(); p = gv.mapToGlobal(r.center()); json.dumps([p.x(), p.y(), r.width(), r.height()])""")
        await drag((pr[0] - pr[2] // 4, pr[1] - pr[3] // 4), (pr[0] + pr[2] // 4, pr[1] + pr[3] // 4), steps=20)
        await s.pg.wait_for_timeout(800)
        nsel = await py(f"w = {W.format('sp')}\nimport numpy as np\nsel = w.graph.selection\njson.dumps(int((sel > 0).sum()) if sel is not None else 0)")
        check("Scatter plot: finger drag selects points", nsel > 0, nsel)
        await s.pg.screenshot(path="/home/claude/wasm/t4_3.png")
        await close('sp')
        # toolbox: tap a widget button adds it; drag one onto the canvas adds it there
        nb = await py("json.dumps(len(T.scheme.nodes))")
        tb = await py("""from AnyQt.QtWidgets import QToolButton
mw_ = T._orange_main[1]
bs = [b for b in mw_.findChildren(QToolButton) if b.isVisible() and b.text().replace('\\n', ' ') in ('Data Table',)]
p = bs[0].mapToGlobal(bs[0].rect().center()); json.dumps([p.x(), p.y()])""")
        await tap(*tb)
        await s.pg.wait_for_timeout(600)
        na = await py("json.dumps(len(T.scheme.nodes))")
        check("tap on toolbox adds a widget", na == nb + 1, (nb, na))
        await drag(tb, (900, 650), steps=25, hold=80)
        await s.pg.wait_for_timeout(600)
        nc = await py("json.dumps(len(T.scheme.nodes))")
        check("drag from toolbox onto canvas adds a widget", nc == na + 1, (na, nc))
        await s.pg.screenshot(path="/home/claude/wasm/t4_4.png")
        print("\nSUMMARY %d/%d" % (sum(res), len(res)))
        errs = [l for l in s.logs if "Traceback" in l]
        if errs:
            i = s.logs.index(errs[0]); print("\n".join(s.logs[i:i+25]))
asyncio.run(main())
