"""شاشة الإحصائيات — مكافئة لـ lib/screens/stats_screen.dart."""
from __future__ import annotations
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel, QScrollArea,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..config import DOCS_DIR, PRIMARY, MUTED, SUCCESS
from ..services.database_service import DatabaseService
from ..services.excel_service import ExcelService
from ..widgets.common import make_card, make_button, label, show_message


class StatsScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("root")
        self.db = DatabaseService()
        self.excel = ExcelService()

        outer = QVBoxLayout(self); outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(14)

        # ── شريط أعلى ──────────────────────
        bar = QHBoxLayout()
        bar.addWidget(label("📊  الإحصائيات", role="title"))
        bar.addStretch(1)
        bar.addWidget(make_button("🔄  تحديث", variant="ghost", on_click=self.refresh))
        bar.addWidget(make_button("📤  تصدير Excel", variant="success",
                                  on_click=self._export_excel))
        wb = QWidget(); wb.setLayout(bar); outer.addWidget(wb)

        # ── ملخص علوي ──────────────────────
        self.summary_row = QHBoxLayout(); self.summary_row.setSpacing(14)
        sw = QWidget(); sw.setLayout(self.summary_row); outer.addWidget(sw)

        # ── جدول البرامج ───────────────────
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(self.scroll, 1)

        self.refresh()

    # ──────────────────────────────────────────
    def _stat_box(self, title: str, value: str, color: str) -> QFrame:
        f = make_card()
        v = f.layout()
        l1 = QLabel(value)
        l1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l1.setStyleSheet(f"color: {color}; font-size: 22pt; font-weight: bold;")
        l2 = QLabel(title)
        l2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l2.setStyleSheet(f"color: {MUTED}; font-size: 10pt;")
        v.addWidget(l1); v.addWidget(l2)
        return f

    # ──────────────────────────────────────────
    def refresh(self) -> None:
        # امسح صف الملخص
        while self.summary_row.count():
            it = self.summary_row.takeAt(0)
            w = it.widget()
            if w: w.deleteLater()

        s = self.db.get_statistics()
        total = s.get("total", 0)
        completed = s.get("completed", 0)
        progress = s.get("progress", 0)
        pending = total - completed

        self.summary_row.addWidget(self._stat_box("الإجمالي", str(total), PRIMARY))
        self.summary_row.addWidget(self._stat_box("المُحصاة", str(completed), SUCCESS))
        self.summary_row.addWidget(self._stat_box("المتبقية", str(pending), "#B45309"))
        self.summary_row.addWidget(self._stat_box("التقدم", f"{progress}%", "#0891B2"))

        # ── جدول البرامج ───────────────────
        rows = s.get("programStats") or []
        headers = [
            "البرنامج", "الحصة", "المحصاة",
            "في طور الانجاز", "على الأعمدة",
            "غ.مشغولة", "مشغولة",
            "كهرباء", "غاز", "مياه", "تطهير",
        ]
        tbl = QTableWidget(len(rows), len(headers))
        tbl.setHorizontalHeaderLabels(headers)
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tbl.setAlternatingRowColors(True)
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        tbl.horizontalHeader().setStretchLastSection(False)

        for i, r in enumerate(rows):
            vals = [
                r.get("program") or "",
                r.get("total") or 0, r.get("done_count") or 0,
                r.get("status_1") or 0, r.get("status_2") or 0,
                r.get("status_3") or 0, r.get("status_4") or 0,
                r.get("elec_sum") or 0, r.get("gas_sum") or 0,
                r.get("water_sum") or 0, r.get("sew_sum") or 0,
            ]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                tbl.setItem(i, j, it)

        # ضع الجدول داخل بطاقة
        card = make_card()
        card.layout().addWidget(label("الإحصائيات حسب البرنامج", bold=True, size=12))
        card.layout().addWidget(tbl)

        wrap = QWidget(); v = QVBoxLayout(wrap); v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(card)
        self._save_rows = rows
        self.scroll.setWidget(wrap)

    # ──────────────────────────────────────────
    def _export_excel(self) -> None:
        try:
            path, _ = QFileDialog.getSaveFileName(
                self, "حفظ ملف Excel",
                str(DOCS_DIR / "إحصائيات_البرامج.xlsx"),
                "Excel (*.xlsx)",
            )
            if not path: return

            main_headers = [
                "البرنامج", "الحصة", "المحصاة",
                "في طور الانجاز", "على الأعمدة",
                "منتهية غير مشغولة", "منتهية ومشغولة",
                "كهرباء", "غاز", "مياه", "تطهير",
            ]
            main_rows = []
            for r in (self._save_rows or []):
                main_rows.append([
                    r.get("program") or "",
                    r.get("total") or 0, r.get("done_count") or 0,
                    r.get("status_1") or 0, r.get("status_2") or 0,
                    r.get("status_3") or 0, r.get("status_4") or 0,
                    r.get("elec_sum") or 0, r.get("gas_sum") or 0,
                    r.get("water_sum") or 0, r.get("sew_sum") or 0,
                ])

            self.excel.export_statistics_to_file(
                file_path=path,
                main_headers=main_headers,
                main_rows=main_rows,
                detail_headers=[], detail_rows=[],
            )
            show_message(self, f"✅ تم الحفظ:\n{path}", ok=True)
        except Exception as e:
            show_message(self, f"❌ فشل التصدير: {e}", ok=False, title="خطأ")
