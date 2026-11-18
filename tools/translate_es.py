"""Fill nbhfapp/i18n/nbhfapp_es.ts with the Spanish texts below, then compile the .qm.

After adding or changing a text of the interface, from the root of the repository:
    .venv/bin/pyside6-lupdate nbhfapp/*.py -ts nbhfapp/i18n/nbhfapp_es.ts -no-obsolete
    .venv/bin/python tools/translate_es.py
"""
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TS = ROOT / "nbhfapp" / "i18n" / "nbhfapp_es.ts"

ES = {
    # table of candidates
    "Time (s)": "Tiempo (s)",
    "Ch.": "Canal",
    "Amplitude": "Amplitud",
    "× threshold": "× umbral",
    "Click level": "Nivel del clic",
    "Ref. level": "Nivel de ref.",
    "Ratio": "Cociente",
    "Peak (kHz)": "Pico (kHz)",
    "Decision": "Decisión",
    "Accepted": "Aceptado",
    "Rejected": "Rechazado",
    # export
    "Export": "Exportar",
    "Export…": "Exportar…",
    "{n} file(s), with level ratio threshold {seuil} and channel merge {fusion} ms.":
        "{n} archivo(s), con umbral del cociente de niveles {seuil} y fusión de canales {fusion} ms.",
    "The results were computed with other parameters than those shown. The export uses the parameters of the run:":
        "Los resultados se calcularon con parámetros distintos de los mostrados. La exportación usa los parámetros del cálculo:",
    "Raven selection tables": "Tablas de selección de Raven",
    "One click per line": "Un clic por línea",
    "Clicks grouped in trains, largest gap": "Clics agrupados en trenes, intervalo máximo",
    "Detection dates (Res_*.txt) and summary (BilanTot.txt)":
        "Fechas de detección (Res_*.txt) y resumen (BilanTot.txt)",
    "Tables of all candidates (Candidats_*.csv)": "Tablas de todos los candidatos (Candidats_*.csv)",
    "Choose…": "Elegir…",
    "Folder:": "Carpeta:",
    # files
    "Add files…": "Añadir archivos…",
    "Add folder…": "Añadir carpeta…",
    "Add files": "Añadir archivos",
    "Add folder": "Añadir carpeta",
    "Remove": "Quitar",
    "Run": "Calcular",
    "Stop": "Detener",
    "Stops after the file being processed": "Se detiene al terminar el archivo en curso",
    "File": "Archivo",
    "Duration": "Duración",
    "Status": "Estado",
    "Detections": "Detecciones",
    "Results folder": "Carpeta de resultados",
    "Results folder:": "Carpeta de resultados:",
    "Waiting": "En espera",
    "Running…": "Calculando…",
    "Done": "Terminado",
    "Error": "Error",
    "No file": "Ningún archivo",
    "{done} of {total} done, {errors} in error": "{done} de {total} terminados, {errors} con error",
    "{done} of {total} done": "{done} de {total} terminados",
    "WAV files (*.wav *.WAV)": "Archivos WAV (*.wav *.WAV)",
    # summary
    "Candidates": "Candidatos",
    "Total": "Total",
    "Peaks of the filtered signal above the amplitude threshold (× std of the chunk)":
        "Picos de la señal filtrada por encima del umbral de amplitud (× desv. estándar del trozo)",
    "Candidates whose click level is above the level ratio threshold × reference level":
        "Candidatos cuyo nivel del clic supera el umbral del cociente × el nivel de referencia",
    "Accepted candidates left after merging the two channels":
        "Candidatos aceptados que quedan tras fusionar los dos canales",
    # main window
    "NBHF click detector": "Detector de clics NBHF",
    "Quit": "Salir",
    "Main": "Principal",
    "The low cut-off of the filter must be under the high cut-off.":
        "La frecuencia de corte baja del filtro debe ser menor que la alta.",
    "The click band must go from a lower to a higher frequency.":
        "La banda del clic debe ir de una frecuencia menor a una mayor.",
    "The reference band must go from a lower to a higher frequency.":
        "La banda de referencia debe ir de una frecuencia menor a una mayor.",
    "Choose a results folder first.": "Elija primero una carpeta de resultados.",
    "The results folder cannot be created:": "No se puede crear la carpeta de resultados:",
    "Stopping after the current file…": "Deteniendo al terminar el archivo en curso…",
    "{n} file(s) processed in {seconds} s": "{n} archivo(s) procesado(s) en {seconds} s",
    "The computation stopped unexpectedly (code {code}).": "El cálculo se detuvo de forma inesperada (código {code}).",
    "{name}: {used} in the run, {shown} shown": "{name}: {used} en el cálculo, {shown} mostrado",
    "The export failed:": "La exportación falló:",
    "{n} file(s) written in {folder}": "{n} archivo(s) escrito(s) en {folder}",
    # parameters
    "Filter, low cut-off": "Filtro, corte bajo",
    "Filter, high cut-off": "Filtro, corte alto",
    "Amplitude threshold (× std)": "Umbral de amplitud (× desv. estándar)",
    "Silenced around a peak": "Silenciado alrededor de un pico",
    "Click band, from": "Banda del clic, desde",
    "Click band, to": "Banda del clic, hasta",
    "Reference band, from": "Banda de referencia, desde",
    "Reference band, to": "Banda de referencia, hasta",
    "Chunk duration": "Duración del trozo",
    "Level ratio threshold": "Umbral del cociente de niveles",
    "Merge of the two channels": "Fusión de los dos canales",
    "Needs a new run": "Requiere un nuevo cálculo",
    "Threshold of the original detector": "Umbral del detector original",
    "Model from a file… (not available yet)": "Modelo desde un archivo… (aún no disponible)",
    "Applied at once": "Se aplica de inmediato",
    "Decision rule": "Regla de decisión",
    "Preset:": "Preajuste:",
    "modified": "modificado",
    # results
    "Parameters changed since this run: these results were computed with the previous ones. Run again to update them.":
        "Los parámetros cambiaron desde este cálculo: estos resultados se obtuvieron con los anteriores. "
        "Vuelva a calcular para actualizarlos.",
    "All candidates": "Todos los candidatos",
    "Accepted only": "Solo aceptados",
    "Rejected only": "Solo rechazados",
    "No result for this file yet": "Aún no hay resultados para este archivo",
    "{candidates} candidates, {accepted} accepted, {merged} after merging the channels":
        "{candidates} candidatos, {accepted} aceptados, {merged} tras fusionar los canales",
    "Candidates of {name}": "Candidatos de {name}",
}


def main():
    tree = ET.parse(TS)
    missing = []
    for message in tree.getroot().iter("message"):
        source = message.find("source").text
        translation = message.find("translation")
        if source in ES:
            translation.text = ES[source]
            translation.attrib.pop("type", None)
        else:
            missing.append(source)
    tree.write(TS, encoding="utf-8", xml_declaration=True)
    for source in missing:
        print("no Spanish text for:", repr(source))

    lrelease = Path(sys.executable).parent / "pyside6-lrelease"
    subprocess.run([str(lrelease), str(TS), "-qm", str(TS.with_suffix(".qm"))], check=True)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
