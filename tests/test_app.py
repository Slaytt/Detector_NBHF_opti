"""nbhfapp: the window, driven without a screen.

These tests click nothing with a mouse: they call what the buttons call and read what
the widgets show. The computation runs in the real separate process. They do not check
how the window looks.

Criteria:
  - an untouched parameter panel gives exactly Parameters() (the values of A*);
  - after a run, the counters shown are those of the run and the Res files those of A;
  - moving seuil changes the decision shown, not the candidate table;
  - changing a parameter of the first group flags the results as outdated;
  - the Spanish translation loads and covers every text.

    launch test :
        .venv/bin/python -m pytest tests/test_app.py
"""

import os
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QEventLoop, QTimer, QTranslator      # noqa: E402
from PySide6.QtWidgets import QApplication                      # noqa: E402

from nbhf.parameters import Parameters                          # noqa: E402
from nbhfapp.export import CLICKS, ExportOptions, ravenName     # noqa: E402
from nbhfapp.mainwindow import MainWindow                       # noqa: E402
from nbhfapp.params_panel import ParamsPanel                    # noqa: E402

HERE = Path(__file__).resolve().parent
WAV_DIR = HERE.parent / "research" / "jeu_equivalence" / "wav"
RES_DIR = HERE.parent / "research" / "jeu_equivalence" / "references_A_v2"
I18N_DIR = HERE.parent / "nbhfapp" / "i18n"

MONO = "6209.260514052458.wav"
STEREO = "FichierTest_FitzRoy.wav"
HAVE_WAVS = all((WAV_DIR / f).exists() for f in (MONO, STEREO))


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _wait(app, signal, seconds=120):
    """Run the event loop until signal is emitted."""
    loop = QEventLoop()
    got = []
    signal.connect(lambda *args: (got.append(args), loop.quit()))
    QTimer.singleShot(int(seconds * 1000), loop.quit)
    loop.exec()
    assert got, "the signal was not emitted in time"
    return got[0]


@pytest.fixture(scope="module")
def window(app, tmp_path_factory):
    """A window on which one run of two files has finished."""
    if not HAVE_WAVS:
        pytest.skip("missing wav files in research/jeu_equivalence/wav")
    out = tmp_path_factory.mktemp("run")
    w = MainWindow()
    w.show()
    w.filesPanel.addPaths([WAV_DIR / MONO, WAV_DIR / STEREO])
    w.filesPanel.outputEdit.setText(str(out))
    w.startRun()
    _wait(app, w.runner.finished)
    app.processEvents()
    w.outDir = out
    yield w
    w.close()


def test_untouched_panel_is_A_star(app):
    panel = ParamsPanel()
    assert panel.current() == Parameters()
    assert panel.modifiedLabel.text() == ""
    for name in ("coefUmbral", "fcutLow", "fcutHigh", "f1clic", "f2clic", "f1", "f2"):
        assert type(getattr(panel.current(), name)) is type(getattr(Parameters(), name)), name


def test_edited_panel(app):
    panel = ParamsPanel()
    panel.setValue("f1clic", 110000)
    panel.seuilSlider.setValue(60)
    p = panel.current()
    assert p.f1clic == 110000 and type(p.f1clic) is int          # the core does f1clic // 1000
    assert p.seuil == 0.6
    assert panel.modifiedLabel.text() != ""
    assert p == Parameters(f1clic=110000, seuil=0.6)
    panel.setValue("f1clic", 120000)
    panel.seuilSlider.setValue(40)
    assert panel.current() == Parameters() and panel.modifiedLabel.text() == ""


def test_run_shows_the_results_of_A(window):
    w = window
    assert set(Path(p).name for p in w.runs) == {MONO, STEREO}
    for name in (f"Res_{Path(MONO).stem}.txt", f"Res_{Path(STEREO).stem}.txt"):
        assert (w.outDir / name).read_bytes() == (RES_DIR / name).read_bytes()

    w.filesPanel.selectPath(WAV_DIR / STEREO)
    run = w.runs[str(WAV_DIR / STEREO)]
    assert STEREO in w.resultsPanel.titleLabel.text()
    assert np.array_equal(w.resultsPanel.mask(), run.table["accepted"])
    assert w.resultsPanel.proxy.rowCount() == len(run.table)
    assert w.exportAction.isEnabled()
    assert not w.summaryPanel.staleLabel.isVisible()


def test_summary_gives_the_counts_of_A(window, app):
    w = window
    w.paramsPanel.seuilSlider.setValue(40)
    app.processEvents()
    rows = {name: (c, a, d) for name, c, a, d in w.summaryPanel.rows()}
    for name in (MONO, STEREO):
        table = w.runs[str(WAV_DIR / name)].table
        merged = (RES_DIR / f"Res_{Path(name).stem}.txt").read_text().splitlines()
        assert rows[name] == (len(table), int(table["accepted"].sum()), len(merged)), name
    assert rows["Total"] == tuple(rows[MONO][k] + rows[STEREO][k] for k in range(3))

    w.paramsPanel.seuilSlider.setValue(200)                      # stricter: fewer accepted, same candidates
    app.processEvents()
    strict = {name: (c, a, d) for name, c, a, d in w.summaryPanel.rows()}
    assert strict[STEREO][0] == rows[STEREO][0] and strict[STEREO][1] < rows[STEREO][1]
    w.paramsPanel.seuilSlider.setValue(40)
    app.processEvents()


def test_moving_seuil_changes_the_decision_not_the_table(window, app):
    w = window
    w.filesPanel.selectPath(WAV_DIR / STEREO)
    table = w.runs[str(WAV_DIR / STEREO)].table
    before = table.copy()
    nAccepted = int(table["accepted"].sum())

    w.paramsPanel.seuilSlider.setValue(200)
    app.processEvents()
    assert w.paramsPanel.seuil() == 2.0
    assert 0 < w.resultsPanel.mask().sum() < nAccepted
    assert np.array_equal(table, before)
    assert not w.summaryPanel.staleLabel.isVisible()             # seuil never needs a new run
    w.resultsPanel.filterCombo.setCurrentIndex(1)
    assert w.resultsPanel.proxy.rowCount() == int(w.resultsPanel.mask().sum())
    w.resultsPanel.filterCombo.setCurrentIndex(0)

    w.paramsPanel.seuilSlider.setValue(40)
    app.processEvents()
    assert np.array_equal(w.resultsPanel.mask(), table["accepted"])


def test_recompute_parameter_flags_the_results(window, app):
    w = window
    w.filesPanel.selectPath(WAV_DIR / MONO)
    w.paramsPanel.setValue("coefUmbral", 12)
    app.processEvents()
    assert w.summaryPanel.staleLabel.isVisible()
    w.paramsPanel.setValue("coefUmbral", 9)
    app.processEvents()
    assert not w.summaryPanel.staleLabel.isVisible()
    assert w.paramsPanel.current() == Parameters()


def test_export_from_the_window(window, tmp_path):
    w = window
    written = w.export(str(tmp_path / "exp"), ExportOptions(res=True, raven=True, ravenMode=CLICKS))
    names = {p.name for p in written}
    assert {ravenName(MONO), ravenName(STEREO), "BilanTot.txt"} <= names
    name = f"Res_{Path(STEREO).stem}.txt"
    assert (tmp_path / "exp" / name).read_bytes() == (RES_DIR / name).read_bytes()


def test_bad_parameters_are_refused(app):
    w = MainWindow()
    assert w.parameterProblems(Parameters()) == []
    assert len(w.parameterProblems(Parameters(f1clic=140000, f2clic=120000, f1=90000, f2=30000))) == 2
    w.close()


def test_spanish_translation_is_complete(app):
    import xml.etree.ElementTree as ET
    ts = I18N_DIR / "nbhfapp_es.ts"
    qm = I18N_DIR / "nbhfapp_es.qm"
    assert ts.exists() and qm.exists()
    for message in ET.parse(ts).getroot().iter("message"):
        translation = message.find("translation")
        assert translation.text and translation.get("type") != "unfinished", message.find("source").text

    translator = QTranslator()
    assert translator.load(str(qm))
    app.installTranslator(translator)
    try:
        w = MainWindow()
        assert w.filesPanel.runButton.text() == "Calcular"
        assert w.exportAction.text() == "Exportar…"
        w.close()
    finally:
        app.removeTranslator(translator)
