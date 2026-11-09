#!/usr/bin/env bash
# Phase 3: link Qt6 + PyQt6 into the Pyodide main module (adapted from build.sh)
set -euo pipefail
source /home/claude/wasm/env.sh
export PATH=/home/claude/wasm/hostpy/bin:$PATH
PATCHES_DIR=$R/patches
qt_lib=$QT_INSTALL/lib; qt_plugins=$QT_INSTALL/plugins; qt_objects=$QT_INSTALL/lib/objects-Release
pyqt_build=$BUILD_DIR/pyqt6-build; sip_build=$BUILD_DIR/pyqt6-sip-build

cat > $BUILD_DIR/pyqt6-ldflags.txt <<LDFLAGS
$pyqt_build/QtCore/libQtCore.a
$pyqt_build/QtGui/libQtGui.a
$pyqt_build/QtWidgets/libQtWidgets.a
$pyqt_build/QtSvg/libQtSvg.a
$pyqt_build/QtSvgWidgets/libQtSvgWidgets.a
$pyqt_build/QtXml/libQtXml.a
$sip_build/libsip.a
$BUILD_DIR/qt_plugin_import.o
$BUILD_DIR/qt_wasm_stubs.o
$qt_lib/libQt6Widgets.a
$qt_lib/libQt6Gui.a
$qt_lib/libQt6Core.a
$qt_lib/libQt6Svg.a
$qt_lib/libQt6SvgWidgets.a
$qt_lib/libQt6Xml.a
$qt_lib/libQt6OpenGL.a
$qt_lib/libQt6BundledHarfbuzz.a
$qt_lib/libQt6BundledFreetype.a
$qt_lib/libQt6BundledLibpng.a
$qt_lib/libQt6BundledLibjpeg.a
$qt_lib/libQt6BundledPcre2.a
$qt_lib/libQt6BundledZLIB.a
$qt_plugins/platforms/libqwasm.a
$qt_plugins/iconengines/libqsvgicon.a
$qt_plugins/imageformats/libqgif.a
$qt_plugins/imageformats/libqico.a
$qt_plugins/imageformats/libqjpeg.a
$qt_plugins/imageformats/libqsvg.a
$qt_objects/QWasmIntegrationPlugin_resources_1/.qt/rcc/qrc_wasmfonts_init.cpp.o
$qt_objects/QWasmIntegrationPlugin_resources_2/.qt/rcc/qrc_wasmwindow_init.cpp.o
$qt_objects/Gui_resources_1/.qt/rcc/qrc_qpdf_init.cpp.o
$qt_objects/Gui_resources_2/.qt/rcc/qrc_gui_shaders_init.cpp.o
$qt_objects/Widgets_resources_1/.qt/rcc/qrc_qstyle_init.cpp.o
$qt_objects/Widgets_resources_2/.qt/rcc/qrc_qstyle1_init.cpp.o
$qt_objects/Widgets_resources_3/.qt/rcc/qrc_qstyle_fusion_init.cpp.o
$qt_objects/Widgets_resources_4/.qt/rcc/qrc_qmessagebox_init.cpp.o
LDFLAGS
for f in $(grep -v '^#' $BUILD_DIR/pyqt6-ldflags.txt); do test -e $f || echo "MISSING $f"; done

python3 $PATCHES_DIR/apply-wasm-patches.py --pyodide $PYODIDE_REPO --build-dir $BUILD_DIR

em++ -fPIC -std=gnu++17 -DQT_STATIC -I$QT_INSTALL/include -I$QT_INSTALL/include/QtCore -I$QT_INSTALL/include/QtGui \
  -c $PATCHES_DIR/qt_plugin_import.cpp -o $BUILD_DIR/qt_plugin_import.o
emcc -fPIC -c $PATCHES_DIR/qt_wasm_stubs.c -o $BUILD_DIR/qt_wasm_stubs.o

dawn_version="v20260219.200501"
if [ ! -d "$PYODIDE_REPO/emdawnwebgpu_pkg" ]; then
  cd $PYODIDE_REPO
  curl -sL -o dawn.zip "https://github.com/google/dawn/releases/download/${dawn_version}/emdawnwebgpu_pkg-${dawn_version}.zip"
  unzip -q dawn.zip && rm -f dawn.zip
fi

cd $PYODIDE_REPO
export PYODIDE_ROOT=$(pwd) PYODIDE_JOBS=2
pylib=$PYODIDE_REPO/cpython/installs/python-3.13.2/lib/python3.13
cp $PATCHES_DIR/pyqt6_import_hook.py $pylib/pyqt6_import_hook.py
mkdir -p $pylib/site-packages
grep -q pyqt6_import_hook $pylib/site-packages/sitecustomize.py 2>/dev/null || echo "import pyqt6_import_hook" >> $pylib/site-packages/sitecustomize.py
make all-but-packages
ls -la dist/
echo "==> LINK DONE"
