"""Zone 2 (centre): summary of the run, every file at once.

Per file, how many candidates, how many pass the level test, how many detections remain
after merging the channels. A candidate can only fail one test
(levelClick > seuil * levelRef), so these three numbers say what the detector did.

The counts are those of the last run, with its parameters.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)


class SummaryPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._runs = []             # FileRun of the last run, in the order they were processed

        self.staleLabel = QLabel(self.tr(
            "Parameters changed since this run: these results were computed with the previous "
            "ones. Run again to update them."))
        self.staleLabel.setWordWrap(True)
        self.staleLabel.setStyleSheet("background: #f5d76e; color: black; padding: 4px;")
        self.staleLabel.hide()

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            [self.tr("File"), self.tr("Candidates"), self.tr("Accepted"), self.tr("Detections")])
        tips = [
            "",
            self.tr("Peaks of the filtered signal above the amplitude threshold (× std of the chunk)"),
            self.tr("Candidates whose click level is above the level ratio threshold × reference level"),
            self.tr("Accepted candidates left after merging the two channels"),
        ]
        for column, tip in enumerate(tips):
            self.table.horizontalHeaderItem(column).setToolTip(tip)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(22)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)

        layout = QVBoxLayout(self)
        layout.addWidget(self.staleLabel)
        layout.addWidget(self.table, 1)
        self.setRuns([])

    def setRuns(self, runs):
        """runs: the FileRun of the last run (an empty list: nothing to show)."""
        self._runs = list(runs)
        self._fill()

    def setStale(self, stale):
        self.staleLabel.setVisible(bool(stale))

    def rows(self):
        """[(name, candidates, accepted, detections)], the total last. Used by the tests."""
        return [tuple(self.table.item(r, c).text() if c == 0 else int(self.table.item(r, c).text())
                      for c in range(4))
                for r in range(self.table.rowCount())]

    def _fill(self):
        lines = []
        for run in self._runs:
            nAccepted = int(run.table["accepted"].sum())
            lines.append((run.path.name, len(run.table), nAccepted, run.nMerged))
        if len(lines) > 1:
            lines.append((self.tr("Total"), *(sum(line[k] for line in lines) for k in (1, 2, 3))))

        self.table.setRowCount(len(lines))
        bold = QFont(self.font())
        bold.setBold(True)
        for r, line in enumerate(lines):
            isTotal = len(lines) > 1 and r == len(lines) - 1
            for c, value in enumerate(line):
                item = QTableWidgetItem(str(value))
                if c > 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if isTotal:
                    item.setFont(bold)
                self.table.setItem(r, c, item)
