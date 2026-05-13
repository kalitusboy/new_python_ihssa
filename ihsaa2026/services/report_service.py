"""خدمة توليد تقارير PDF بالعربية (RTL).
تستعمل reportlab + arabic_reshaper + python-bidi.
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from ..config import DOCS_DIR, assets_dir
from .database_service import DatabaseService


# ──────────────────────────────────────────────
# تسجيل خط Cairo (يدعم العربية)
# ──────────────────────────────────────────────
_FONT_REGISTERED = False


def _register_fonts() -> str:
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return "Cairo"
    try:
        regular = assets_dir() / "fonts" / "Cairo-Regular.ttf"
        bold = assets_dir() / "fonts" / "Cairo-Bold.ttf"
        if regular.exists():
            pdfmetrics.registerFont(TTFont("Cairo", str(regular)))
        if bold.exists():
            pdfmetrics.registerFont(TTFont("Cairo-Bold", str(bold)))
        _FONT_REGISTERED = True
        return "Cairo"
    except Exception:
        return "Helvetica"


# ──────────────────────────────────────────────
# معالج النص العربي (تشكيل + bidi)
# ──────────────────────────────────────────────
def ar(text: str) -> str:
    """يحوّل النص العربي إلى صيغة قابلة للعرض الصحيح في PDF."""
    if text is None:
        return ""
    s = str(text)
    if not s.strip():
        return s
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(s))
    except Exception:
        return s


# ──────────────────────────────────────────────
class ReportService:
    def __init__(self):
        self.db = DatabaseService()
        self.font = _register_fonts()
        self.bold_font = "Cairo-Bold" if self.font == "Cairo" else "Helvetica-Bold"

    def _styles(self):
        styles = getSampleStyleSheet()
        title = ParagraphStyle(
            "ArTitle", parent=styles["Heading1"],
            fontName=self.bold_font, fontSize=18, alignment=1,
            textColor=colors.HexColor("#0D47A1"),
        )
        h2 = ParagraphStyle(
            "ArH2", parent=styles["Heading2"],
            fontName=self.bold_font, fontSize=14, alignment=2,
            textColor=colors.HexColor("#0A3880"),
            spaceBefore=8, spaceAfter=6,
        )
        normal = ParagraphStyle(
            "ArNormal", parent=styles["Normal"],
            fontName=self.font, fontSize=11, alignment=2, leading=16,
        )
        small = ParagraphStyle(
            "ArSmall", parent=styles["Normal"],
            fontName=self.font, fontSize=9, alignment=2,
            textColor=colors.HexColor("#64748B"),
        )
        return title, h2, normal, small

    # ──────────────────────────────────────────
    def export_program_report(self, program: str, output_path: Optional[Path] = None) -> Path:
        """تقرير PDF تفصيلي لبرنامج واحد."""
        if output_path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe = program.replace("/", "_").replace("\\", "_")
            output_path = DOCS_DIR / f"تقرير_{safe}_{ts}.pdf"

        stats = self.db.get_report_stats(program)
        title_s, h2_s, normal_s, small_s = self._styles()

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=15 * mm, leftMargin=15 * mm,
            topMargin=15 * mm, bottomMargin=15 * mm,
        )

        story = []
        story.append(Paragraph(ar("تقرير برنامج: ") + ar(program), title_s))
        story.append(Paragraph(ar("تاريخ التوليد: ") + datetime.now().strftime("%Y-%m-%d %H:%M"), small_s))
        story.append(Spacer(1, 8 * mm))

        # ── جدول الحالة العامة ─────────────────
        story.append(Paragraph(ar("الحالة العامة"), h2_s))
        gen_data = [
            [ar("البيان"), ar("العدد")],
            [ar("الحصة (الإجمالي)"), str(stats.get("quota") or 0)],
            [ar("المُحصاة"), str(stats.get("done") or 0)],
            [ar("في طور الانجاز"), str(stats.get("in_progress") or 0)],
            [ar("على مستوى الأعمدة"), str(stats.get("pillars") or 0)],
            [ar("منتهية غير مشغولة"), str(stats.get("finished_not_occupied") or 0)],
            [ar("منتهية ومشغولة"), str(stats.get("finished_occupied") or 0)],
        ]
        story.append(self._build_table(gen_data))
        story.append(Spacer(1, 6 * mm))

        # ── جدول الشبكات ──────────────────────
        story.append(Paragraph(ar("الربط بالشبكات (للمنتهية والمشغولة)"), h2_s))
        net_data = [
            [ar("الشبكة"), ar("العدد")],
            [ar("كهرباء"), str(stats.get("elec_occ") or 0)],
            [ar("غاز"), str(stats.get("gas_occ") or 0)],
            [ar("مياه"), str(stats.get("water_occ") or 0)],
            [ar("تطهير"), str(stats.get("sew_occ") or 0)],
            [ar("جميع الشبكات معاً"), str(stats.get("fully_connected") or 0)],
        ]
        story.append(self._build_table(net_data))
        story.append(Spacer(1, 8 * mm))

        # ── معرض الصور (أول 12 صورة) ──────────
        images = self.db.get_program_images(program)
        if images:
            story.append(Paragraph(ar("معرض الصور (نموذج)"), h2_s))
            grid_rows: list[list] = []
            row: list = []
            count = 0
            for img in images[:12]:
                p = img.get("path") or ""
                if p and Path(p).exists():
                    try:
                        cell = Image(p, width=4.5 * cm, height=4.5 * cm, kind="proportional")
                    except Exception:
                        continue
                    name = ar(f"{img.get('first_name','')} {img.get('last_name','')}".strip())
                    inner = Table([[cell], [Paragraph(name, small_s)]], colWidths=[5 * cm])
                    inner.setStyle(TableStyle([
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ]))
                    row.append(inner)
                    count += 1
                    if len(row) == 3:
                        grid_rows.append(row); row = []
            if row:
                while len(row) < 3:
                    row.append("")
                grid_rows.append(row)
            if grid_rows:
                gallery = Table(grid_rows, colWidths=[5.5 * cm] * 3)
                gallery.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]))
                story.append(gallery)

        doc.build(story)
        return Path(output_path)

    # ──────────────────────────────────────────
    def export_advanced_stats_pdf(self, output_path: Optional[Path] = None) -> Path:
        """تقرير الإحصائيات المتقدمة الشامل."""
        if output_path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = DOCS_DIR / f"تقرير_شامل_{ts}.pdf"

        adv = self.db.get_advanced_stats()
        title_s, h2_s, _, small_s = self._styles()

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=landscape(A4),
            rightMargin=12 * mm, leftMargin=12 * mm,
            topMargin=12 * mm, bottomMargin=12 * mm,
        )
        story = []
        story.append(Paragraph(ar("التقرير الإحصائي المتقدم"), title_s))
        story.append(Paragraph(ar("إحصاء السكن الريفي 2026 — نسيم الحوضان"), small_s))
        story.append(Paragraph(ar("تاريخ التوليد: ") + datetime.now().strftime("%Y-%m-%d %H:%M"), small_s))
        story.append(Spacer(1, 6 * mm))

        # حسب البرامج
        story.append(Paragraph(ar("الإحصائيات حسب البرنامج"), h2_s))
        head = [
            ar("البرنامج"), ar("الحصة"), ar("المحصاة"),
            ar("في طور الانجاز"), ar("على الأعمدة"),
            ar("منتهية غ.مشغولة"), ar("منتهية مشغولة"),
            ar("كهرباء"), ar("غاز"), ar("مياه"), ar("تطهير"), ar("بصور"),
        ]
        rows = [head]
        for r in adv.get("byProgram", []):
            rows.append([
                ar(r.get("program") or ""),
                r.get("total") or 0, r.get("done") or 0,
                r.get("s1") or 0, r.get("s2") or 0,
                r.get("s3") or 0, r.get("s4") or 0,
                r.get("elec") or 0, r.get("gas") or 0,
                r.get("water") or 0, r.get("sewage") or 0,
                r.get("with_image") or 0,
            ])
        story.append(self._build_table(rows, header_bg="#0D47A1"))

        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph(ar("الإحصائيات حسب الحالة"), h2_s))
        head2 = [ar("الحالة"), ar("العدد"), ar("كهرباء"), ar("غاز"), ar("مياه"), ar("تطهير"), ar("بدون شبكة"), ar("بصور")]
        rows2 = [head2]
        for r in adv.get("byStatus", []):
            rows2.append([
                ar(r.get("status") or ""),
                r.get("total") or 0, r.get("elec") or 0, r.get("gas") or 0,
                r.get("water") or 0, r.get("sewage") or 0,
                r.get("none") or 0, r.get("with_image") or 0,
            ])
        story.append(self._build_table(rows2, header_bg="#0A3880"))

        doc.build(story)
        return Path(output_path)

    # ──────────────────────────────────────────
    def _build_table(self, data: List[List], header_bg: str = "#0D47A1") -> Table:
        t = Table(data, repeatRows=1, hAlign="CENTER")
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), self.font),
            ("FONTNAME", (0, 0), (-1, 0), self.bold_font),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_bg)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTSIZE", (0, 0), (-1, 0), 11),
            ("FONTSIZE", (0, 1), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("TOPPADDING", (0, 0), (-1, 0), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ]))
        return t
