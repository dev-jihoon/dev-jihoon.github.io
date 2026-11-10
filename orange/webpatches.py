# Patches that make Orange's blocking UI flows work in a single-threaded
# browser build where nested event loops (menu.exec(), dialog.exec(),
# drag.exec()) return immediately.
import logging, os, traceback
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

    - scroll lists, tables and panels by dragging a finger (QScroller)
    - text fields only take focus when tapped, so the on-screen keyboard
      does not appear when a window opens
    - tapping the arrows of a spin box steps the value without focusing
      its text field (which would bring up the keyboard)
    """
    def __init__(self):
        super().__init__()
        from AnyQt.QtWidgets import (
            QAbstractScrollArea, QGraphicsView, QLineEdit, QAbstractSpinBox,
            QTextEdit, QPlainTextEdit, QComboBox)
        self._done = set()
        self.QAbstractScrollArea = QAbstractScrollArea
        self.QGraphicsView = QGraphicsView
        self.text_types = (QLineEdit, QAbstractSpinBox, QTextEdit, QPlainTextEdit)
        self.QComboBox = QComboBox
        self.QAbstractSpinBox = QAbstractSpinBox
        try:
            from AnyQt.QtWidgets import QScroller
            self.QScroller = QScroller
        except ImportError:
            self.QScroller = None

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
            # the keyboard). The spin box itself takes no focus; its text
            # field still does when tapped, and forwards focus to it.
            w.setFocusPolicy(Qt.NoFocus)
            w.setAttribute(Qt.WA_AcceptTouchEvents, True)
        if self.QScroller is not None and isinstance(w, self.QAbstractScrollArea) \
                and not isinstance(w, self.QGraphicsView) \
                and not isinstance(w, (self.QAbstractSpinBox,)):
            try:
                self.QScroller.grabGesture(
                    w.viewport(), self.QScroller.ScrollerGestureType.TouchGesture)
            except Exception:
                pass

    def eventFilter(self, obj, ev):
        t = ev.type()
        if t == QEvent.Show and isinstance(obj, QWidget):
            self._setup(obj)
        elif t == QEvent.MouseButtonPress and \
                isinstance(obj.parent() if isinstance(obj, QWidget) else None,
                           self.QAbstractSpinBox):
            # mouse/trackpad click in the text part of a spin box
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
               patch_toolbox_drag, patch_file_widget, patch_save_graph):
        try:
            fn()
        except Exception:
            traceback.print_exc()
    try:
        patch_canvas_files(mainwindow_cls)
    except Exception:
        traceback.print_exc()
