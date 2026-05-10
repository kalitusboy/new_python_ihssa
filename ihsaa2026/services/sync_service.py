"""خدمة المزامنة — مطابقة لـ lib/services/sync_service.dart.
نفس بنية الحزم (data.json / diff.json + الصور)، نفس مفاتيح الدمج،
نفس قواعد فض النزاع، حتى تتوافق 100% مع تطبيق Flutter على الهواتف.
"""
from __future__ import annotations
import io
import json
import os
import time
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple

from ..config import IMAGES_DIR, TMP_DIR, BACKUPS_DIR, DB_PATH
from ..models.beneficiary import Beneficiary
from .database_service import DatabaseService


def _key(r: dict) -> str:
    fn = (r.get("first_name") or "").strip().lower()
    ln = (r.get("last_name") or "").strip().lower()
    bd = (r.get("birth_date") or "").strip()
    ad = (r.get("address") or "").strip().lower()
    return f"{fn}|{ln}|{bd}|{ad}"


def _resolve(local: dict, remote: dict) -> dict:
    """نفس قواعد فض النزاع في sync_service.dart."""
    ld = int(local.get("done") or 0)
    rd = int(remote.get("done") or 0)
    if ld == 1 and rd == 0:
        return {**local, "id": local.get("id")}
    if rd == 1 and ld == 0:
        return {**remote, "id": local.get("id")}
    lt = int(local.get("updated_at") or 0)
    rt = int(remote.get("updated_at") or 0)
    winner = remote if rt > lt else local
    return {**winner, "id": local.get("id")}


class SyncService:
    """نقطة مركزية للمزامنة — Singleton."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.db = DatabaseService()

    # ──────────────────────────────────────────
    def get_all_records(self) -> List[dict]:
        rows = self.db._conn().execute("SELECT * FROM beneficiaries").fetchall()
        return [dict(r) for r in rows]

    def get_summary(self) -> List[dict]:
        rows = self.db._conn().execute("""
            SELECT id, first_name, last_name, birth_date, address,
                   updated_at, done, image_file_name FROM beneficiaries
        """).fetchall()
        return [{
            "first_name": r["first_name"],
            "last_name": r["last_name"],
            "birth_date": r["birth_date"],
            "address": r["address"],
            "updated_at": r["updated_at"],
            "done": r["done"],
            "image_file_name": r["image_file_name"],
        } for r in rows]

    # ──────────────────────────────────────────
    def merge_records(self, incoming: List[dict]) -> Dict[str, int]:
        added = 0
        updated = 0
        local_list = self.get_all_records()
        local_map: Dict[str, dict] = {_key(r): dict(r) for r in local_list}

        conn = self.db._conn()
        for remote in incoming:
            k = _key(remote)
            if k not in local_map:
                to_insert = dict(remote)
                to_insert.pop("id", None)
                img = (to_insert.get("image_file_name") or "")
                if img:
                    to_insert["image_path"] = str(IMAGES_DIR / img)
                cols = list(to_insert.keys())
                ph = ", ".join(["?"] * len(cols))
                conn.execute(
                    f"INSERT INTO beneficiaries ({', '.join(cols)}) VALUES ({ph})",
                    [to_insert[c] for c in cols],
                )
                added += 1
            else:
                merged = _resolve(local_map[k], remote)
                img = (merged.get("image_file_name") or "")
                if img:
                    merged["image_path"] = str(IMAGES_DIR / img)
                id_ = merged.pop("id", None)
                sets = ", ".join([f"{k2} = ?" for k2 in merged.keys()])
                conn.execute(
                    f"UPDATE beneficiaries SET {sets} WHERE id = ?",
                    list(merged.values()) + [id_],
                )
                updated += 1
        conn.commit()
        return {"added": added, "updated": updated}

    # ──────────────────────────────────────────
    def compare_and_get_missing(self, remote_summary: List[dict]) -> dict:
        """يقارن ملخص العميل مع البيانات المحلية ويعيد ما هو مفقود/أحدث محلياً."""
        local_records = self.get_all_records()
        local_map: Dict[str, dict] = {_key(r): r for r in local_records}

        # خريطة سريعة للملخص البعيد
        remote_map: Dict[str, dict] = {}
        for r in remote_summary:
            remote_map[_key(r)] = r

        missing: List[dict] = []
        images: set = set()

        for k, local in local_map.items():
            remote = remote_map.get(k)
            if remote is None:
                missing.append(local)
                img = local.get("image_file_name")
                if img:
                    images.add(img)
            else:
                lt = int(local.get("updated_at") or 0)
                rt = int(remote.get("updated_at") or 0)
                if lt > rt:
                    missing.append(local)
                    img = local.get("image_file_name")
                    if img:
                        images.add(img)
        return {"records": missing, "images": list(images)}

    # ──────────────────────────────────────────
    def create_zip_for_items(self, records: List[dict], image_names: List[str]) -> Path:
        """ينشئ diff.zip لإرساله للعميل."""
        out = TMP_DIR / f"diff_{int(time.time()*1000)}.zip"
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            payload = json.dumps({"beneficiaries": records}, ensure_ascii=False)
            z.writestr("diff.json", payload.encode("utf-8"))
            for name in image_names:
                p = IMAGES_DIR / name
                if not p.exists():
                    # ابحث عن ملف بنفس basename بأي امتداد
                    base = Path(name).stem
                    candidate = next(
                        (f for f in IMAGES_DIR.iterdir()
                         if f.is_file() and f.stem == base),
                        None,
                    )
                    if candidate:
                        p = candidate
                if p.exists():
                    z.write(p, arcname=p.name)
        return out

    def create_zip_package(self) -> Path:
        """ينشئ data.zip كامل (لرفعه إلى المدير)."""
        out = TMP_DIR / f"full_{int(time.time()*1000)}.zip"
        records = self.get_all_records()
        existing = {f.name for f in IMAGES_DIR.iterdir()
                    if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png")}
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            payload = json.dumps({"beneficiaries": records}, ensure_ascii=False)
            z.writestr("data.json", payload.encode("utf-8"))
            added = set()
            for r in records:
                img = (r.get("image_file_name") or "")
                if not img:
                    continue
                matched = None
                if img in existing:
                    matched = img
                else:
                    base = Path(img).stem
                    matched = next((f for f in existing if Path(f).stem == base), None)
                if matched and matched not in added:
                    p = IMAGES_DIR / matched
                    if p.exists():
                        z.write(p, arcname=matched)
                        added.add(matched)
        return out

    # ──────────────────────────────────────────
    def process_received_zip(self, zip_path: Path) -> Dict[str, int]:
        """يستقبل data.zip أو diff.zip ويدمج محتواه."""
        added = 0
        updated = 0
        images_copied = 0
        json_content: str | None = None

        with zipfile.ZipFile(zip_path, "r") as z:
            for info in z.infolist():
                if info.is_dir():
                    continue
                name = Path(info.filename).name  # احذف أي مسار متضمن
                lower = name.lower()
                if name in ("data.json", "diff.json"):
                    json_content = z.read(info).decode("utf-8")
                elif lower.endswith((".jpg", ".jpeg", ".png")):
                    target = IMAGES_DIR / name
                    target.write_bytes(z.read(info))
                    images_copied += 1

        if json_content:
            data = json.loads(json_content)
            records: List[dict] = list(data.get("beneficiaries") or [])
            # تصحيح أسماء الصور (في حال اختلاف الامتدادات)
            for rec in records:
                img = rec.get("image_file_name") or ""
                if img:
                    candidate = IMAGES_DIR / img
                    if not candidate.exists():
                        base = Path(img).stem
                        found = next(
                            (f for f in IMAGES_DIR.iterdir()
                             if f.is_file() and f.stem == base),
                            None,
                        )
                        if found:
                            rec["image_file_name"] = found.name
            stats = self.merge_records(records)
            added = stats["added"]
            updated = stats["updated"]

        return {"added": added, "updated": updated, "images": images_copied}

    # ──────────────────────────────────────────
    def backup(self) -> Path | None:
        try:
            if DB_PATH.exists():
                ts = time.strftime("%Y-%m-%d_%H-%M-%S")
                dst = BACKUPS_DIR / f"backup_{ts}.db"
                dst.write_bytes(DB_PATH.read_bytes())
                return dst
        except Exception:
            return None
        return None
