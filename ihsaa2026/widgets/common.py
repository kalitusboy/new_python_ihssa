"""مكونات واجهة قابلة لإعادة الاستخدام (بطاقات، صفوف معلومات، snackbar...)."""
from __future__ import annotations
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
    QGraphicsDropShadowEffect, QMessageBox,
)
from ..config import PRIMARY, MUTED, SUCCESS, DANGER, WARN


def make_card(*, padding: int = 20) -> QFrame:
    f = QFrame()
    f.setObjectName("card")
    f.setLayout(QVBoxLayout())
    f.layout().setContentsMargins(padding, padding, padding, padding)
    f.layout().setSpacing(10)
    sh = QGraphicsDropShadowEffect(f)
    sh.setBlurRadius(18)
    sh.setOffset(0, 4)
    sh.setColor(QColor(15, 23, 42, 18))
    f.setGraphicsEffect(sh)
    return f


def make_button(text: str, *, variant: str = "primary",
                icon: str | None = None, on_click=None,
                min_height: int = 40) -> QPushButton:
    btn = QPushButton(("" if not icon else f"{icon}  ") + text)
    btn.setMinimumHeight(min_height)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setProperty("variant", variant)
    btn.style().unpolish(btn); btn.style().polish(btn)
    if on_click:
        btn.clicked.connect(on_click)
    return btn


def label(text: str, *, role: str | None = None, bold: bool = False,
          color: str | None = None, size: int | None = None) -> QLabel:
    lbl = QLabel(text)
    lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    if role:
        lbl.setProperty("role", role)
    if bold or size or color:
        f = lbl.font()
        if bold: f.setBold(True)
        if size: f.setPointSize(size)
        lbl.setFont(f)
    if color:
        lbl.setStyleSheet(f"color: {color};")
    return lbl


def info_row(label_text: str, value: str, *, value_bold: bool = True,
             label_color: str = MUTED) -> QWidget:
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 4, 0, 4)
    h.setSpacing(10)
    l1 = QLabel(f"{label_text}: ")
    l1.setStyleSheet(f"color: {label_color}; font-size: 10pt;")
    l2 = QLabel(value)
    f = l2.font(); f.setBold(value_bold); l2.setFont(f)
    l2.setWordWrap(True)
    h.addWidget(l1)
    h.addWidget(l2, 1)
    return w


def show_message(parent, text: str, *, ok: bool = True, title: str | None = None) -> None:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Information if ok else QMessageBox.Icon.Warning)
    box.setWindowTitle(title or ("نجاح" if ok else "تنبيه"))
    box.setText(text)
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.exec()


def confirm(parent, text: str, *, title: str = "تأكيد") -> bool:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(title)
    box.setText(text)
    yes = box.addButton("نعم", QMessageBox.ButtonRole.YesRole)
    box.addButton("إلغاء", QMessageBox.ButtonRole.RejectRole)
    box.exec()
    return box.clickedButton() is yes


# ──────────────────────────────────────────────
class Snackbar(QFrame):
    """شريط تنبيه عائم في أسفل الشاشة (يحاكي SnackBar في Flutter)."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("snack")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        h = QHBoxLayout(self)
        h.setContentsMargins(16, 12, 16, 12)
        self._icon = QLabel("ℹ️")
        self._text = QLabel("")
        self._text.setStyleSheet("color: white; font-weight: 600;")
        self._icon.setStyleSheet("color: white; font-size: 14pt;")
        h.addWidget(self._icon); h.addWidget(self._text, 1)
        self.hide()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.hide)

    def show_msg(self, text: str, ok: bool = True) -> None:
        self._text.setText(text)
        self._icon.setText("✅" if ok else "❌")
        bg = SUCCESS if ok else DANGER
        self.setStyleSheet(f"QFrame#snack {{ background: {bg}; border-radius: 10px; }}")
        # ضعه في أسفل وسط النافذة الأم
        if self.parent():
            par = self.parent()
            self.adjustSize()
            x = (par.width() - self.width()) // 2
            y = par.height() - self.height() - 24
            self.move(max(20, x), max(20, y))
        self.show()
        self.raise_()
        self._timer.start(3000)
