# إحصاء السكن الريفي 2026 — نسخة Python (PyQt6)

تطبيق سطح المكتب لإدارة إحصاء السكن الريفي، **نسخة Python كاملة** مكافئة للنسخة الأصلية المكتوبة بلغة Dart/Flutter، مع الحفاظ على:

- ✅ **التوافق التام لبروتوكول المزامنة** مع تطبيق Flutter للهواتف
  (نفس البورت `8080`، نفس المسارات `/ping /auth /metasync /upload_zip`،
  نفس بنية ZIP وملفات `data.json` / `diff.json`).
- ✅ **نفس قاعدة البيانات SQLite** (`Documents/ihsaa2026/ihsa_2026.db`)
  بنفس بنية الجداول والفهارس (لا حاجة لأي ترحيل بيانات).
- ✅ **نفس الواجهة العربية RTL** بألوان وتنسيقات مطابقة.
- ✅ **التقارير PDF بالعربية** (مع مكتبة Cairo + bidi/arabic-reshaper).
- ✅ **استيراد/تصدير Excel و JSON** بنفس صيغة Flutter.
- ✅ **رمز QR** للهواتف لتسهيل الاتصال (نفس صيغة `nhsync://IP:PORT?pw=...`).

---

## التثبيت

```bash
cd ihsaa2026_py
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

## التشغيل

```bash
python main.py
# أو
python -m ihsaa2026
```

---

## بنية المشروع

```
ihsaa2026_py/
├── main.py                      # نقطة الإقلاع
├── requirements.txt             # حزم Python
├── assets/fonts/                # خطوط Cairo + الأيقونة
└── ihsaa2026/
    ├── __init__.py
    ├── __main__.py
    ├── app.py                   # MainWindow + QApplication
    ├── config.py                # إعدادات + Prefs (≈ SharedPreferences)
    ├── models/
    │   └── beneficiary.py       # نموذج المستفيد (Beneficiary)
    ├── services/
    │   ├── database_service.py  # SQLite (مطابق لـ database_service.dart)
    │   ├── sync_service.py      # محرك المزامنة (Singleton)
    │   ├── sync_server.py       # خادم HTTP للمدير
    │   ├── sync_client.py       # عميل HTTP للعون
    │   ├── excel_service.py     # استيراد/تصدير Excel
    │   ├── export_service.py    # JSON / ZIP / دمج
    │   └── report_service.py    # تقارير PDF بالعربية
    ├── widgets/
    │   ├── style.py             # ستايل QSS موحد
    │   ├── common.py            # بطاقات، أزرار، Snackbar
    │   └── beneficiary_card.py  # بطاقة المستفيد
    └── screens/
        ├── setup_screen.py
        ├── home_screen.py
        ├── add_beneficiary_screen.py
        ├── survey_screen.py
        ├── stats_screen.py
        ├── advanced_stats_screen.py
        ├── report_screen.py
        └── sync_screen.py
```

---

## التوافق مع تطبيق Flutter للهواتف

### مسار البيانات
كلا التطبيقين (Python و Flutter) يستعملان نفس المسار على Windows:

```
%USERPROFILE%\Documents\ihsaa2026\
├── ihsa_2026.db        # قاعدة البيانات الأساسية (SQLite)
├── images/             # صور المستفيدين
├── backups/            # نسخ احتياطية
└── tmp/                # ملفات المزامنة المؤقتة
```

### بروتوكول المزامنة
- **`GET /ping`** → `{"ok": true}`
- **`POST /auth`** ← `{"password": "..."}` → `{"ok": true|false}`
- **`POST /metasync`** ← `{"summary": [...]}` → ZIP يحوي `diff.json` + الصور
- **`POST /upload_zip`** ← bytes ZIP يحوي `data.json` + الصور → `{"ok": true, "stats": {...}}`

العنوان الذي يُولِّده تطبيق Python في رمز QR مطابق تماماً لما يقرأه تطبيق Flutter:
```
nhsync://192.168.1.5:8080?pw=URL_ENCODED_PASSWORD
```

### قواعد فض النزاع (Conflict Resolution)
متطابقة 100% مع `sync_service.dart`:
1. إن كان أحد الطرفين `done=1` والآخر `done=0` → الفائز هو `done=1`.
2. وإلا الأحدث (`updated_at` أكبر) يفوز.
3. الـ `id` يبقى للسجل المحلي (لتفادي اضطراب الفهارس).

---

## بناء ملف Setup.exe (Windows)

استعمل [PyInstaller](https://pyinstaller.org/):

```bash
pip install pyinstaller
pyinstaller --noconfirm --windowed ^
    --name "إحصاء_السكن_الريفي_2026" ^
    --icon "assets/fonts/icon.ico" ^
    --add-data "assets;assets" ^
    main.py
```

ثم استعمل [Inno Setup](https://jrsoftware.org/isinfo.php) لإنشاء مُثبِّت `.exe` مماثل لـ `inno_bundle` في النسخة الأصلية.

---

## المؤلف

حميتي نسيم — الحوضان · `nas.hamiti89@gmail.com`
