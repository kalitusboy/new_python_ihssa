"""نموذج المستفيد — مطابق لـ lib/models/beneficiary.dart."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
import re


@dataclass
class Beneficiary:
    id: Optional[int] = None
    first_name: str = ""
    last_name: str = ""
    full_name: Optional[str] = None
    birth_date: Optional[str] = None
    birth_place: Optional[str] = None
    address: Optional[str] = None
    program: Optional[str] = "عام"
    done: int = 0
    electricity: int = 0
    gas: int = 0
    water: int = 0
    sewage: int = 0
    status: str = "في طور الانجاز"
    image_path: Optional[str] = None
    image_file_name: Optional[str] = None
    created_at: Optional[int] = None  # ms since epoch
    updated_at: Optional[int] = None  # ms since epoch

    # ──────────────────────────────────────────
    @classmethod
    def from_row(cls, row) -> "Beneficiary":
        """من sqlite Row أو dict."""
        d = dict(row) if not isinstance(row, dict) else row
        return cls(
            id=d.get("id"),
            first_name=d.get("first_name") or "",
            last_name=d.get("last_name") or "",
            full_name=d.get("full_name"),
            birth_date=d.get("birth_date"),
            birth_place=d.get("birth_place"),
            address=d.get("address"),
            program=d.get("program") or "عام",
            done=int(d.get("done") or 0),
            electricity=int(d.get("electricity") or 0),
            gas=int(d.get("gas") or 0),
            water=int(d.get("water") or 0),
            sewage=int(d.get("sewage") or 0),
            status=d.get("status") or "في طور الانجاز",
            image_path=d.get("image_path"),
            image_file_name=d.get("image_file_name"),
            created_at=d.get("created_at"),
            updated_at=d.get("updated_at"),
        )

    def to_map(self) -> dict:
        """صيغة متطابقة مع toMap() في Dart — للمزامنة مع Flutter."""
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "birth_date": self.birth_date,
            "birth_place": self.birth_place,
            "address": self.address,
            "program": self.program,
            "done": self.done,
            "electricity": self.electricity,
            "gas": self.gas,
            "water": self.water,
            "sewage": self.sewage,
            "status": self.status,
            "image_path": self.image_path,
            "image_file_name": self.image_file_name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    # ──────────────────────────────────────────
    @property
    def display_name(self) -> str:
        if self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        return self.full_name or "مستفيد"

    @property
    def birth_info(self) -> str:
        parts = []
        if self.birth_date:
            parts.append(f"📅 {self.birth_date}")
        if self.birth_place:
            parts.append(f"📍 {self.birth_place}")
        return " | ".join(parts)

    def generate_image_filename(self) -> str:
        def norm(s: str) -> str:
            s = re.sub(r'[\\/?%*:|"<>]', "_", s or "")
            s = re.sub(r"\s+", "_", s)
            s = re.sub(r"_+", "_", s)
            return s

        parts = [
            norm(self.program or "عام"),
            norm(self.address or "غير_محدد"),
            norm(self.display_name),
            norm("_".join(filter(None, [self.birth_date or "", self.birth_place or ""]))),
            datetime.now().isoformat().replace(":", "-").replace(".", "-"),
        ]
        return "__".join([p for p in parts if p]) + ".jpg"

    def copy_with(self, **kwargs) -> "Beneficiary":
        d = self.to_map()
        d.update(kwargs)
        return Beneficiary.from_row(d)
