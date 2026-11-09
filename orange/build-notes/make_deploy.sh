#!/usr/bin/env bash
# Assemble the optimized static site for GitHub Pages into deploy/orange
#  - only the packages Orange needs (STARTUP_PACKAGES + LATER_PACKAGES in orange.html)
#  - everything precompiled to .pyc (no compiling in the browser)
#  - a prebuilt widget registry (no widget discovery at startup)
#  - big files gzip-compressed, every file cached in Cache Storage per build
set -euo pipefail
W=/home/claude/wasm
S=$W/site; D=$W/deploy/orange
PYHOST=/home/claude/cenv/bin/python
rm -rf $W/deploy; mkdir -p $D
cd $S
cp pyodide.mjs pyodide.js pyodide.asm.js pyodide.asm.wasm python_stdlib.zip boot.py webpatches.py NanumGothic.ttf $D/

# 1. packages + lock file
python3 - <<'PY'
import json, re, shutil
S='/home/claude/wasm/site'; D='/home/claude/wasm/deploy/orange'
html = open(S+'/orange.html').read()
want = []
for name in ("STARTUP_PACKAGES", "LATER_PACKAGES"):
    want += json.loads(re.search(name + r'\s*=\s*(\[[^\]]*\])', html, re.S).group(1))
lock = json.load(open(S+'/pyodide-lock.json')); pk = lock['packages']
# networkx only lists these for optional features (drawing); Orange does not use them
pk['networkx']['depends'] = [d for d in pk['networkx']['depends'] if d not in ('matplotlib', 'setuptools')]
norm = {k.lower().replace('_','-'): k for k in pk}
seen=set(); stack=[norm[w.lower().replace('_','-')] for w in want]
while stack:
    n=stack.pop()
    if n in seen: continue
    seen.add(n); stack += [norm[d.lower().replace('_','-')] for d in pk[n].get('depends', [])]
lock['packages'] = {k: pk[k] for k in sorted(seen)}
for k in seen: shutil.copy(S+'/'+pk[k]['file_name'], D)
json.dump(lock, open(D+'/pyodide-lock.json','w'), indent=1, sort_keys=True)
print(len(seen), 'packages')
PY

# 2. .py -> .pyc in wheels and the standard library (updates the lock file)
cd $D && $W/hostpy/bin/pyodide py-compile --silent .

# 3. Orange and its pure-Python dependencies, precompiled
rm -rf /tmp/orange-sp-pyc && mkdir -p /tmp/orange-sp-pyc
tar xf $S/orange-sp.tar -C /tmp/orange-sp-pyc
$PYHOST -m compileall -b -q -j 2 /tmp/orange-sp-pyc
find /tmp/orange-sp-pyc -name "*.py" -delete
find /tmp/orange-sp-pyc -name __pycache__ -prune -exec rm -rf {} \;
(cd /tmp/orange-sp-pyc && tar cf $D/orange-sp.tar --sort=name --mtime='2026-01-01' --owner=0 --group=0 .)

# 4. prebuilt widget registry (generated from the dev site, see getreg.py)
cp $W/widget-registry.pck $D/widget-registry.pck

# 5. index.html: gzip + Cache Storage fetch layer, no cache-busting queries
BUILD_ID=$(cd $D && cat pyodide.asm.wasm orange-sp.tar boot.py webpatches.py pyodide-lock.json widget-registry.pck | sha256sum | cut -c1-12)
python3 - "$BUILD_ID" <<'PY'
import sys
build = sys.argv[1]
S='/home/claude/wasm/site'; D='/home/claude/wasm/deploy/orange'
html = open(S+'/orange.html').read()
layer = '''// Fetch layer:
//  - big files are stored gzip-compressed and decompressed here
//  - every file is kept in Cache Storage for this build, so later visits
//    load from the device instead of the network
const BUILD = "%s";
const CACHE_NAME = "orange-web-" + BUILD;
const GZ = ["pyodide.asm.wasm", "orange-sp.tar", "NanumGothic.ttf"];
const _fetch = window.fetch.bind(window);
let cacheP = null;
try { cacheP = caches.open(CACHE_NAME).catch(() => null); } catch (e) { cacheP = Promise.resolve(null); }
try {
  caches.keys().then(keys => keys.filter(k => k.startsWith("orange-web-") && k !== CACHE_NAME)
                                 .forEach(k => caches.delete(k))).catch(() => {});
} catch (e) {}
async function cachedFetch(url) {
  const cache = await cacheP;
  if (cache) {
    try { const hit = await cache.match(url); if (hit) return hit; } catch (e) {}
  }
  const r = await _fetch(url);
  if (cache && r.ok) { try { await cache.put(url, r.clone()); } catch (e) {} }
  return r;
}
window.fetch = async (input, init) => {
  const url = new URL(typeof input === "string" ? input : (input instanceof URL ? input.href : input.url), location.href);
  if (url.origin !== location.origin || (init && init.method && init.method !== "GET")) return _fetch(input, init);
  url.search = "";
  const name = url.pathname.split("/").pop();
  if (GZ.includes(name)) {
    const r = await cachedFetch(url.href + ".gz");
    if (!r.ok) throw new Error("download failed: " + name);
    const body = r.body.pipeThrough(new DecompressionStream("gzip"));
    const type = name.endsWith(".wasm") ? "application/wasm" : "application/octet-stream";
    return new Response(body, { status: 200, headers: { "Content-Type": type } });
  }
  return cachedFetch(url.href);
};''' % build
html = html.replace('import { loadPyodide } from "./pyodide.mjs";',
                    'import { loadPyodide } from "./pyodide.mjs";\n' + layer, 1)
html = html.replace('"./boot.py?" + Date.now()', '"./boot.py"').replace('"./webpatches.py?" + Date.now()', '"./webpatches.py"')
html = html.replace(', viewport-fit=cover', '')
open(D+'/index.html', 'w').write(html)
print("build", build)
PY

cd $D
for f in pyodide.asm.wasm orange-sp.tar NanumGothic.ttf; do gzip -9 -n -f $f; done
touch .nojekyll
du -sh $D; find $D -size +24M
