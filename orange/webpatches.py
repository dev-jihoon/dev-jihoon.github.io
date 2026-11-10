# Patches that make Orange's blocking UI flows work in a single-threaded
# browser build where nested event loops (menu.exec(), dialog.exec(),
# drag.exec()) return immediately.
import logging, os, sys, traceback
from AnyQt.QtCore import Qt, QObject, QEvent, QPoint, QPointF, QTimer, QMimeData
from AnyQt.QtWidgets import QApplication, QLabel, QGraphicsView, QWidget

log = logging.getLogger("webpatches")


# ---------------------------------------------------------------------------
# Quick menu: asynchronous variant of QuickMenu.exec()
# ---------------------------------------------------------------------------
def quickmenu_async(menu, pos, search_text, callback, on_done=None):
    prev = getattr(menu, "_web_async_handler", None)
    if prev is not None:
        try:
            menu.triggered.disconnect(prev)
        except Exception:
            pass

    def handler(action):
        try:
            menu.triggered.disconnect(handler)
        except Exception:
            pass
        menu._web_async_handler = None
        try:
            callback(action)
        except Exception:
            traceback.print_exc()
        finally:
            if on_done is not None:
                on_done()

    menu._web_async_handler = handler
    menu.triggered.connect(handler)
    menu.popup(pos, search_text)
    menu.setFocus(Qt.PopupFocusReason)


# ---------------------------------------------------------------------------
# Dialogs: open() + finished signal instead of exec()
# ---------------------------------------------------------------------------
_alive = set()


def dialog_async(dlg, callback=None):
    """Show `dlg` window-modal and call `callback(result)` when it closes.

    exec() cannot block in the browser, so every place that needs the answer
    of a dialog continues from here instead.
    """
    _alive.add(dlg)

    def finished(result):
        try:
            dlg.finished.disconnect(finished)
        except Exception:
            pass
        QTimer.singleShot(0, lambda: _alive.discard(dlg))
        if callback is not None:
            try:
                callback(result)
            except Exception:
                traceback.print_exc()
    dlg.finished.connect(finished)
    dlg.open()
    return dlg


def message_box_async(mbox, callback):
    """Like dialog_async, but report the clicked standard button."""
    def done(_result):
        btn = mbox.clickedButton()
        callback(mbox.standardButton(btn) if btn is not None else mbox.escapeButton())
    return dialog_async(mbox, done)


def patch_menus():
    # A QMenu that only Python holds would be garbage collected as soon as
    # the (now non-blocking) exec() returns; keep it until it closes.
    from AnyQt.QtWidgets import QMenu
    orig = QMenu.exec

    def exec_(self, *args, **kwargs):
        if isinstance(self, QMenu):
            _alive.add(self)
            self.aboutToHide.connect(
                lambda m=self: QTimer.singleShot(0, lambda: _alive.discard(m)))
        return orig(self, *args, **kwargs)
    QMenu.exec = exec_
    QMenu.exec_ = exec_


def patch_interactions():
    from orangecanvas.document import interactions as I
    from orangecanvas.document import commands
    from orangecanvas.registry.qt import QtWidgetRegistry
    from orangecanvas.document.usagestatistics import UsageStatistics
    from orangecanvas.utils import unique
    import orangecanvas.scheme as _scheme_mod

    # --- right click / double click / typing on empty canvas ---------------
    def create_new(self, pos, search_text=""):
        menu = self.document.quickMenu()
        menu.setFilterFunc(None)

        def defaultSort(left, right):
            default_suggestions = self.suggestions.get_default_suggestions()
            return sum(default_suggestions[left].values()) > \
                sum(default_suggestions[right].values())
        menu.setSortingFunc(defaultSort)
        document = self.document

        def done(action):
            if not action:
                return
            item = action.property("item")
            desc = item.data(QtWidgetRegistry.WIDGET_DESC_ROLE)
            view = document.view()
            p = view.mapToScene(view.mapFromGlobal(pos))
            document.usageStatistics().begin_action(UsageStatistics.QuickMenu)
            node = document.newNodeHelper(desc, position=(p.x(), p.y()))
            document.addNode(node)
        quickmenu_async(menu, pos, search_text, done)
        return None
    I.NewNodeAction.create_new = create_new

    # --- link dragged onto an empty part of the canvas ---------------------
    orig_release = I.NewLinkAction.mouseReleaseEvent

    def mouseReleaseEvent(self, event):
        if self.tmp_link_item is not None and \
                self.target_node_item_at(event.scenePos()) is None:
            self._web_create_new_async(event)
            self.end()
            return True
        return orig_release(self, event)

    def _web_create_new_async(self, event):
        pos = event.screenPos()
        scene_pos = event.scenePos()
        menu = self.document.quickMenu()
        node = self.scene.node_for_item(self.from_item)
        from_node = node
        from_signal = self.from_signal
        from_desc = node.description
        direction = self.direction
        scheme_ = self.scheme
        document = self.document
        suggestions = self.suggestions
        from_sink = direction == self.FROM_SINK

        def is_compatible(source_signal, source, sink, sink_signal):
            return any(_scheme_mod.compatible_channels(output, input_)
                       for output in ([source_signal] if source_signal else source.outputs)
                       for input_ in ([sink_signal] if sink_signal else sink.inputs))
        if from_sink:
            is_compat = lambda a, b, c, d: is_compatible(d, c, b, a)
            suggestion_sort = suggestions.get_source_suggestions(from_desc.name)
        else:
            is_compat = is_compatible
            suggestion_sort = suggestions.get_sink_suggestions(from_desc.name)
        menu.setSortingFunc(lambda l, r: suggestion_sort[l] > suggestion_sort[r])

        def filt(index):
            desc = index.data(QtWidgetRegistry.WIDGET_DESC_ROLE)
            from orangecanvas.registry import WidgetDescription
            if isinstance(desc, WidgetDescription):
                return is_compat(from_signal, from_desc, desc, None)
            return False
        menu.setFilterFunc(filt)
        menu.triggerSearch()

        def done(action):
            if not action:
                return
            item = action.property("item")
            desc = item.data(QtWidgetRegistry.WIDGET_DESC_ROLE)
            offset = 31 * (-1 if from_sink else 1)
            document.usageStatistics().begin_extend_action(from_sink, from_node)
            new_node = document.newNodeHelper(
                desc, position=(scene_pos.x() + offset, scene_pos.y()))
            macro = I.UndoCommand(self.tr("Add link"))
            commands.AddNodeCommand(scheme_, new_node, parent=macro)
            if from_sink:
                source_node, sink_node = new_node, from_node
                source_signal, sink_signal = None, from_signal
            else:
                source_node, sink_node = from_node, new_node
                source_signal, sink_signal = from_signal, None
            self.macro = macro
            suggestions.set_direction(direction)
            try:
                self.connect_nodes(source_node, sink_node, source_signal, sink_signal)
            except Exception:
                traceback.print_exc()
            document.undoStack().push(macro)
            self.macro = None

        quickmenu_async(menu, pos, "", done, on_done=lambda: menu.setFilterFunc(None))

    I.NewLinkAction.mouseReleaseEvent = mouseReleaseEvent
    I.NewLinkAction._web_create_new_async = _web_create_new_async


def _apply_link_edits(document, scheme_, source_node, sink_node, links_spec):
    """Apply the result of an EditLinksDialog (same as EditNodeLinksAction)."""
    from orangecanvas.scheme import SchemeLink
    existing = scheme_.find_links(source_node=source_node, sink_node=sink_node)
    existing_links = [(l.source_channel, l.sink_channel) for l in existing]
    links_to_add = set(links_spec) - set(existing_links)
    links_to_remove = set(existing_links) - set(links_spec)
    if not links_to_add and not links_to_remove:
        return
    stack = document.undoStack()
    stack.beginMacro("Edit Links")
    try:
        for _, sink_channel in links_to_add:
            if sink_channel.single:
                others = scheme_.find_links(sink_node=sink_node, sink_channel=sink_channel)
                for link in others:
                    if link.source_node is not source_node:
                        document.removeLink(link)
        for source_channel, sink_channel in links_to_remove:
            for link in scheme_.find_links(source_node, source_channel,
                                           sink_node, sink_channel):
                document.removeLink(link)
        for source_channel, sink_channel in links_to_add:
            document.addLink(SchemeLink(source_node, source_channel,
                                        sink_node, sink_channel))
    finally:
        stack.endMacro()


def open_link_editor(document, scheme_, source_node, sink_node, initial_links=None):
    from orangecanvas.document.editlinksdialog import EditLinksDialog
    dlg = EditLinksDialog(document, windowTitle="Edit Links")
    if initial_links is None:
        initial_links = [(l.source_channel, l.sink_channel) for l in
                         scheme_.find_links(source_node=source_node, sink_node=sink_node)]
    dlg.setNodes(source_node, sink_node)
    dlg.setLinks(initial_links)

    def done(result):
        if result == EditLinksDialog.Accepted:
            _apply_link_edits(document, scheme_, source_node, sink_node, dlg.links())
    dialog_async(dlg, done)


def patch_link_dialogs():
    from orangecanvas.document import interactions as I
    from orangecanvas.document.editlinksdialog import EditLinksDialog

    def new_link_edit_links(self, source_node, sink_node, initial_links=None):
        # The new link is ambiguous: let the user choose in the dialog, which
        # applies the links itself when accepted. The drag ends here.
        open_link_editor(self.document, self.scheme, source_node, sink_node, initial_links)
        return EditLinksDialog.Rejected, [], []
    I.NewLinkAction.edit_links = new_link_edit_links

    def node_links_edit_links(self, initial_links=None):
        open_link_editor(self.document, self.scheme, self.source_node,
                         self.sink_node, initial_links)
    I.EditNodeLinksAction.edit_links = node_links_edit_links


# ---------------------------------------------------------------------------
# Toolbox drag & drop without QDrag.exec(): follow the pointer ourselves
# ---------------------------------------------------------------------------
class _ManualDrag(QObject):
    def __init__(self):
        super().__init__()
        self.mime = None
        self.label = None

    def start(self, mime, pixmap):
        self.mime = mime
        lbl = QLabel(None, Qt.ToolTip | Qt.FramelessWindowHint)
        lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        lbl.setAttribute(Qt.WA_TranslucentBackground)
        if pixmap is not None and not pixmap.isNull():
            lbl.setPixmap(pixmap)
            lbl.resize(pixmap.size())
        self.label = lbl
        QApplication.instance().installEventFilter(self)

    def _finish(self):
        QApplication.instance().removeEventFilter(self)
        if self.label is not None:
            self.label.hide()
            self.label.deleteLater()
        self.label = None
        self.mime = None

    def eventFilter(self, obj, ev):
        t = ev.type()
        if t == QEvent.MouseMove and self.label is not None:
            gp = ev.globalPosition().toPoint()
            self.label.move(gp - QPoint(self.label.width() // 2, self.label.height() // 2))
            if not self.label.isVisible():
                self.label.show()
            return False
        if t == QEvent.MouseButtonRelease and self.mime is not None:
            gp = ev.globalPosition().toPoint()
            mime = self.mime
            self._finish()
            QTimer.singleShot(0, lambda: _drop_at(gp, mime))
            return False
        return False


_manual_drag = None


def _drop_at(global_pos, mime):
    target = QApplication.widgetAt(global_pos)
    w = target
    view = None
    while w is not None:
        if isinstance(w, QGraphicsView):
            view = w
            break
        w = w.parentWidget()
    if view is None:
        return
    name = bytes(mime.data("application/vnd.orange-canvas.registry.qualified-name")).decode("utf-8")
    from orangecanvas.registry import global_registry
    desc = global_registry().widget(name)
    doc = view.parentWidget()
    while doc is not None and not hasattr(doc, "createNewNode"):
        doc = doc.parentWidget()
    if doc is None:
        return
    p = view.mapToScene(view.viewport().mapFromGlobal(global_pos))
    doc.createNewNode(desc, position=(p.x(), p.y()))


class FakeDrag(QObject):
    def __init__(self, source=None):
        super().__init__(source)
        self._mime = None
        self._pixmap = None
    def setMimeData(self, m): self._mime = m
    def mimeData(self): return self._mime
    def setPixmap(self, p): self._pixmap = p
    def pixmap(self): return self._pixmap
    def setHotSpot(self, p): pass
    def exec(self, *a, **k):
        global _manual_drag
        _manual_drag = _ManualDrag()
        _manual_drag.start(self._mime, self._pixmap)
        return Qt.IgnoreAction
    exec_ = exec


def patch_toolbox_drag():
    from orangecanvas.application import widgettoolbox, canvastooldock
    widgettoolbox.QDrag = FakeDrag
    canvastooldock.QDrag = FakeDrag


# ---------------------------------------------------------------------------
# Files: browser upload / download instead of Qt file dialogs
# ---------------------------------------------------------------------------
UPLOAD_DIR = "/home/pyodide/data"


def _js():
    import js
    return js


def browser_open_file(accept, callback):
    """Ask the browser for a file, copy it into the virtual FS, then callback(path)."""
    from pyodide.ffi import create_proxy
    js = _js()
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    def on_file(name, data):
        try:
            path = os.path.join(UPLOAD_DIR, str(name))
            with open(path, "wb") as f:
                f.write(bytes(data.to_py()))
            callback(path)
        except Exception:
            traceback.print_exc()
    proxy = create_proxy(on_file)
    js.orangeWebPickFile(accept, proxy)


def browser_save_file(path, suggested_name):
    js = _js()
    from pyodide.ffi import to_js
    with open(path, "rb") as f:
        data = f.read()
    js.orangeWebDownload(suggested_name, to_js(data))


def patch_file_widget():
    from Orange.widgets.data import owfile
    from Orange.widgets.utils import filedialogs

    def browse_file(self, in_demos=False):
        from AnyQt.QtWidgets import QMenu
        from AnyQt.QtGui import QCursor
        exts = set()
        for r in getattr(self, "available_readers", []):
            exts.update(getattr(r, "EXTENSIONS", ()))
        accept = ",".join(sorted(exts)) or "*"

        def load(path):
            self.add_path(path)
            self.source = self.LOCAL_FILE
            self.load_data()

        def upload():
            browser_open_file(accept, load)

        if not in_demos:
            # Opening the browser's file picker must happen inside the click.
            upload()
            return
        menu = QMenu(self)
        sample_dir = owfile.get_sample_datasets_dir()
        try:
            names = sorted(n for n in os.listdir(sample_dir)
                           if n.endswith((".tab", ".csv", ".xlsx", ".tsv")))
        except OSError:
            names = []
        for n in names:
            act = menu.addAction(n)
            act.triggered.connect(lambda _=False, n=n: load(os.path.join(sample_dir, n)))
        menu.popup(QCursor.pos())
        self._web_menu = menu
    owfile.OWFile.browse_file = browse_file


def patch_save_graph():
    """The save-image button of plot widgets: pick PNG or SVG, then download."""
    import tempfile
    from AnyQt.QtWidgets import QMenu
    from AnyQt.QtGui import QCursor
    from orangewidget.utils import saveplot

    def save_plot(data, file_formats, start_dir="", filename=""):
        writers = [w for w in file_formats
                   if any(ext in (".png", ".svg") for ext in getattr(w, "EXTENSIONS", ()))]
        menu = QMenu()
        for writer in writers:
            ext = writer.EXTENSIONS[0]
            act = menu.addAction("%s (*%s)" % (writer.DESCRIPTION, ext))

            def save(_=False, writer=writer, ext=ext):
                name = (os.path.splitext(os.path.basename(filename))[0] or "graph") + ext
                path = os.path.join(tempfile.gettempdir(), name)
                try:
                    writer.write(path, data)
                    browser_save_file(path, name)
                except Exception:
                    traceback.print_exc()
            act.triggered.connect(save)
        _alive.add(menu)
        menu.aboutToHide.connect(lambda: QTimer.singleShot(0, lambda: _alive.discard(menu)))
        menu.popup(QCursor.pos())
    saveplot.save_plot = save_plot


def patch_canvas_files(mainwindow_cls):
    import tempfile
    from AnyQt.QtWidgets import QMessageBox, QDialog
    from orangecanvas.application import canvasmain as cm
    from orangecanvas import config

    def _download_name(self):
        document = self.current_document()
        path = document.path()
        if path:
            name = os.path.basename(path)
        else:
            title = (document.scheme().title or "workflow").strip() or "workflow"
            name = "".join(c if c.isalnum() or c in "-_ ." else "_" for c in title)
        if not name.lower().endswith(".ows"):
            name += ".ows"
        return name

    def save_scheme_as(self):
        document = self.current_document()
        scheme = document.scheme()
        name = _download_name(self)
        path = os.path.join(tempfile.gettempdir(), name)
        try:
            self.save_scheme_to(scheme, path)
            browser_save_file(path, name)
            document.setModified(False)
            return QDialog.Accepted
        except Exception:
            traceback.print_exc()
            return QDialog.Rejected

    def save_scheme(self):
        return save_scheme_as(self)

    def ask_save_changes_async(self, proceed):
        """Ask Save / Don't Save / Cancel; call proceed() unless cancelled."""
        document = self.current_document()
        if not document.isModifiedStrict():
            proceed()
            return
        # Same message box as CanvasMainWindow.ask_save_changes
        _tr = cm._tr
        path = document.path()
        if path:
            text = self.tr(_tr.m[165, 'Do you want to save changes made to %s?']) \
                % os.path.basename(path)
        else:
            text = self.tr(_tr.m[166, 'Do you want to save this workflow?'])
        mb = QMessageBox(QMessageBox.Question, self.tr(_tr.m[167, "Save Changes?"]),
                         text,
                         QMessageBox.Save | QMessageBox.Cancel | QMessageBox.Discard,
                         self)
        mb.setInformativeText(
            self.tr(_tr.m[168, "Your changes will be lost if you do not save them."]))
        mb.setDefaultButton(QMessageBox.Save)

        def answered(button):
            if button == QMessageBox.Save:
                if save_scheme(self) == QDialog.Accepted:
                    proceed()
            elif button == QMessageBox.Discard:
                proceed()
        message_box_async(mb, answered)

    def ask_save_changes(self):
        # Synchronous callers (e.g. closing the window) cannot wait for an
        # answer in the browser; ask, and report "cancelled" for now.
        ask_save_changes_async(self, lambda: None)
        return QDialog.Rejected

    def new_workflow_window(self):
        # One window in the browser: replace the current workflow instead of
        # opening another main window.
        def proceed():
            document = self.current_document()
            self.set_scheme(config.workflow_constructor(parent=self))
            document.setPath("")
            document.undoStack().clear()
            document.setModified(False)
        ask_save_changes_async(self, proceed)

    def open_scheme(self):
        def loaded(path):
            try:
                self.load_scheme(path)
                self.current_document().setModified(False)
            except Exception:
                traceback.print_exc()
        ask_save_changes_async(self, lambda: browser_open_file(".ows", loaded))
        return QDialog.Accepted

    def show_scheme_properties(self):
        current_doc = self.current_document()
        scheme = current_doc.scheme()
        dlg = self.scheme_properties_dialog()
        dlg.setAutoCommit(False)
        dlg.setScheme(scheme)

        def done(status):
            if status == QDialog.Accepted:
                editor = dlg.editor
                stack = current_doc.undoStack()
                stack.beginMacro("Change Info")
                current_doc.setTitle(editor.title())
                current_doc.setDescription(editor.description())
                stack.endMacro()
        dialog_async(dlg, done)
        return QDialog.Accepted

    for cls in {cm.CanvasMainWindow, mainwindow_cls}:
        cls.save_scheme_as = save_scheme_as
        cls.save_scheme = save_scheme
        cls.open_scheme = open_scheme
        cls.ask_save_changes = ask_save_changes
        cls.ask_save_changes_async = ask_save_changes_async
        cls.new_workflow_window = new_workflow_window
        cls.show_scheme_properties = show_scheme_properties

    # Options > Settings: apply the preferences when the dialog closes
    from Orange.canvas.mainwindow import OUserSettingsDialog

    def open_canvas_settings(self):
        dlg = OUserSettingsDialog(self, windowTitle=self.tr("Preferences"))
        dialog_async(dlg, lambda status: self.user_preferences_changed_notify_all())
    mainwindow_cls.open_canvas_settings = open_canvas_settings


def install_unload_guard(mainwindow):
    """Let the browser warn before leaving the page with unsaved changes."""
    js = _js()
    document = mainwindow.current_document()

    def update(*_):
        try:
            js.window.orangeModified = bool(document.isModifiedStrict())
        except Exception:
            pass
    document.modificationChanged.connect(update)
    update()


# ---------------------------------------------------------------------------
# Touch devices (iPad)
# ---------------------------------------------------------------------------
def is_touch_device():
    try:
        return int(_js().navigator.maxTouchPoints) > 0
    except Exception:
        return False


class _TouchTweaks(QObject):
    """App-wide event filter used on touch devices:

    - scroll lists and tables by dragging a finger (taps still click)
    - a combo box pop-up ignores taps in its first moments, so the second
      tap of a double tap does not pick an item right away
    - text fields only take focus when tapped, so the on-screen keyboard
      does not appear when a window opens
    - tapping the arrows of a spin box steps the value without focusing
      its text field (which would bring up the keyboard)
    - touch and hold opens the context menu (e.g. Remove a widget or link
      on the canvas), as a right click would
    """
    LONG_PRESS_MS = 550
    LONG_PRESS_SLOP = 12

    def __init__(self):
        super().__init__()
        from AnyQt.QtWidgets import (
            QAbstractItemView, QGraphicsView, QLineEdit, QAbstractSpinBox,
            QTextEdit, QPlainTextEdit, QComboBox)
        from AnyQt.QtGui import QInputDevice
        self._done = set()
        self.QAbstractItemView = QAbstractItemView
        self.text_types = (QLineEdit, QAbstractSpinBox, QTextEdit, QPlainTextEdit)
        self.QComboBox = QComboBox
        self.QAbstractSpinBox = QAbstractSpinBox
        self.TouchScreen = QInputDevice.DeviceType.TouchScreen
        try:
            from AnyQt.QtWidgets import QScroller
            self.QScroller = QScroller
        except ImportError:
            self.QScroller = None
        self._scroll = None   # finger scrolling state for an item view
        self._replaying = False
        self._hold_timer = QTimer(self, singleShot=True, interval=self.LONG_PRESS_MS)
        self._hold_timer.timeout.connect(self._long_press)
        self._hold_pos = None
        self._popup_shown_at = None   # QElapsedTimer of the last combo pop-up
        self._swallow_release = None

    POPUP_GRACE_MS = 400

    def _popup_guard(self, obj, ev, t):
        """Ignore touch taps that reach a combo pop-up right after it opened."""
        if t == QEvent.Show and isinstance(obj, QWidget) and \
                obj.metaObject().className() == "QComboBoxPrivateContainer":
            from AnyQt.QtCore import QElapsedTimer
            self._popup_shown_at = QElapsedTimer()
            self._popup_shown_at.start()
            return False
        if t == QEvent.MouseButtonRelease and self._swallow_release is not None \
                and obj is self._swallow_release:
            # only at the widget that lost its press; never at the window
            # level, where Qt clears its mouse grab
            self._swallow_release = None
            return True
        if t == QEvent.MouseButtonPress and isinstance(obj, QWidget) \
                and obj is not self._swallow_release:
            self._swallow_release = None
        if t in (QEvent.MouseButtonPress, QEvent.MouseButtonDblClick) \
                and self._popup_shown_at is not None and self._is_touch(ev) \
                and isinstance(obj, QWidget) \
                and obj.window().metaObject().className() == "QComboBoxPrivateContainer" \
                and self._popup_shown_at.elapsed() < self.POPUP_GRACE_MS:
            self._swallow_release = obj
            return True
        return False

    @staticmethod
    def _in_combo_popup(w):
        p = w.parentWidget()
        while p is not None:
            if p.metaObject().className() == "QComboBoxPrivateContainer":
                return True
            p = p.parentWidget()
        return False

    def _setup(self, w):
        key = id(w)
        if key in self._done:
            return
        self._done.add(key)
        w.destroyed.connect(lambda *_, key=key: self._done.discard(key))
        if isinstance(w, self.text_types) or \
                (isinstance(w, self.QComboBox) and w.isEditable()):
            if w.focusPolicy() & Qt.TabFocus:
                w.setFocusPolicy(Qt.ClickFocus)
        if isinstance(w, self.QAbstractSpinBox):
            # Tapping the arrows must not focus the spin box (that brings up
            # the keyboard). The spin box itself takes no focus; tapping its
            # number focuses it explicitly (see eventFilter).
            w.setFocusPolicy(Qt.NoFocus)
            w.setAttribute(Qt.WA_AcceptTouchEvents, True)
        if isinstance(w, self.QAbstractItemView) and not self._in_combo_popup(w):
            # smooth finger scrolling (see eventFilter)
            w.setVerticalScrollMode(self.QAbstractItemView.ScrollMode.ScrollPerPixel)
            w.setHorizontalScrollMode(self.QAbstractItemView.ScrollMode.ScrollPerPixel)

    def _is_touch(self, ev):
        try:
            return ev.device().type() == self.TouchScreen
        except Exception:
            return False

    def _long_press(self):
        from AnyQt.QtGui import QContextMenuEvent
        if self._hold_pos is None:
            return
        gpos = self._hold_pos
        self._hold_pos = None
        if self._scroll is not None:
            self._scroll["cancel"] = True   # no click after the menu
        target = QApplication.widgetAt(gpos)
        if target is None:
            return
        ev = QContextMenuEvent(QContextMenuEvent.Reason.Mouse,
                               target.mapFromGlobal(gpos), gpos)
        QApplication.sendEvent(target, ev)

    def _item_view_of_viewport(self, obj):
        p = obj.parent() if isinstance(obj, QWidget) else None
        if isinstance(p, self.QAbstractItemView) and p.viewport() is obj \
                and not self._in_combo_popup(p):
            return p
        return None

    def _finger_scroll(self, obj, ev, t):
        """Drag a finger over a list/table to scroll it.

        The press is held back until the finger lifts: if it moved, the
        gesture was a scroll and the view never sees the press (so nothing
        gets selected); if it did not, the press (and a double click) is
        replayed before the release, so taps work as clicks."""
        if self._replaying:
            return False
        if t == QEvent.MouseButtonPress and self._is_touch(ev):
            view = self._item_view_of_viewport(obj)
            if view is None:
                return False
            gp = ev.globalPosition()
            self._scroll = dict(view=view, viewport=obj, start=gp, last=gp,
                                active=False, cancel=False,
                                pending=[self._copy_mouse(ev)])
            return True
        st = self._scroll
        if st is None or obj is not st["viewport"]:
            return False
        if t == QEvent.MouseButtonDblClick:
            st["pending"].append(self._copy_mouse(ev))
            return True
        if t == QEvent.MouseMove:
            gp = ev.globalPosition()
            d0 = gp - st["start"]
            if not st["active"] and (abs(d0.x()) > 10 or abs(d0.y()) > 10):
                st["active"] = True
            if st["active"]:
                d = gp - st["last"]
                st["last"] = gp
                view = st["view"]
                vs, hs = view.verticalScrollBar(), view.horizontalScrollBar()
                vs.setValue(vs.value() - int(round(d.y())))
                hs.setValue(hs.value() - int(round(d.x())))
            return True
        if t == QEvent.MouseButtonRelease:
            self._scroll = None
            if st["active"] or st["cancel"]:
                return True
            self._replaying = True
            try:
                for e in st["pending"]:
                    QApplication.sendEvent(obj, e)
            finally:
                self._replaying = False
            return False
        return False

    @staticmethod
    def _copy_mouse(ev):
        from AnyQt.QtGui import QMouseEvent
        return QMouseEvent(ev.type(), ev.position(), ev.scenePosition(),
                           ev.globalPosition(), ev.button(), ev.buttons(),
                           ev.modifiers(), ev.pointingDevice())

    def eventFilter(self, obj, ev):
        t = ev.type()
        if self._popup_guard(obj, ev, t):
            return True
        if t == QEvent.Show and isinstance(obj, QWidget):
            self._setup(obj)
        elif t == QEvent.MouseButtonPress and self._is_touch(ev) and not self._replaying:
            if not self._hold_timer.isActive():
                self._hold_pos = ev.globalPosition().toPoint()
                self._hold_timer.start()
        elif t == QEvent.MouseMove and self._hold_timer.isActive():
            d = ev.globalPosition().toPoint() - self._hold_pos
            if abs(d.x()) > self.LONG_PRESS_SLOP or abs(d.y()) > self.LONG_PRESS_SLOP:
                self._hold_timer.stop()
                self._hold_pos = None
        elif t == QEvent.MouseButtonRelease:
            self._hold_timer.stop()
            self._hold_pos = None
        if t in (QEvent.MouseButtonPress, QEvent.MouseButtonDblClick,
                 QEvent.MouseMove, QEvent.MouseButtonRelease) \
                and self._finger_scroll(obj, ev, t):
            return True

        if t == QEvent.MouseButtonPress and \
                isinstance(obj.parent() if isinstance(obj, QWidget) else None,
                           self.QAbstractSpinBox):
            # click/tap in the text part of a spin box
            obj.parent().setFocus(Qt.MouseFocusReason)
        elif t in (QEvent.TouchBegin, QEvent.TouchUpdate, QEvent.TouchEnd) \
                and isinstance(obj, self.QAbstractSpinBox):
            points = ev.points()
            if not points:
                return False
            pos = points[0].position().toPoint()
            if pos.x() < obj.width() - 22:
                # text part: focus it, which brings up the keyboard
                if t == QEvent.TouchBegin and obj.isEnabled():
                    obj.setFocus(Qt.MouseFocusReason)
                return False
            if t == QEvent.TouchBegin and obj.isEnabled():
                if pos.y() < obj.height() / 2:
                    obj.stepUp()
                else:
                    obj.stepDown()
            ev.accept()
            return True
        return False


_touch_tweaks = None


def apply_touch_tweaks(mainwindow):
    global _touch_tweaks
    if not is_touch_device():
        return False
    app = QApplication.instance()
    _touch_tweaks = _TouchTweaks()
    app.installEventFilter(_touch_tweaks)
    for w in app.allWidgets():
        _touch_tweaks._setup(w)
    # start with the canvas focused instead of the toolbox filter field
    try:
        mainwindow.current_document().view().setFocus(Qt.OtherFocusReason)
    except Exception:
        pass
    return True


def apply_all(mainwindow_cls):
    for fn in (patch_menus, patch_interactions, patch_link_dialogs,
               patch_toolbox_drag, patch_file_widget, patch_save_graph,
               patch_dialog_exec, patch_modal_dialogs, patch_error_reporting,
               patch_save_svg, patch_canvas_dialogs, patch_csv_import):
        try:
            fn()
        except Exception:
            traceback.print_exc()
    try:
        patch_canvas_files(mainwindow_cls)
    except Exception:
        traceback.print_exc()


class _TouchDebug(QObject):
    """?touchdebug: draw where Qt receives presses (red) and releases (green);
    the page draws where the finger touched (blue)."""
    def eventFilter(self, obj, ev):
        from AnyQt.QtGui import QWindow
        t = ev.type()
        if t in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease) and isinstance(obj, QWindow):
            p = ev.globalPosition()
            try:
                _js().orangeQtPoint(p.x(), p.y(), t == QEvent.MouseButtonPress)
            except Exception:
                pass
        return False


_touch_debug = None


def apply_touch_debug():
    global _touch_debug
    try:
        if not bool(_js().orangeTouchDebug):
            return False
    except Exception:
        return False
    _touch_debug = _TouchDebug()
    QApplication.instance().installEventFilter(_touch_debug)
    return True


def apply_windows_look():
    """Look like Orange on Windows 11: Qt 6.8's "windows11" style (built into
    this Qt), Selawik for Segoe UI (same metrics), light colors with the
    default Windows accent, as Orange's Windows installer (PyQt6 6.8) shows."""
    from AnyQt.QtGui import QFontDatabase, QFont, QPalette, QColor, QGuiApplication
    for f in ("selawk.ttf", "selawksb.ttf", "selawkb.ttf", "OrangeWebFluentIcons.otf"):
        QFontDatabase.addApplicationFont("/fonts/" + f)
    app = QApplication.instance()
    try:
        QGuiApplication.styleHints().setColorScheme(Qt.ColorScheme.Light)
    except AttributeError:
        pass
    font = QFont("Selawik")
    font.setPointSizeF(9)
    app.setFont(font)
    pal = app.palette()
    # Windows default accent; controls use AccentDark1 in light mode
    pal.setColor(QPalette.ColorRole.Accent, QColor(0x00, 0x5F, 0xB8))
    pal.setColor(QPalette.ColorRole.Link, QColor(0x00, 0x3E, 0x92))
    pal.setColor(QPalette.ColorRole.LinkVisited, QColor(0x00, 0x1A, 0x68))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(0xFF, 0xFF, 0xFF))
    app.setPalette(pal)
    app.setStyle("windows11")
    return app.style().objectName()


# ---------------------------------------------------------------------------
# Every other modal dialog: QFileDialog, QMessageBox
# ---------------------------------------------------------------------------
# exec() and the static QFileDialog / QMessageBox helpers return at once in the
# browser, so code waiting for an answer would get "Cancel". These replacements
#  - save dialogs: answer at once with a fresh temporary path and download the
#    file when the calling code has written it;
#  - open dialogs and questions: show the browser file picker / the message
#    box, and when the user answers, run the Qt slot that asked again; this
#    time the dialog answers at once with what the user chose.
# Message boxes that only inform are shown without blocking.

SAVE_DIR = "/home/pyodide/save"
_pending = {}        # kind -> answer for the replayed call
_replaying = [0]


def _calling_slot(skip=2):
    """Return a callable that repeats the outermost Python method call on the
    stack (the slot Qt called), or None."""
    import inspect
    from AnyQt.QtCore import QEvent as _QEvent
    f = sys._getframe(skip)
    frames = []
    while f is not None:
        frames.append(f)
        f = f.f_back
    for fr in reversed(frames):
        self_ = fr.f_locals.get("self")
        if self_ is None or isinstance(self_, QApplication):
            continue
        if fr.f_globals.get("__name__", "").startswith(("_pyodide", "pyodide")):
            continue
        name = fr.f_code.co_name
        if name.startswith("__") or name in ("event", "eventFilter", "notify") or name.endswith("Event"):
            continue
        try:
            meth = getattr(self_, name)
        except Exception:
            continue
        func = getattr(meth, "__func__", None)
        if func is None:
            continue
        try:
            func = inspect.unwrap(func)
        except Exception:
            pass
        if getattr(func, "__code__", None) is not fr.f_code:
            continue
        co = fr.f_code
        n, k = co.co_argcount, co.co_kwonlyargcount
        loc = fr.f_locals
        names = co.co_varnames[1:n]
        if any(isinstance(loc.get(a), _QEvent) for a in names):
            continue
        args = [loc[a] for a in names if a in loc]
        kw = {a: loc[a] for a in co.co_varnames[n:n + k] if a in loc}
        if co.co_flags & inspect.CO_VARARGS:
            args += list(loc.get(co.co_varnames[n + k], ()))
        return lambda: meth(*args, **kw)
    return None


def _replay_with(kind, answer, replay):
    _pending[kind] = answer
    _replaying[0] += 1
    try:
        replay()
    except Exception:
        traceback.print_exc()
    finally:
        _replaying[0] -= 1
        _pending.pop(kind, None)


def _filter_exts(filter_str):
    """'Tab (*.tab);;CSV (*.csv *.txt)' -> ['.tab', '.csv', '.txt']; [] if any."""
    import re
    exts = []
    for pat in re.findall(r"\*(\.[\w.]+|)", filter_str or ""):
        if not pat:
            return []
        exts.append(pat.lower())
    return exts


def _filter_for(filter_str, path):
    for f in (filter_str or "").split(";;"):
        exts = _filter_exts(f)
        if not exts or any(path.lower().endswith(e) for e in exts):
            return f
    return ""


def _new_save_path(name, filter_str="", default_suffix=""):
    import tempfile
    name = os.path.basename(name or "") or "untitled"
    exts = _filter_exts(filter_str)
    if not os.path.splitext(name)[1]:
        if exts:
            name += exts[0]
        elif default_suffix:
            name += "." + default_suffix.lstrip(".")
    os.makedirs(SAVE_DIR, exist_ok=True)
    return os.path.join(tempfile.mkdtemp(dir=SAVE_DIR), name)


def _download_when_written(path):
    def check():
        try:
            if os.path.exists(path) and os.path.getsize(path) > 0:
                browser_save_file(path, os.path.basename(path))
        except Exception:
            traceback.print_exc()
    QTimer.singleShot(0, check)


def _ask_open(filter_str, multi, replay):
    accept = ",".join(_filter_exts(filter_str))

    def got(path):
        answer = ([path] if multi else path, _filter_for(filter_str, path))
        _replay_with("open", answer, replay)
    browser_open_file(accept, got)


def patch_modal_dialogs():
    from AnyQt.QtWidgets import QFileDialog, QMessageBox, QDialog

    # ---- QFileDialog static helpers
    def getSaveFileName(parent=None, caption="", directory="", filter="",
                        initialFilter="", options=None, **kw):
        path = _new_save_path(directory, initialFilter or filter.split(";;")[0])
        _download_when_written(path)
        return path, initialFilter or _filter_for(filter, path)

    def _open(multi):
        def get(parent=None, caption="", directory="", filter="",
                initialFilter="", options=None, **kw):
            if "open" in _pending:
                return _pending.pop("open")
            replay = _calling_slot(2)
            if replay is not None:
                _ask_open(filter, multi, replay)
            return ([] if multi else ""), ""
        return staticmethod(get)

    QFileDialog.getSaveFileName = staticmethod(getSaveFileName)
    QFileDialog.getOpenFileName = _open(False)
    QFileDialog.getOpenFileNames = _open(True)

    # ---- QFileDialog instances
    def fd_exec(self):
        filters = ";;".join(self.nameFilters())
        if self.acceptMode() == QFileDialog.AcceptMode.AcceptSave:
            sel = self.selectedFiles()
            path = _new_save_path(sel[0] if sel else "", self.selectedNameFilter(),
                                  self.defaultSuffix())
            self.selectedFiles = lambda: [path]
            QDialog.done(self, QDialog.DialogCode.Accepted)
            _download_when_written(path)
            return QDialog.DialogCode.Accepted
        if "open" in _pending:
            paths, flt = _pending.pop("open")
            paths = paths if isinstance(paths, list) else [paths]
            self.selectedFiles = lambda: list(paths)
            if flt:
                self.selectedNameFilter = lambda: flt
            QDialog.done(self, QDialog.DialogCode.Accepted)
            return QDialog.DialogCode.Accepted
        replay = _calling_slot(2)
        multi = self.fileMode() == QFileDialog.FileMode.ExistingFiles
        if replay is not None:
            _ask_open(filters, multi, replay)
        QDialog.done(self, QDialog.DialogCode.Rejected)
        return QDialog.DialogCode.Rejected
    QFileDialog.exec = fd_exec
    QFileDialog.exec_ = fd_exec

    # ---- QMessageBox
    Std = QMessageBox.StandardButton
    NEGATIVE = (Std.Cancel, Std.No, Std.Abort, Std.Ignore, Std.Close, Std.Discard)

    def _is_question(box):
        return len(box.buttons()) > 1

    def _negative(box):
        esc = box.escapeButton()
        if esc is not None and box.standardButton(esc) != Std.NoButton:
            return box.standardButton(esc)
        for b in NEGATIVE:
            if box.button(b) is not None:
                return b
        btns = box.buttons()
        return box.standardButton(btns[-1]) if btns else Std.Ok

    def _show_box(box, on_answer=None):
        box.setWindowModality(Qt.WindowModality.WindowModal if box.parent() is not None
                              else Qt.WindowModality.ApplicationModal)
        _alive.add(box)

        def finished(_r):
            QTimer.singleShot(0, lambda: _alive.discard(box))
            if on_answer is not None:
                btn = box.clickedButton()
                text = btn.text() if btn is not None else None
                std = box.standardButton(btn) if btn is not None else _negative(box)
                on_answer(std, text)
        box.finished.connect(finished)
        box.show()
        box.raise_()

    def mb_exec(self):
        if "mbox" in _pending:
            std, text = _pending.pop("mbox")
            match = [b for b in self.buttons() if b.text() == text]
            if match:
                self.clickedButton = lambda m=match[0]: m
            return int(std.value) if hasattr(std, "value") else int(std)
        if not _is_question(self):
            _show_box(self)
            btns = self.buttons()
            return int(self.standardButton(btns[0]).value) if btns else int(Std.Ok.value)
        replay = _calling_slot(2)
        if replay is None:
            _show_box(self)
        else:
            _show_box(self, lambda std, text: _replay_with("mbox", (std, text), replay))
        neg = _negative(self)
        return int(neg.value)
    QMessageBox.exec = mb_exec
    QMessageBox.exec_ = mb_exec

    def _static(icon, question=False):
        def f(parent, title, text, buttons=None, defaultButton=Std.NoButton):
            if buttons is None:
                buttons = (Std.Yes | Std.No) if question else Std.Ok
            box = QMessageBox(icon, title, text, buttons, parent)
            if defaultButton != Std.NoButton:
                box.setDefaultButton(defaultButton)
            r = box.exec()
            return Std(r)
        return staticmethod(f)
    QMessageBox.information = _static(QMessageBox.Icon.Information)
    QMessageBox.warning = _static(QMessageBox.Icon.Warning)
    QMessageBox.critical = _static(QMessageBox.Icon.Critical)
    QMessageBox.question = _static(QMessageBox.Icon.Question, question=True)

    def about(parent, title, text):
        box = QMessageBox(QMessageBox.Icon.Information, title, text, Std.Ok, parent)
        _show_box(box)
    QMessageBox.about = staticmethod(about)


def patch_error_reporting():
    """An exception shows Orange's "Error Encountered" box (what Orange shows on
    Windows without internet) without blocking, and never tries to reach the
    report server."""
    from orangewidget.workflow import errorreporting
    errorreporting.internet_on = lambda: False


def patch_save_svg():
    """File > Save Workflow Image as SVG: write the SVG and download it."""
    from orangecanvas.application.canvasmain import CanvasMainWindow
    from orangecanvas.canvas import scene as _scene

    def save_as_svg(self):
        doc = self.current_document()
        path = doc.path()
        base = os.path.splitext(os.path.basename(path))[0] if path else "untitled"
        out = _new_save_path(base + ".svg")
        try:
            content = _scene.grab_svg(doc.scene())
            with open(out, "wt", encoding="utf-8") as f:
                f.write(content)
            browser_save_file(out, os.path.basename(out))
        except Exception:
            traceback.print_exc()
    CanvasMainWindow.save_as_svg = save_as_svg


def patch_dialog_exec():
    """Any other dialog shown with exec(): show it (window-modal) and keep it
    alive until it closes, instead of leaving a modal window behind."""
    from AnyQt.QtWidgets import QDialog

    def exec_(self):
        dialog_async(self)
        return int(QDialog.DialogCode.Rejected.value)
    QDialog.exec = exec_
    QDialog.exec_ = exec_


def patch_canvas_dialogs():
    """File > Open Recent and Help > Example Workflows."""
    from AnyQt.QtWidgets import QDialog
    from AnyQt.QtCore import QSettings
    from orangecanvas.application import canvasmain as cm
    from orangecanvas.preview import previewdialog, previewmodel
    from orangecanvas.utils.settings import QSettings_readArray
    from orangecanvas import config

    def _show_preview(self, title, items, on_choose):
        dialog = previewdialog.PreviewDialog(self)
        model = previewmodel.PreviewModel(dialog, items=items)
        dialog.setWindowTitle(title)
        template = ('<h3 style="font-size: 26px">\n' + ('{0}\n' + '</h3>'))
        dialog.setHeading(template.format(title))
        dialog.setModel(model)
        model.delayedScanUpdate()

        def done(status):
            index = dialog.currentIndex()
            dialog.deleteLater()
            if status == QDialog.DialogCode.Accepted and index >= 0:
                on_choose(model.item(index).path())
        dialog_async(dialog, done)
        return QDialog.DialogCode.Rejected

    def recent_scheme(self):
        settings = QSettings()
        recent_items = QSettings_readArray(
            settings, "mainwindow/recent-items", {"title": (str, ""), "path": (str, "")})
        recent = [cm.RecentItem(**item) for item in recent_items]
        recent = [item for item in recent if os.path.exists(item.path)]
        items = [previewmodel.PreviewItem(name=item.title, path=item.path) for item in recent]
        return _show_preview(self, self.tr(cm._tr.m[200, "Recent Workflows"]), items,
                             self.open_scheme_file)

    def examples_dialog(self):
        tutors = cm.examples.workflows(config.default)
        items = [previewmodel.PreviewItem(path=t.abspath()) for t in tutors]
        return _show_preview(self, self.tr(cm._tr.m[201, "Example Workflows"]), items,
                             self.open_example_scheme)

    cm.CanvasMainWindow.recent_scheme = recent_scheme
    cm.CanvasMainWindow.examples_dialog = examples_dialog


def patch_csv_import():
    """CSV File Import: pick the file in the browser, then the Import Options
    dialog, without blocking."""
    from AnyQt.QtWidgets import QDialog
    from Orange.widgets.data import owcsvimport as M

    def browse(self, prefixname=None, directory=None):
        dlg = self._browse_dialog()
        filters = ";;".join(dlg.nameFilters())
        formats = list(dlg.fileFormats())
        dlg.deleteLater()

        def picked(path):
            flt = _filter_for(filters, path)
            names = [M.FileDialog.filterStr(f) for f in formats]
            selected_filter = formats[names.index(flt)] if flt in names else formats[0]
            self.dialog_state["directory"] = os.path.dirname(path)
            self.dialog_state["filter"] = M.FileDialog.filterStr(selected_filter)
            if prefixname:
                _prefixpath = self._replacements().get(prefixname, "")
                if not M.isprefixed(_prefixpath, path):
                    self._path_must_be_relative_mb(_prefixpath).show()
                    return
                varpath = M.VarPath(prefixname, os.path.relpath(path, _prefixpath))
            else:
                varpath = M.PathItem.AbsPath(path)
            options = M.default_options_for_mime_type(path, selected_filter.mime_type)
            items = self.itemsFromSettings()
            idx = M.index_where(items, lambda t: M.samepath(t[0], path))
            if idx is not None:
                _, options_ = items[idx]
                if options_ is not None:
                    options = options_
            d = M.CSVImportDialog(self, windowTitle="Import Options", sizeGripEnabled=True)
            d.setWindowModality(Qt.WindowModality.WindowModal)
            d.setPath(path)
            d.setOptions(options)

            def done(status):
                d.deleteLater()
                if status == QDialog.DialogCode.Accepted:
                    self.set_selected_file(path, d.options())
                    self.current_item().setVarPath(varpath)
            dialog_async(d, done)
        browser_open_file(",".join(_filter_exts(filters)), picked)
    M.OWCSVFileImport.browse = browse
