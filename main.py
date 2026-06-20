import sys
import os

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow


def load_stylesheet(app: QApplication) -> None:
    qss_path = os.path.join(os.path.dirname(__file__), "app", "style.qss")
    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("冷藏车断电复盘工具")
    app.setOrganizationName("ColdChainQA")

    load_stylesheet(app)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
