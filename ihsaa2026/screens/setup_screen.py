"""شاشة الإعداد الأولي — مكافئة لـ lib/screens/setup_screen.dart."""
from __future__ import annotations
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QWidget, QSizePolicy,
)

from ..config import Prefs, PRIMARY, MUTED, BG
from ..widgets.common import make_card, make_button, label, show_message


_DEFAULT_IP = "192.168.1.1"


class _RoleCard(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, *, role: str, icon: str, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        self.role = role
        self._selected = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(110)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 14, 14, 14)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.setSpacing(4)

        ic = QLabel(icon); ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setStyleSheet("font-size: 24pt;")
        ti = QLabel(title); ti.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ti.setStyleSheet("font-weight: bold;")
        sub = QLabel(subtitle); sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"color: {MUTED}; font-size: 9pt;")
        sub.setWordWrap(True)
        v.addWidget(ic); v.addWidget(ti); v.addWidget(sub)
        self._refresh()

    def setSelected(self, on: bool) -> None:
        self._selected = on
        self._refresh()

    def _refresh(self) -> None:
        if self._selected:
            self.setStyleSheet(
                f"QFrame {{ border: 2px solid {PRIMARY}; border-radius: 12px;"
                f"background: {PRIMARY}14; }}"
            )
        else:
            self.setStyleSheet(
                "QFrame { border: 1px solid #E2E8F0; border-radius: 12px;"
                "background: #F8FAFC; }"
            )

    def mousePressEvent(self, ev) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.role)


class SetupScreen(QWidget):
    """شاشة الإعداد — تَبعث إشارة done() عند الإكمال."""

    done = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("root")
        self._role: str | None = None

        outer = QHBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.addStretch(1)

        card = make_card(padding=32)
        card.setMaximumWidth(540)
        card.setMinimumWidth(440)
        v = card.layout()

        # ── الترويسة ─────────────────────────
        ic = QLabel("🏘️"); ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setStyleSheet("font-size: 40pt;")
        v.addWidget(ic)
        v.addWidget(label("إحصاء السكن الريفي 2026", role="title"))
        sub = label("نسيم — الحوضان", role="subtitle")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(sub)
        v.addSpacing(20)

        # ── نوع الجهاز ───────────────────────
        v.addWidget(label("نوع الجهاز:", bold=True))
        roles_box = QWidget()
        roles = QHBoxLayout(roles_box)
        roles.setSpacing(12)
        roles.setContentsMargins(0, 0, 0, 0)
        self.admin_card = _RoleCard(role="admin", icon="👨‍💼", title="مدير",
                                    subtitle="يستقبل بيانات الأعوان")
        self.agent_card = _RoleCard(role="agent", icon="👤", title="عون",
                                    subtitle="يرسل البيانات للمدير")
        for c in (self.admin_card, self.agent_card):
            c.clicked.connect(self._on_role)
            roles.addWidget(c)
        v.addWidget(roles_box)
        v.addSpacing(14)

        # ── كلمة المرور ──────────────────────
        v.addWidget(label("كلمة المرور (مشتركة بين جميع الأجهزة):"))
        self.pass_in = QLineEdit()
        self.pass_in.setPlaceholderText("أدخل كلمة المرور (4 أحرف على الأقل)")
        self.pass_in.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_in.setMinimumHeight(40)
        v.addWidget(self.pass_in)

        # خانة IP — للعون فقط
        self.ip_holder = QFrame()
        ip_lay = QVBoxLayout(self.ip_holder)
        ip_lay.setContentsMargins(0, 8, 0, 0)
        ip_lay.addWidget(label("عنوان IP لكمبيوتر المدير (مثال: 192.168.1.100):"))
        self.ip_in = QLineEdit(_DEFAULT_IP)
        self.ip_in.setMinimumHeight(40)
        ip_lay.addWidget(self.ip_in)
        ip_lay.addWidget(label("يمكنك معرفة IP من ipconfig في CMD", role="muted"))
        self.ip_holder.setVisible(False)
        v.addWidget(self.ip_holder)
        v.addSpacing(10)

        # ── زر الحفظ ─────────────────────────
        save_btn = make_button("✓  بدء التطبيق", min_height=52, on_click=self._save)
        v.addWidget(save_btn)

        outer.addWidget(card)
        outer.addStretch(1)

        # حالة افتراضية
        prev_role = Prefs.get("device_role")
        prev_pwd = Prefs.get("sync_password", "")
        prev_ip = Prefs.get("admin_ip", _DEFAULT_IP)
        if prev_role in ("admin", "agent"):
            self._on_role(prev_role)
        if prev_pwd:
            self.pass_in.setText(prev_pwd)
        if prev_ip:
            self.ip_in.setText(prev_ip)

    # ──────────────────────────────────────────
    def _on_role(self, role: str) -> None:
        self._role = role
        self.admin_card.setSelected(role == "admin")
        self.agent_card.setSelected(role == "agent")
        self.ip_holder.setVisible(role == "agent")

    def _save(self) -> None:
        if not self._role:
            show_message(self, "اختر نوع الجهاز أولاً", ok=False, title="تنبيه")
            return
        pwd = self.pass_in.text().strip()
        if len(pwd) < 4:
            show_message(self, "كلمة المرور يجب أن تكون 4 أحرف على الأقل", ok=False, title="تنبيه")
            return
        if self._role == "agent" and not self.ip_in.text().strip():
            show_message(self, "أدخل IP الخادم (كمبيوتر المدير)", ok=False, title="تنبيه")
            return

        Prefs.set("device_role", self._role)
        Prefs.set("sync_password", pwd)
        Prefs.set("admin_ip",
                  _DEFAULT_IP if self._role == "admin" else self.ip_in.text().strip())
        Prefs.set("setup_done", True)
        self.done.emit()
