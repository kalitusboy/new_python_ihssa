"""شاشة الإحصاء/التعديل — مكافئة لـ lib/screens/survey_screen.dart."""
from __future__ import annotations
from datetime import datetime, timedelta
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QPushButton, QRadioButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
    QButtonGroup,
)

from ..config import IMAGES_DIR, STATUSES, STATUS_COLORS, PRIMARY, MUTED, BG
from ..models.beneficiary import Beneficiary
from ..services.database_service import DatabaseService
from ..widgets.common import make_card, make_button, label, info_row, confirm, show_message


class SurveyDialog(QDialog):
    """نافذة حوار لإحصاء أو تعديل مستفيد."""

    saved = pyqtSignal()
    deleted = pyqtSignal()

    def __init__(self, beneficiary: Beneficiary, parent=None):
        super().__init__(parent)
        self.b = beneficiary
        self.db = DatabaseService()
        self._image_path: str | None = None  # صورة جديدة محتملة

        self.setWindowTitle(f"📝 {beneficiary.display_name}")
        self.setModal(True)
        self.resize(1100, 720)
        self.setStyleSheet(f"QDialog {{ background: {BG}; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── شريط أعلى ──────────────────────
        bar = QFrame(); bar.setObjectName("appbar")
        bh = QHBoxLayout(bar); bh.setContentsMargins(20, 12, 20, 12)
        bh.addWidget(label(f"📝 {beneficiary.display_name}"))
        bh.addStretch(1)
        del_btn = make_button("🗑️  حذف", variant="danger", on_click=self._delete)
        save_btn = make_button("💾  حفظ وإتمام", variant="success", on_click=self._save)
        cls_btn = make_button("✕  إغلاق", variant="ghost", on_click=self.reject)
        bh.addWidget(del_btn); bh.addWidget(save_btn); bh.addWidget(cls_btn)
        root.addWidget(bar)

        # ── المحتوى الرئيسي ───────────────
        body = QWidget(); body_l = QHBoxLayout(body)
        body_l.setContentsMargins(20, 20, 20, 20)
        body_l.setSpacing(20)
        root.addWidget(body, 1)

        # العمود الأيمن — البيانات
        left = QScrollArea(); left.setWidgetResizable(True)
        left.setFrameShape(QScrollArea.Shape.NoFrame)
        left_inner = QWidget(); ll = QVBoxLayout(left_inner)
        ll.setContentsMargins(0, 0, 0, 0); ll.setSpacing(16)
        left.setWidget(left_inner)
        body_l.addWidget(left, 3)

        # ▸ كرت بيانات المستفيد
        info = make_card()
        v = info.layout()
        v.addWidget(label(beneficiary.display_name, role="title"))
        if beneficiary.birth_info:
            v.addWidget(label(beneficiary.birth_info, color=MUTED))
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#E2E8F0;")
        v.addWidget(sep)
        v.addWidget(info_row("📁 البرنامج", beneficiary.program or "عام"))
        v.addWidget(info_row("🏠 العنوان", beneficiary.address or "غير محدد"))
        if beneficiary.birth_date:
            v.addWidget(info_row("🎂 تاريخ الميلاد", beneficiary.birth_date))
        if beneficiary.birth_place:
            v.addWidget(info_row("📍 مكان الميلاد", beneficiary.birth_place))
        ll.addWidget(info)

        # ▸ كرت الشبكات
        nets = make_card()
        nets.layout().addWidget(label("🔗 الربط بالشبكات", bold=True, size=12))
        nets_row = QHBoxLayout(); nets_row.setSpacing(10)
        self.cb_e = self._network_chk("⚡  كهرباء", beneficiary.electricity == 1)
        self.cb_g = self._network_chk("🔥  غاز",    beneficiary.gas == 1)
        self.cb_w = self._network_chk("💧  مياه",  beneficiary.water == 1)
        self.cb_s = self._network_chk("🚿  تطهير", beneficiary.sewage == 1)
        for c in (self.cb_e, self.cb_g, self.cb_w, self.cb_s):
            nets_row.addWidget(c, 1)
        wrap = QWidget(); wrap.setLayout(nets_row)
        nets.layout().addWidget(wrap)
        ll.addWidget(nets)

        # ▸ كرت الحالة الفيزيائية
        status_card = make_card()
        status_card.layout().addWidget(label("🏗️ الحالة الفيزيائية", bold=True, size=12))
        self._status_group = QButtonGroup(self)
        self._status_group.setExclusive(True)
        for s in STATUSES:
            rb = QRadioButton(s)
            rb.setStyleSheet(f"QRadioButton {{ padding: 8px; font-size: 11pt; }}")
            if s == beneficiary.status: rb.setChecked(True)
            self._status_group.addButton(rb)
            status_card.layout().addWidget(rb)
        ll.addWidget(status_card)
        ll.addStretch(1)

        # العمود الأيسر — الصورة
        img_card = make_card()
        img_card.setMaximumWidth(380)
        il = img_card.layout()
        il.addWidget(label("📷 صورة المستفيد", bold=True, size=12))
        pick = make_button("📂  اختيار صورة من الكمبيوتر",
                           variant="ghost", on_click=self._pick_image)
        il.addWidget(pick)

        self.image_lbl = QLabel()
        self.image_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_lbl.setMinimumHeight(280)
        self.image_lbl.setStyleSheet(
            "border: 1px dashed #CBD5E1; border-radius: 12px;"
            "background:#F8FAFC; color:#94A3B8; font-size: 11pt;"
        )
        self.image_lbl.setText("لا توجد صورة")
        il.addWidget(self.image_lbl, 1)

        self.image_caption = QLabel("")
        self.image_caption.setStyleSheet(f"color: {MUTED}; font-size: 9pt;")
        self.image_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        il.addWidget(self.image_caption)

        body_l.addWidget(img_card, 2)

        # ── إن وُجدت صورة سابقة، أظهرها ─────
        if beneficiary.image_path and Path(beneficiary.image_path).exists():
            self._render_image(beneficiary.image_path, is_new=False)

    # ──────────────────────────────────────────
    def _network_chk(self, text: str, checked: bool) -> QCheckBox:
        cb = QCheckBox(text)
        cb.setChecked(checked)
        cb.setMinimumHeight(40)
        cb.setStyleSheet("QCheckBox { font-size: 11pt; padding: 6px; }")
        return cb

    def _render_image(self, path: str, *, is_new: bool) -> None:
        pm = QPixmap(path)
        if pm.isNull():
            return
        scaled = pm.scaled(
            self.image_lbl.width() or 320, 320,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_lbl.setPixmap(scaled)
        self.image_lbl.setStyleSheet("border: 1px solid #E2E8F0; border-radius: 12px;")
        cap = "صورة جديدة: " if is_new else "صورة محفوظة: "
        self.image_caption.setText(cap + Path(path).name)

    def _pick_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "اختر صورة المستفيد", "",
            "صور (*.jpg *.jpeg *.png *.bmp *.webp);;كل الملفات (*)",
        )
        if not path:
            return
        self._image_path = path
        self._render_image(path, is_new=True)

    # ──────────────────────────────────────────
    def _save(self) -> None:
        try:
            new_image_path = self.b.image_path
            new_image_name = self.b.image_file_name
            if self._image_path:
                # ننسخ إلى مجلد الصور الدائم
                IMAGES_DIR.mkdir(parents=True, exist_ok=True)
                gen = self.b.generate_image_filename()
                dest = IMAGES_DIR / gen
                dest.write_bytes(Path(self._image_path).read_bytes())
                new_image_path = str(dest)
                new_image_name = gen

            checked = self._status_group.checkedButton()
            status = checked.text() if checked else self.b.status

            updated = self.b.copy_with(
                done=1,
                electricity=1 if self.cb_e.isChecked() else 0,
                gas=1 if self.cb_g.isChecked() else 0,
                water=1 if self.cb_w.isChecked() else 0,
                sewage=1 if self.cb_s.isChecked() else 0,
                status=status,
                image_path=new_image_path,
                image_file_name=new_image_name,
                updated_at=int((datetime.now() + timedelta(minutes=1)).timestamp() * 1000),
            )
            self.db.update_beneficiary(updated)
            self.saved.emit()
            self.accept()
        except Exception as e:
            show_message(self, f"❌ فشل الحفظ: {e}", ok=False, title="خطأ")

    def _delete(self) -> None:
        if not confirm(self,
            f'هل أنت متأكد من حذف "{self.b.display_name}"؟ لا يمكن التراجع.',
            title="حذف المستفيد"
        ):
            return
        try:
            if self.b.id is not None:
                self.db.delete_beneficiary(self.b.id)
            self.deleted.emit()
            self.accept()
        except Exception as e:
            show_message(self, f"❌ فشل الحذف: {e}", ok=False, title="خطأ")
