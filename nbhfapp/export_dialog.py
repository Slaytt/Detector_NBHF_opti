"""Export dialog: which files to write from the results shown, and where.

The dialog only collects choices; export.exportRuns writes the files.
"""
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QRadioButton, QVBoxLayout,
)

from nbhfapp.export import CLICKS, TRAINS, ExportOptions


class ExportDialog(QDialog):
    def __init__(self, parent, nFiles, seuil, tFusion, folder, staleLines):
        """staleLines: one text line per parameter that differs between the panel and the run
        (empty when the results shown match the parameters shown)."""
        super().__init__(parent)
        self.setWindowTitle(self.tr("Export"))

        self.summaryLabel = QLabel(self.tr(
            "{n} file(s), with level ratio threshold {seuil} and channel merge {fusion} ms.")
            .format(n=nFiles, seuil="%g" % seuil, fusion="%g" % (tFusion * 1000)))
        self.summaryLabel.setWordWrap(True)

        self.staleLabel = QLabel()
        self.staleLabel.setWordWrap(True)
        self.staleLabel.setStyleSheet("background: #f5d76e; color: black; padding: 4px;")
        if staleLines:
            self.staleLabel.setText(self.tr(
                "The results were computed with other parameters than those shown. "
                "The export uses the parameters of the run:") + "\n" + "\n".join(staleLines))
        self.staleLabel.setVisible(bool(staleLines))

        self.ravenCheck = QCheckBox(self.tr("Raven selection tables"))
        self.ravenCheck.setChecked(True)
        self.clicksRadio = QRadioButton(self.tr("One click per line"))
        self.clicksRadio.setChecked(True)
        self.trainsRadio = QRadioButton(self.tr("Clicks grouped in trains, largest gap"))
        self.gapSpin = QDoubleSpinBox()
        self.gapSpin.setRange(0.01, 60)
        self.gapSpin.setDecimals(2)
        self.gapSpin.setSingleStep(0.1)
        self.gapSpin.setValue(0.5)
        self.gapSpin.setSuffix(" s")
        trains = QHBoxLayout()
        trains.addWidget(self.trainsRadio)
        trains.addWidget(self.gapSpin)
        trains.addStretch()
        ravenOptions = QVBoxLayout()
        ravenOptions.setContentsMargins(24, 0, 0, 0)
        ravenOptions.addWidget(self.clicksRadio)
        ravenOptions.addLayout(trains)

        self.resCheck = QCheckBox(self.tr("Detection dates (Res_*.txt) and summary (BilanTot.txt)"))
        self.candidatesCheck = QCheckBox(self.tr("Tables of all candidates (Candidats_*.csv)"))

        self.folderEdit = QLineEdit(str(folder))
        self.folderButton = QPushButton(self.tr("Choose…"))
        self.folderButton.clicked.connect(self._chooseFolder)
        folderRow = QHBoxLayout()
        folderRow.addWidget(self.folderEdit, 1)
        folderRow.addWidget(self.folderButton)
        form = QFormLayout()
        form.addRow(self.tr("Folder:"), folderRow)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr("Export"))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.summaryLabel)
        layout.addWidget(self.staleLabel)
        layout.addWidget(self.ravenCheck)
        layout.addLayout(ravenOptions)
        layout.addWidget(self.resCheck)
        layout.addWidget(self.candidatesCheck)
        layout.addLayout(form)
        layout.addWidget(self.buttons)

        for box in (self.ravenCheck, self.resCheck, self.candidatesCheck):
            box.toggled.connect(self._refresh)
        self.trainsRadio.toggled.connect(self._refresh)
        self.folderEdit.textChanged.connect(self._refresh)
        self._refresh()

    def options(self):
        return ExportOptions(
            res=self.resCheck.isChecked(),
            raven=self.ravenCheck.isChecked(),
            ravenMode=TRAINS if self.trainsRadio.isChecked() else CLICKS,
            maxGap=self.gapSpin.value(),
            candidates=self.candidatesCheck.isChecked(),
        )

    def folder(self):
        return self.folderEdit.text().strip()

    def _refresh(self):
        raven = self.ravenCheck.isChecked()
        self.clicksRadio.setEnabled(raven)
        self.trainsRadio.setEnabled(raven)
        self.gapSpin.setEnabled(raven and self.trainsRadio.isChecked())
        something = raven or self.resCheck.isChecked() or self.candidatesCheck.isChecked()
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(something and bool(self.folder()))

    def _chooseFolder(self):
        folder = QFileDialog.getExistingDirectory(self, self.tr("Export"), self.folder())
        if folder:
            self.folderEdit.setText(folder)
