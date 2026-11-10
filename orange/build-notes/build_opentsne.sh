#!/usr/bin/env bash
# Cross-compile openTSNE's C++ extensions as Pyodide side modules (.so)
set -uo pipefail
source /home/claude/wasm/env.sh
SRC=${1:-/tmp/otsne/opentsne-1.0.4}
OUT=/home/claude/wasm/orange/otsne-out
PYINC=$PYODIDE_REPO/cpython/installs/python-3.13.2/include/python3.13
NPINC=/home/claude/wasm/orange/npwasm/numpy/_core/include
CF="-O2 -g0 -fPIC -fwasm-exceptions -sSUPPORT_LONGJMP -I$PYINC -I$NPINC -DNPY_NO_DEPRECATED_API=0 -Wno-version-check"
LF="-O2 -g0 -fwasm-exceptions -sSUPPORT_LONGJMP -sWASM_BIGINT -sSIDE_MODULE=1 -Wno-version-check"
SUF=.cpython-313-wasm32-emscripten.so
rm -rf $OUT; mkdir -p $OUT/obj
cd $SRC
# Cython -> C++ against numpy 2.2.5's .pxd (same numpy as Pyodide 0.29);
# matrix_mul uses numpy's FFT (no FFTW) and keeps its package module name
NPPXD=/tmp/np225   # pip install --target /tmp/np225 numpy==2.2.5
for f in openTSNE/quad_tree openTSNE/_tsne openTSNE/kl_divergence; do
  cython -3 --cplus -I $NPPXD -I openTSNE -I . $f.pyx -o $f.cpp
done
cython -3 --cplus -I $NPPXD -I openTSNE -I . --module-name openTSNE._matrix_mul.matrix_mul \
  openTSNE/_matrix_mul/matrix_mul_numpy.pyx -o openTSNE/_matrix_mul/matrix_mul_numpy.cpp
build() { local mod=$1 src=$2; local rel=${mod//./\/}
  mkdir -p $OUT/$(dirname $rel)
  if em++ $CF ${3:-} -c $src -o $OUT/obj/$mod.o 2>$OUT/obj/$mod.err && em++ $LF $OUT/obj/$mod.o -o $OUT/$rel$SUF 2>>$OUT/obj/$mod.err; then echo "OK   $mod"; else echo "FAIL $mod"; grep -m5 error $OUT/obj/$mod.err; fi; }
build openTSNE.quad_tree openTSNE/quad_tree.cpp "-I openTSNE"
build openTSNE._tsne openTSNE/_tsne.cpp "-I openTSNE"
build openTSNE.kl_divergence openTSNE/kl_divergence.cpp "-I openTSNE"
build openTSNE._matrix_mul.matrix_mul openTSNE/_matrix_mul/matrix_mul_numpy.cpp "-I openTSNE"
build openTSNE.dependencies.annoy.annoylib openTSNE/dependencies/annoy/annoymodule.cc "-std=c++14"
# Then: copy openTSNE/*.py + $OUT/openTSNE/**/*.so into orange/sp/openTSNE and repack orange-sp.tar
