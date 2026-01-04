"""Run the GUI demo with TLE panel and map."""
import sys
from PyQt6 import QtWidgets
from nast_gs.gui.main_window import MainWindow


def main():
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
