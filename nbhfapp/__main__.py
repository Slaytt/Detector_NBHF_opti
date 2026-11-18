"""Entry point: python -m nbhfapp
"""
import multiprocessing
import sys
from pathlib import Path


def main():
    from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
    from PySide6.QtWidgets import QApplication

    from nbhfapp import settings
    from nbhfapp.mainwindow import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("NBHF click detector")

    # language chosen in the preferences, else the one of the system; English when no
    # translation exists for it (the texts of the code are in English)
    chosen = settings.language()
    locale = QLocale() if chosen == settings.SYSTEM else QLocale(chosen)
    translator = QTranslator(app)
    if translator.load(locale, "nbhfapp", "_", str(Path(__file__).parent / "i18n")):
        app.installTranslator(translator)
        # the texts of Qt itself (Cancel, the file dialogs), in the same language
        qtTranslator = QTranslator(app)
        if qtTranslator.load(locale, "qtbase", "_", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
            app.installTranslator(qtTranslator)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    # the computation runs in a spawned process, which imports this module again:
    # nothing may start outside this guard. freeze_support is for the future executables.
    multiprocessing.freeze_support()
    sys.exit(main())
