"""شاشة الإحصائيات المتقدمة — مكافئة لـ lib/screens/advanced_stats_screen.dart.
تعرض جدولين: حسب البرنامج وحسب الحالة، مع تصدير Excel/PDF.
"""
from __future__ import annotations
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel, QScrollArea,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..config import DOCS_DIR, PRIMARY, MUTED, SUCCESS
from ..services.database_service import DatabaseService
from ..services.excel_service import ExcelService
from ..services.report_service import ReportService
from ..widgets.common import make_card, make_button, label, show_message


class AdvancedStatsScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("root")
        self.db = DatabaseService()
        self.excel = ExcelService()
        self.report = ReportService()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(14)

        bar = QHBoxLayout()
        bar.addWidget(label("📈  الإحصائيات المتقدمة", role="title"))
        bar.addStretch(1)
        bar.addWidget(make_button("🔄  تحديث", variant="ghost", on_click=self.refresh))
        bar.addWidget(make_button("📤  Excel", variant="success", on_click=self._export_excel))
        bar.addWidget(make_button("📄  PDF شامل", variant="primary", on_click=self._export_pdf))
        wb = QWidget(); wb.setLayout(bar); outer.addWidget(wb)

        # صف الإجماليات
        self.totals_row = QHBoxLayout(); self.totals_row.setSpacing(14)
        tw = QWidget(); tw.setLayout(self.totals_row)
        outer.addWidget(tw)

        # محتوى قابل للتمرير
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(self.scroll, 1)

        self.refresh()

    # ──────────────────────────────────────────
    def _stat_box(self, title: str, value, color: str) -> QFrame:
        f = make_card()
        v = f.layout()
        l1 = QLabel(str(value))
        l1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l1.setStyleSheet(f"color: {color}; font-size: 20pt; font-weight: bold;")
        l2 = QLabel(title)
        l2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l2.setStyleSheet(f"color: {MUTED}; font-size: 9pt;")
        v.addWidget(l1); v.addWidget(l2)
        return f

    def _build_table(self, headers: list[str], rows: list[list]) -> QTableWidget:
        t = QTableWidget(len(rows), len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        t.setAlternatingRowColors(True)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        for i, row in enumerate(rows):
            for j, v in enumerate(row):
                it = QTableWidgetItem(str(v))
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                t.setItem(i, j, it)
        t.setMinimumHeight(min(420, max(180, 32 * (len(rows) + 1) + 10)))
        return t

    # ──────────────────────────────────────────
    def refresh(self) -> None:
        # امسح صف الإجماليات
        while self.totals_row.count():
            it = self.totals_row.takeAt(0)
            w = it.widget()
            if w: w.deleteLater()

        adv = self.db.get_advanced_stats()
        totals = adv.get("totals") or {}
        self.totals_row.addWidget(self._stat_box("الإجمالي", totals.get("total") or 0, PRIMARY))
        self.totals_row.addWidget(self._stat_box("المحصاة",  totals.get("done") or 0, SUCCESS))
        self.totals_row.addWidget(self._stat_box("بصور",     totals.get("with_image") or 0, "#0891B2"))
        self.totals_row.addWidget(self._stat_box("بدون صور", totals.get("without_image") or 0, "#B45309"))
        self.totals_row.addWidget(self._stat_box("⚡ كهرباء", totals.get("elec") or 0, "#F59E0B"))
        self.totals_row.addWidget(self._stat_box("🔥 غاز",   totals.get("gas") or 0, "#EA580C"))
        self.totals_row.addWidget(self._stat_box("💧 مياه",  totals.get("water") or 0, "#0EA5E9"))
        self.totals_row.addWidget(self._stat_box("🚿 تطهير", totals.get("sewage") or 0, "#16A34A"))

        # ── الجداول ─────────────────────────
        wrap = QWidget(); v = QVBoxLayout(wrap); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(14)

        # حسب البرنامج
        c1 = make_card()
        c1.layout().addWidget(label("📁  الإحصائيات حسب البرنامج", bold=True, size=12))
        prog_headers = [
            "البرنامج", "الحصة", "المحصاة",
            "في طور الانجاز", "على الأعمدة",
            "غ.مشغولة", "مشغولة",
            "كهرباء", "غاز", "مياه", "تطهير", "بصور",
        ]
        prog_rows = []
        for r in adv.get("byProgram", []):
            prog_rows.append([
                r.get("program") or "",
                r.get("total") or 0, r.get("done") or 0,
                r.get("s1") or 0, r.get("s2") or 0,
                r.get("s3") or 0, r.get("s4") or 0,
                r.get("elec") or 0, r.get("gas") or 0,
                r.get("water") or 0, r.get("sewage") or 0,
                r.get("with_image") or 0,
            ])
        self._prog_rows = prog_rows
        self._prog_headers = prog_headers
        c1.layout().addWidget(self._build_table(prog_headers, prog_rows))
        v.addWidget(c1)

        # حسب الحالة
        c2 = make_card()
        c2.layout().addWidget(label("🏗️  الإحصائيات حسب الحالة", bold=True, size=12))
        st_headers = [
            "الحالة", "العدد",
            "كهرباء", "غاز", "مياه", "تطهير", "بدون شبكة", "بصور",
        ]
        st_rows = []
        for r in adv.get("byStatus", []):
            st_rows.append([
                r.get("status") or "",
                r.get("total") or 0,
                r.get("elec") or 0, r.get("gas") or 0,
                r.get("water") or 0, r.get("sewage") or 0,
                r.get("none") or 0, r.get("with_image") or 0,
            ])
        self._status_rows = st_rows
        self._status_headers = st_headers
        c2.layout().addWidget(self._build_table(st_headers, st_rows))
        v.addWidget(c2)

        v.addStretch(1)
        self.scroll.setWidget(wrap)

    # ──────────────────────────────────────────
    def _export_excel(self) -> None:
        try:
            path, _ = QFileDialog.getSaveFileName(
                self, "حفظ ملف Excel",
                str(DOCS_DIR / "إحصائيات_متقدمة.xlsx"),
                "Excel (*.xlsx)",
            )
            if not path: return
            self.excel.export_statistics_to_file(
                file_path=Path(path),
                main_headers=self._prog_headers,
                main_rows=self._prog_rows,
                detail_headers=self._status_headers,
                detail_rows=self._status_rows,
            )
            show_message(self, f"✅ تم الحفظ:\n{path}", ok=True)
        except Exception as e:
            show_message(self, f"❌ فشل: {e}", ok=False, title="خطأ")

    def _export_pdf(self) -> None:
        try:
            path, _ = QFileDialog.getSaveFileName(
                self, "حفظ التقرير الشامل (PDF)",
                str(DOCS_DIR / "تقرير_شامل.pdf"),
                "PDF (*.pdf)",
            )
            if not path: return
            out = self.report.export_advanced_stats_pdf(Path(path))
            show_message(self, f"✅ تم الحفظ:\n{out}", ok=True)
        except Exception as e:
            show_message(self, f"❌ فشل: {e}", ok=False, title="خطأ")
