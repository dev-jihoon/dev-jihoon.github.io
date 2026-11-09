#!/usr/bin/env bash
# Build Qt 6.10.2 (qtbase + qtsvg) for WebAssembly using Pyodide's emscripten layout
set -euo pipefail
source /home/claude/wasm/env.sh

emcc --version | head -1

mkdir -p $SRC/qtbase/build-wasm
cd $SRC/qtbase/build-wasm
if [ ! -f config.summary ]; then
  ../configure \
    -qt-host-path "$CENV" \
    -platform wasm-emscripten \
    -static \
    -prefix "$QT_INSTALL" \
    -no-feature-thread \
    -feature-wasm-exceptions \
    -no-feature-sql \
    -no-feature-testlib \
    -opensource -confirm-license \
    -nomake examples -nomake tests \
    -no-warnings-are-errors \
    -- -DCMAKE_POSITION_INDEPENDENT_CODE=ON
fi
cmake --build . --parallel 2
cmake --install .

echo "==> qtsvg"
mkdir -p $SRC/qtsvg/build-wasm
cd $SRC/qtsvg/build-wasm
"$QT_INSTALL/bin/qt-configure-module" .. -- -DCMAKE_POSITION_INDEPENDENT_CODE=ON
cmake --build . --parallel 2
cmake --install .
echo "==> QT DONE"
