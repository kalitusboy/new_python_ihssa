"""بطاقة عرض المستفيد في القوائم — مكافئة لـ lib/widgets/beneficiary_card.dart."""
from __future__ import annotations
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QColor
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
    QGraphicsDropShadowEffect,
)

from ..models.beneficiary import Beneficiary
from ..config import PRIMARY, MUTED, STATUS_COLORS


class BeneficiaryCard(QFrame):
    clicked = pyqtSignal(object)  # يبعث Beneficiary

    def __init__(self, beneficiary: Beneficiary, parent=None):
        super().__init__(parent)
        self.b = beneficiary
        self.setObjectName("card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(96)
        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(14); sh.setOffset(0, 3); sh.setColor(QColor(15, 23, 42, 18))
        self.setGraphicsEffect(sh)

        h = QHBoxLayout(self)
        h.setContentsMargins(14, 12, 14, 12)
        h.setSpacing(14)

        # ── الصورة / الأيقونة ─────────────────
        avatar = QLabel()
        avatar.setFixedSize(64, 64)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet(
            f"background: {PRIMARY}1A; border-radius: 12px;"
            f"color: {PRIMARY}; font-size: 18pt; font-weight: bold;"
        )
        if beneficiary.image_path and Path(beneficiary.image_path).exists():
            pm = QPixmap(beneficiary.image_path).scaled(
                64, 64, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            avatar.setPixmap(pm)
            avatar.setStyleSheet("border-radius: 12px;")
        else:
            initials = (
                (beneficiary.first_name[:1] if beneficiary.first_name else "")
                + (beneficiary.last_name[:1] if beneficiary.last_name else "")
            ).strip() or "؟"
            avatar.setText(initials)
        h.addWidget(avatar)

        # ── المعلومات ─────────────────────────
        info = QVBoxLayout()
        info.setSpacing(4)

        name = QLabel(beneficiary.display_name)
        name.setStyleSheet(f"color: {PRIMARY}; font-weight: bold; font-size: 13pt;")
        info.addWidget(name)

        meta_parts = []
        if beneficiary.program: meta_parts.append(f"📁 {beneficiary.program}")
        if beneficiary.address: meta_parts.append(f"🏠 {beneficiary.address}")
        if meta_parts:
            meta = QLabel(" · ".join(meta_parts))
            meta.setStyleSheet(f"color: {MUTED}; font-size: 10pt;")
            info.addWidget(meta)

        bi = beneficiary.birth_info
        if bi:
            bi_lbl = QLabel(bi)
            bi_lbl.setStyleSheet(f"color: {MUTED}; font-size: 9pt;")
            info.addWidget(bi_lbl)

        # شريط الشبكات (إن كانت محصاة)
        if beneficiary.done == 1:
            nets = QHBoxLayout()
            nets.setSpacing(6)
            for ic, on, label in [
                ("⚡", beneficiary.electricity, "كهرباء"),
                ("🔥", beneficiary.gas, "غاز"),
                ("💧", beneficiary.water, "مياه"),
                ("🚿", beneficiary.sewage, "تطهير"),
            ]:
                pill = QLabel(f"{ic} {label}")
                if on:
                    pill.setStyleSheet(
                        "background:#DCFCE7; color:#15803D; padding:2px 8px;"
                        "border-radius:8px; font-size: 9pt;"
                    )
                else:
                    pill.setStyleSheet(
                        "background:#F1F5F9; color:#94A3B8; padding:2px 8px;"
                        "border-radius:8px; font-size: 9pt;"
                    )
                nets.addWidget(pill)
            nets.addStretch(1)
            box = QWidget(); box.setLayout(nets); info.addWidget(box)

        h.addLayout(info, 1)

        # ── الحالة ────────────────────────────
        status_lbl = QLabel(beneficiary.status if beneficiary.done == 1 else "⏳ قيد الإحصاء")
        col = STATUS_COLORS.get(beneficiary.status, "#94A3B8") if beneficiary.done == 1 else "#F59E0B"
        status_lbl.setStyleSheet(
            f"background: {col}1A; color: {col}; font-weight: bold;"
            "padding: 6px 12px; border-radius: 10px; font-size: 10pt;"
        )
        status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h.addWidget(status_lbl)

    def mousePressEvent(self, ev) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.b)
        super().mousePressEvent(ev)
