"""الشاشة الرئيسية — مكافئة لـ lib/screens/home_screen.dart.
تتضمن: الشريط الجانبي + لوحة المعلومات + قائمة المستفيدين + تبويب (متبقي/محصاة) + بحث + استيراد/تصدير.
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QProgressBar, QPushButton, QScrollArea,
    QStackedWidget, QTabBar, QVBoxLayout, QWidget, QSizePolicy,
)

from ..config import (
    Prefs, PRIMARY, PRIMARY_DARK, MUTED, SUCCESS, DANGER, WARN,
    DOCS_DIR, IMAGES_DIR,
)
from ..models.beneficiary import Beneficiary
from ..services.database_service import DatabaseService
from ..services.excel_service import ExcelService
from ..services.export_service import ExportService

from ..widgets.beneficiary_card import BeneficiaryCard
from ..widgets.common import (
    make_card, make_button, label, show_message, confirm, Snackbar,
)

from .add_beneficiary_screen import AddBeneficiaryDialog
from .survey_screen import SurveyDialog
from .stats_screen import StatsScreen
from .advanced_stats_screen import AdvancedStatsScreen
from .report_screen import ReportScreen
from .sync_screen import SyncScreen
from .admin_merge_screen import AdminMergeScreen


PAGE_SIZE = 100


class HomeScreen(QWidget):
    """نافذة رئيسية كاملة بشريط جانبي + محتوى تبادلي."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("root")
        self.db = DatabaseService()
        self.excel = ExcelService()
        self.export = ExportService()

        self._search = ""
        self._addr: Optional[str] = None
        self._tab = 0  # 0 = pending, 1 = completed
        self._offset = 0
        self._has_more = True
        self._loading = False
        self._results: list[Beneficiary] = []

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._reload)

        # ── التخطيط ────────────────────────
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        self._build_sidebar()
        root.addWidget(self.sidebar)

        # المحتوى المتبادل
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        # الصفحة 0: لوحة المستفيدين
        self.dashboard_page = self._build_dashboard()
        self.stack.addWidget(self.dashboard_page)

        # باقي الصفحات تُنشأ عند الطلب
        self.stats_page = StatsScreen(self)
        self.advanced_page = AdvancedStatsScreen(self)
        self.report_page = ReportScreen(self)
        self.sync_page = SyncScreen(self)
        self.admin_merge_page = AdminMergeScreen(self)
        for w in (self.stats_page, self.advanced_page, self.report_page, self.sync_page, self.admin_merge_page):
            self.stack.addWidget(w)

        # Snackbar
        self.snackbar = Snackbar(self)

        # تحميل أولي
        self._load_addresses()
        self._reload()
        self._load_dashboard()

    # ══════════════════════════════════════════
    # الشريط الجانبي
    # ══════════════════════════════════════════
    def _build_sidebar(self) -> None:
        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(230)

        v = QVBoxLayout(self.sidebar)
        v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0)

        # الترويسة
        header = QWidget(); header.setObjectName("sidebarHeader")
        hv = QVBoxLayout(header); hv.setContentsMargins(16, 18, 16, 14); hv.setSpacing(6)
        hv.addWidget(QLabel("🏘️", styleSheet="font-size: 24pt; color: white;"))
        t = QLabel("إحصاء السكن الريفي")
        t.setStyleSheet("color: white; font-weight: bold; font-size: 12pt;")
        sub = QLabel("نسيم — الحوضان · 2026")
        sub.setStyleSheet("color: rgba(255,255,255,0.65); font-size: 9pt;")
        hv.addWidget(t); hv.addWidget(sub)

        # شريط التقدم
        prog_row = QHBoxLayout(); prog_row.setSpacing(6)
        self.lbl_pct = QLabel("0%"); self.lbl_pct.setStyleSheet("color: white; font-size: 9pt;")
        self.bar = QProgressBar(); self.bar.setMaximum(100); self.bar.setValue(0)
        self.bar.setTextVisible(False); self.bar.setFixedHeight(6)
        self.bar.setStyleSheet("""
            QProgressBar { background: rgba(255,255,255,0.18); border-radius: 3px; }
            QProgressBar::chunk { background: #FFD54F; border-radius: 3px; }
        """)
        prog_row.addWidget(self.lbl_pct); prog_row.addWidget(self.bar, 1)
        wp = QWidget(); wp.setLayout(prog_row); hv.addWidget(wp)

        stats_row = QHBoxLayout(); stats_row.setSpacing(8)
        self.mini_total = self._mini_stat("الكل", "0", "white")
        self.mini_done  = self._mini_stat("محصاة", "0", "#86EFAC")
        self.mini_pend  = self._mini_stat("متبقية", "0", "#FCD34D")
        for w in (self.mini_total, self.mini_done, self.mini_pend):
            stats_row.addWidget(w, 1)
        ws = QWidget(); ws.setLayout(stats_row); hv.addWidget(ws)
        v.addWidget(header)

        # زر إضافة
        v.addSpacing(6)
        add_wrap = QWidget(); add_l = QVBoxLayout(add_wrap)
        add_l.setContentsMargins(12, 4, 12, 8)
        add_btn = make_button("➕  إضافة مستفيد", variant="success",
                              min_height=42, on_click=self._add_beneficiary)
        add_l.addWidget(add_btn)
        v.addWidget(add_wrap)

        # روابط الصفحات
        self._nav_buttons: list[QPushButton] = []
        for icon, text, idx in [
            ("📋", "المستفيدون", 0),
            ("📊", "الإحصائيات", 1),
            ("📈", "إحصائيات متقدمة", 2),
            ("📑", "التقارير", 3),
            ("📡", "مزامنة WiFi", 4),
            ("👥", "دمج المدير", 5),
        ]:
            btn = QPushButton(f"  {icon}    {text}")
            btn.setMinimumHeight(46)
            btn.setProperty("variant", "sidebar")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, i=idx: self._go(i))
            v.addWidget(btn)
            self._nav_buttons.append(btn)

        v.addStretch(1)

        # عمليات سريعة
        ops = QVBoxLayout(); ops.setContentsMargins(12, 8, 12, 8); ops.setSpacing(6)
        ops.addWidget(make_button("📥  استيراد Excel", variant="ghost",
                                  min_height=38, on_click=self._import_excel))
        ops.addWidget(make_button("📤  تصدير Excel", variant="ghost",
                                  min_height=38, on_click=self._export_excel))
        ops.addWidget(make_button("🔀  دمج JSON", variant="ghost",
                                  min_height=38, on_click=self._merge_json))
        ops.addWidget(make_button("ℹ️  حول", variant="ghost",
                                  min_height=38, on_click=self._about))
        wo = QWidget(); wo.setLayout(ops); v.addWidget(wo)

        self._set_active(0)

    def _mini_stat(self, title: str, value: str, color: str) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(2)
        l1 = QLabel(value); l1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l1.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 14pt;")
        l2 = QLabel(title); l2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l2.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 8pt;")
        v.addWidget(l1); v.addWidget(l2)
        # نخزّن مرجعاً للقيمة كي نحدّثها لاحقاً
        w._value_label = l1  # type: ignore[attr-defined]
        return w

    def _set_active(self, idx: int) -> None:
        for i, b in enumerate(self._nav_buttons):
            b.setProperty("variant", "sidebarActive" if i == idx else "sidebar")
            b.style().unpolish(b); b.style().polish(b)

    def _go(self, idx: int) -> None:
        self.stack.setCurrentIndex(idx)
        self._set_active(idx)
        # تحديث الصفحات الحية
        if idx == 1: self.stats_page.refresh()
        elif idx == 2: self.advanced_page.refresh()
        elif idx == 3: self.report_page._reload_programs()
        elif idx == 5: pass  # admin_merge_page لا يحتاج تحديث تلقائي

    # ══════════════════════════════════════════
    # لوحة المستفيدين
    # ══════════════════════════════════════════
    def _build_dashboard(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page); v.setContentsMargins(20, 20, 20, 20); v.setSpacing(14)

        # ── شريط البحث + الفلتر ──────────
        bar = QHBoxLayout(); bar.setSpacing(10)
        self.search_in = QLineEdit()
        self.search_in.setPlaceholderText("🔍  البحث عن مستفيد (الاسم، اللقب، العنوان، البرنامج)...")
        self.search_in.setMinimumHeight(44)
        self.search_in.textChanged.connect(self._on_search_change)
        bar.addWidget(self.search_in, 4)

        self.addr_combo = QComboBox()
        self.addr_combo.setMinimumHeight(44)
        self.addr_combo.addItem("📍  جميع العناوين", None)
        self.addr_combo.currentIndexChanged.connect(self._on_addr_change)
        bar.addWidget(self.addr_combo, 2)

        wb = QWidget(); wb.setLayout(bar); v.addWidget(wb)

        # ── Tabs ─────────────────────────
        self.tabs = QTabBar()
        self.tabs.addTab("⏳  متبقية")
        self.tabs.addTab("✅  محصاة")
        self.tabs.setExpanding(False)
        self.tabs.currentChanged.connect(self._on_tab_change)
        v.addWidget(self.tabs)

        # ── قائمة النتائج ────────────────
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.verticalScrollBar().valueChanged.connect(self._on_scroll)

        self.list_holder = QWidget()
        self.list_v = QVBoxLayout(self.list_holder)
        self.list_v.setContentsMargins(0, 0, 0, 0); self.list_v.setSpacing(8)
        self.list_v.addStretch(1)
        self.scroll.setWidget(self.list_holder)
        v.addWidget(self.scroll, 1)

        return page

    # ──────────────────────────────────────────
    def _load_addresses(self) -> None:
        addrs = self.db.get_distinct_addresses()
        cur = self._addr
        self.addr_combo.blockSignals(True)
        self.addr_combo.clear()
        self.addr_combo.addItem("📍  جميع العناوين", None)
        for a in addrs:
            self.addr_combo.addItem(a, a)
        if cur and cur in addrs:
            i = self.addr_combo.findData(cur)
            if i >= 0:
                self.addr_combo.setCurrentIndex(i)
        self.addr_combo.blockSignals(False)

    def _load_dashboard(self) -> None:
        d = self.db.get_dashboard_stats()
        total = d.get("total") or 0
        done = d.get("done") or 0
        pending = d.get("pending") or 0
        pct = round(done / total * 100) if total else 0
        self.bar.setValue(pct)
        self.lbl_pct.setText(f"{pct}%")
        self.mini_total._value_label.setText(str(total))    # type: ignore
        self.mini_done._value_label.setText(str(done))      # type: ignore
        self.mini_pend._value_label.setText(str(pending))   # type: ignore

    # ──────────────────────────────────────────
    def _on_search_change(self, text: str) -> None:
        self._search = text.strip()
        self._debounce.start(350)

    def _on_addr_change(self, _: int) -> None:
        self._addr = self.addr_combo.currentData()
        self._reload()

    def _on_tab_change(self, idx: int) -> None:
        self._tab = idx
        self._reload()

    def _on_scroll(self, _: int) -> None:
        sb = self.scroll.verticalScrollBar()
        if sb.maximum() - sb.value() < 200:
            self._load_more()

    # ──────────────────────────────────────────
    def _reload(self) -> None:
        self._offset = 0
        self._has_more = True
        self._results = []
        self._render_list()
        self._load_more(reset=True)
        self._load_dashboard()

    def _load_more(self, reset: bool = False) -> None:
        if self._loading or (not reset and not self._has_more):
            return
        self._loading = True
        try:
            res = self.db.search_beneficiaries(
                done_value=0 if self._tab == 0 else 1,
                query=self._search,
                address=self._addr,
                limit=PAGE_SIZE,
                offset=0 if reset else self._offset,
            )
            if reset:
                self._results = res
            else:
                self._results.extend(res)
            self._offset = len(self._results)
            self._has_more = len(res) == PAGE_SIZE
            self._render_list()
        except Exception as e:
            self.snackbar.show_msg(f"❌ {e}", ok=False)
        finally:
            self._loading = False

    def _render_list(self) -> None:
        # امسح القائمة
        while self.list_v.count():
            it = self.list_v.takeAt(0)
            w = it.widget()
            if w: w.deleteLater()

        if not self._results:
            empty = make_card()
            empty.layout().addWidget(label(
                "🔎  لا توجد بيانات مطابقة" if (self._search or self._addr)
                else ("✨ لا توجد حالات محصاة بعد" if self._tab == 1 else "📭 لا يوجد مستفيدون"),
                bold=True
            ))
            empty.layout().addWidget(label("ابدأ بإضافة مستفيد جديد أو استيراد ملف Excel.",
                                           role="muted"))
            self.list_v.addWidget(empty)
        else:
            for b in self._results:
                card = BeneficiaryCard(b)
                card.clicked.connect(self._open_survey)
                self.list_v.addWidget(card)
        self.list_v.addStretch(1)

    # ──────────────────────────────────────────
    def _open_survey(self, b: Beneficiary) -> None:
        dlg = SurveyDialog(b, self)
        dlg.saved.connect(self._after_change)
        dlg.deleted.connect(self._after_change)
        dlg.exec()

    def _add_beneficiary(self) -> None:
        dlg = AddBeneficiaryDialog(self)
        dlg.saved.connect(self._after_change)
        dlg.exec()

    def _after_change(self) -> None:
        self._load_addresses()
        self._reload()

    # ══════════════════════════════════════════
    # عمليات الاستيراد/التصدير
    # ══════════════════════════════════════════
    def _import_excel(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "اختر ملف Excel للاستيراد", "",
            "Excel/CSV (*.xlsx *.xls *.csv);;كل الملفات (*)",
        )
        if not path: return
        try:
            items = self.excel.import_from_excel(Path(path))
            if not items:
                self.snackbar.show_msg("⚠️ لم يُستورد أي بيان، تأكد من تنسيق الأعمدة", ok=False)
                return
            self.db.insert_beneficiaries(items)
            self.snackbar.show_msg(f"✅ تم استيراد {len(items)} مستفيد", ok=True)
            self._after_change()
        except Exception as e:
            show_message(self, f"❌ فشل الاستيراد: {e}", ok=False, title="خطأ")

    def _export_excel(self) -> None:
        try:
            items = self.db.get_completed_beneficiaries()
            if not items:
                self.snackbar.show_msg("⚠️ لا توجد حالات محصاة", ok=False); return
            path, _ = QFileDialog.getSaveFileName(
                self, "حفظ ملف Excel",
                str(DOCS_DIR / "تصدير_المستفيدين.xlsx"),
                "Excel (*.xlsx)",
            )
            if not path: return
            out = self.excel.export_to_excel(items, file_path=Path(path))
            self.snackbar.show_msg(f"✅ تم: {out.name}", ok=True)
        except Exception as e:
            show_message(self, f"❌ {e}", ok=False, title="خطأ")

    def _merge_json(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "اختر ملفات JSON للدمج", "",
            "JSON (*.json);;كل الملفات (*)",
        )
        if not paths: return
        try:
            r = self.export.merge_databases([Path(p) for p in paths])
            self.snackbar.show_msg(
                f"✅ {r.get('imported',0)} جديد · {r.get('skipped',0)} مكرّر",
                ok=True,
            )
            self._after_change()
        except Exception as e:
            show_message(self, f"❌ {e}", ok=False, title="خطأ")

    def _about(self) -> None:
        show_message(self, (
            "💻 إحصاء السكن الريفي 2026 — نسخة Python\n"
            "الإصدار: 11.1.0 (PyQt6)\n\n"
            "دعم عربي RTL + تقارير PDF + إحصائيات متقدمة\n"
            "مزامنة WiFi مع هواتف الأعوان (متوافق مع نسخة Flutter).\n\n"
            "المطور: حميتي نسيم — الحوضان\n"
            "nas.hamiti89@gmail.com"
        ), ok=True, title="حول البرنامج")
