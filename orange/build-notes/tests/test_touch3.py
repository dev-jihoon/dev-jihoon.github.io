import sys
from AnyQt.QtCore import QPointF
main, mw = sys.modules["__main__"]._orange_main
from orangecanvas.registry import global_registry
from orangecanvas.scheme import SchemeLink
reg = global_registry(); doc = mw.current_document(); scheme = doc.scheme()
W = lambda q: reg.widget("Orange.widgets." + q)
f = doc.createNewNode(W("data.owfile.OWFile"), position=(120, 200))
t = doc.createNewNode(W("data.owtable.OWTable"), position=(380, 90))
k = doc.createNewNode(W("model.owknn.OWKNNLearner"), position=(380, 330))
ts = doc.createNewNode(W("evaluate.owtestandscore.OWTestAndScore"), position=(640, 250))
sp = doc.createNewNode(W("visualize.owscatterplot.OWScatterPlot"), position=(380, 470))
ds = doc.createNewNode(W("visualize.owdistributions.OWDistributions"), position=(640, 470))
for a, b, o, i in [(f, t, "Data", "Data"), (f, ts, "Data", "Data"), (k, ts, "Learner", "Learner"),
                   (f, sp, "Data", "Data"), (f, ds, "Data", "Data")]:
    doc.addLink(SchemeLink(a, a.output_channel(o), b, b.input_channel(i)))
view = doc.view()


def g(x, y):
    p = view.viewport().mapToGlobal(view.mapFromScene(QPointF(x, y)))
    return p.x(), p.y()


T = sys.modules["__main__"]
T.nodes = dict(f=f, t=t, k=k, ts=ts, sp=sp, ds=ds)
T.g = g
T.doc = doc
T.scheme = scheme
print("[test] setup ok")
