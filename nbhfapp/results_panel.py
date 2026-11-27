"""Zone 4: the table of candidates of the selected file.

The panel never changes the candidate table. The decision shown is the one of the run
(its `accepted` column).
"""
import numpy as np
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QLabel, QTableView,
    QVBoxLayout, QWidget,
)

REJECTED_COLOR = (150, 150, 150)     # rejected rows are written in grey

ALL, ACCEPTED, REJECTED = range(3)
# amplitude, threshold, levels, ratio and peak frequency stay in the table (export,
# Raven) but are not shown: they made the list harder to read.
COL_TIME, COL_CHANNEL, COL_DECISION = range(3)


class CandidateModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._table = None
        self._mask = np.zeros(0, dtype=bool)     # the accepted column of the table
        self._values = []           # one numeric array per column, for sorting
        self._headers = [
            self.tr("Time (s)"), self.tr("Ch."), self.tr("Decision"),
        ]
        self._formats = ["%.4f", "%d", None]
        self._greyBrush = QBrush(QColor(*REJECTED_COLOR))

    def setTable(self, table):
        self.beginResetModel()
        self._table = table
        if table is None:
            self._mask = np.zeros(0, dtype=bool)
            self._values = []
        else:
            self._mask = table["accepted"]
            self._values = [table["date"], table["channel"], None]
        self.endResetModel()

    def accepted(self, row):
        return bool(self._mask[row])

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() or self._table is None else len(self._table)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._headers)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self._headers[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row, column = index.row(), index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            if column == COL_DECISION:
                return self.tr("Accepted") if self._mask[row] else self.tr("Rejected")
            return self._formats[column] % self._values[column][row]
        if role == Qt.ItemDataRole.UserRole:        # sort key
            if column == COL_DECISION:
                return int(self._mask[row])
            return float(self._values[column][row])
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if column == COL_DECISION:
                return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.ForegroundRole and not self._mask[row]:
            return self._greyBrush
        return None


class CandidateFilter(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = ALL
        self.setSortRole(Qt.ItemDataRole.UserRole)

    def setMode(self, mode):
        self.beginFilterChange()
        self._mode = mode
        self.endFilterChange()

    def filterAcceptsRow(self, sourceRow, sourceParent):
        if self._mode == ALL:
            return True
        accepted = self.sourceModel().accepted(sourceRow)
        return accepted if self._mode == ACCEPTED else not accepted


class ResultsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.titleLabel = QLabel()
        self.filterCombo = QComboBox()
        self.filterCombo.addItems([self.tr("All candidates"), self.tr("Accepted only"),
                                   self.tr("Rejected only")])

        self.model = CandidateModel(self)
        self.proxy = CandidateFilter(self)
        self.proxy.setSourceModel(self.model)
        self.view = QTableView()
        self.view.setModel(self.proxy)
        self.view.setSortingEnabled(True)
        self.view.sortByColumn(COL_TIME, Qt.SortOrder.AscendingOrder)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.view.verticalHeader().setVisible(False)
        self.view.verticalHeader().setDefaultSectionSize(22)
        self.view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.view.horizontalHeader().setStretchLastSection(True)

        top = QHBoxLayout()
        top.addWidget(self.titleLabel, 1)
        top.addWidget(self.filterCombo)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.view, 1)

        self.filterCombo.currentIndexChanged.connect(self.proxy.setMode)
        self.clear()

    # --- content -------------------------------------------------------------------

    def clear(self):
        self.setFile("", None)

    def setFile(self, name, table):
        """Show the candidate table of one file (None: nothing to show)."""
        self.model.setTable(table)
        self.titleLabel.setText(self.tr("Candidates of {name}").format(name=name) if table is not None
                                else self.tr("No result for this file yet"))
        self.setEnabled(table is not None)
