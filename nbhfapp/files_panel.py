"""Zone 1: the list of files, the output folder, Run and Stop.

The panel holds no result and starts no computation: it shows states and emits signals.
"""
from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from nbhf.reading import read_info

WAITING, RUNNING, DONE, ERROR = "waiting", "running", "done", "error"

COL_NAME, COL_DURATION, COL_STATE, COL_DETECTIONS = range(4)


def formatDuration(seconds):
    minutes, s = divmod(int(round(seconds)), 60)
    return f"{minutes}:{s:02d}"


class FilesPanel(QWidget):
    runRequested = Signal()
    stopRequested = Signal()
    fileSelected = Signal(str)          # path of the selected file, "" when nothing is selected
    listChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._paths = []                # row k of the table <-> self._paths[k]
        self._outputEdited = False      # True once the user has chosen the output folder
        self._running = False

        self.addFilesButton = QPushButton(self.tr("Add files…"))
        self.addFolderButton = QPushButton(self.tr("Add folder…"))
        self.removeButton = QPushButton(self.tr("Remove"))
        self.runButton = QPushButton(self.tr("Run"))
        self.stopButton = QPushButton(self.tr("Stop"))
        self.stopButton.setToolTip(self.tr("Stops after the file being processed"))

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([
            self.tr("File"), self.tr("Duration"), self.tr("Status"), self.tr("Detections"),
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        for column in (COL_DURATION, COL_STATE, COL_DETECTIONS):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)

        self.outputEdit = QLineEdit()
        self.outputEdit.setPlaceholderText(self.tr("Results folder"))
        self.outputButton = QPushButton(self.tr("Choose…"))
        self.summaryLabel = QLabel()

        top = QHBoxLayout()
        top.addWidget(self.addFilesButton)
        top.addWidget(self.addFolderButton)
        top.addWidget(self.removeButton)
        top.addStretch()

        output = QHBoxLayout()
        output.addWidget(QLabel(self.tr("Results folder:")))
        output.addWidget(self.outputEdit, 1)
        output.addWidget(self.outputButton)

        bottom = QHBoxLayout()
        bottom.addWidget(self.summaryLabel, 1)
        bottom.addWidget(self.runButton)
        bottom.addWidget(self.stopButton)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.table, 1)
        layout.addLayout(output)
        layout.addLayout(bottom)

        self.addFilesButton.clicked.connect(self._chooseFiles)
        self.addFolderButton.clicked.connect(self._chooseFolder)
        self.removeButton.clicked.connect(self.removeSelected)
        self.outputButton.clicked.connect(self._chooseOutput)
        self.outputEdit.textEdited.connect(self._onOutputEdited)
        self.runButton.clicked.connect(self.runRequested)
        self.stopButton.clicked.connect(self.stopRequested)
        self.table.itemSelectionChanged.connect(self._onSelection)

        self._refresh()

    # --- content -------------------------------------------------------------------

    def paths(self):
        return list(self._paths)

    def outputDir(self):
        return self.outputEdit.text().strip()

    def addPaths(self, paths):
        """Add wav files, skipping those already listed. Returns the number added."""
        added = 0
        for path in paths:
            path = Path(path)
            if path in self._paths:
                continue
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._paths.append(path)
            name = QTableWidgetItem(path.name)
            name.setToolTip(str(path))
            self.table.setItem(row, COL_NAME, name)
            for column in (COL_DURATION, COL_STATE, COL_DETECTIONS):
                item = QTableWidgetItem("")
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, column, item)
            try:
                info = read_info(path)
                self.table.item(row, COL_DURATION).setText(formatDuration(info.n_samples / info.sample_rate))
                self._setState(row, WAITING)
            except Exception as e:
                # shown at once, and the run will report the same error
                self._setState(row, ERROR, f"{type(e).__name__}: {e}")
            added += 1
        if added:
            if not self._outputEdited:
                # next to the first file
                parent = self._paths[0].parent
                self.outputEdit.setText(str(parent / f"Resultats_{date.today().isoformat()}"))
            self._refresh()
            self.listChanged.emit()
        return added

    def addFolder(self, folder):
        """Add the wav files directly inside folder (sub-folders are not visited)."""
        wavs = sorted(p for p in Path(folder).iterdir()
                      if p.is_file() and p.suffix.lower() == ".wav" and not p.name.startswith("."))
        return self.addPaths(wavs)

    def removeSelected(self):
        if self._running:
            return
        rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)
            del self._paths[row]
        if rows:
            self._refresh()
            self.listChanged.emit()

    # --- states, driven by the window ----------------------------------------------

    def setRunning(self, running):
        self._running = running
        self._refresh()

    def resetStates(self):
        for row in range(self.table.rowCount()):
            self._setState(row, WAITING)
            self.table.item(row, COL_DETECTIONS).setText("")

    def markRunning(self, path):
        row = self._row(path)
        if row is not None:
            self._setState(row, RUNNING)
            self.table.scrollToItem(self.table.item(row, COL_NAME))

    def markDone(self, path, nMerged):
        row = self._row(path)
        if row is not None:
            self._setState(row, DONE)
            self.table.item(row, COL_DETECTIONS).setText(str(nMerged))
        self._refresh()

    def markFailed(self, path, message):
        row = self._row(path)
        if row is not None:
            self._setState(row, ERROR, message)
        self._refresh()

    def selectPath(self, path):
        row = self._row(path)
        if row is not None:
            self.table.selectRow(row)

    # --- internals -----------------------------------------------------------------

    def _row(self, path):
        try:
            return self._paths.index(Path(path))
        except ValueError:
            return None

    def _stateText(self, state):
        return {
            WAITING: self.tr("Waiting"),
            RUNNING: self.tr("Running…"),
            DONE: self.tr("Done"),
            ERROR: self.tr("Error"),
        }[state]

    def _setState(self, row, state, message=""):
        item = self.table.item(row, COL_STATE)
        item.setData(Qt.ItemDataRole.UserRole, state)
        item.setText(self._stateText(state))
        item.setToolTip(message)

    def _refresh(self):
        n = len(self._paths)
        states = [self.table.item(row, COL_STATE).data(Qt.ItemDataRole.UserRole) for row in range(n)]
        done, errors = states.count(DONE), states.count(ERROR)
        if n == 0:
            self.summaryLabel.setText(self.tr("No file"))
        elif errors:
            self.summaryLabel.setText(self.tr("{done} of {total} done, {errors} in error")
                                      .format(done=done, total=n, errors=errors))
        else:
            self.summaryLabel.setText(self.tr("{done} of {total} done").format(done=done, total=n))

        idle = not self._running
        for widget in (self.addFilesButton, self.addFolderButton, self.outputEdit, self.outputButton):
            widget.setEnabled(idle)
        self.removeButton.setEnabled(idle and bool(self.table.selectedIndexes()))
        self.runButton.setEnabled(idle and n > 0)
        self.stopButton.setEnabled(self._running)

    def _onSelection(self):
        rows = sorted({index.row() for index in self.table.selectedIndexes()})
        self.removeButton.setEnabled(not self._running and bool(rows))
        self.fileSelected.emit(str(self._paths[rows[0]]) if len(rows) == 1 else "")

    def _onOutputEdited(self):
        self._outputEdited = True

    def _startFolder(self):
        return str(self._paths[-1].parent) if self._paths else ""

    def _chooseFiles(self):
        names, _ = QFileDialog.getOpenFileNames(
            self, self.tr("Add files"), self._startFolder(), self.tr("WAV files (*.wav *.WAV)"))
        if names:
            self.addPaths(names)

    def _chooseFolder(self):
        folder = QFileDialog.getExistingDirectory(self, self.tr("Add folder"), self._startFolder())
        if folder:
            self.addFolder(folder)

    def _chooseOutput(self):
        folder = QFileDialog.getExistingDirectory(self, self.tr("Results folder"), self.outputDir())
        if folder:
            self.outputEdit.setText(folder)
            self._outputEdited = True
