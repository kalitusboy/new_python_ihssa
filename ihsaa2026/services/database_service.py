"""خدمة قاعدة البيانات — مطابقة لـ lib/services/database_service.dart.
تستخدم نفس مسار الملف ونفس البنية حتى تبقى المزامنة مع Flutter متوافقة 100%.
"""
from __future__ import annotations
import os
import sqlite3
import json
import threading
import time
from pathlib import Path
from typing import Iterable, List, Optional

from ..config import DB_PATH
from ..models.beneficiary import Beneficiary


_TABLE = "beneficiaries"
_INDEXES = [
    f"CREATE INDEX IF NOT EXISTS idx_done ON {_TABLE}(done)",
    f"CREATE INDEX IF NOT EXISTS idx_program ON {_TABLE}(program)",
    f"CREATE INDEX IF NOT EXISTS idx_status ON {_TABLE}(status)",
    f"CREATE INDEX IF NOT EXISTS idx_address ON {_TABLE}(address)",
    f"CREATE INDEX IF NOT EXISTS idx_done_status ON {_TABLE}(done, status)",
    f"CREATE INDEX IF NOT EXISTS idx_done_program ON {_TABLE}(done, program)",
    f"CREATE INDEX IF NOT EXISTS idx_image ON {_TABLE}(image_file_name)",
    f"CREATE INDEX IF NOT EXISTS idx_first_name ON {_TABLE}(first_name COLLATE NOCASE)",
    f"CREATE INDEX IF NOT EXISTS idx_last_name ON {_TABLE}(last_name COLLATE NOCASE)",
    f"CREATE INDEX IF NOT EXISTS idx_full_name ON {_TABLE}(full_name COLLATE NOCASE)",
    f"CREATE INDEX IF NOT EXISTS idx_done_address ON {_TABLE}(done, address)",
    f"CREATE INDEX IF NOT EXISTS idx_done_updated_at ON {_TABLE}(done, updated_at DESC)",
    f"CREATE INDEX IF NOT EXISTS idx_lookup_identity ON {_TABLE}(first_name, last_name, birth_date, address)",
]


class DatabaseService:
    """Singleton — قابل للاستخدام من أي خيط."""

    _instance: "DatabaseService" = None  # type: ignore
    _lock = threading.RLock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_done = False
            return cls._instance

    def __init__(self):
        if getattr(self, "_init_done", False):
            return
        self._local = threading.local()
        self._ensure_schema()
        self._init_done = True

    # ──────────────────────────────────────────
    def _conn(self) -> sqlite3.Connection:
        c = getattr(self._local, "conn", None)
        if c is None:
            c = sqlite3.connect(str(DB_PATH), timeout=30, check_same_thread=False)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=NORMAL")
            c.execute("PRAGMA cache_size=-32000")
            c.execute("PRAGMA temp_store=MEMORY")
            self._local.conn = c
        return c

    def _ensure_schema(self) -> None:
        conn = self._conn()
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {_TABLE}(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                full_name TEXT,
                birth_date TEXT,
                birth_place TEXT,
                address TEXT,
                program TEXT DEFAULT 'عام',
                done INTEGER DEFAULT 0,
                electricity INTEGER DEFAULT 0,
                gas INTEGER DEFAULT 0,
                water INTEGER DEFAULT 0,
                sewage INTEGER DEFAULT 0,
                status TEXT DEFAULT 'في طور الانجاز',
                image_path TEXT,
                image_file_name TEXT,
                created_at INTEGER,
                updated_at INTEGER
            )
        """)
        for idx in _INDEXES:
            conn.execute(idx)
        conn.commit()

    # ──────────────────────────────────────────
    @staticmethod
    def _now_ms() -> int:
        return int(time.time() * 1000)

    # ──────────────────────────────────────────
    def get_all_beneficiaries(self) -> List[Beneficiary]:
        rows = self._conn().execute(f"SELECT * FROM {_TABLE} ORDER BY id DESC").fetchall()
        return [Beneficiary.from_row(r) for r in rows]

    def get_pending_beneficiaries(self) -> List[Beneficiary]:
        return self.search_beneficiaries(done_value=0, limit=1_000_000)

    def get_completed_beneficiaries(self) -> List[Beneficiary]:
        return self.search_beneficiaries(done_value=1, limit=1_000_000)

    def get_distinct_addresses(self) -> List[str]:
        rows = self._conn().execute(
            f"""SELECT DISTINCT address FROM {_TABLE}
                WHERE address IS NOT NULL AND TRIM(address) <> ''
                ORDER BY address COLLATE NOCASE ASC"""
        ).fetchall()
        return [(r["address"] or "").strip() for r in rows if (r["address"] or "").strip()]

    def search_beneficiaries(
        self,
        done_value: int,
        query: str = "",
        address: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Beneficiary]:
        wheres = ["done = ?"]
        args: list = [done_value]
        if address and address.strip():
            wheres.append("address = ?")
            args.append(address.strip())
        q = (query or "").strip()
        if q:
            like = f"{q.replace('%', '')}%"
            wheres.append("""(
                first_name LIKE ? COLLATE NOCASE OR
                last_name  LIKE ? COLLATE NOCASE OR
                full_name  LIKE ? COLLATE NOCASE OR
                address    LIKE ? COLLATE NOCASE OR
                program    LIKE ? COLLATE NOCASE
            )""")
            args.extend([like] * 5)
        order = "updated_at DESC, id DESC" if done_value == 1 else "id DESC"
        sql = f"SELECT * FROM {_TABLE} WHERE {' AND '.join(wheres)} ORDER BY {order} LIMIT ? OFFSET ?"
        args.extend([limit, offset])
        rows = self._conn().execute(sql, args).fetchall()
        return [Beneficiary.from_row(r) for r in rows]

    def get_beneficiary(self, id_: int) -> Optional[Beneficiary]:
        r = self._conn().execute(f"SELECT * FROM {_TABLE} WHERE id = ?", (id_,)).fetchone()
        return Beneficiary.from_row(r) if r else None

    # ──────────────────────────────────────────
    def insert_beneficiary(self, b: Beneficiary) -> int:
        m = b.to_map()
        now = self._now_ms()
        m["created_at"] = now
        m["updated_at"] = now
        m.pop("id", None)
        cols = ", ".join(m.keys())
        ph = ", ".join(["?"] * len(m))
        cur = self._conn().execute(
            f"INSERT INTO {_TABLE} ({cols}) VALUES ({ph})", list(m.values())
        )
        self._conn().commit()
        return cur.lastrowid or 0

    def insert_beneficiaries(self, items: Iterable[Beneficiary]) -> None:
        conn = self._conn()
        now = self._now_ms()
        rows = []
        for b in items:
            m = b.to_map()
            m["created_at"] = now
            m["updated_at"] = now
            m.pop("id", None)
            rows.append(m)
        if not rows:
            return
        cols = list(rows[0].keys())
        ph = ", ".join(["?"] * len(cols))
        sql = f"INSERT INTO {_TABLE} ({', '.join(cols)}) VALUES ({ph})"
        conn.executemany(sql, [[r[c] for c in cols] for r in rows])
        conn.commit()

    def update_beneficiary(self, b: Beneficiary) -> int:
        m = b.to_map()
        m["updated_at"] = self._now_ms()
        id_ = m.pop("id", None)
        if id_ is None:
            return 0
        sets = ", ".join([f"{k} = ?" for k in m.keys()])
        cur = self._conn().execute(f"UPDATE {_TABLE} SET {sets} WHERE id = ?", list(m.values()) + [id_])
        self._conn().commit()
        return cur.rowcount

    def update_beneficiary_from_map(self, id_: int, new_data: dict) -> None:
        new_data = dict(new_data)
        new_data.pop("created_at", None)
        new_data["updated_at"] = self._now_ms()
        sets = ", ".join([f"{k} = ?" for k in new_data.keys()])
        self._conn().execute(f"UPDATE {_TABLE} SET {sets} WHERE id = ?", list(new_data.values()) + [id_])
        self._conn().commit()

    def delete_beneficiary(self, id_: int) -> int:
        b = self.get_beneficiary(id_)
        if b and b.image_path:
            try:
                p = Path(b.image_path)
                if p.exists():
                    p.unlink()
            except Exception:
                pass
        cur = self._conn().execute(f"DELETE FROM {_TABLE} WHERE id = ?", (id_,))
        self._conn().commit()
        return cur.rowcount

    # ──────────────────────────────────────────
    def find_beneficiary_by_key(
        self,
        first_name: str,
        last_name: str,
        birth_date: Optional[str],
        address: Optional[str],
    ) -> Optional[Beneficiary]:
        r = self._conn().execute(
            f"SELECT * FROM {_TABLE} WHERE first_name = ? AND last_name = ? AND birth_date = ? AND address = ? LIMIT 1",
            (first_name, last_name, birth_date or "", address or ""),
        ).fetchone()
        return Beneficiary.from_row(r) if r else None

    def beneficiary_exists(
        self, first_name: str, last_name: str, birth_date: Optional[str], address: Optional[str]
    ) -> bool:
        return self.find_beneficiary_by_key(first_name, last_name, birth_date, address) is not None

    # ──────────────────────────────────────────
    def get_dashboard_stats(self) -> dict:
        row = self._conn().execute(f"""
            SELECT
                COUNT(*)                                                   AS total,
                SUM(CASE WHEN done=1 THEN 1 ELSE 0 END)                   AS done,
                SUM(CASE WHEN done=0 THEN 1 ELSE 0 END)                   AS pending,
                SUM(CASE WHEN done=1 AND image_file_name IS NOT NULL
                         AND image_file_name != '' THEN 1 ELSE 0 END)     AS with_image,
                SUM(CASE WHEN done=1 AND (image_file_name IS NULL
                         OR image_file_name='') THEN 1 ELSE 0 END)        AS without_image,
                SUM(CASE WHEN done=1 AND status='منتهية ومشغولة' THEN 1 ELSE 0 END) AS occupied
            FROM {_TABLE}
        """).fetchone()
        return {k: (row[k] or 0) for k in row.keys()}

    def get_advanced_stats(self) -> dict:
        conn = self._conn()
        totals = dict(conn.execute(f"""
            SELECT
                COUNT(*)                                                   AS total,
                SUM(CASE WHEN done=1 THEN 1 ELSE 0 END)                   AS done,
                SUM(CASE WHEN done=1 AND image_file_name IS NOT NULL
                         AND image_file_name != '' THEN 1 ELSE 0 END)     AS with_image,
                SUM(CASE WHEN done=1 AND (image_file_name IS NULL
                         OR image_file_name='') THEN 1 ELSE 0 END)        AS without_image,
                SUM(CASE WHEN done=1 AND electricity=1 THEN 1 ELSE 0 END) AS elec,
                SUM(CASE WHEN done=1 AND gas=1 THEN 1 ELSE 0 END)         AS gas,
                SUM(CASE WHEN done=1 AND water=1 THEN 1 ELSE 0 END)       AS water,
                SUM(CASE WHEN done=1 AND sewage=1 THEN 1 ELSE 0 END)      AS sewage
            FROM {_TABLE}
        """).fetchone())

        by_program = [dict(r) for r in conn.execute(f"""
            SELECT
                program,
                COUNT(*)                                                   AS total,
                SUM(CASE WHEN done=1 THEN 1 ELSE 0 END)                   AS done,
                SUM(CASE WHEN done=1 AND status='في طور الانجاز'    THEN 1 ELSE 0 END) AS s1,
                SUM(CASE WHEN done=1 AND status='على مستوى الاعمدة' THEN 1 ELSE 0 END) AS s2,
                SUM(CASE WHEN done=1 AND status='منتهية غير مشغولة' THEN 1 ELSE 0 END) AS s3,
                SUM(CASE WHEN done=1 AND status='منتهية ومشغولة'    THEN 1 ELSE 0 END) AS s4,
                SUM(CASE WHEN done=1 AND electricity=1 THEN 1 ELSE 0 END)              AS elec,
                SUM(CASE WHEN done=1 AND gas=1         THEN 1 ELSE 0 END)              AS gas,
                SUM(CASE WHEN done=1 AND water=1       THEN 1 ELSE 0 END)              AS water,
                SUM(CASE WHEN done=1 AND sewage=1      THEN 1 ELSE 0 END)              AS sewage,
                SUM(CASE WHEN done=1 AND image_file_name IS NOT NULL
                         AND image_file_name != '' THEN 1 ELSE 0 END)                  AS with_image,
                MIN(created_at)                                                          AS min_created,
                MAX(id)                                                                  AS max_id
            FROM {_TABLE}
            WHERE program IS NOT NULL
            GROUP BY program
            ORDER BY MIN(created_at) ASC, program ASC
        """).fetchall()]

        by_status = [dict(r) for r in conn.execute(f"""
            SELECT
                status,
                COUNT(*)                                                              AS total,
                SUM(CASE WHEN electricity=1 THEN 1 ELSE 0 END)                       AS elec,
                SUM(CASE WHEN gas=1         THEN 1 ELSE 0 END)                       AS gas,
                SUM(CASE WHEN water=1       THEN 1 ELSE 0 END)                       AS water,
                SUM(CASE WHEN sewage=1      THEN 1 ELSE 0 END)                       AS sewage,
                SUM(CASE WHEN electricity=0 AND gas=0 AND water=0 AND sewage=0
                         THEN 1 ELSE 0 END)                                           AS none,
                SUM(CASE WHEN image_file_name IS NOT NULL AND image_file_name != ''
                         THEN 1 ELSE 0 END)                                           AS with_image
            FROM {_TABLE}
            WHERE done=1
            GROUP BY status
            ORDER BY CASE status
                WHEN 'منتهية ومشغولة'    THEN 1
                WHEN 'منتهية غير مشغولة' THEN 2
                WHEN 'على مستوى الاعمدة' THEN 3
                ELSE 4 END
        """).fetchall()]

        image_by_status = [dict(r) for r in conn.execute(f"""
            SELECT
                status,
                SUM(CASE WHEN image_file_name IS NOT NULL AND image_file_name != ''
                         THEN 1 ELSE 0 END) AS with_image,
                SUM(CASE WHEN image_file_name IS NULL OR image_file_name=''
                         THEN 1 ELSE 0 END) AS without_image
            FROM {_TABLE}
            WHERE done=1
            GROUP BY status
        """).fetchall()]

        return {
            "totals": totals,
            "byProgram": by_program,
            "byStatus": by_status,
            "imageByStatus": image_by_status,
        }

    def get_statistics(self) -> dict:
        conn = self._conn()
        total = conn.execute(f"SELECT COUNT(*) c FROM {_TABLE}").fetchone()["c"]
        completed = conn.execute(f"SELECT COUNT(*) c FROM {_TABLE} WHERE done=1").fetchone()["c"]
        rows = [dict(r) for r in conn.execute(f"""
            SELECT program, COUNT(*) AS total,
                SUM(CASE WHEN done=1 THEN 1 ELSE 0 END) AS done_count,
                SUM(CASE WHEN done=1 AND status='في طور الانجاز'    THEN 1 ELSE 0 END) AS status_1,
                SUM(CASE WHEN done=1 AND status='على مستوى الاعمدة' THEN 1 ELSE 0 END) AS status_2,
                SUM(CASE WHEN done=1 AND status='منتهية غير مشغولة' THEN 1 ELSE 0 END) AS status_3,
                SUM(CASE WHEN done=1 AND status='منتهية ومشغولة'    THEN 1 ELSE 0 END) AS status_4,
                SUM(CASE WHEN done=1 THEN electricity ELSE 0 END) AS elec_sum,
                SUM(CASE WHEN done=1 THEN gas         ELSE 0 END) AS gas_sum,
                SUM(CASE WHEN done=1 THEN water       ELSE 0 END) AS water_sum,
                SUM(CASE WHEN done=1 THEN sewage      ELSE 0 END) AS sew_sum
            FROM {_TABLE} WHERE program IS NOT NULL
            GROUP BY program
            ORDER BY MIN(created_at) ASC, program ASC
        """).fetchall()]
        return {
            "total": total,
            "completed": completed,
            "progress": round(completed / total * 100) if total else 0,
            "programStats": rows,
        }

    def get_report_stats(self, program: str) -> dict:
        conn = self._conn()
        general = dict(conn.execute(f"""
            SELECT
                COUNT(*)                                                                AS quota,
                SUM(CASE WHEN done=1 THEN 1 ELSE 0 END)                                AS done,
                SUM(CASE WHEN done=1 AND status='في طور الانجاز'    THEN 1 ELSE 0 END) AS in_progress,
                SUM(CASE WHEN done=1 AND status='على مستوى الاعمدة' THEN 1 ELSE 0 END) AS pillars,
                SUM(CASE WHEN done=1 AND status='منتهية غير مشغولة' THEN 1 ELSE 0 END) AS finished_not_occupied,
                SUM(CASE WHEN done=1 AND status='منتهية ومشغولة'    THEN 1 ELSE 0 END) AS finished_occupied
            FROM {_TABLE} WHERE program = ?
        """, (program,)).fetchone())
        networks = dict(conn.execute(f"""
            SELECT
                SUM(CASE WHEN electricity=1 THEN 1 ELSE 0 END) AS elec_occ,
                SUM(CASE WHEN gas=1         THEN 1 ELSE 0 END) AS gas_occ,
                SUM(CASE WHEN water=1       THEN 1 ELSE 0 END) AS water_occ,
                SUM(CASE WHEN sewage=1      THEN 1 ELSE 0 END) AS sew_occ,
                SUM(CASE WHEN electricity=1 AND gas=1 AND water=1 AND sewage=1
                         THEN 1 ELSE 0 END)                    AS fully_connected
            FROM {_TABLE}
            WHERE program = ? AND done=1 AND status='منتهية ومشغولة'
        """, (program,)).fetchone())
        return {**general, **networks}

    def get_program_images(self, program: str) -> List[dict]:
        rows = self._conn().execute(f"""
            SELECT image_file_name, image_path, first_name, last_name FROM {_TABLE}
            WHERE program = ? AND done=1 AND image_file_name IS NOT NULL AND image_file_name != ''
        """, (program,)).fetchall()
        return [{
            "name": r["image_file_name"] or "",
            "path": r["image_path"] or "",
            "first_name": r["first_name"] or "",
            "last_name": r["last_name"] or "",
        } for r in rows]

    def get_programs(self) -> List[str]:
        rows = self._conn().execute(f"""
            SELECT program, MIN(created_at) AS min_c, MAX(id) AS max_id FROM {_TABLE}
            WHERE program IS NOT NULL AND program != ''
            GROUP BY program
            ORDER BY MIN(created_at) ASC, program ASC
        """).fetchall()
        return [r["program"] for r in rows]

    def rename_program(self, old: str, new: str) -> int:
        cur = self._conn().execute(
            f"UPDATE {_TABLE} SET program = ?, updated_at = ? WHERE program = ?",
            (new, self._now_ms(), old),
        )
        self._conn().commit()
        return cur.rowcount

    # ──────────────────────────────────────────
    def export_to_json(self) -> str:
        items = self.get_all_beneficiaries()
        from datetime import datetime
        return json.dumps({
            "version": "1.0",
            "exportDate": datetime.now().isoformat(),
            "beneficiaries": [b.to_map() for b in items],
        }, ensure_ascii=False, indent=2)

    def import_from_json(self, json_str: str) -> None:
        data = json.loads(json_str)
        items = [Beneficiary.from_row(x) for x in (data.get("beneficiaries") or [])]
        self.insert_beneficiaries(items)

    def merge_from_json_files(self, files: List[Path]) -> dict:
        imported, duplicates = 0, 0
        existing = self.get_all_beneficiaries()
        keys = {f"{b.first_name}|{b.last_name}|{b.birth_date}|{b.address}" for b in existing}
        for f in files:
            try:
                data = json.loads(Path(f).read_text(encoding="utf-8"))
                for item in data.get("beneficiaries") or []:
                    b = Beneficiary.from_row(item)
                    k = f"{b.first_name}|{b.last_name}|{b.birth_date}|{b.address}"
                    if k not in keys:
                        self.insert_beneficiary(b)
                        keys.add(k)
                        imported += 1
                    else:
                        duplicates += 1
            except Exception:
                pass
        return {"imported": imported, "duplicates": duplicates}
