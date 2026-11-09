# Boot Orange inside Pyodide + PyQt6 (WebAssembly, single-threaded)
import os, sys, types, time, traceback, logging
os.environ["QT_API"] = "pyqt6"
os.environ.setdefault("HOME", "/home/pyodide")

t0 = time.time()
def log(*a):
    print("[boot %.1fs]" % (time.time() - t0), *a)

# ---------------------------------------------------------------------------
# 1. Threading shims (WASM Qt is built without threads)
# ---------------------------------------------------------------------------
from PyQt6 import QtCore
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

class QThread(QObject):
    started = pyqtSignal()
    finished = pyqtSignal()

    class Priority:
        IdlePriority = 0; LowestPriority = 1; LowPriority = 2; NormalPriority = 3
        HighPriority = 4; HighestPriority = 5; TimeCriticalPriority = 6; InheritPriority = 7

    _main = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._finished = False

    @staticmethod
    def currentThread():
        return QThread._main

    @staticmethod
    def idealThreadCount():
        return 1

    @staticmethod
    def msleep(ms): pass
    @staticmethod
    def usleep(us): pass
    @staticmethod
    def sleep(s): pass
    @staticmethod
    def yieldCurrentThread(): pass

    def isMainThread(self):
        return self is QThread._main

    def run(self):
        pass

    def start(self, priority=None):
        # Run "in the background" on the next event loop iteration
        def _go():
            self._running = True
            self.started.emit()
            try:
                self.run()
            except Exception:
                traceback.print_exc()
            self._running = False
            self._finished = True
            self.finished.emit()
        QTimer.singleShot(0, _go)

    def isRunning(self): return self._running
    def isFinished(self): return self._finished
    def quit(self): pass
    def exit(self, code=0): pass
    def terminate(self): pass
    def wait(self, *a): return True
    def requestInterruption(self): pass
    def isInterruptionRequested(self): return False
    def setPriority(self, p): pass
    def setStackSize(self, s): pass
    def setObjectName(self, n): QObject.setObjectName(self, n)
    def eventDispatcher(self): return None

QThread._main = QThread()
QtCore.QThread = QThread
QObject.thread = lambda self: QThread._main
QObject.moveToThread = lambda self, thread: None

class QRunnable:
    def __init__(self, *a):
        self._auto = True
    def run(self): pass
    def autoDelete(self): return self._auto
    def setAutoDelete(self, v): self._auto = v
    @staticmethod
    def create(fn):
        r = QRunnable(); r.run = fn; return r

class QThreadPool(QObject):
    _global = None
    def __init__(self, parent=None):
        super().__init__(parent)
        self._max = 1
        self._pending = []
    @staticmethod
    def globalInstance():
        if QThreadPool._global is None:
            QThreadPool._global = QThreadPool()
        return QThreadPool._global
    def start(self, runnable, priority=0):
        fn = runnable if callable(runnable) and not isinstance(runnable, QRunnable) else runnable.run
        self._pending.append(fn)
        def _go():
            if fn in self._pending:
                self._pending.remove(fn)
                try:
                    fn()
                except Exception:
                    traceback.print_exc()
        QTimer.singleShot(0, _go)
    def tryStart(self, runnable):
        self.start(runnable); return True
    def waitForDone(self, msecs=-1):
        while self._pending:
            fn = self._pending.pop(0)
            try: fn()
            except Exception: traceback.print_exc()
        return True
    def clear(self): self._pending.clear()
    def maxThreadCount(self): return self._max
    def setMaxThreadCount(self, n): self._max = n
    def activeThreadCount(self): return 0
    def setStackSize(self, s): pass
    def stackSize(self): return 0
    def setExpiryTimeout(self, t): pass

class _NoLock:
    def __init__(self, *a, **k): pass
    def lock(self, *a): pass
    def unlock(self): pass
    def tryLock(self, *a): return True
    def lockForRead(self, *a): pass
    def lockForWrite(self, *a): pass
    def tryLockForRead(self, *a): return True
    def tryLockForWrite(self, *a): return True
    def acquire(self, n=1): pass
    def tryAcquire(self, *a): return True
    def release(self, n=1): pass
    def available(self): return 1
    def wait(self, *a): return True
    def wakeOne(self): pass
    def wakeAll(self): pass
    def relock(self): pass
    def mutex(self): return self
    def __enter__(self): return self
    def __exit__(self, *a): return False

for _n in ("QMutex", "QRecursiveMutex", "QReadWriteLock", "QSemaphore", "QWaitCondition",
           "QMutexLocker", "QReadLocker", "QWriteLocker", "QSemaphoreReleaser"):
    setattr(QtCore, _n, type(_n, (_NoLock,), {}))
QtCore.QRunnable = QRunnable
QtCore.QThreadPool = QThreadPool

# Python-level threads: run synchronously
import concurrent.futures as _cf
class SyncExecutor(_cf.Executor):
    def __init__(self, *a, **k):
        self._shutdown = False
    def submit(self, fn, /, *args, **kwargs):
        f = _cf.Future()
        if not f.set_running_or_notify_cancel():
            return f
        try:
            f.set_result(fn(*args, **kwargs))
        except BaseException as e:
            f.set_exception(e)
        return f
    def shutdown(self, wait=True, *, cancel_futures=False):
        self._shutdown = True
import concurrent.futures.thread as _cft
_cf.ThreadPoolExecutor = SyncExecutor
_cft.ThreadPoolExecutor = SyncExecutor

import threading
_orig_thread_start = threading.Thread.start
def _sync_thread_start(self):
    # Run thread body later on the Qt event loop
    def _go():
        try:
            self.run()
        except Exception:
            traceback.print_exc()
    QTimer.singleShot(0, _go)
threading.Thread.start = _sync_thread_start

# ---------------------------------------------------------------------------
# 2. Missing Qt modules -> small stubs
# ---------------------------------------------------------------------------
import PyQt6
class _Dummy:
    def __init__(self, *a, **k): pass
    def __call__(self, *a, **k): return _Dummy()
    def __getattr__(self, n): return _Dummy()
    def __bool__(self): return False

def _stub_module(name, attrs=()):
    m = types.ModuleType(name)
    def __getattr__(attr, _name=name):
        if attr.startswith("__"):
            raise AttributeError(attr)
        return type(attr, (_Dummy,), {})
    m.__getattr__ = __getattr__
    for a in attrs:
        setattr(m, a, type(a, (_Dummy,), {}))
    sys.modules[name] = m
    setattr(PyQt6, name.split(".")[-1], m)
    return m

_stub_module("PyQt6.QtNetwork", ["QNetworkDiskCache", "QNetworkAccessManager", "QNetworkRequest",
                                  "QNetworkReply", "QNetworkProxy", "QNetworkProxyFactory",
                                  "QNetworkCookieJar", "QSslSocket", "QAbstractNetworkCache",
                                  "QNetworkCacheMetaData", "QHostAddress", "QLocalSocket", "QLocalServer"])
_stub_module("PyQt6.QtPrintSupport", ["QPrinter", "QPrintDialog", "QPrintPreviewDialog"])
_stub_module("PyQt6.QtTest", ["QTest", "QSignalSpy"])
_stub_module("PyQt6.uic", [])
_stub_module("PyQt6.QtOpenGL", [])
_stub_module("PyQt6.QtOpenGLWidgets", [])

def _stub_py(name):
    m = types.ModuleType(name)
    m.__getattr__ = lambda attr: (_ for _ in ()).throw(AttributeError(attr)) if attr.startswith("__") else type(attr, (_Dummy,), {})
    m.__path__ = []
    sys.modules[name] = m
    return m
for _n in ("requests_cache", "truststore"):
    _stub_py(_n)
# openTSNE is not available in the browser build: stub it so PCA/MDS/etc. import
# (only the t-SNE widget itself will not work)
_ot = _stub_py("openTSNE")
for _sub in ("tsne", "affinity", "initialization"):
    _m = _stub_py("openTSNE." + _sub)
    _m.log = logging.getLogger("openTSNE." + _sub)
    setattr(_ot, _sub, _m)

for _m in ("QtCore", "QtGui", "QtWidgets", "QtSvg", "QtSvgWidgets", "QtXml"):
    _mod = __import__("PyQt6." + _m, fromlist=["x"])
    if not hasattr(_mod, "__file__"):
        _mod.__file__ = "/lib/python3.13/PyQt6/%s.abi3.so" % _m
sys.argv = ["orange-canvas"]

log("shims installed")

# ---------------------------------------------------------------------------
# 3. Start Orange canvas (without app.exec(); the browser drives events)
# ---------------------------------------------------------------------------
try:
    import AnyQt
    log("AnyQt", AnyQt.USED_API if hasattr(AnyQt, "USED_API") else "")
    # pyqtgraph: the pre-rendered symbol atlas path (drawPixmapFragments) draws
    # nothing in the wasm build, so draw scatter symbols one by one instead.
    import pyqtgraph as _pg
    _spi_init = _pg.ScatterPlotItem.__init__
    def _spi_init_nocache(self, *a, **k):
        _spi_init(self, *a, **k)
        self.opts["useCache"] = False
    _pg.ScatterPlotItem.__init__ = _spi_init_nocache
    import Orange.widgets as _ow
    _ow.WIDGET_HELP_PATH = ()   # online help needs network + QtWebEngine
    import Orange.canvas.__main__ as om
    om.check_for_updates = lambda: None
    om.send_usage_statistics = lambda: None
    om.pull_notifications = lambda: None
    log("Orange.canvas imported")
    sys.path.insert(0, "/")
    import webpatches
    from Orange.canvas.mainwindow import MainWindow as _OMW
    webpatches.apply_all(_OMW)
    log("web patches applied")

    from orangecanvas.registry import set_global_registry

    from contextlib import ExitStack
    main = om.OMain()
    main.stack = ExitStack()
    # A widget registry built ahead of time (same Orange version) lets us
    # skip widget discovery, which would import every widget module.
    _prebuilt_registry = os.path.exists("/widget-registry.pck")
    main.parse_arguments(["orange-canvas", "--no-splash", "--no-welcome"]
                         + (["--no-discovery"] if _prebuilt_registry else []))
    main.activate_default_config()
    if _prebuilt_registry:
        import shutil
        from orangecanvas import config as _occonfig
        os.makedirs(_occonfig.cache_dir(), exist_ok=True)
        shutil.copy("/widget-registry.pck",
                    os.path.join(_occonfig.cache_dir(), "widget-registry.pck"))
    main.setup_application()
    log("application created")
    # Korean glyphs: Qt's built-in web fonts have no Hangul
    from PyQt6.QtGui import QFontDatabase
    from PyQt6.QtCore import QChar
    _fid = QFontDatabase.addApplicationFont("/fonts/NanumGothic.ttf")
    if _fid >= 0:
        for _fam in QFontDatabase.applicationFontFamilies(_fid):
            QFontDatabase.addApplicationFallbackFontFamily(QChar.Script.Script_Hangul, _fam)
        log("korean font loaded", QFontDatabase.applicationFontFamilies(_fid))
    _so, _se, _eh = sys.stdout, sys.stderr, sys.excepthook
    main.setup_sys_redirections()
    sys.stdout, sys.stderr = _so, _se
    main.setup_logging()
    registry = main.run_discovery()
    set_global_registry(registry)
    log("widgets discovered:", len(registry.widgets()))
    mainwindow = main.setup_main_window()
    mainwindow.showMaximized()
    webpatches.install_unload_guard(mainwindow)
    globals()["_orange_main"] = (main, mainwindow)
    sys.modules["__main__"]._orange_main = (main, mainwindow)
    log("main window shown")
except Exception:
    traceback.print_exc()
    raise
