"""عميل HTTP للمزامنة — مكافئ لـ lib/services/sync_client.dart.
يستعمل urllib من المكتبة القياسية (لا تبعيات خارجية إجبارية)،
وإن وُجدت requests يستعملها (أسرع/أوضح).
"""
from __future__ import annotations
import json
import time
from dataclasses import dataclass
from typing import Callable, Optional

from ..config import TMP_DIR
from .sync_service import SyncService

try:
    import requests  # type: ignore
    _HAS_REQUESTS = True
except Exception:
    _HAS_REQUESTS = False
    import urllib.request as _ur
    import urllib.error as _ue


@dataclass
class SyncResult:
    success: bool
    added: int = 0
    updated: int = 0
    images_up: int = 0
    images_down: int = 0
    error: Optional[str] = None

    @classmethod
    def ok(cls, added: int, updated: int, images_up: int, images_down: int) -> "SyncResult":
        return cls(True, added, updated, images_up, images_down, None)

    @classmethod
    def fail(cls, error: str) -> "SyncResult":
        return cls(False, error=error)


class SyncClient:
    _instance: "SyncClient" = None  # type: ignore

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_inited"):
            self._ip = ""
            self._password = ""
            self._sync = SyncService()
            self._inited = True

    @property
    def base(self) -> str:
        return f"http://{self._ip}:8080"

    def configure(self, ip: str, password: str) -> None:
        self._ip = (ip or "").strip()
        self._password = (password or "").strip()

    @property
    def headers(self) -> dict:
        return {
            "x-password": self._password,
            "Content-Type": "application/json; charset=utf-8",
        }

    # ──────────────────────────────────────────
    # طبقة HTTP رقيقة — تعمل مع/بدون requests
    # ──────────────────────────────────────────
    def _http_get(self, path: str, timeout: float = 5.0):
        url = self.base + path
        if _HAS_REQUESTS:
            return requests.get(url, headers=self.headers, timeout=timeout)
        req = _ur.Request(url, headers=self.headers, method="GET")
        try:
            r = _ur.urlopen(req, timeout=timeout)
            return _Resp(r.status, r.read(), dict(r.headers))
        except _ue.HTTPError as e:
            return _Resp(e.code, e.read() or b"", dict(e.headers or {}))
        except Exception:
            return _Resp(0, b"", {})

    def _http_post_json(self, path: str, body: dict, timeout: float = 300.0):
        url = self.base + path
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        if _HAS_REQUESTS:
            return requests.post(url, data=data, headers=self.headers, timeout=timeout)
        req = _ur.Request(url, data=data, headers=self.headers, method="POST")
        try:
            r = _ur.urlopen(req, timeout=timeout)
            return _Resp(r.status, r.read(), dict(r.headers))
        except _ue.HTTPError as e:
            return _Resp(e.code, e.read() or b"", dict(e.headers or {}))
        except Exception as e:
            return _Resp(0, str(e).encode("utf-8"), {})

    def _http_post_bytes(self, path: str, payload: bytes, timeout: float = 300.0):
        url = self.base + path
        headers = {
            "x-password": self._password,
            "Content-Type": "application/octet-stream",
        }
        if _HAS_REQUESTS:
            return requests.post(url, data=payload, headers=headers, timeout=timeout)
        req = _ur.Request(url, data=payload, headers=headers, method="POST")
        try:
            r = _ur.urlopen(req, timeout=timeout)
            return _Resp(r.status, r.read(), dict(r.headers))
        except _ue.HTTPError as e:
            return _Resp(e.code, e.read() or b"", dict(e.headers or {}))
        except Exception as e:
            return _Resp(0, str(e).encode("utf-8"), {})

    # ──────────────────────────────────────────
    def ping(self) -> bool:
        try:
            r = self._http_get("/ping", timeout=5)
            return getattr(r, "status_code", getattr(r, "status", 0)) == 200
        except Exception:
            return False

    def authenticate(self) -> bool:
        try:
            r = self._http_post_json("/auth", {"password": self._password}, timeout=5)
            sc = getattr(r, "status_code", getattr(r, "status", 0))
            if sc != 200:
                return False
            body = json.loads(_body_text(r) or "{}")
            return bool(body.get("ok"))
        except Exception:
            return False

    # ──────────────────────────────────────────
    def download_from_server(self, on_progress: Optional[Callable[[str], None]] = None) -> SyncResult:
        try:
            if on_progress: on_progress("🔌 جاري الاتصال...")
            if not self.ping():
                return SyncResult.fail("تعذر الاتصال")
            if on_progress: on_progress("🔑 جاري التحقق...")
            if not self.authenticate():
                return SyncResult.fail("كلمة المرور خاطئة")

            if on_progress: on_progress("📋 إعداد الملخص...")
            my_summary = self._sync.get_summary()

            if on_progress: on_progress("🔄 استقبال تحديثات المدير...")
            r = self._http_post_json("/metasync", {"summary": my_summary}, timeout=300)
            sc = getattr(r, "status_code", getattr(r, "status", 0))
            if sc != 200:
                return SyncResult.fail("خطأ في metasync")

            ctype = _content_type(r)
            if "application/zip" in ctype.lower():
                tmp = TMP_DIR / f"from_server_{int(time.time()*1000)}.zip"
                tmp.write_bytes(_body_bytes(r))
                stats = self._sync.process_received_zip(tmp)
                try: tmp.unlink()
                except Exception: pass
                return SyncResult.ok(
                    added=stats.get("added", 0),
                    updated=stats.get("updated", 0),
                    images_up=0,
                    images_down=stats.get("images", 0),
                )
            else:
                body = json.loads(_body_text(r) or "{}")
                if body.get("ok"):
                    return SyncResult.ok(0, 0, 0, 0)
                return SyncResult.fail(body.get("error") or "فشل")
        except Exception as e:
            return SyncResult.fail(str(e))

    def upload_to_server(self, on_progress: Optional[Callable[[str], None]] = None) -> SyncResult:
        try:
            if on_progress: on_progress("🔌 جاري الاتصال...")
            if not self.ping():
                return SyncResult.fail("تعذر الاتصال")
            if on_progress: on_progress("🔑 جاري التحقق...")
            if not self.authenticate():
                return SyncResult.fail("كلمة المرور خاطئة")

            if on_progress: on_progress("📦 تجهيز حزمة الرفع...")
            zip_path = self._sync.create_zip_package()
            payload = zip_path.read_bytes()

            if on_progress: on_progress("⬆️ رفع البيانات والصور...")
            r = self._http_post_bytes("/upload_zip", payload, timeout=600)
            sc = getattr(r, "status_code", getattr(r, "status", 0))
            try:
                zip_path.unlink()
            except Exception:
                pass
            if sc != 200:
                return SyncResult.fail("فشل الرفع")
            body = json.loads(_body_text(r) or "{}")
            if not body.get("ok"):
                return SyncResult.fail(body.get("error") or "فشل")
            stats = body.get("stats") or {}
            return SyncResult.ok(0, 0, stats.get("images", 0), 0)
        except Exception as e:
            return SyncResult.fail(str(e))


# ──────────────────────────────────────────────
# مساعدات صغيرة للتعامل مع الاستجابات
# ──────────────────────────────────────────────
class _Resp:
    """مغلِّف بسيط لاستجابة urllib لتحاكي requests."""
    def __init__(self, status: int, body: bytes, headers: dict):
        self.status = status
        self.status_code = status
        self._body = body
        self.headers = headers
    @property
    def content(self) -> bytes:
        return self._body
    @property
    def text(self) -> str:
        try:
            return self._body.decode("utf-8")
        except Exception:
            return ""

def _body_bytes(r) -> bytes:
    return getattr(r, "content", b"") or getattr(r, "_body", b"")

def _body_text(r) -> str:
    if hasattr(r, "text"):
        return r.text or ""
    return _body_bytes(r).decode("utf-8", errors="replace")

def _content_type(r) -> str:
    h = getattr(r, "headers", {}) or {}
    if hasattr(h, "get"):
        return h.get("Content-Type") or h.get("content-type") or ""
    return ""
