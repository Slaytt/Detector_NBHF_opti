"""The single window: files (left), summary of the run (centre), parameters (right),
and the candidates of the selected file (bottom).

The window owns the state of the last run (its parameters, one candidate table per
file) and passes it to the panels. The panels do not know each other.
"""
import dataclasses
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QFrame, QLabel, QMainWindow, QMessageBox, QSplitter

from nbhf.reading import read_info
from nbhfapp.export import FileRun, exportRuns
from nbhfapp.export_dialog import ExportDialog
from nbhfapp.files_panel import FilesPanel
from nbhfapp.params_panel import ParamsPanel
from nbhfapp.results_panel import ResultsPanel
from nbhfapp.summary_panel import SummaryPanel
from nbhfapp.worker import Runner


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(self.tr("NBHF click detector"))
        self.resize(1400, 860)

        self.runParams = None           # Parameters of the last run
        self.runOutDir = ""             # its results folder
        self.runs = {}                  # path (str) -> FileRun of the last run
        self.selectedPath = ""
        self.runner = Runner(self)

        self.filesPanel = FilesPanel()
        self.resultsPanel = ResultsPanel()
        self.paramsPanel = ParamsPanel()
        self.summaryPanel = SummaryPanel()

        top = QSplitter(Qt.Orientation.Horizontal)
        top.addWidget(self.filesPanel)
        top.addWidget(self.summaryPanel)
        top.addWidget(self.paramsPanel)
        top.setStretchFactor(0, 3)
        top.setStretchFactor(1, 3)
        top.setStretchFactor(2, 2)
        top.setSizes([480, 480, 440])

        # bottom right: room kept for the future metrics tab (precision / recall)
        self.metricsPlaceholder = QLabel(self.tr("Metrics (coming later)"))
        self.metricsPlaceholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.metricsPlaceholder.setFrameShape(QFrame.Shape.StyledPanel)
        self.metricsPlaceholder.setEnabled(False)

        bottom = QSplitter(Qt.Orientation.Horizontal)
        bottom.addWidget(self.resultsPanel)
        bottom.addWidget(self.metricsPlaceholder)
        bottom.setStretchFactor(0, 1)
        bottom.setStretchFactor(1, 1)
        bottom.setSizes([700, 700])

        main = QSplitter(Qt.Orientation.Vertical)
        main.addWidget(top)
        main.addWidget(bottom)
        main.setStretchFactor(0, 4)
        main.setStretchFactor(1, 1)
        main.setSizes([620, 240])
        self.setCentralWidget(main)
        self.statusBar()

        self.exportAction = QAction(self.tr("Export…"), self)
        self.exportAction.setShortcut(QKeySequence("Ctrl+E"))
        self.exportAction.triggered.connect(self.openExport)
        quitAction = QAction(self.tr("Quit"), self)
        quitAction.setMenuRole(QAction.MenuRole.QuitRole)
        quitAction.setShortcut(QKeySequence.StandardKey.Quit)
        quitAction.triggered.connect(self.close)
        menu = self.menuBar().addMenu(self.tr("File"))
        menu.addAction(self.exportAction)
        menu.addSeparator()
        menu.addAction(quitAction)
        toolbar = self.addToolBar(self.tr("Main"))
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        toolbar.addAction(self.exportAction)

        self.filesPanel.runRequested.connect(self.startRun)
        self.filesPanel.stopRequested.connect(self.stopRun)
        self.filesPanel.listChanged.connect(self._forgetRemoved)
        self.filesPanel.fileSelected.connect(self._onFileSelected)
        self.paramsPanel.changed.connect(self._onParamsChanged)
        self.runner.fileStarted.connect(self._onStarted)
        self.runner.fileDone.connect(self._onDone)
        self.runner.fileFailed.connect(self.filesPanel.markFailed)
        self.runner.finished.connect(self._onFinished)
        self.runner.crashed.connect(self._onCrashed)

        self._refreshActions()

    # --- run -----------------------------------------------------------------------

    def parameterProblems(self, p):
        """Reasons why these parameters cannot be used, in words; empty when they are fine."""
        problems = []
        if not p.fcutLow < p.fcutHigh:
            problems.append(self.tr("The low cut-off of the filter must be under the high cut-off."))
        if not p.f1clic < p.f2clic:
            problems.append(self.tr("The click band must go from a lower to a higher frequency."))
        if not p.f1 < p.f2:
            problems.append(self.tr("The reference band must go from a lower to a higher frequency."))
        return problems

    def startRun(self):
        """Process the whole list again: BilanTot.txt then always describes the list shown."""
        paths = self.filesPanel.paths()
        outDir = self.filesPanel.outputDir()
        if not paths or self.runner.isRunning():
            return
        params = self.paramsPanel.current()
        problems = self.parameterProblems(params)
        if problems:
            QMessageBox.warning(self, self.windowTitle(), "\n".join(problems))
            return
        if not outDir:
            QMessageBox.warning(self, self.windowTitle(), self.tr("Choose a results folder first."))
            return
        try:
            Path(outDir).mkdir(parents=True, exist_ok=True)
        except OSError as e:
            QMessageBox.warning(self, self.windowTitle(),
                                self.tr("The results folder cannot be created:") + f"\n{e}")
            return
        self.runParams = params
        self.runOutDir = outDir
        self.runs.clear()
        self._showSelected()
        self.summaryPanel.setRuns([])
        self.summaryPanel.setStale(False)
        self.filesPanel.resetStates()
        self.filesPanel.setRunning(True)
        self.paramsPanel.setEditable(False)
        self._refreshActions()
        self.runner.start(paths, outDir, params)

    def stopRun(self):
        self.runner.requestStop()
        self.statusBar().showMessage(self.tr("Stopping after the current file…"))

    def _onStarted(self, path):
        self.filesPanel.markRunning(path)
        self.statusBar().showMessage(Path(path).name)

    def _onDone(self, path, n1, n2, nMerged, table):
        try:
            info = read_info(path)
        except Exception as e:
            self.filesPanel.markFailed(path, f"{type(e).__name__}: {e}")
            return
        self.runs[path] = FileRun(Path(path), table, info.sample_rate, info.n_channels > 1, nMerged)
        self.filesPanel.markDone(path, nMerged)
        self.summaryPanel.setRuns(self.runs.values())
        if path == self.selectedPath:
            self._showSelected()

    def _onFinished(self, nProcessed, seconds):
        self._endRun()
        self.statusBar().showMessage(
            self.tr("{n} file(s) processed in {seconds} s").format(n=nProcessed, seconds=f"{seconds:.1f}"))
        if not self.selectedPath and self.runs:
            self.filesPanel.selectPath(next(iter(self.runs)))

    def _onCrashed(self, code):
        self._endRun()
        QMessageBox.critical(self, self.windowTitle(),
                             self.tr("The computation stopped unexpectedly (code {code}).").format(code=code))

    def _endRun(self):
        self.filesPanel.setRunning(False)
        self.paramsPanel.setEditable(True)
        self._refreshActions()

    def _onFileSelected(self, path):
        self.selectedPath = path
        self._showSelected()

    def _showSelected(self):
        run = self.runs.get(self.selectedPath)
        if run is None:
            self.resultsPanel.clear()
        else:
            self.resultsPanel.setFile(run.path.name, run.table)

    def _onParamsChanged(self):
        self.summaryPanel.setStale(bool(self._staleNames()))

    def _staleNames(self):
        if self.runParams is None or not self.runs:
            return []
        # any parameter differing from the run makes the results stale
        shown = self.paramsPanel.current()
        return [f.name for f in dataclasses.fields(shown)
                if getattr(shown, f.name) != getattr(self.runParams, f.name)]

    def _forgetRemoved(self):
        listed = {str(p) for p in self.filesPanel.paths()}
        for path in [p for p in self.runs if p not in listed]:
            del self.runs[path]
        self.summaryPanel.setRuns(self.runs.values())
        self._refreshActions()

    def _refreshActions(self):
        self.exportAction.setEnabled(bool(self.runs) and not self.runner.isRunning())

    # --- dialogs -------------------------------------------------------------------

    def openExport(self):
        if not self.runs:
            return
        dialog = ExportDialog(self, len(self.runs), self.runParams.seuil, self.runParams.tFusion,
                              Path(self.runOutDir) / "Export")
        if dialog.exec() != ExportDialog.DialogCode.Accepted:
            return
        self.export(dialog.folder(), dialog.options())

    def export(self, folder, options):
        """Write the export; returns the files written (empty on failure)."""
        try:
            written = exportRuns(list(self.runs.values()), folder, self.runParams, options)
        except OSError as e:
            QMessageBox.warning(self, self.windowTitle(), self.tr("The export failed:") + f"\n{e}")
            return []
        self.statusBar().showMessage(
            self.tr("{n} file(s) written in {folder}").format(n=len(written), folder=folder))
        return written

    def closeEvent(self, event):
        self.runner.abort()
        super().closeEvent(event)
