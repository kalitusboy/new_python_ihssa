"""ستايل موحد للتطبيق (QSS) — يحاكي نمط ThemeData في Flutter."""
from __future__ import annotations
from PyQt6.QtGui import QFontDatabase, QFont
from ..config import (
    PRIMARY, PRIMARY_DARK, BG, TEXT, MUTED, BORDER,
    SUCCESS, DANGER, WARN, assets_dir,
)


# مفتاح عائلة الخط (يُحدَّث بعد التحميل)
_FONT_FAMILY = "Cairo"


def load_fonts() -> str:
    """يُحمِّل خطوط Cairo ويعيد اسم العائلة."""
    global _FONT_FAMILY
    fonts_dir = assets_dir() / "fonts"
    families: list[str] = []
    for name in ("Cairo-Regular.tt", "Cairo-Bold.ttf"):
        p = fonts_dir / name
        if p.exists():
            fid = QFontDatabase.addApplicationFont(str(p))
            if fid != -1:
                fams = QFontDatabase.applicationFontFamilies(fid)
                families.extend(fams)
    if families:
        _FONT_FAMILY = families[0]
    return _FONT_FAMILY


def app_font(size: int = 12, bold: bool = False) -> QFont:
    f = QFont(_FONT_FAMILY, size)
    f.setBold(bold)
    return f


# ──────────────────────────────────────────────
def app_qss() -> str:
    return f"""
    * {{
        font-family: "{_FONT_FAMILY}", "Segoe UI", Arial;
        color: {TEXT};
    }}
    QMainWindow, QDialog, QWidget#root {{
        background-color: {BG};
    }}
    /* الشريط الجانبي */
    QWidget#sidebar {{
        background-color: {PRIMARY};
        color: white;
    }}
    QWidget#sidebar QLabel {{ color: white; }}
    QWidget#sidebarHeader {{
        background-color: {PRIMARY_DARK};
        color: white;
    }}

    /* AppBar */
    QFrame#appbar {{
        background-color: {PRIMARY};
        color: white;
        min-height: 56px;
        border: none;
    }}
    QFrame#appbar QLabel {{
        color: white;
        font-size: 16pt;
        font-weight: bold;
    }}
    QFrame#appbar QPushButton {{
        background-color: rgba(255,255,255,0.10);
        color: white;
        border: 1px solid rgba(255,255,255,0.25);
        border-radius: 8px;
        padding: 6px 14px;
    }}
    QFrame#appbar QPushButton:hover {{
        background-color: rgba(255,255,255,0.18);
    }}

    /* Card */
    QFrame#card {{
        background-color: white;
        border-radius: 14px;
        border: 1px solid #E2E8F0;
    }}

    /* TextField */
    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDateEdit {{
        background-color: white;
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 8px 12px;
        font-size: 11pt;
        selection-background-color: {PRIMARY};
        selection-color: white;
    }}
    QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QDateEdit:focus {{
        border: 2px solid {PRIMARY};
    }}
    QComboBox::drop-down {{ border: none; width: 24px; }}

    /* Buttons */
    QPushButton {{
        background-color: {PRIMARY};
        color: white;
        border: none;
        border-radius: 10px;
        padding: 10px 18px;
        font-weight: bold;
        font-size: 11pt;
    }}
    QPushButton:hover  {{ background-color: {PRIMARY_DARK}; }}
    QPushButton:pressed{{ background-color: #082A66; }}
    QPushButton:disabled {{ background-color: #94A3B8; color: #E2E8F0; }}

    QPushButton[variant="success"]  {{ background-color: {SUCCESS}; }}
    QPushButton[variant="success"]:hover {{ background-color: #166534; }}
    QPushButton[variant="danger"]   {{ background-color: {DANGER}; }}
    QPushButton[variant="danger"]:hover  {{ background-color: #991B1B; }}
    QPushButton[variant="warn"]     {{ background-color: {WARN}; }}
    QPushButton[variant="ghost"]    {{
        background-color: transparent;
        color: {PRIMARY};
        border: 1px solid {BORDER};
    }}
    QPushButton[variant="ghost"]:hover {{ background-color: #E2E8F0; }}
    QPushButton[variant="sidebar"] {{
        background-color: transparent;
        color: white;
        text-align: right;
        padding: 12px 16px;
        border-radius: 0;
        font-weight: 500;
    }}
    QPushButton[variant="sidebar"]:hover {{
        background-color: rgba(255,255,255,0.10);
    }}
    QPushButton[variant="sidebarActive"] {{
        background-color: rgba(255,255,255,0.15);
        color: white;
        text-align: right;
        padding: 12px 16px;
        border-radius: 0;
        border-right: 4px solid #FFD54F;
        font-weight: bold;
    }}

    /* Labels */
    QLabel[role="title"]   {{ font-size: 18pt; font-weight: bold; color: {PRIMARY}; }}
    QLabel[role="subtitle"]{{ font-size: 13pt; color: {MUTED}; }}
    QLabel[role="muted"]   {{ color: {MUTED}; font-size: 10pt; }}
    QLabel[role="stat"]    {{ font-size: 22pt; font-weight: bold; color: {PRIMARY}; }}
    QLabel[role="statLabel"]{{ color: {MUTED}; font-size: 10pt; }}

    /* Tabs */
    QTabBar::tab {{
        background: transparent;
        color: {MUTED};
        padding: 10px 22px;
        border-bottom: 3px solid transparent;
        font-weight: bold;
    }}
    QTabBar::tab:selected {{
        color: {PRIMARY};
        border-bottom: 3px solid {PRIMARY};
    }}
    QTabWidget::pane {{ border: none; }}

    /* Tables */
    QTableWidget, QTableView {{
        background-color: white;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        gridline-color: #E2E8F0;
        selection-background-color: #DBEAFE;
        selection-color: {TEXT};
    }}
    QHeaderView::section {{
        background-color: {PRIMARY};
        color: white;
        padding: 8px;
        border: none;
        font-weight: bold;
    }}
    QTableWidget::item {{ padding: 6px; }}

    /* Scrollbars */
    QScrollBar:vertical {{
        background: transparent; width: 10px; margin: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: #94A3B8; border-radius: 4px; min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {PRIMARY}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

    /* CheckBox */
    QCheckBox {{ spacing: 8px; }}
    QCheckBox::indicator {{
        width: 18px; height: 18px;
        border: 2px solid {BORDER};
        border-radius: 4px;
        background: white;
    }}
    QCheckBox::indicator:checked {{
        background: {PRIMARY};
        border-color: {PRIMARY};
        image: none;
    }}

    /* Progress */
    QProgressBar {{
        background: #E2E8F0;
        border-radius: 4px;
        height: 8px;
        text-align: center;
        color: white;
    }}
    QProgressBar::chunk {{ background: {PRIMARY}; border-radius: 4px; }}
    """
