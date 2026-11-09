#!/usr/bin/env bash
set -euo pipefail
source /home/claude/wasm/env.sh
export PATH=/home/claude/wasm/hostpy/bin:$PATH
cd $PYODIDE_REPO
export PYODIDE_ROOT=$(pwd) PYODIDE_JOBS=2
rm -f dist/pyodide.asm.js dist/pyodide.asm.wasm
make all-but-packages
cp dist/{pyodide.asm.js,pyodide.asm.wasm,pyodide.js,pyodide.mjs,python_stdlib.zip} /home/claude/wasm/site/
echo RELINK_OK
