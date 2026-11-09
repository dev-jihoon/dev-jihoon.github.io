#!/usr/bin/env bash
# Assemble the static site for GitHub Pages into deploy/orange
set -euo pipefail
S=/home/claude/wasm/site; D=/home/claude/wasm/deploy/orange
rm -rf /home/claude/wasm/deploy; mkdir -p $D
cd $S
cp pyodide.mjs pyodide.js pyodide.asm.js pyodide.asm.wasm python_stdlib.zip orange-sp.tar boot.py webpatches.py NanumGothic.ttf $D/
python3 - <<'PY'
import json, os, re, shutil
S='/home/claude/wasm/site'; D='/home/claude/wasm/deploy/orange'
html = open(S+'/orange.html').read()
want = json.loads(re.search(r'loadPackage\((\[[^\]]*\])', html, re.S).group(1))
lock = json.load(open(S+'/pyodide-lock.json')); pk = lock['packages']
norm = {k.lower().replace('_','-'): k for k in pk}
seen=set(); stack=[norm[w.lower().replace('_','-')] for w in want]
while stack:
    n=stack.pop()
    if n in seen: continue
    seen.add(n); stack += [norm[d.lower().replace('_','-')] for d in pk[n].get('depends', [])]
lock['packages'] = {k: pk[k] for k in seen}
for k in seen: shutil.copy(S+'/'+pk[k]['file_name'], D)
json.dump(lock, open(D+'/pyodide-lock.json','w'))
gz = '''// Large files are stored gzip-compressed (keeps every file under upload limits);
// decompress them transparently in the browser.
const GZ = ["pyodide.asm.wasm", "orange-sp.tar", "NanumGothic.ttf"];
const _fetch = window.fetch.bind(window);
window.fetch = async (input, init) => {
  const url = typeof input === "string" ? input : (input instanceof URL ? input.href : input.url);
  const name = url.split("?")[0].split("/").pop();
  if (GZ.includes(name)) {
    const r = await _fetch(url.split("?")[0] + ".gz", init);
    if (!r.ok) throw new Error("download failed: " + name);
    const body = r.body.pipeThrough(new DecompressionStream("gzip"));
    const type = name.endsWith(".wasm") ? "application/wasm" : "application/octet-stream";
    return new Response(body, { status: 200, headers: { "Content-Type": type } });
  }
  return _fetch(input, init);
};'''
html = html.replace('import { loadPyodide } from "./pyodide.mjs";', 'import { loadPyodide } from "./pyodide.mjs";\n' + gz, 1)
html = html.replace(', viewport-fit=cover', '')
open(D+'/index.html','w').write(html)
print(len(seen), 'packages')
PY
cd $D
for f in pyodide.asm.wasm orange-sp.tar NanumGothic.ttf; do gzip -9 -f $f; done
touch .nojekyll
du -sh $D; find $D -size +24M
