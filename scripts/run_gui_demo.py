"""Run the GUI demo with TLE panel and map."""
import sys
from PyQt6 import QtWidgets, QtCore, QtGui
from nast_gs.gui.main_window import MainWindow


def main():
    # Force English locale so numbers show as 0-9 (not Devanagari)
    QtCore.QLocale.setDefault(QtCore.QLocale(QtCore.QLocale.Language.English, QtCore.QLocale.Country.UnitedStates))

    app = QtWidgets.QApplication(sys.argv)

    # Force a font that renders Latin digits consistently
    app.setFont(QtGui.QFont("DejaVu Sans", 9))

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
