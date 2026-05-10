"""شاشة دمج بيانات الأعوان (المدير) — مطابقة لـ admin_merge_screen.dart.

المنطق مطابق 100% لنسخة Flutter:
  1. اختيار ملفات JSON من الأعوان
  2. اختيار ملفات ZIP التي تحتوي صور الأعوان
  3. فك ضغط الصور → بناء فهرس → ربطها بالمستفيدين
  4. دمج البيانات بنفس قواعد فض النزاع (done=1 لا يُستبدل بـ done=0)
  5. حفظ ملف JSON موحَّد في مجلد المستندات
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import time
import zipfile
from pathlib import Path
from typing import List

from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QFileDialog, QGroupBox, QHBoxLayout, QLabel,
    QMessageBox, QProgressBar, QPushButton, QScrollArea,
    QSizePolicy, QTextEdit, QVBoxLayout, QWidget,
)
from PyQt6.QtGui import QFont

from ..config import DOCS_DIR, IMAGES_DIR
from ..services.database_service import DatabaseService
from ..widgets.style import PRIMARY, SUCCESS, WARNING, DANGER, BG_LIGHT


# ──────────────────────────────────────────────────────────────────
# Worker Thread
# ──────────────────────────────────────────────────────────────────
class _MergeWorker(QThread):
    log_msg  = pyqtSignal(str)      # رسالة سجل
    finished = pyqtSignal(str)      # مسار الملف الناتج
    error    = pyqtSignal(str)      # رسالة خطأ

    def __init__(self, json_files: List[Path], zip_files: List[Path]):
        super().__init__()
        self.json_files = json_files
        self.zip_files  = zip_files
        self.db = DatabaseService()

    def run(self):
        try:
            self._merge()
        except Exception as e:
            import traceback
            self.error.emit(f"❌ خطأ: {e}\n{traceback.format_exc()}")

    def _merge(self):
        log = self.log_msg.emit

        # ── 1. مجلد مؤقت لفك ضغط الصور ───────────────────────────
        tmp_dir = Path(tempfile.mkdtemp(prefix="ihsaa_merge_"))
        extract_dir = tmp_dir / f"images_{int(time.time())}"
        extract_dir.mkdir(parents=True, exist_ok=True)

        try:
            # ── 2. فك ضغط جميع ملفات ZIP ──────────────────────────
            images_count = 0
            for zf in self.zip_files:
                log(f"📦 فك ضغط: {zf.name}")
                with zipfile.ZipFile(zf, "r") as z:
                    for member in z.infolist():
                        if not member.is_dir():
                            out = extract_dir / Path(member.filename).name
                            out.parent.mkdir(parents=True, exist_ok=True)
                            with z.open(member) as src, open(out, "wb") as dst:
                                shutil.copyfileobj(src, dst)
                            images_count += 1
            log(f"✅ تم فك ضغط {images_count} ملف")

            # ── 3. بناء فهرس الصور ─────────────────────────────────
            image_index: dict[str, Path] = {}
            for f in extract_dir.rglob("*"):
                if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png"):
                    image_index[f.name] = f
                    image_index[f.stem]  = f   # بدون الامتداد أيضاً
            log(f"✅ تم فهرسة {len(image_index) // 2} صورة فريدة")

            # ── 4. مجلد الصور الدائم (نفس مسار المزامنة) ──────────
            IMAGES_DIR.mkdir(parents=True, exist_ok=True)
            log(f"📁 مجلد الصور الدائم: {IMAGES_DIR}")

            # ── 5. دمج ملفات JSON ──────────────────────────────────
            merged: dict[str, dict] = {}
            for jf in self.json_files:
                log(f"📄 قراءة JSON: {jf.name}")
                try:
                    data = json.loads(jf.read_text(encoding="utf-8"))
                    for b in (data.get("beneficiaries") or []):
                        fn  = (b.get("first_name") or "").strip()
                        ln  = (b.get("last_name")  or "").strip()
                        bd  = (b.get("birth_date") or "").strip()
                        ad  = (b.get("address")    or "").strip()
                        key = f"{fn}|{ln}|{bd}|{ad}"

                        if key not in merged:
                            merged[key] = dict(b)
                        else:
                            # نفس قاعدة Flutter: done=1 لا يُستبدل بـ done=0
                            existing_done = int(merged[key].get("done") or 0)
                            new_done      = int(b.get("done") or 0)
                            if existing_done == 1 and new_done == 0:
                                continue  # نبقي النسخة المكتملة
                            # نأخذ الأحدث updated_at
                            lt = int(merged[key].get("updated_at") or 0)
                            rt = int(b.get("updated_at") or 0)
                            if rt > lt:
                                merged[key] = dict(b)
                except Exception as e:
                    log(f"⚠️ فشل قراءة {jf.name}: {e}")
            log(f"👥 إجمالي المستفيدين بعد الدمج: {len(merged)}")

            # ── 6. ربط الصور بالمستفيدين ───────────────────────────
            updated_count  = 0
            not_found_count = 0
            for key, b in merged.items():
                img_name = (b.get("image_file_name") or "").strip()
                if not img_name:
                    continue
                # إذا كان المسار الحالي موجوداً → لا نغيره
                current = (b.get("image_path") or "").strip()
                if current and Path(current).exists():
                    continue
                # ابحث في الفهرس
                src_path = image_index.get(img_name) or image_index.get(Path(img_name).stem)
                if src_path and src_path.exists():
                    try:
                        safe_name = f"{int(time.time() * 1000)}_{img_name}"
                        dst = IMAGES_DIR / safe_name
                        shutil.copy2(src_path, dst)
                        b["image_path"]      = str(dst)
                        b["image_file_name"] = safe_name
                        updated_count += 1
                        log(f"✅ تم نقل صورة: {b.get('full_name') or img_name}")
                    except Exception as e:
                        log(f"⚠️ فشل نقل {img_name}: {e}")
                else:
                    not_found_count += 1
                    log(f"❌ لم يُعثر على صورة: {img_name}")
            log(f"📸 تم نقل {updated_count} صورة، لم يُعثر على {not_found_count} صورة")

            # ── 7. حفظ JSON الناتج ─────────────────────────────────
            DOCS_DIR.mkdir(parents=True, exist_ok=True)
            ts = int(time.time())
            out_path = DOCS_DIR / f"merged_database_{ts}.json"
            out_path.write_text(
                json.dumps(
                    {"version": "1.0", "beneficiaries": list(merged.values())},
                    ensure_ascii=False, indent=2
                ),
                encoding="utf-8"
            )
            log(f"💾 تم حفظ الملف: {out_path}")
            log("✅ انتهت العملية بنجاح!")
            self.finished.emit(str(out_path))

        finally:
            # تنظيف المجلد المؤقت
            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                log("🗑️ تم حذف المجلد المؤقت")
            except Exception:
                pass


# ──────────────────────────────────────────────────────────────────
# الشاشة الرئيسية
# ──────────────────────────────────────────────────────────────────
class AdminMergeScreen(QWidget):
    """شاشة دمج بيانات الأعوان — مطابقة لـ AdminMergeScreen في Flutter."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._json_files: List[Path] = []
        self._zip_files:  List[Path] = []
        self._worker: _MergeWorker | None = None
        self._build_ui()

    # ── بناء الواجهة ───────────────────────────────────────────────
    def _build_ui(self):
        self.setLayoutDirection(Qt.RightToLeft)
        self.setStyleSheet(f"background:{BG_LIGHT};")
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # ── عنوان ─────────────────────────────────────────────────
        title = QLabel("👥 دمج بيانات الأعوان (المدير)")
        title.setFont(QFont("Cairo", 15, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"color:{PRIMARY}; padding:8px;")
        root.addWidget(title)

        # ── بطاقة الأزرار ─────────────────────────────────────────
        btn_group = QGroupBox()
        btn_group.setStyleSheet("""
            QGroupBox { background:white; border-radius:12px;
                        border:1px solid #E2E8F0; padding:12px; }
        """)
        btn_lay = QVBoxLayout(btn_group)
        btn_lay.setSpacing(10)

        self._btn_json = self._make_btn(
            "📂 اختر ملفات JSON  (0)", PRIMARY, self._pick_json)
        self._btn_zip = self._make_btn(
            "📦 اختر ملفات ZIP  (0)", WARNING, self._pick_zip)
        self._btn_start = self._make_btn(
            "🔀 بدء الدمج والصور", SUCCESS, self._start_merge)

        btn_lay.addWidget(self._btn_json)
        btn_lay.addWidget(self._btn_zip)
        btn_lay.addWidget(self._btn_start)
        root.addWidget(btn_group)

        # ── شريط التقدم ───────────────────────────────────────────
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)   # indeterminate
        self._progress.setVisible(False)
        self._progress.setFixedHeight(6)
        self._progress.setStyleSheet(
            f"QProgressBar::chunk {{ background:{SUCCESS}; }}"
            "QProgressBar { border:none; background:#E2E8F0; }"
        )
        root.addWidget(self._progress)

        # ── منطقة السجل ───────────────────────────────────────────
        log_group = QGroupBox("سجل العمليات:")
        log_group.setStyleSheet("""
            QGroupBox { background:white; border-radius:12px;
                        border:1px solid #E2E8F0; padding:8px;
                        font-weight:bold; font-size:13px; }
        """)
        log_lay = QVBoxLayout(log_group)
        self._log_box = QTextEdit()
        self._log_box.setReadOnly(True)
        self._log_box.setStyleSheet(
            "font-family:Consolas,monospace; font-size:11px; background:#F8FAFC;"
            "border:none; border-radius:8px;"
        )
        self._log_box.setPlaceholderText(
            "⚠️ لم يتم تنفيذ أي عملية بعد.\n\n"
            "الخطوات:\n"
            "  1. اختر ملفات JSON من أجهزة الأعوان\n"
            "  2. اختر ملفات ZIP التي تحتوي الصور\n"
            "  3. اضغط «بدء الدمج والصور»"
        )
        log_lay.addWidget(self._log_box)
        root.addWidget(log_group, stretch=1)

    @staticmethod
    def _make_btn(text: str, color: str, slot) -> QPushButton:
        btn = QPushButton(text)
        btn.setFont(QFont("Cairo", 11))
        btn.setMinimumHeight(44)
        btn.setStyleSheet(f"""
            QPushButton {{
                background:{color}; color:white; border-radius:10px;
                padding:6px 12px;
            }}
            QPushButton:hover {{ opacity:0.9; }}
            QPushButton:disabled {{ background:#94A3B8; }}
        """)
        btn.clicked.connect(slot)
        return btn

    def _log(self, msg: str):
        self._log_box.append(msg)
        # مرر لآخر سطر
        sb = self._log_box.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ── اختيار ملفات ──────────────────────────────────────────────
    def _pick_json(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "اختر ملفات JSON", str(DOCS_DIR),
            "JSON files (*.json)"
        )
        if files:
            self._json_files = [Path(f) for f in files]
            self._btn_json.setText(
                f"📂 ملفات JSON  ({len(self._json_files)} مختار)")
            self._log(f"✅ تم اختيار {len(self._json_files)} ملف JSON")

    def _pick_zip(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "اختر ملفات ZIP للصور", str(DOCS_DIR),
            "ZIP files (*.zip)"
        )
        if files:
            self._zip_files = [Path(f) for f in files]
            self._btn_zip.setText(
                f"📦 ملفات ZIP  ({len(self._zip_files)} مختار)")
            self._log(f"✅ تم اختيار {len(self._zip_files)} ملف ZIP")

    # ── بدء الدمج ─────────────────────────────────────────────────
    def _start_merge(self):
        if not self._json_files:
            self._log("❌ الرجاء اختيار ملفات JSON أولاً")
            return
        if not self._zip_files:
            self._log("❌ الرجاء اختيار ملفات ZIP أولاً")
            return

        self._log_box.clear()
        self._log("🚀 بدء عملية الدمج...")
        self._set_busy(True)

        self._worker = _MergeWorker(self._json_files, self._zip_files)
        self._worker.log_msg.connect(self._log)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _set_busy(self, busy: bool):
        self._btn_json.setEnabled(not busy)
        self._btn_zip.setEnabled(not busy)
        self._btn_start.setEnabled(not busy)
        self._progress.setVisible(busy)

    def _on_done(self, out_path: str):
        self._set_busy(False)
        QMessageBox.information(
            self, "✅ تم بنجاح",
            f"تم الدمج بنجاح!\n\nالملف الناتج:\n{out_path}"
        )

    def _on_error(self, msg: str):
        self._set_busy(False)
        self._log(msg)
        QMessageBox.critical(self, "❌ خطأ", msg[:400])
