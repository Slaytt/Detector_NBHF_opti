"""Zone 2: preset and parameters, in two groups.

"Needs a new run": parameters that change which candidates exist.
"Applied at once": parameters that choose among the candidates already measured.

A value left as the preset shows it is returned exactly as the preset holds it (no
round trip through the display units), so an untouched panel gives the Parameters of A.
"""
import dataclasses
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QSlider,
    QVBoxLayout, QWidget,
)

from nbhf.parameters import Parameters

SPECIES_DIR = Path(__file__).resolve().parent.parent / "species"
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
SEUIL_SLIDER_MAX = 200          # the slider covers 0.00 to 2.00


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
    recomputeChanged = Signal()     # a parameter of the first group changed
    directChanged = Signal()        # seuil or tFusion changed

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

        self.recomputeGroup = QGroupBox(self.tr("Needs a new run"))
        form = QFormLayout(self.recomputeGroup)
        for name in ("fcutLow", "fcutHigh", "coefUmbral", "tMinimo",
                     "f1clic", "f2clic", "f1", "f2", "chunkDuration"):
            form.addRow(labels[name], self._spins[name])
            self._spins[name].valueChanged.connect(self._onRecompute)

        self.seuilSlider = QSlider(Qt.Orientation.Horizontal)
        self.seuilSlider.setRange(0, SEUIL_SLIDER_MAX)
        self.ruleCombo = QComboBox()
        self.ruleCombo.addItems([self.tr("Threshold of the original detector"),
                                 self.tr("Model from a file… (not available yet)")])
        self.ruleCombo.model().item(1).setEnabled(False)

        self.directGroup = QGroupBox(self.tr("Applied at once"))
        form = QFormLayout(self.directGroup)
        form.addRow(self.tr("Decision rule"), self.ruleCombo)
        form.addRow(labels["seuil"], self._spins["seuil"])
        form.addRow("", self.seuilSlider)
        form.addRow(labels["tFusion"], self._spins["tFusion"])
        self._spins["seuil"].valueChanged.connect(self._onSeuilSpin)
        self.seuilSlider.valueChanged.connect(self._onSeuilSlider)
        self._spins["tFusion"].valueChanged.connect(self._onDirect)

        presetRow = QHBoxLayout()
        presetRow.addWidget(QLabel(self.tr("Preset:")))
        presetRow.addWidget(self.presetCombo, 1)
        presetRow.addWidget(self.modifiedLabel)

        layout = QVBoxLayout(self)
        layout.addLayout(presetRow)
        layout.addWidget(self.recomputeGroup)
        layout.addWidget(self.directGroup)
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

    def seuil(self):
        return self.current().seuil

    def tFusion(self):
        return self.current().tFusion

    def setValue(self, name, value):
        """Set one parameter, in the units of Parameters (Hz, s). Used by the tests."""
        self._spins[name].setValue(toDisplay(name, value))

    def setRecomputeEnabled(self, enabled):
        self.presetCombo.setEnabled(enabled)
        self.recomputeGroup.setEnabled(enabled)

    # --- internals -----------------------------------------------------------------

    def _onPreset(self, name):
        if name not in self._presets:
            return
        self._base = self._presets[name]
        self._loading = True
        for field, spin in self._spins.items():
            spin.setValue(toDisplay(field, getattr(self._base, field)))
        self.seuilSlider.setValue(self._sliderPosition())
        self._loading = False
        self._showModified()
        self.recomputeChanged.emit()
        self.directChanged.emit()

    def _sliderPosition(self):
        return min(SEUIL_SLIDER_MAX, int(round(self._spins["seuil"].value() * 100)))

    def _showModified(self):
        self.modifiedLabel.setText(self.tr("modified") if self.current() != self._base else "")

    def _onRecompute(self):
        if not self._loading:
            self._showModified()
            self.recomputeChanged.emit()

    def _onDirect(self):
        if not self._loading:
            self._showModified()
            self.directChanged.emit()

    def _onSeuilSpin(self):
        if self._loading:
            return
        self._loading = True
        self.seuilSlider.setValue(self._sliderPosition())
        self._loading = False
        self._onDirect()

    def _onSeuilSlider(self, position):
        if self._loading:
            return
        self._loading = True
        self._spins["seuil"].setValue(position / 100)
        self._loading = False
        self._onDirect()
