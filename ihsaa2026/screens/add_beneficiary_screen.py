"""شاشة إضافة مستفيد — مكافئة لـ lib/screens/add_beneficiary_screen.dart."""
from __future__ import annotations
from PyQt6.QtCore import Qt, pyqtSignal, QDate
from PyQt6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from ..config import BG, MUTED
from ..models.beneficiary import Beneficiary
from ..services.database_service import DatabaseService
from ..widgets.common import make_card, make_button, label, show_message


class AddBeneficiaryDialog(QDialog):
    saved = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = DatabaseService()
        self.setWindowTitle("➕ إضافة مستفيد جديد")
        self.setModal(True)
        self.resize(620, 720)
        self.setStyleSheet(f"QDialog {{ background: {BG}; }}")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        bar = QFrame(); bar.setObjectName("appbar")
        bh = QHBoxLayout(bar); bh.setContentsMargins(20, 12, 20, 12)
        bh.addWidget(label("➕ إضافة مستفيد جديد"))
        bh.addStretch(1)
        bh.addWidget(make_button("✕  إغلاق", variant="ghost", on_click=self.reject))
        outer.addWidget(bar)

        body = QWidget(); bv = QVBoxLayout(body)
        bv.setContentsMargins(20, 20, 20, 20); bv.setSpacing(14)
        outer.addWidget(body, 1)

        card = make_card()
        v = card.layout()

        # ── الحقول ─────────────────────────
        self.first_in = self._field("الاسم الأول *", "👤")
        self.last_in  = self._field("اللقب *", "👥")
        self.bp_in    = self._field("مكان الميلاد", "📍")
        self.addr_in  = self._field("العنوان", "🏠")

        # تاريخ الميلاد
        v.addWidget(label("تاريخ الميلاد", bold=True))
        self.bd_in = QDateEdit()
        self.bd_in.setCalendarPopup(True)
        self.bd_in.setDisplayFormat("yyyy-MM-dd")
        self.bd_in.setMinimumDate(QDate(1920, 1, 1))
        self.bd_in.setMaximumDate(QDate.currentDate())
        self.bd_in.setDate(QDate(1980, 1, 1))
        self.bd_in.setMinimumHeight(40)
        v.addWidget(self.bd_in)

        for w in (self.first_in, self.last_in, self.bp_in, self.addr_in):
            pass  # تم إضافتها داخل _field

        for w in (self.first_in, self.last_in, self.bp_in, self.addr_in):
            v.addWidget(w["wrap"])

        # البرنامج
        v.addWidget(label("البرنامج", bold=True))
        prog_row = QHBoxLayout(); prog_row.setSpacing(10)
        self.prog_combo = QComboBox()
        self.prog_combo.setMinimumHeight(40)
        self.prog_combo.setEditable(False)
        progs = self.db.get_programs()
        self.prog_combo.addItems(progs if progs else [])
        self.prog_combo.addItem("➕ برنامج جديد...")
        self.prog_combo.currentIndexChanged.connect(self._on_prog_changed)
        prog_row.addWidget(self.prog_combo, 2)

        self.new_prog_in = QLineEdit()
        self.new_prog_in.setPlaceholderText("اسم البرنامج الجديد")
        self.new_prog_in.setMinimumHeight(40)
        self.new_prog_in.setVisible(False)
        prog_row.addWidget(self.new_prog_in, 2)
        wrap = QWidget(); wrap.setLayout(prog_row)
        v.addWidget(wrap)

        bv.addWidget(card)

        # ── أزرار الحفظ ────────────────────
        actions = QHBoxLayout(); actions.setSpacing(10)
        actions.addWidget(make_button("✕  إلغاء", variant="ghost", on_click=self.reject), 1)
        actions.addWidget(make_button("💾  حفظ", variant="success", on_click=self._save), 2)
        ww = QWidget(); ww.setLayout(actions)
        bv.addWidget(ww)
        bv.addStretch(1)

    def _field(self, lbl: str, icon: str) -> dict:
        wrap = QWidget()
        v = QVBoxLayout(wrap)
        v.setContentsMargins(0, 0, 0, 0); v.setSpacing(4)
        v.addWidget(label(lbl, bold=True))
        ed = QLineEdit()
        ed.setPlaceholderText(f"{icon}  {lbl.replace('*','').strip()}")
        ed.setMinimumHeight(40)
        v.addWidget(ed)
        return {"wrap": wrap, "edit": ed}

    def _on_prog_changed(self, idx: int) -> None:
        is_new = self.prog_combo.itemText(idx).startswith("➕")
        self.new_prog_in.setVisible(is_new)

    # ──────────────────────────────────────────
    def _save(self) -> None:
        first = self.first_in["edit"].text().strip()
        last  = self.last_in["edit"].text().strip()
        if not first and not last:
            show_message(self, "أدخل الاسم الأول واللقب", ok=False); return

        bp = self.bp_in["edit"].text().strip() or None
        addr = self.addr_in["edit"].text().strip() or None
        bd = self.bd_in.date().toString("yyyy-MM-dd")

        if self.prog_combo.currentText().startswith("➕"):
            program = self.new_prog_in.text().strip()
            if not program:
                show_message(self, "أدخل اسم البرنامج الجديد", ok=False); return
        else:
            program = self.prog_combo.currentText().strip() or "عام"

        try:
            if self.db.beneficiary_exists(first, last, bd, addr):
                show_message(self, "⚠️ يوجد مستفيد بنفس البيانات مسبقاً", ok=False)
                return
            b = Beneficiary(
                first_name=first, last_name=last,
                full_name=f"{first} {last}".strip(),
                birth_date=bd, birth_place=bp, address=addr,
                program=program,
            )
            self.db.insert_beneficiary(b)
            self.saved.emit()
            self.accept()
        except Exception as e:
            show_message(self, f"❌ فشل الإضافة: {e}", ok=False, title="خطأ")
