"""إعدادات عامة، مسارات الملفات، الألوان."""
from __future__ import annotations
import sys
import json
from pathlib import Path

# ──────────────────────────────────────────────
# المسارات (متوافقة مع تطبيق Flutter)
# على Windows : C:\Users\<user>\Documents\ihsaa2026
# على Linux   : ~/Documents/ihsaa2026
# على macOS   : ~/Documents/ihsaa2026
# ──────────────────────────────────────────────
def _documents_dir() -> Path:
    home = Path.home()
    if sys.platform == "win32":
        # نحاول أولاً Documents الحقيقية عبر السجل، وإلا fallback
        try:
            import ctypes
            from ctypes import wintypes
            CSIDL_PERSONAL = 5  # My Documents
            SHGFP_TYPE_CURRENT = 0
            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(
                None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf
            )
            return Path(buf.value)
        except Exception:
            return home / "Documents"
    return home / "Documents"


DOCS_DIR: Path = _documents_dir() / "ihsaa2026"
DOCS_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH: Path = DOCS_DIR / "ihsa_2026.db"
IMAGES_DIR: Path = DOCS_DIR / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
BACKUPS_DIR: Path = DOCS_DIR / "backups"
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
TMP_DIR: Path = DOCS_DIR / "tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)

# ملف الإعدادات (يحاكي SharedPreferences على Flutter)
PREFS_PATH: Path = DOCS_DIR / "settings.json"

# ──────────────────────────────────────────────
# الألوان (مطابقة لـ Flutter)
# ──────────────────────────────────────────────
PRIMARY = "#0D47A1"
PRIMARY_DARK = "#0A3880"
BG = "#F1F5F9"
TEXT = "#0F172A"
MUTED = "#64748B"
BORDER = "#CBD5E1"
SUCCESS = "#15803D"
DANGER = "#B91C1C"
WARN = "#B45309"
ACCENT_GREEN = "#16A34A"

STATUSES = [
    "في طور الانجاز",
    "على مستوى الاعمدة",
    "منتهية غير مشغولة",
    "منتهية ومشغولة",
]

STATUS_COLORS = {
    "في طور الانجاز": "#F59E0B",
    "على مستوى الاعمدة": "#2563EB",
    "منتهية غير مشغولة": "#15803D",
    "منتهية ومشغولة": "#00897B",
}

SYNC_PORT = 8080  # نفس البورت الذي يستعمله تطبيق Flutter

# ──────────────────────────────────────────────
# مسار الموارد (الخطوط)
# ──────────────────────────────────────────────
def assets_dir() -> Path:
    """يعيد مسار assets سواء كنا داخل PyInstaller أو من المصدر."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "assets"
    return Path(__file__).resolve().parent.parent / "assets"


# ──────────────────────────────────────────────
# Prefs (محاكاة SharedPreferences)
# ──────────────────────────────────────────────
class Prefs:
    _data: dict = {}
    _loaded: bool = False

    @classmethod
    def load(cls) -> None:
        if cls._loaded:
            return
        if PREFS_PATH.exists():
            try:
                cls._data = json.loads(PREFS_PATH.read_text(encoding="utf-8"))
            except Exception:
                cls._data = {}
        cls._loaded = True

    @classmethod
    def save(cls) -> None:
        try:
            PREFS_PATH.write_text(
                json.dumps(cls._data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    @classmethod
    def get(cls, key: str, default=None):
        cls.load()
        return cls._data.get(key, default)

    @classmethod
    def set(cls, key: str, value) -> None:
        cls.load()
        cls._data[key] = value
        cls.save()
