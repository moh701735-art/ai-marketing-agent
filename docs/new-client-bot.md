# إضافة بوت عميل جديد (من القالب)

القالب = workflow «عميل احمد فوريفر» (تيليگرام + تيك توك: رفع، جدولة، مراقبة المراجعة، طعن تلقائي، اختبار الجمهور، سقف سعر الرسالة).

## ما يحتاجه كل عميل
1. بوت تيليگرام جديد من @BotFather → التوكن.
2. معرّف تيليگرام الرقمي للعميل (chat id).
3. توكن تيك توك للعميل (Access-Token) وأرقام حساباته الإعلانية وعملتها.
4. (اختياري) Meta: credential خاص بالعميل فقط. بدونه تتعطل عقد Meta (authentication=none).

## الخطوات
1. n8n: Duplicate للقالب ← سمّه «عميل <الاسم>» (لا تنشره بعد).
2. n8n: أنشئ credentials: Telegram (توكن العميل)، Header Auth `Access-Token - <الاسم>` (Header: Access-Token).
3. أنشئ 9 جداول بلاحقة « - <الاسم>» بنفس أعمدة جداول القالب (create_data_table).
4. `get_workflow_details` للـ workflow المكرر ← احفظ الناتج، واكتب config.json (انظر رأس provision.py).
5. `python3 scripts/client-bot/provision.py details.json config.json > ops.json` ثم طبّق ops على دفعات ≤100 (update_workflow).
6. أضف صف العميل بجدول «حساب العميل» (phone = chat id، client، tiktok_advertiser_id) وصف chat id بجدول «قائمة المصرح لهم» (active=true).
7. شغّل يدوياً «سقف التكلفة» ثم publish. اختبر برسالة من تيليگرام.

## ملاحظات
- التوكن يُكتب داخل عقدة «بناء رابط الوسائط» (يحتاجه رابط ملفات تيليگرام) — لا تشاركه بأي مكان آخر.
- حدّ سعر الرسالة بالدينار (`limit_iqd`)؛ 20 سنت ≈ 262 د.ع.
- الربط التلقائي لا يغيّر غير ما ذُكر؛ راجع أي نص يخص اسم العميل داخل prompt الـAI.
