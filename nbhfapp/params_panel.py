"""Zone 2: preset and parameters. Every change takes effect at the next run.

A value left as the preset shows it is returned exactly as the preset holds it (no
round trip through the display units), so an untouched panel gives the Parameters of A.
"""
import dataclasses
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QVBoxLayout,
    QWidget,
)

from nbhf.parameters import Parameters

SPECIES_DIR = Path(__file__).resolve().parent / "species"
DEFAULT_PRESET = "bahia"

KHZ, MS, SECONDS, PLAIN = "khz", "ms", "s", "plain"
# name -> (unit, decimals, minimum, maximum) in display units
FIELDS = {
    # one decimal for kHz: with three, a French or Spanish system shows "100,000 kHz"
    "fcutLow": (KHZ, 1, 1, 1000),
    "fcutHigh": (KHZ, 1, 1, 1000),
    "coefUmbral": (PLAIN, 1, 0.1, 1000),
    "tMinimo": (MS, 2, 0.01, 1000),
    "f1clic": (KHZ, 1, 1, 1000),
    "f2clic": (KHZ, 1, 1, 1000),
    "f1": (KHZ, 1, 1, 1000),
    "f2": (KHZ, 1, 1, 1000),
    "chunkDuration": (SECONDS, 2, 0.1, 3600),
    "seuil": (PLAIN, 2, 0, 10),
    "tFusion": (MS, 2, 0, 1000),
}


def toDisplay(name, value):
    unit = FIELDS[name][0]
    if unit == KHZ:
        return value / 1000
    if unit == MS:
        return value * 1000
    return value


def fromDisplay(name, shown):
    unit = FIELDS[name][0]
    if unit == KHZ:
        return int(round(shown * 1000))     # the core needs whole Hz (it does f // 1000)
    if unit == MS:
        return shown / 1000
    return shown


def loadPresets(folder=SPECIES_DIR):
    """{name: Parameters} from the .toml files of folder; a file that does not load is skipped.
    Always contains at least the defaults of the core."""
    presets = {}
    if Path(folder).is_dir():
        for path in sorted(Path(folder).glob("*.toml")):
            try:
                presets[path.stem] = Parameters.fromToml(path)
            except Exception:
                continue
    if not presets:
        presets[DEFAULT_PRESET] = Parameters()
    return presets


class ParamsPanel(QWidget):
    changed = Signal()              # a parameter or the preset changed

    def __init__(self, parent=None, presets=None):
        super().__init__(parent)
        self._presets = presets if presets is not None else loadPresets()
        self._base = None
        self._loading = False
        self._spins = {}

        self.presetCombo = QComboBox()
        self.presetCombo.addItems(list(self._presets))
        self.modifiedLabel = QLabel()

        labels = {
            "fcutLow": self.tr("Filter, low cut-off"),
            "fcutHigh": self.tr("Filter, high cut-off"),
            "coefUmbral": self.tr("Amplitude threshold (× std)"),
            "tMinimo": self.tr("Silenced around a peak"),
            "f1clic": self.tr("Click band, from"),
            "f2clic": self.tr("Click band, to"),
            "f1": self.tr("Reference band, from"),
            "f2": self.tr("Reference band, to"),
            "chunkDuration": self.tr("Chunk duration"),
            "seuil": self.tr("Level ratio threshold"),
            "tFusion": self.tr("Merge of the two channels"),
        }
        suffixes = {KHZ: " kHz", MS: " ms", SECONDS: " s", PLAIN: ""}

        for name, (unit, decimals, low, high) in FIELDS.items():
            spin = QDoubleSpinBox()
            spin.setDecimals(decimals)
            spin.setRange(low, high)
            spin.setSuffix(suffixes[unit])
            spin.setKeyboardTracking(False)     # no signal for every typed digit
            spin.setAlignment(Qt.AlignmentFlag.AlignRight)
            self._spins[name] = spin
        self._spins["seuil"].setSingleStep(0.01)
        self._spins["coefUmbral"].setSingleStep(0.5)

        self.paramsGroup = QGroupBox()
        form = QFormLayout(self.paramsGroup)
        for name in FIELDS:
            form.addRow(labels[name], self._spins[name])
            self._spins[name].valueChanged.connect(self._onValue)

        presetRow = QHBoxLayout()
        presetRow.addWidget(QLabel(self.tr("Preset:")))
        presetRow.addWidget(self.presetCombo, 1)
        presetRow.addWidget(self.modifiedLabel)

        layout = QVBoxLayout(self)
        layout.addLayout(presetRow)
        layout.addWidget(self.paramsGroup)
        layout.addStretch()

        self.presetCombo.currentTextChanged.connect(self._onPreset)
        start = DEFAULT_PRESET if DEFAULT_PRESET in self._presets else next(iter(self._presets))
        self.presetCombo.setCurrentText(start)
        self._onPreset(start)

    # --- values --------------------------------------------------------------------

    def current(self):
        """The Parameters shown. Untouched values are those of the preset, exactly."""
        values = {}
        for name, spin in self._spins.items():
            base = getattr(self._base, name)
            tolerance = 0.5 * 10 ** -FIELDS[name][1]
            if abs(spin.value() - toDisplay(name, base)) < tolerance:
                values[name] = base
            else:
                values[name] = fromDisplay(name, spin.value())
        return dataclasses.replace(self._base, **values)

    def setValue(self, name, value):
        """Set one parameter, in the units of Parameters (Hz, s). Used by the tests."""
        self._spins[name].setValue(toDisplay(name, value))

    def setEditable(self, editable):
        self.presetCombo.setEnabled(editable)
        self.paramsGroup.setEnabled(editable)

    # --- internals -----------------------------------------------------------------

    def _onPreset(self, name):
        if name not in self._presets:
            return
        self._base = self._presets[name]
        self._loading = True
        for field, spin in self._spins.items():
            spin.setValue(toDisplay(field, getattr(self._base, field)))
        self._loading = False
        self._showModified()
        self.changed.emit()

    def _showModified(self):
        self.modifiedLabel.setText(self.tr("modified") if self.current() != self._base else "")

    def _onValue(self):
        if not self._loading:
            self._showModified()
            self.changed.emit()
