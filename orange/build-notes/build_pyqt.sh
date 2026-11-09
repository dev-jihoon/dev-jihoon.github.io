#!/usr/bin/env bash
# Build PyQt6-sip + PyQt6 (Core/Gui/Widgets/Svg/SvgWidgets/Xml) as static wasm libs.
# Adapted from pyodide-with-pyqt6/build.sh (phase 2) for this environment.
set -euo pipefail
source /home/claude/wasm/env.sh
export PATH=/home/claude/wasm/hostpy/bin:$PATH
PATCHES_DIR=$R/patches
PYQT6_SRC=$SRC/pyqt6-6.10.2
PYQT6_SIP_SRC=$SRC/pyqt6_sip-13.11.0
PYINC=$PYODIDE_REPO/cpython/installs/python-3.13.2/include/python3.13
CFLAGS_PY="-O2 -g0 -fPIC -fwasm-exceptions -sSUPPORT_LONGJMP"
test -f $PYINC/Python.h

echo "==> sip module"
SIPB=$BUILD_DIR/pyqt6-sip-build; mkdir -p $SIPB
for src in sip_core.c sip_array.c sip_descriptors.c sip_enum.c sip_int_convertors.c sip_object_map.c sip_threads.c sip_voidptr.c; do
  emcc $CFLAGS_PY -DSIP_STATIC_MODULE=1 -I$PYINC -I$PYQT6_SIP_SRC -c $PYQT6_SIP_SRC/$src -o $SIPB/${src%.c}.o 2>&1 | grep -v "version-check" || true
done
rm -f $SIPB/libsip.a; emar crs $SIPB/libsip.a $SIPB/*.o

echo "==> patch PyQt6 sources"
BINDINGS_PY=$(python -c 'import pyqtbuild, os; print(os.path.join(os.path.dirname(pyqtbuild.__file__), "bindings.py"))')
python $PATCHES_DIR/apply-wasm-patches.py $PYQT6_SRC $BINDINGS_PY

echo "==> sip-build"
PQB=$BUILD_DIR/pyqt6-build; mkdir -p $PQB
cd $PYQT6_SRC
export PATH=$QT_INSTALL/bin:$PATH
export QMAKE=$QT_INSTALL/bin/qmake6
export PYQT_WASM_FEATURES="QtCore=static,PyQt_Process,PyQt_Timezone,PyQt_SystemSemaphore,PyQt_Thread;QtGui=PyQt_XCB,PyQt_Wayland,PyQt_Vulkan;QtWidgets=;QtSvg=;QtSvgWidgets=;QtXml="
DIS=""
for m in QtDBus QtDesigner QtHelp QtMultimedia QtMultimediaWidgets QtNetwork QtNfc QtOpenGL QtOpenGLWidgets QtPdf QtPdfWidgets QtPositioning QtPrintSupport QtQml QtQuick QtQuick3D QtQuickWidgets QtRemoteObjects QtSensors QtSerialPort QtSpatialAudio QtSql QtStateMachine QtTest QtTextToSpeech QtWebChannel QtWebSockets QtBluetooth QAxContainer; do DIS="$DIS --disable $m"; done
sip-build --verbose --confirm-license --no-make --build-dir $PQB --qmake $QMAKE \
  --no-designer-plugin --no-qml-plugin --no-dbus-python --no-tools $DIS 2>&1 | tail -40 || true

echo "==> fix includes"
HOSTINC=$(python -c 'import sysconfig; print(sysconfig.get_path("include"))')
find $PQB -name Makefile | while read -r mf; do
  d=$(dirname $mf)
  rel=$(python -c "import os; print(os.path.relpath('$HOSTINC', '$d'))")
  sed -i "s|$rel|$PYINC|g; s|$HOSTINC|$PYINC|g" $mf
  sed -i 's/^CFLAGS\s*=\(.*\)/CFLAGS        = -fPIC\1/; s/^CXXFLAGS\s*=\(.*\)/CXXFLAGS      = -fPIC\1/' $mf
done

echo "==> make"
cd $PQB && make -j2 2>&1 | grep -E "error|Error|^make" | head -50
ls -la $PQB/*/lib*.a
echo "==> PYQT DONE"
