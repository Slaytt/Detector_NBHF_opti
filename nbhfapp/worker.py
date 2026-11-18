"""Qt side of a run: starts batch.runBatch in a separate process and turns its messages
into signals. The window never computes anything itself, so it stays responsive.

"""
import multiprocessing
import queue as queueModule

from PySide6.QtCore import QObject, QTimer, Signal

from nbhfapp.batch import runBatch

POLL_MS = 100


class Runner(QObject):
    fileStarted = Signal(str)
    fileDone = Signal(str, int, int, int, object)      # path, n1, n2, nMerged, table
    fileFailed = Signal(str, str)                      # path, message
    finished = Signal(int, float)                      # files processed, seconds
    crashed = Signal(str)                              # the process died without finishing

    def __init__(self, parent=None):
        super().__init__(parent)
        # "spawn" everywhere: it is the only start method on Windows, and the default on macOS
        self._context = multiprocessing.get_context("spawn")
        self._process = None
        self._queue = None
        self._stopEvent = None
        self._timer = QTimer(self)
        self._timer.setInterval(POLL_MS)
        self._timer.timeout.connect(self._poll)

    def isRunning(self):
        return self._process is not None

    def start(self, paths, outDir, params):
        if self.isRunning():
            return
        self._queue = self._context.Queue()
        self._stopEvent = self._context.Event()
        self._process = self._context.Process(
            target=runBatch,
            args=([str(p) for p in paths], str(outDir), params, self._queue, self._stopEvent),
            daemon=True,
        )
        self._process.start()
        self._timer.start()

    def requestStop(self):
        """Stop after the file being processed."""
        if self.isRunning():
            self._stopEvent.set()

    def abort(self):
        """Kill the process at once (the window is closing)."""
        if self.isRunning():
            self._timer.stop()
            self._process.terminate()
            self._process.join(2)
            self._cleanup()

    def _cleanup(self):
        self._process = None
        self._queue = None
        self._stopEvent = None

    def _poll(self):
        while self.isRunning():
            try:
                message = self._queue.get_nowait()
            except queueModule.Empty:
                break
            kind = message[0]
            if kind == "started":
                self.fileStarted.emit(message[1])
            elif kind == "done":
                self.fileDone.emit(*message[1:])
            elif kind == "failed":
                self.fileFailed.emit(message[1], message[2])
            elif kind == "finished":
                self._timer.stop()
                self._process.join(5)
                self._cleanup()
                self.finished.emit(message[1], message[2])
                return

        if self.isRunning() and not self._process.is_alive() and self._queue.empty():
            code = self._process.exitcode
            self._timer.stop()
            self._cleanup()
            self.crashed.emit(str(code))
