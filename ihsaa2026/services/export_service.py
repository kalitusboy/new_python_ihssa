"""خدمة التصدير — مكافئة لـ lib/services/export_service.dart."""
from __future__ import annotations
import time
import zipfile
from pathlib import Path
from typing import List

from ..config import DOCS_DIR, IMAGES_DIR
from .database_service import DatabaseService


class ExportService:
    def __init__(self):
        self.db = DatabaseService()

    # ── تصدير JSON ────────────────────────────
    def export_full_database(self) -> Path:
        ts = int(time.time() * 1000)
        out = DOCS_DIR / f"ihsa_backup_{ts}.json"
        out.write_text(self.db.export_to_json(), encoding="utf-8")
        return out

    # ── تصدير الصور ZIP ───────────────────────
    def export_images_as_zip(self) -> Path:
        items = self.db.get_completed_beneficiaries()
        with_images = [b for b in items if b.image_path and Path(b.image_path).exists()]
        if not with_images:
            raise Exception("لا توجد صور للتصدير")

        ts = int(time.time() * 1000)
        out = DOCS_DIR / f"ihsa_images_{ts}.zip"
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for b in with_images:
                p = Path(b.image_path)
                if p.exists():
                    name = b.image_file_name or p.name
                    z.write(p, arcname=name)
        return out

    # ── دمج قواعد البيانات من JSON ────────────
    def merge_databases(self, files: List[Path]) -> dict:
        files = [Path(f) for f in files if Path(f).exists()]
        if not files:
            return {"imported": 0, "updated": 0, "skipped": 0}
        stats = self.db.merge_from_json_files(files)
        return {
            "imported": stats.get("imported", 0),
            "updated": 0,
            "skipped": stats.get("duplicates", 0),
        }

    # ── تصدير صور برنامج محدد ZIP ────────────
    def export_program_images_zip(self, program: str) -> Path:
        """تصدير صور برنامج واحد كـ ZIP — مطابق لـ advanced_report_service.dart."""
        from ..services.word_report_service import WordReportService
        return WordReportService().export_program_images_zip(program)

    # ── استيراد JSON ──────────────────────────
    def import_from_json(self, file: Path) -> dict:
        """استيراد بيانات من ملف JSON."""
        return self.merge_databases([Path(file)])

