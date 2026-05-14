"""شاشة المزامنة WiFi — مكافئة لـ lib/screens/sync_screen.dart.
تتضمن خادم HTTP (للمدير) + رمز QR للهواتف،
وعميل HTTP (للعون) لرفع/تنزيل البيانات.
"""
from __future__ import annotations
import io
from datetime import datetime
from urllib.parse import quote

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QGuiApplication
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..config import Prefs, PRIMARY, SUCCESS, DANGER, WARN
from ..services.sync_server import SyncServer
from ..services.sync_client import SyncClient
from ..widgets.common import make_card, make_button, label, info_row, show_message


# ──────────────────────────────────────────────
# خيط مزامنة (لا نُجمّد الواجهة أثناء HTTP)
# ──────────────────────────────────────────────
class _SyncWorker(QThread):
    progress = pyqtSignal(str)
    finished_ok = pyqtSignal(int, int, int, int)   # added, updated, up, down
    finished_err = pyqtSignal(str)

    def __init__(self, mode: str, parent=None):
        super().__init__(parent)
        self._mode = mode  # 'download' | 'upload'

    def run(self) -> None:
        try:
            client = SyncClient()
            if self._mode == "download":
                res = client.download_from_server(on_progress=self.progress.emit)
            else:
                res = client.upload_to_server(on_progress=self.progress.emit)
            if res.success:
                self.finished_ok.emit(res.added, res.updated, res.images_up, res.images_down)
            else:
                self.finished_err.emit(res.error or "فشل غير معروف")
        except Exception as e:
            self.finished_err.emit(str(e))


# ──────────────────────────────────────────────
def _make_qr_pixmap(text: str, size: int = 220) -> QPixmap | None:
    try:
        import qrcode
        img = qrcode.make(text)
        bio = io.BytesIO()
        img.save(bio, format="PNG")
        pm = QPixmap()
        pm.loadFromData(bio.getvalue(), "PNG")
        return pm.scaled(
            size, size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    except Exception:
        return None


# ──────────────────────────────────────────────
class SyncScreen(QWidget):
    """شاشة كاملة قابلة للعرض داخل الإطار الرئيسي."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("root")
        self.server = SyncServer()
        self.client = SyncClient()
        self._worker: _SyncWorker | None = None

        self._role = Prefs.get("device_role", "admin")
        self._password = Prefs.get("sync_password", "")
        self._admin_ip = Prefs.get("admin_ip", "")
        self._last_sync = Prefs.get("last_sync", "لم تتم بعد")

        self.client.configure(ip=self._admin_ip, password=self._password)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(20)

        # ── العمود الأيسر ───────────────────
        left = QVBoxLayout(); left.setSpacing(14)
        outer.addLayout(left, 3)

        # كرت معلومات الجهاز
        info_card = make_card()
        ic = info_card.layout()
        ic.addWidget(label("ℹ️  معلومات الجهاز", bold=True, size=12))
        ic.addWidget(info_row("الدور",
                              "👨‍💼 مدير" if self._role == "admin" else "👤 عون"))
        self.lbl_last_sync = QLabel(self._last_sync)
        last_row = QHBoxLayout()
        last_row.addWidget(QLabel("آخر مزامنة:")); last_row.addWidget(self.lbl_last_sync, 1)
        wlast = QWidget(); wlast.setLayout(last_row); ic.addWidget(wlast)
        self.lbl_ip = QLabel("—")
        ip_row = QHBoxLayout()
        ip_row.addWidget(QLabel("IP الكمبيوتر:"))
        ip_row.addWidget(self.lbl_ip, 1)
        wip = QWidget(); wip.setLayout(ip_row); ic.addWidget(wip)
        ic.addWidget(make_button("🔄  إعادة الإعداد", variant="ghost",
                                 on_click=self._reset_setup))
        left.addWidget(info_card)

        # تحكم المدير / العون
        ctl = make_card()
        cv = ctl.layout()
        if self._role == "admin":
            cv.addWidget(label("🖥️  السيرفر (كمبيوتر المدير)", bold=True, size=12))
            self.btn_server = make_button("▶  تشغيل السيرفر",
                                          variant="success", min_height=46,
                                          on_click=self._toggle_server)
            cv.addWidget(self.btn_server)
            cv.addWidget(label("الأعوان يتصلون بنفس شبكة WiFi ويُدخلون IP هذا الكمبيوتر",
                               role="muted"))
        else:
            cv.addWidget(label("📤  المزامنة مع المدير", bold=True, size=12))
            row = QHBoxLayout(); row.setSpacing(10)
            row.addWidget(make_button("⬇  تنزيل من المدير",
                                      variant="primary", min_height=46,
                                      on_click=lambda: self._start_sync("download")), 1)
            row.addWidget(make_button("⬆  رفع للمدير",
                                      variant="success", min_height=46,
                                      on_click=lambda: self._start_sync("upload")), 1)
            ww = QWidget(); ww.setLayout(row); cv.addWidget(ww)
            cv.addWidget(label(f"IP المدير: {self._admin_ip}", role="muted"))
        left.addWidget(ctl)

        # رسالة الحالة
        self.status_card = make_card()
        sv = self.status_card.layout()
        self.status_lbl = QLabel("")
        self.status_lbl.setWordWrap(True)
        sv.addWidget(self.status_lbl)
        self.status_card.setVisible(False)
        left.addWidget(self.status_card)
        left.addStretch(1)

        # ── العمود الأيمن — QR Code ────────
        if self._role == "admin":
            self.qr_card = make_card()
            qv = self.qr_card.layout()
            qv.addWidget(label("📱  QR للهواتف", bold=True, size=12))
            qv.addWidget(label("امسح بهاتف العون", role="muted"))
            self.qr_lbl = QLabel("شغّل السيرفر لعرض الرمز")
            self.qr_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.qr_lbl.setMinimumSize(240, 240)
            self.qr_lbl.setStyleSheet(
                "border: 1px dashed #CBD5E1; border-radius: 12px;"
                "background:#F8FAFC; color:#94A3B8; padding: 20px;"
            )
            qv.addWidget(self.qr_lbl)
            self.lbl_addr = QLabel("")
            self.lbl_addr.setAlignment(Qt.AlignmentFlag.AlignCenter)
            f = self.lbl_addr.font(); f.setBold(True); self.lbl_addr.setFont(f)
            qv.addWidget(self.lbl_addr)
            qv.addWidget(make_button("📋  نسخ IP", variant="ghost", on_click=self._copy_ip))
            self.qr_card.setMaximumWidth(300)
            outer.addWidget(self.qr_card, 2)

        # حالة السيرفر مبدئياً
        self._refresh_server_state()

    # ──────────────────────────────────────────
    def _refresh_server_state(self) -> None:
        if self._role != "admin":
            return
        running = self.server.is_running
        ip = self.server.local_ip
        self.btn_server.setText("⏹  إيقاف السيرفر" if running else "▶  تشغيل السيرفر")
        self.btn_server.setProperty("variant", "danger" if running else "success")
        self.btn_server.style().unpolish(self.btn_server)
        self.btn_server.style().polish(self.btn_server)
        if running and ip:
            self.lbl_ip.setText(f"{ip}:8080")
            self.lbl_addr.setText(f"{ip}:8080")
            qr_data = f"nhsync://{ip}:8080?pw={quote(self._password)}"
            pm = _make_qr_pixmap(qr_data, size=220)
            if pm:
                self.qr_lbl.setPixmap(pm)
                self.qr_lbl.setStyleSheet(
                    "border: 1px solid #E2E8F0; border-radius: 12px;"
                    "background: white; padding: 10px;"
                )
            else:
                self.qr_lbl.setText("(qrcode غير مثبتة)")
        else:
            self.lbl_ip.setText("—")
            self.lbl_addr.setText("")
            self.qr_lbl.clear()
            self.qr_lbl.setText("شغّل السيرفر لعرض الرمز")
            self.qr_lbl.setStyleSheet(
                "border: 1px dashed #CBD5E1; border-radius: 12px;"
                "background:#F8FAFC; color:#94A3B8; padding: 20px;"
            )

    # ──────────────────────────────────────────
    def _toggle_server(self) -> None:
        if self.server.is_running:
            self.server.stop()
            self._set_status("⏹  السيرفر متوقف.", color=WARN)
        else:
            self._set_status("⏳ جاري تشغيل السيرفر...", color=PRIMARY)
            ip = self.server.start(password=self._password)
            if ip:
                self._set_status(f"✅ السيرفر يعمل — IP: {ip}:8080", color=SUCCESS)
            else:
                self._set_status("❌ تعذر تشغيل السيرفر — تأكد من الشبكة", color=DANGER)
        self._refresh_server_state()

    # ──────────────────────────────────────────
    def _start_sync(self, mode: str) -> None:
        if self._worker and self._worker.isRunning():
            return
        self._set_status("⏳ جاري المزامنة...", color=PRIMARY)
        self._worker = _SyncWorker(mode, self)
        self._worker.progress.connect(lambda m: self._set_status(m, color=PRIMARY))
        self._worker.finished_ok.connect(self._on_sync_ok)
        self._worker.finished_err.connect(self._on_sync_err)
        self._worker.start()

    def _on_sync_ok(self, added: int, updated: int, up: int, down: int) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        Prefs.set("last_sync", ts)
        self._last_sync = ts
        self.lbl_last_sync.setText(ts)
        msg_parts = []
        if added or updated:
            msg_parts.append(f"{added} مضاف · {updated} محدث")
        if up:   msg_parts.append(f"⬆ {up} صورة")
        if down: msg_parts.append(f"⬇ {down} صورة")
        msg = "✅  تمت المزامنة" + (" — " + " · ".join(msg_parts) if msg_parts else "")
        self._set_status(msg, color=SUCCESS)

    def _on_sync_err(self, err: str) -> None:
        self._set_status(f"❌  فشل: {err}", color=DANGER)

    # ──────────────────────────────────────────
    def _set_status(self, text: str, *, color: str = PRIMARY) -> None:
        self.status_lbl.setText(text)
        self.status_lbl.setStyleSheet(f"color: {color}; font-weight: 600;")
        self.status_card.setVisible(bool(text))

    def _copy_ip(self) -> None:
        ip = self.server.local_ip
        if ip:
            QGuiApplication.clipboard().setText(f"{ip}:8080")
            self._set_status("📋  تم نسخ IP", color=SUCCESS)

    def _reset_setup(self) -> None:
        Prefs.set("setup_done", False)
        show_message(self, "تم إعادة الإعداد. أعِد تشغيل التطبيق لاستكمال الإعداد.",
                     ok=True, title="إعادة الإعداد")
