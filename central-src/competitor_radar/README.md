# 🕵️ Competitor Radar (رادار المنافسين) — إضافة مستقلة

**الحالة: المرحلة 1 (خلفية + قاعدة بيانات + اختبارات). غير مركّبة على السيرفر ولا مربوطة ببوت تيليغرام.** لا يوجد أي تعديل على ملف قديم.

## القواعد
- لا تلمس: Broker، التوثيق/المفاتيح، الجداول والدوال الحالية، workflows n8n، تكاملات TikTok/Snap/Meta، المراقبة/الإيقاف/الجدولة/التقارير.
- لا توجد أي عملية كتابة لمنصة إعلانية: لا إنشاء/تشغيل/إيقاف/تعديل حملة، ولا استدعاء Broker (اختبار `test_module_has_no_ad_platform_write_path` يفرضه).
- التعطيل: `COMPETITOR_RADAR_ENABLED=false` (الحاوية) + مفتاح DB `competitor_radar.settings.enabled=false` (افتراضي) + `features.competitor_radar=false` لكل عميل.

## الملفات
- `service/` خدمة Python (stdlib فقط عدا psycopg بالتشغيل): `safe_fetch` (حماية SSRF) · `extract` · `lexicon` · `classify` · `confidence` · `analyze` (Pipeline) · `strategy` (+فحص عدم النسخ) · `market` · `cache` · `llm` · `store` · `engine` · `app` (HTTP داخلي + HMAC).
- `db/80_competitor_radar.sql` + `80_competitor_radar_down.sql`: مخطط `competitor_radar` مستقل، دوال SECURITY DEFINER تفرض عزل العميل من ctx؛ الدور `radar_rt`؛ `app_runtime` يقرأ `config` فقط.
- `tests/` 82 اختبار: core(32) safe_fetch(11) engine(20) app(8) db(9، Postgres 16 مؤقت) old_system_untouched(2).

## مصادر البيانات (مشروعة فقط)
1. نص يلصقه المستخدم (الأساسي). 2. oEmbed الرسمي من TikTok. 3. وسوم HTML العامة (title/description/og) من الرابط المُدخل، مع robots.txt وحماية SSRF.
صفحات تسجيل الدخول/المحمية = «لا يوجد وصول» ولا يُخمَّن شي. بدون بيانات كافية: «⚠️ بيانات غير كافية للتحليل.»

## ثقة التحليل (تُحسب بالكود)
🟢 عالي = اقتباس مباشر · 🟡 متوسط = ≥2 عينة · 🔴 منخفض = عينة وحدة/معرفة عامة. مخرجات الـLLM تُتحقق (أدلة موجودة) ولا تتجاوز متوسط.

## المراحل القادمة (تحتاج موافقة قبل كل واحدة)
- P2: حاوية + compose override جديد + سكربت تثبيت (مفاتيح تُكتب مخفية) + تطبيق الهجرة يدوياً + `pages.py` + باتش الربط (ingress + زر الرئيسية) بعلامات وتراجع `.pre`.
- P3: تفعيل لـmohm فقط واختبار حي بعينات ملصوقة. P4: بقية العملاء.
