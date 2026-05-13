"""نقطة الإقلاع الرئيسية للتطبيق."""
from __future__ import annotations
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QLocale
from PyQt6.QtGui import QIcon, QGuiApplication
from PyQt6.QtWidgets import QApplication, QMainWindow, QStackedWidget, QWidget

from .config import Prefs, BG, assets_dir
from .widgets.style import load_fonts, app_qss, app_font
from .screens.setup_screen import SetupScreen
from .screens.home_screen import HomeScreen


class MainWindow(QMainWindow):
    """نافذة رئيسية تحوي شاشة الإعداد ثم الشاشة الرئيسية."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("إحصاء السكن الريفي 2026 — نسيم الحوضان")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setStyleSheet(f"QMainWindow {{ background: {BG}; }}")
        self.resize(1280, 800)
        self.setMinimumSize(1000, 650)

        # أيقونة
        ico = assets_dir() / "fonts" / "icon.ico"
        if ico.exists():
            self.setWindowIcon(QIcon(str(ico)))

        # Stack: 0 = SetupScreen, 1 = HomeScreen
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # شاشة الإعداد
        self.setup_screen = SetupScreen()
        self.setup_screen.done.connect(self._on_setup_done)
        self.stack.addWidget(self.setup_screen)

        # الشاشة الرئيسية (لاحقاً)
        self.home_screen: HomeScreen | None = None

        # هل سبق وأُنجز الإعداد؟
        Prefs.load()
        if Prefs.get("setup_done"):
            self._on_setup_done()

    def _on_setup_done(self) -> None:
        if self.home_screen is None:
            self.home_screen = HomeScreen()
            self.stack.addWidget(self.home_screen)
        self.stack.setCurrentWidget(self.home_screen)

    # ضع الشريط العائم (Snackbar) في مكانه الصحيح عند تغيير الحجم
    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        if self.home_screen and getattr(self.home_screen, "snackbar", None):
            sb = self.home_screen.snackbar
            if sb.isVisible():
                sb.adjustSize()
                par = self.home_screen
                x = (par.width() - sb.width()) // 2
                y = par.height() - sb.height() - 24
                sb.move(max(20, x), max(20, y))


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("إحصاء السكن الريفي 2026")
    app.setOrganizationName("Nassim Hamiti — Houden")
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    QLocale.setDefault(QLocale(QLocale.Language.Arabic, QLocale.Country.Algeria))

    # خط افتراضي + ستايل
    load_fonts()
    app.setFont(app_font(11))
    app.setStyleSheet(app_qss())

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(run())
