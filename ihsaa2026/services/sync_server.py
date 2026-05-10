"""خادم HTTP للمزامنة — متوافق تماماً مع SyncServer في Flutter.
نفس البورت 8080، ونفس المسارات: /ping /auth /metasync /upload_zip
ونفس صيغة الاستجابات (JSON أو ZIP حسب المسار).
"""
from __future__ import annotations
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

from ..config import SYNC_PORT, TMP_DIR
from .sync_service import SyncService


def _get_local_ip() -> str:
    """يفضّل عناوين 192.168.43.* (هوت سبوت أندرويد)، ثم أي IP غير loopback."""
    candidates: list[str] = []
    try:
        # طريقة 1: استعلام مرتبط — يعمل غالباً
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            candidates.append(s.getsockname()[0])
        except Exception:
            pass
        finally:
            s.close()
    except Exception:
        pass

    try:
        host = socket.gethostname()
        for info in socket.getaddrinfo(host, None, socket.AF_INET):
            ip = info[4][0]
            if ip and ip not in candidates:
                candidates.append(ip)
    except Exception:
        pass

    # فضّل 192.168.43.*
    for ip in candidates:
        if ip.startswith("192.168.43."):
            return ip
    for ip in candidates:
        if not ip.startswith("127."):
            return ip
    return "192.168.43.1"


class _Handler(BaseHTTPRequestHandler):
    server_version = "IhsaaSync/1.0"

    # تخفيض الضوضاء في stdout
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        pass

    # ──────────────────────────────────────────
    def _password(self) -> str:
        return getattr(self.server, "_password", "") or ""

    def _check_auth(self) -> bool:
        return self.headers.get("x-password", "") == self._password()

    def _send_json(self, code: int, body: dict) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_bytes(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return b""
        return self.rfile.read(length)

    # ──────────────────────────────────────────
    def do_GET(self) -> None:
        if self.path == "/ping":
            self._send_json(200, {"ok": True})
            return
        self._send_json(404, {"ok": False, "error": "غير موجود"})

    def do_POST(self) -> None:
        try:
            if self.path == "/auth":
                body = self._read_body()
                try:
                    payload = json.loads(body or b"{}")
                except Exception:
                    self._send_json(400, {"ok": False, "error": "طلب غير صالح"})
                    return
                if payload.get("password") == self._password():
                    self._send_json(200, {"ok": True})
                else:
                    self._send_json(403, {"ok": False, "error": "كلمة المرور خاطئة"})
                return

            if self.path == "/metasync":
                if not self._check_auth():
                    self._send_json(401, {"ok": False, "error": "غير مصرح"})
                    return
                try:
                    body = self._read_body()
                    payload = json.loads(body or b"{}")
                    client_summary = list(payload.get("summary") or [])
                    sync = SyncService()
                    diff = sync.compare_and_get_missing(client_summary)
                    zip_path: Path = sync.create_zip_for_items(
                        diff["records"], diff["images"]
                    )
                    data = zip_path.read_bytes()
                    try:
                        zip_path.unlink()
                    except Exception:
                        pass
                    self._send_bytes(200, data, "application/zip")
                except Exception as e:
                    self._send_json(500, {"ok": False, "error": f"فشل metasync: {e}"})
                return

            if self.path == "/upload_zip":
                if not self._check_auth():
                    self._send_json(401, {"ok": False, "error": "غير مصرح"})
                    return
                try:
                    raw = self._read_body()
                    if not raw:
                        self._send_json(400, {"ok": False, "error": "الملف فارغ"})
                        return
                    tmp = TMP_DIR / f"upload_{int(time.time()*1000)}.zip"
                    tmp.write_bytes(raw)
                    sync = SyncService()
                    stats = sync.process_received_zip(tmp)
                    try:
                        tmp.unlink()
                    except Exception:
                        pass
                    self._send_json(200, {"ok": True, "stats": stats})
                except Exception as e:
                    self._send_json(500, {"ok": False, "error": f"فشل معالجة الرفع: {e}"})
                return

            self._send_json(404, {"ok": False, "error": "غير موجود"})
        except Exception as e:
            try:
                self._send_json(500, {"ok": False, "error": str(e)})
            except Exception:
                pass


class SyncServer:
    """Singleton — يوفر start()/stop() مماثلة لتلك في Dart."""

    _instance: "SyncServer" = None  # type: ignore

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_inited"):
            self._http: Optional[ThreadingHTTPServer] = None
            self._thread: Optional[threading.Thread] = None
            self._local_ip: Optional[str] = None
            self._inited = True

    @property
    def is_running(self) -> bool:
        return self._http is not None

    @property
    def local_ip(self) -> Optional[str]:
        return self._local_ip

    def start(self, password: str) -> Optional[str]:
        if self.is_running:
            return self._local_ip
        try:
            httpd = ThreadingHTTPServer(("0.0.0.0", SYNC_PORT), _Handler)
            httpd._password = password  # type: ignore[attr-defined]
            self._http = httpd
            self._thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            self._thread.start()
            self._local_ip = _get_local_ip()
            return self._local_ip
        except Exception:
            self._http = None
            self._thread = None
            self._local_ip = None
            return None

    def stop(self) -> None:
        if self._http:
            try:
                self._http.shutdown()
                self._http.server_close()
            except Exception:
                pass
        self._http = None
        self._thread = None
        self._local_ip = None
