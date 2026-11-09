# Shared environment for the Orange-in-browser build
export W=/home/claude/wasm
export R=$W/pyodide-with-pyqt6
export BUILD_DIR=$R/build
export SRC=$BUILD_DIR/sources
export PYODIDE_REPO=$SRC/pyodide
export CENV=/home/claude/cenv
export EMSDK=$PYODIDE_REPO/emsdk/emsdk
export EM_CONFIG=$EMSDK/.emscripten
export PATH=$EMSDK/upstream/emscripten:$CENV/bin:$PATH
export CONDA_PREFIX=$CENV
export QT_INSTALL=$BUILD_DIR/qt6-wasm
