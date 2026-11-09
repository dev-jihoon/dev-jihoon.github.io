#!/usr/bin/env bash
# Cross-compile Orange3's C/Cython extensions as Pyodide side modules (.so)
set -uo pipefail
source /home/claude/wasm/env.sh
O=/home/claude/wasm/orange
OSRC=$O/orange3-3.41.0
OUT=$O/ext-out
PYINC=$PYODIDE_REPO/cpython/installs/python-3.13.2/include/python3.13
NPWHL=$(ls /home/claude/wasm/pyodide-full/pyodide/numpy-2.2.5-cp313-cp313-pyodide_2025_0_wasm32.whl)
mkdir -p $O/npwasm && cd $O/npwasm && unzip -q -o $NPWHL 'numpy/_core/include/*'
NPINC=$O/npwasm/numpy/_core/include
CF="-O2 -g0 -fPIC -fwasm-exceptions -sSUPPORT_LONGJMP -I$PYINC -I$NPINC -DNPY_NO_DEPRECATED_API=0 -Wno-version-check"
LF="-O2 -g0 -fwasm-exceptions -sSUPPORT_LONGJMP -sWASM_BIGINT -sSIDE_MODULE=1 -Wno-version-check"
SUF=.cpython-313-wasm32-emscripten.so
rm -rf $OUT; mkdir -p $OUT/obj
cd $OSRC
build() { # modname src compiler
  local mod=$1 src=$2 cc=$3
  local rel=${mod//./\/}
  mkdir -p $OUT/$(dirname $rel)
  if $cc $CF -c $src -o $OUT/obj/${mod}.o 2>$OUT/obj/${mod}.err && \
     $cc $LF $OUT/obj/${mod}.o -o $OUT/${rel}$SUF 2>>$OUT/obj/${mod}.err; then
    echo "OK   $mod"
  else
    echo "FAIL $mod"; grep -m5 error $OUT/obj/${mod}.err
  fi
}
for pyx in $(find Orange -name "*.pyx" | grep -v /tests/); do
  base=${pyx%.pyx}; mod=${base//\//.}
  if [ -f $base.cpp ]; then build $mod $base.cpp em++; else build $mod $base.c emcc; fi
done
CF="$CF -D_GNU_SOURCE -D__GNU__" build Orange.classification._simple_tree Orange/classification/_simple_tree.c emcc
build Orange.widgets.utils._grid_density Orange/widgets/utils/_grid_density.cpp em++
find $OUT -name "*.so" | sed "s|$OUT/||"
