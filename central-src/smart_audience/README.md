# smart_audience — 🎯 Smart Audience Builder (منشئ الجمهور الذكي)

Module مستقل فوق البوت المركزي. **النظام يقترح — المستخدم يختار — تيك توك يعطي الحجم — النظام يعرضه حرفياً — المستخدم يقرر.**
لا يختار الجمهور نيابة عن المستخدم، لا ينشئ حملات، لا أي عملية كتابة.

## تشغيل/إيقاف (Rollback بأمر واحد)
```
bash ops/smart-audience-sync.sh on|off                 # SMART_AUDIENCE_ENABLED=true|false بـ deploy/.env + القاعدة، فوراً
bash ops/smart-audience-sync.sh tenant <slug> off      # لعميل واحد
bash ops/smart-audience-sync.sh threshold 500000 2000000 6000000 12000000   # عتبات التقييم
```
OFF: يختفي زر «🎯 منشئ الجمهور الذكي» وأي `sa:*` و`/audience` يرد الرد القديم. الحملات والتقارير والأوامر القديمة لا تعرف بوجوده. الافتراضي بعد التثبيت OFF.

## كيف يشتغل (مبني على فحص حقيقي على حساب mohm)
1. المستخدم يختار السوق (أو `/audience <منتج>`): القاموس الثابت (`MK` بـ pages.py) يترجم المنتج→سوق→مصطلحات بحث إنكليزية (seeds). **القاموس مفاتيح بحث فقط.**
2. `tiktok.recommend_interests` (موجودة أصلاً بالـBroker) تجيب اهتمامات تيك توك الحقيقية (`keyword_id`, status=EFFECTIVE). كل مستوى = ناتج seeds مستواه: 🔥 مباشر، 🟢 مرتبط، 🟡 قريب، 🔵 مجاور (الأعلى يغلب عند التكرار).
3. المستخدم يضغط المربعات ☐↔☑. مستويات التوسع (دقيق/متوازن/واسع/توسع كبير) تغيّر **العرض** فقط.
4. التقدير: `tiktok.estimate_audience` (إضافة قراءة فقط بالـBroker) يعطي `user_count{lower_end, upper_end}` + `user_count_stage`، يُعرض كما رجع.
   **نتيجة الفحص الحقيقي: التقدير يتغير مع الدولة/الجنس/العمر ولا يتغير مع الاهتمامات بأي صيغة** (0/1/6 اهتمامات = نفس الرقم). لذلك الواجهة تقول ذلك صراحة، وأزرار الجنس/العمر/🔄 هي اللي تعيد التقدير.
   التقدير يحتاج ملف حملة واتساب كامل (objective_type=LEAD_GENERATION + optimize_goal **و** optimization_goal=CONVERSATION + promotion_type=LEAD_GEN_CLICK_TO_SOCIAL_MEDIA_APP_MESSAGE + optimization_event=MESSAGE + messaging_app_type=WHATSAPP + billing_event=OCPM …).
   غير متاح/فشل/مهلة/حد طلبات ⇒ «⚠️ لا يتوفر تقدير مباشر لحجم الجمهور من TikTok لهذا الاستهداف حالياً» بدون أي رقم.
5. التقييم 🔴ضيق/🟡متوسط/🟢جيد/🟢واسع/🔵واسع جداً بعتبات من القاعدة (`smart_audience.settings.thresholds`، تُعدَّل بالأمر أعلاه) على **منتصف** نطاق تيك توك. العتبات غير مضبوطة ⇒ لا تقييم.
6. ⚖️ مقارنة: تحفظ حتى 3 مجموعات (A/B/C) بتقديرات تيك توك لها (الفرق الحقيقي = الجنس/العمر).
7. ➡️ متابعة: تتحقق (IDs لازم تكون مما رجّعه تيك توك بالجلسة + `tiktok.check_interests` إن توفر) وتحفظ القائمة النهائية بـ `sa:<chat>` (`final`). **ربطها بخطوة الاستهداف بمعالج الحملة = المرحلة 2** بعد فحص المعالج على السيرفر.

## الـCache
- قاعدة: `smart_audience.cache` (لكل عميل، مفتاح عام صغير، `cache_list`/`cache_set` بسياق موقّع): اكتشاف اهتمامات السوق 24 ساعة، تقدير الدولة/الجنس/العمر 6 ساعات. الفشل لا يُكاش (ما نخزّن أرقاماً مختلقة).
- الجلسة: `ui_state` مفتاح `sa:<chat>` ساعة واحدة (القائمة، الاختيارات، التقدير، المقارنات).

## الأقسام المطلوبة ← أين هي
interest_discovery/interest_expansion/interest_categories (`MK` + `JS_PLAN` seeds + `JS_RENDER` اكتشاف)، audience_estimator (`estParams`/`readEst`)، audience_cache (db/72 + sets بالـrender)، audience_comparator (`sa:sv`/`sa:cmp`)، audience_validator (`sa:ok`)، telegram_ui (`JS_RENDER`)، configuration (`smart_audience.settings`)، tests (`smart_audience/tests`).

## الملفات
جديدة: `smart_audience/{pages.py,README.md,tests/*}`، `db/72_smart_audience.sql`، `db/tests/96_smart_audience.sql`، `ops/smart-audience-sync.sh`.
قديمة معدّلة (أقل ربط): `n8n/ui_pages.py` (صف SQL + علم `saOn` + زر)، `n8n/wf_ingress.py` (تحويل `sa`، أوامر `smartaud/audience`، مخرج 33، تحميل الـmodule). عملية Broker قراءة فقط `tiktok.estimate_audience` أُضيفت قبلاً (p147–p149).

## ما لم يُختبر على تيك توك الحقيقي
الاختبارات (40 node + 13 DB) على استجابات بصيغة تيك توك الحقيقية المسجّلة من فحص mohm. المسار الكامل داخل n8n الحقيقي يُجرَّب بحساب واحد بعد التثبيت. فتح سوق = ~10 نداءات قراءة (قد ياخذ عدة ثواني).
