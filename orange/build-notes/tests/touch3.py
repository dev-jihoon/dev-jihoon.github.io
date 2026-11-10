"""Touch-only walkthrough of common Orange tasks (Chrome touch emulation)."""
import sys, asyncio, json
from playwright.async_api import async_playwright

PORT, PAGE = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "orange.html")
OUT = "/home/claude/wasm/tt_"
results = []


def check(name, ok, info=""):
    results.append((name, ok))
    print(("PASS " if ok else "FAIL ") + name + (("  | " + str(info)) if info else ""))


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        ctx = await b.new_context(viewport={"width": 1180, "height": 820}, has_touch=True,
                                  accept_downloads=True)
        pg = await ctx.new_page()
        cdp = await ctx.new_cdp_session(pg)
        await cdp.send("Emulation.setTouchEmulationEnabled", {"enabled": True, "maxTouchPoints": 5})
        logs = []
        pg.on("console", lambda m: logs.append(m.text))

        async def touch(kind, x, y):
            pts = [] if kind == "touchEnd" else [{"x": x, "y": y, "id": 1}]
            await cdp.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": pts})

        async def tap(x, y, hold=60):
            await touch("touchStart", x, y); await pg.wait_for_timeout(hold); await touch("touchEnd", x, y)
            await pg.wait_for_timeout(350)

        async def dtap(x, y):
            await touch("touchStart", x, y); await pg.wait_for_timeout(50); await touch("touchEnd", x, y)
            await pg.wait_for_timeout(120)
            await touch("touchStart", x + 5, y + 4); await pg.wait_for_timeout(50); await touch("touchEnd", x + 5, y + 4)
            await pg.wait_for_timeout(2500)

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
            return json.loads(await pg.evaluate("(c) => py.runPython(c)", code))

        async def keyboard_up():
            # would the on-screen keyboard be shown? (Qt focused its <input>)
            return await pg.evaluate("""() => {
                let a = document.activeElement;
                while (a && a.shadowRoot && a.shadowRoot.activeElement) a = a.shadowRoot.activeElement;
                return !!(a && a.classList && a.classList.contains('qt-window-input-element') && a.inputMode !== 'none');
            }""")

        PRE = "import sys, json\nT = sys.modules['__main__']\nfrom AnyQt.QtWidgets import *\nfrom AnyQt.QtCore import *\n"

        def gpt(w_expr, x_expr="r.center().x()", y_expr="r.center().y()", rect="w.rect()"):
            return PRE + f"w = {w_expr}\nr = {rect}\np = w.mapToGlobal(QPoint({x_expr}, {y_expr}))\njson.dumps([p.x(), p.y()])"

        await pg.goto(f"http://localhost:{PORT}/{PAGE}?test=test_touch3.py")
        for _ in range(160):
            await pg.wait_for_timeout(500)
            if any("[test] setup ok" in l for l in logs): break
        await pg.wait_for_timeout(800)
        node = {}
        for n in ("f", "t", "k", "ts", "sp", "ds"):
            node[n] = await py(PRE + f"n = T.nodes['{n}']\njson.dumps(T.g(n.position[0], n.position[1]))")

        await pg.screenshot(path=OUT + "0_start.png")
        print("node coords", node)
        print("visible at start:", await py(PRE + "json.dumps([w.windowTitle() for w in QApplication.topLevelWidgets() if w.isVisible()])"))
        check("no keyboard at start", not await keyboard_up())

        # 1. File widget: change the role of "iris" from target to feature, Apply
        await dtap(*node["f"])
        await pg.screenshot(path=OUT + "0b_after_dtap.png")
        vis = await py(PRE + "json.dumps(T.scheme.widget_manager.widget_for_node(T.nodes['f']).isVisible())")
        check("double tap opens File", vis)
        cell = await py(PRE + """w = T.scheme.widget_manager.widget_for_node(T.nodes['f'])
v = w.domain_editor
r = v.visualRect(v.model().index(4, 2))
p = v.viewport().mapToGlobal(r.center())
json.dumps([p.x(), p.y(), v.model().index(4, 2).data()])""")
        print("role cell", cell)
        await dtap(cell[0], cell[1])
        await pg.screenshot(path=OUT + "1_combo.png")
        check("no keyboard when editing a role", not await keyboard_up())
        item = await py(PRE + """pops = [x for x in QApplication.topLevelWidgets() if x.isVisible() and x.metaObject().className() == 'QComboBoxPrivateContainer']
if not pops:
    out = None
else:
    lv = pops[0].findChild(QListView)
    m = lv.model()
    rows = [m.index(i, 0).data() for i in range(m.rowCount())]
    i = rows.index('feature')
    p = lv.viewport().mapToGlobal(lv.visualRect(m.index(i, 0)).center())
    out = [p.x(), p.y(), rows]
json.dumps(out)""")
        check("role pop-up opens", item is not None, item)
        if item:
            await tap(item[0], item[1])
        role = await py(PRE + """w = T.scheme.widget_manager.widget_for_node(T.nodes['f'])
json.dumps([w.domain_editor.model().index(4, 2).data(), w.apply_button.isEnabled()])""")
        check("role changed to feature, Apply enabled", role == ["feature", True], role)
        check("no keyboard after choosing", not await keyboard_up())
        ab = await py(gpt("T.scheme.widget_manager.widget_for_node(T.nodes['f']).apply_button"))
        await tap(*ab)
        await pg.wait_for_timeout(800)
        applied = await py(PRE + """w = T.scheme.widget_manager.widget_for_node(T.nodes['f'])
d = T.scheme.widget_manager.widget_for_node(T.nodes['ds']).data
json.dumps([d is not None and d.domain.class_var is None, w.apply_button.isEnabled()])""")
        check("Apply applies (no class variable now)", applied == [True, False], applied)
        await pg.screenshot(path=OUT + "2_applied.png")

        # 2. close the File window with its X button
        xb = await py(PRE + """w = T.scheme.widget_manager.widget_for_node(T.nodes['f'])
fg = w.frameGeometry()
g_ = w.geometry()
json.dumps([g_.right() - 10, g_.top() - 14])""")
        await tap(*xb)
        await pg.wait_for_timeout(500)
        vis = await py(PRE + "json.dumps(T.scheme.widget_manager.widget_for_node(T.nodes['f']).isVisible())")
        check("X button closes widget window", not vis)

        # 3. touch and hold on a node -> context menu -> Remove
        nbefore = await py(PRE + "json.dumps(len(T.scheme.nodes))")
        await hold(*node["k"])
        await pg.screenshot(path=OUT + "3_nodemenu.png")
        rm = await py(PRE + """ms = [x for x in QApplication.topLevelWidgets() if isinstance(x, QMenu) and x.isVisible()]
out = None
for m in ms:
    for a in m.actions():
        if a.text().replace('&', '') == 'Remove' and a.isVisible():
            r = m.actionGeometry(a); p = m.mapToGlobal(r.center()); out = [p.x(), p.y()]
json.dumps(out)""")
        check("hold on node opens its menu", rm is not None)
        if rm:
            await tap(*rm)
        nafter = await py(PRE + "json.dumps(len(T.scheme.nodes))")
        check("Remove deletes the widget", nafter == nbefore - 1, (nbefore, nafter))

        # 4. touch and hold on a link -> Remove
        lbefore = await py(PRE + "json.dumps(len(T.scheme.links))")
        mid = [(node["f"][0] + node["t"][0]) // 2, (node["f"][1] + node["t"][1]) // 2]
        lp = await py(PRE + """from orangecanvas.canvas import items
l = [l for l in T.scheme.links if l.sink_node is T.nodes['t']][0]
it = T.doc.scene().item_for_link(l)
c = it.curveItem.path().pointAtPercent(0.5)
sp_ = it.mapToScene(c)
json.dumps(T.g(sp_.x(), sp_.y()))""")
        await hold(*lp)
        await pg.screenshot(path=OUT + "4_linkmenu.png")
        rm = await py(PRE + """ms = [x for x in QApplication.topLevelWidgets() if isinstance(x, QMenu) and x.isVisible()]
out = None
for m in ms:
    for a in m.actions():
        if a.text().replace('&', '') == 'Remove' and a.isVisible():
            r = m.actionGeometry(a); p = m.mapToGlobal(r.center()); out = [p.x(), p.y()]
json.dumps(out)""")
        check("hold on link opens its menu", rm is not None)
        if rm:
            await tap(*rm)
        lafter = await py(PRE + "json.dumps(len(T.scheme.links))")
        check("Remove deletes the link", lafter == lbefore - 1, (lbefore, lafter))

        # 5. select a node by tap, then Edit menu -> Remove
        await tap(*node["t"])
        em = await py(PRE + """mb = T._orange_main[1].menuBar()
a = [a for a in mb.actions() if a.text().replace('&', '') == 'Edit'][0]
p = mb.mapToGlobal(mb.actionGeometry(a).center())
json.dumps([p.x(), p.y()])""")
        await tap(*em)
        await pg.screenshot(path=OUT + "5_editmenu.png")
        rm = await py(PRE + """ms = [x for x in QApplication.topLevelWidgets() if isinstance(x, QMenu) and x.isVisible()]
out = None
for m in ms:
    for a in m.actions():
        if a.text().replace('&', '') == 'Remove' and a.isEnabled():
            r = m.actionGeometry(a); p = m.mapToGlobal(r.center()); out = [p.x(), p.y()]
json.dumps(out)""")
        check("Edit menu opens with Remove enabled", rm is not None)
        nb = await py(PRE + "json.dumps(len(T.scheme.nodes))")
        if rm:
            await tap(*rm)
        na = await py(PRE + "json.dumps(len(T.scheme.nodes))")
        check("Edit > Remove deletes the selected widget", na == nb - 1, (nb, na))

        # 6. move a node with a finger
        before = await py(PRE + "json.dumps(list(T.nodes['sp'].position))")
        await drag(node["sp"], (node["sp"][0] + 120, node["sp"][1] - 60))
        after = await py(PRE + "json.dumps(list(T.nodes['sp'].position))")
        check("drag moves a widget", abs(after[0] - before[0] - 120) < 15, (before, after))
        node["sp"] = await py(PRE + "n = T.nodes['sp']\njson.dumps(T.g(n.position[0], n.position[1]))")

        # 7. Scatter plot: choose x axis from its combo box
        await dtap(*node["sp"])
        cb = await py(gpt("T.scheme.widget_manager.widget_for_node(T.nodes['sp']).controls.attr_x"))
        await tap(*cb)
        await pg.screenshot(path=OUT + "7_combo.png")
        item = await py(PRE + """pops = [x for x in QApplication.topLevelWidgets() if x.isVisible() and x.metaObject().className() in ('QComboBoxPrivateContainer', 'QListView')]
out = None
if pops:
    lv = pops[0] if isinstance(pops[0], QListView) else pops[0].findChild(QListView); m = lv.model()
    for i in range(m.rowCount()):
        if str(m.index(i, 0).data()) == 'petal length':
            p = lv.viewport().mapToGlobal(lv.visualRect(m.index(i, 0)).center()); out = [p.x(), p.y()]
json.dumps(out)""")
        check("axis combo opens", item is not None)
        if item:
            await pg.wait_for_timeout(300)
            await tap(*item)
        ax = await py(PRE + "json.dumps(str(T.scheme.widget_manager.widget_for_node(T.nodes['sp']).attr_x))")
        check("axis changed by tap", ax == "petal length", ax)
        check("no keyboard after combo", not await keyboard_up())

        # 8. move the window by dragging its title bar
        g0 = await py(PRE + "w = T.scheme.widget_manager.widget_for_node(T.nodes['sp'])\nfg = w.frameGeometry()\ng_ = w.geometry()\njson.dumps([fg.x(), fg.y(), g_.center().x(), g_.top() - 14])")
        await drag((g0[2], g0[3]), (g0[2] - 150, g0[3] + 80), steps=20)
        g1 = await py(PRE + "w = T.scheme.widget_manager.widget_for_node(T.nodes['sp'])\nfg = w.frameGeometry()\njson.dumps([fg.x(), fg.y()])")
        check("title bar drag moves the window", abs((g1[0] - g0[0]) + 150) < 20, (g0[:2], g1))

        # 9. Distributions: drag the bin width slider
        await dtap(*node["ds"])
        sl = await py(PRE + """w = T.scheme.widget_manager.widget_for_node(T.nodes['ds'])
s = [s for s in w.findChildren(QSlider) if s.isVisible()][0]
o = QStyleOptionSlider(); s.initStyleOption(o)
h = s.style().subControlRect(QStyle.ComplexControl.CC_Slider, o, QStyle.SubControl.SC_SliderHandle, s)
a = s.mapToGlobal(h.center())
json.dumps([a.x(), a.y(), s.value(), s.maximum(), s.width()])""")
        await drag((sl[0], sl[1]), (sl[0] - int(sl[4] * 0.6), sl[1]), steps=20)
        v2 = await py(PRE + """w = T.scheme.widget_manager.widget_for_node(T.nodes['ds'])
s = [s for s in w.findChildren(QSlider) if s.isVisible()][0]
json.dumps(s.value())""")
        check("slider drag changes value", v2 != sl[2], (sl[2], v2))
        await pg.screenshot(path=OUT + "9_slider.png")
        await tap(*(await py(PRE + "w = T.scheme.widget_manager.widget_for_node(T.nodes['ds'])\nfg = w.frameGeometry()\ng_ = w.geometry()\njson.dumps([g_.right() - 10, g_.top() - 14])")))
        await tap(*(await py(PRE + "w = T.scheme.widget_manager.widget_for_node(T.nodes['sp'])\nfg = w.frameGeometry()\ng_ = w.geometry()\njson.dumps([g_.right() - 10, g_.top() - 14])")))

        # 10. link to an empty spot -> quick menu -> tap an item
        nb = await py(PRE + "json.dumps(len(T.scheme.nodes))")
        await drag((node["ts"][0] + 26, node["ts"][1]), (node["ts"][0] + 260, node["ts"][1] + 40), steps=25)
        await pg.screenshot(path=OUT + "10_quickmenu.png")
        qi = await py(PRE + """from orangecanvas.document.quickmenu import QuickMenu
qs = [x for x in QApplication.topLevelWidgets() if isinstance(x, QuickMenu) and x.isVisible()]
out = None
if qs:
    q = qs[0]
    views = [v for v in q.findChildren(QAbstractItemView) if v.isVisible() and v.model() is not None and v.model().rowCount() > 0]
    if views:
        v = views[0]; p = v.viewport().mapToGlobal(v.visualRect(v.model().index(0, 0)).center()); out = [p.x(), p.y(), str(v.model().index(0, 0).data())]
json.dumps(out)""")
        check("quick menu opens with items", qi is not None, qi)
        check("no keyboard when quick menu opens", not await keyboard_up())
        if qi:
            await tap(qi[0], qi[1])
            await pg.wait_for_timeout(800)
        na = await py(PRE + "json.dumps(len(T.scheme.nodes))")
        check("tapping a quick menu item adds a widget", na == nb + 1, (nb, na))
        await pg.screenshot(path=OUT + "10b_added.png")

        # 11. text field: tapping the toolbox filter brings up the keyboard; tapping canvas hides it
        fl = await py(PRE + """from AnyQt.QtWidgets import QLineEdit
mw_ = T._orange_main[1]
le = [l for l in mw_.findChildren(QLineEdit) if l.isVisible() and l.placeholderText().startswith('Filter')][0]
p = le.mapToGlobal(le.rect().center()); json.dumps([p.x(), p.y()])""")
        await tap(*fl)
        check("tapping a text field shows the keyboard", await keyboard_up())
        await tap(900, 720)
        check("tapping the canvas hides it", not await keyboard_up())

        print("\nSUMMARY %d/%d passed" % (sum(ok for _, ok in results), len(results)))
        errs = [l for l in logs if "Traceback" in l or "Error" in l]
        if errs:
            print("console errors:", errs[:5])
        await b.close()

asyncio.run(main())
