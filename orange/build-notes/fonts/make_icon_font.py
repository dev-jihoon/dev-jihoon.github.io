"""Build "Orange Web Fluent Icons": the glyphs Qt's Windows 11 style draws from
Segoe Fluent Icons (not redistributable), made from Microsoft's MIT-licensed
Fluent UI System Icons at the same code points."""
import sys, os, re
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.transformPen import TransformPen
from fontTools.svgLib.path import parse_path

ICONS = sys.argv[1]
OUT = sys.argv[2]
UPM = 2048
MAP = {
    0xE70D: "chevron_down_16_regular", 0xE70E: "chevron_up_16_regular",
    0xEDD9: "caret_left_16_filled", 0xEDDA: "caret_right_16_filled",
    0xEDDB: "caret_up_16_filled", 0xEDDC: "caret_down_16_filled",
    0xE8BB: "dismiss_16_regular", 0xE921: "subtract_16_regular",
    0xE922: "square_16_regular", 0xE923: "square_multiple_16_regular",
    0xE897: "question_16_regular",
    0xE96D: "chevron_up_12_regular", 0xE96E: "chevron_down_12_regular",
    0xE73E: "checkmark_16_regular", 0xE73C: "subtract_12_regular",
    0xE973: "chevron_left_12_regular", 0xE974: "chevron_right_12_regular",
}
glyph_order = [".notdef", "space"]
cmap = {0x20: "space"}
charstrings = {}
metrics = {}

def empty():
    pen = T2CharStringPen(UPM, None)
    return pen.getCharString()

charstrings[".notdef"] = empty(); metrics[".notdef"] = (UPM, 0)
charstrings["space"] = empty(); metrics["space"] = (UPM, 0)
for cp, name in MAP.items():
    svg = open(os.path.join(ICONS, name + ".svg")).read()
    vb = float(re.search(r'viewBox="0 0 (\d+) ', svg).group(1))
    off = (16 - vb) / 2
    k = UPM / 16
    pen = T2CharStringPen(UPM, None)
    # SVG y grows down; font y grows up. Place on a 16-unit em.
    tpen = TransformPen(pen, (k, 0, 0, -k, off * k, (16 - off) * k))
    for d in re.findall(r'<path[^>]* d="([^"]+)"', svg):
        parse_path(d, tpen)
    gname = "uni%04X" % cp
    glyph_order.append(gname)
    cmap[cp] = gname
    charstrings[gname] = pen.getCharString()
    metrics[gname] = (UPM, 0)

fb = FontBuilder(UPM, isTTF=False)
fb.setupGlyphOrder(glyph_order)
fb.setupCharacterMap(cmap)
fam = "Orange Web Fluent Icons"
fb.setupCFF(fam.replace(" ", ""), {"FullName": fam}, charstrings, {})
fb.setupHorizontalMetrics(metrics)
fb.setupHorizontalHeader(ascent=UPM, descent=0)
fb.setupNameTable({"familyName": fam, "styleName": "Regular",
                   "copyright": "Glyphs from Fluent UI System Icons, Copyright (c) Microsoft Corporation, MIT License"})
fb.setupOS2(sTypoAscender=UPM, sTypoDescender=0, sTypoLineGap=0, usWinAscent=UPM, usWinDescent=0)
fb.setupPost()
fb.save(OUT)
print("ok", OUT, os.path.getsize(OUT))
