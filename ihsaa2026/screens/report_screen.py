"""شاشة التقارير — توليد PDF/Excel لكل برنامج."""
from __future__ import annotations
import os
import sys
import subprocess
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QVBoxLayout, QWidget,
)

from ..config import DOCS_DIR, PRIMARY, MUTED
from ..services.database_service import DatabaseService
from ..services.report_service import ReportService
from ..widgets.common import make_card, make_button, label, show_message


def _open_file(path: Path) -> None:
    """يفتح الملف بالبرنامج الافتراضي للنظام."""
    try:
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


class ReportScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("root")
        self.db = DatabaseService()
        self.report = ReportService()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(14)

        bar = QHBoxLayout()
        bar.addWidget(label("📑  التقارير", role="title"))
        bar.addStretch(1)
        bar.addWidget(make_button("🔄  تحديث القائمة", variant="ghost",
                                  on_click=self._reload_programs))
        wb = QWidget(); wb.setLayout(bar); outer.addWidget(wb)

        # كرت اختيار البرنامج
        select_card = make_card()
        v = select_card.layout()
        v.addWidget(label("اختر برنامجاً لتوليد تقريره:", bold=True))
        self.combo = QComboBox()
        self.combo.setMinimumHeight(42)
        v.addWidget(self.combo)

        actions = QHBoxLayout(); actions.setSpacing(10)
        actions.addWidget(make_button("📄  تقرير PDF", variant="primary",
                                      on_click=self._gen_program_pdf), 1)
        actions.addWidget(make_button("📊  تقرير شامل (PDF)", variant="success",
                                      on_click=self._gen_advanced_pdf), 1)
        ww = QWidget(); ww.setLayout(actions); v.addWidget(ww)
        outer.addWidget(select_card)

        # قائمة الإحصائيات السريعة للبرنامج المختار
        self.preview_card = make_card()
        self.preview_card.layout().addWidget(label("ملخص سريع للبرنامج", bold=True))
        self.preview_list = QListWidget()
        self.preview_list.setStyleSheet("QListWidget { border: none; }")
        self.preview_card.layout().addWidget(self.preview_list)
        outer.addWidget(self.preview_card, 1)

        self.combo.currentTextChanged.connect(self._update_preview)
        self._reload_programs()

    # ──────────────────────────────────────────
    def _reload_programs(self) -> None:
        self.combo.clear()
        progs = self.db.get_programs()
        if progs:
            self.combo.addItems(progs)
        else:
            self.combo.addItem("(لا توجد برامج)")
        self._update_preview(self.combo.currentText())

    def _update_preview(self, program: str) -> None:
        self.preview_list.clear()
        if not program or program.startswith("("):
            return
        try:
            s = self.db.get_report_stats(program)
        except Exception:
            return
        items = [
            ("📦 الحصة", s.get("quota") or 0),
            ("✅ المحصاة", s.get("done") or 0),
            ("⏳ في طور الانجاز", s.get("in_progress") or 0),
            ("🏗️ على مستوى الأعمدة", s.get("pillars") or 0),
            ("🏠 منتهية غير مشغولة", s.get("finished_not_occupied") or 0),
            ("🎉 منتهية ومشغولة", s.get("finished_occupied") or 0),
            ("⚡ كهرباء (مشغولة)", s.get("elec_occ") or 0),
            ("🔥 غاز (مشغولة)", s.get("gas_occ") or 0),
            ("💧 مياه (مشغولة)", s.get("water_occ") or 0),
            ("🚿 تطهير (مشغولة)", s.get("sew_occ") or 0),
            ("🌐 جميع الشبكات", s.get("fully_connected") or 0),
        ]
        for k, v in items:
            it = QListWidgetItem(f"{k}    →    {v}")
            it.setTextAlignment(Qt.AlignmentFlag.AlignRight)
            self.preview_list.addItem(it)

    # ──────────────────────────────────────────
    def _gen_program_pdf(self) -> None:
        program = self.combo.currentText().strip()
        if not program or program.startswith("("):
            show_message(self, "اختر برنامجاً أولاً", ok=False); return
        try:
            path, _ = QFileDialog.getSaveFileName(
                self, "حفظ تقرير PDF",
                str(DOCS_DIR / f"تقرير_{program}.pdf"),
                "PDF (*.pdf)",
            )
            if not path: return
            out = self.report.export_program_report(program, Path(path))
            show_message(self, f"✅ تم الحفظ:\n{out}", ok=True)
            _open_file(out)
        except Exception as e:
            show_message(self, f"❌ فشل التوليد: {e}", ok=False, title="خطأ")

    def _gen_advanced_pdf(self) -> None:
        try:
            path, _ = QFileDialog.getSaveFileName(
                self, "حفظ التقرير الشامل",
                str(DOCS_DIR / "تقرير_شامل.pdf"),
                "PDF (*.pdf)",
            )
            if not path: return
            out = self.report.export_advanced_stats_pdf(Path(path))
            show_message(self, f"✅ تم الحفظ:\n{out}", ok=True)
            _open_file(out)
        except Exception as e:
            show_message(self, f"❌ فشل التوليد: {e}", ok=False, title="خطأ")
