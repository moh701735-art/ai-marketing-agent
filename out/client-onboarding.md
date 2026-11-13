# جدول إضافة عميل جديد للنظام المركزي

املأ العمود الأخير مرة وحدة، وبعدها انسخ القيم للأوامر بالأسفل. **لا تكتب التوكنات ولا App Secret ولا auth_code هنا أبداً** (تنكتب مخفية بالتيرمنال فقط).

| # | المعلومة | مثال (مصطفى بغداد) | قيمة العميل الجديد |
|---|---|---|---|
| 1 | اسم العميل | مصطفى بغداد | |
| 2 | slug (إنجليزي صغير بدون مسافات) | mustafa-baghdad | |
| 3 | Telegram ID للمالك (أرقام) | 5864699816 | |
| 4 | موظفين إضافيين (ID:دور، الدور owner/manager/viewer) | — | |
| 5 | username البوت (بدون @) | MustafaClientsBot | |
| 6 | رابط البوت | t.me/MustafaClientsBot | |
| 7 | رقم الحساب الإعلاني بتيك توك (يبدأ بـ 76 أو 7) | 7691331863249256500 | |
| 8 | حسابات تيك توك إضافية | — | |
| 9 | العملة (USD أو IQD) — اسأل عن عملة حساباته الإعلانية **قبل** الأمر (علي التركي طلعت IQD وكنا كاتبينها USD؛ التصليح: `update core.tenants set currency='IQD' where slug='SLUG'`) | USD | |
| 10 | المنطقة الزمنية | Asia/Baghdad | |
| 11 | الخطة | standard | |
| 12 | مدة الاشتراك بالأيام | 30 | |
| 13 | تاريخ بداية الاشتراك | (يوم التنفيذ) | |
| 14 | تاريخ انتهاء الاشتراك | (بداية + 30 يوم) | |
| 15 | رقم واتساب Business المربوط بتيك توك | — | |
| 16 | ميتا: حساب فيسبوك / الصفحة / حساب الإعلانات | غير مربوط بعد | |
| 17 | سقف تكلفة الرسالة للإيقاف التلقائي | 0.30$ (الافتراضي) | |
| 18 | المبلغ المدفوع / حالة الدفع | — | |
| 19 | ملاحظات | | |
| 20 | bc_id للبزنس (للتعبئة من البزنس) | 7691331863249256500 (يتأكد منه) | |
| 21 | يريد رسائل تيك توك؟ (نعم/لا) | نعم | |
| 22 | حساب تيك توك المربوط (@) وهل موثّق | @hhfhhyg1 موثّق | |

## الأوامر (استبدل القيم من الجدول)

الخطوة 1: إنشاء العميل (يسأل عن توكن البوت مخفي):

```
cd /opt/central
export PG_CONTAINER=central-stg-pg BROKER_NETWORK=central-stg_backend BROKER_IMAGE=central-broker:prod ENV_FILE=deploy/.env TENANT_DB=central
python3 ops/add-tenant.py --slug SLUG --name "الاسم" --features schedule \
  --owner TG_ID --bot-username BOT_USERNAME --plan standard --days 30 \
  --tz Asia/Baghdad --currency USD --set-webhook
```

الخطوة 2: ربط تيك توك (يسأل slug وApp ID وApp Secret وauth_code، ثم اكتب `all`):

```
python3 ops/link-tiktok-agency.py
```

الخطوة 3: الجاهزية مرتين، لازم يطلع `SLUG READY`:

```
bash deploy/run-readiness.sh
bash deploy/run-readiness.sh
```

الخطوة 4: التجربة من تيليجرام: `/start` ثم `/accounts` ثم `/balance`.

الخطوة 5: bc_id للعميل (لازم للتعبئة من البزنس):

```
update core.tenants set features = features || jsonb_build_object('bc_id','BC_ID') where slug='SLUG';
```

الخطوة 6 (إذا يريد رسائل تيك توك): فحص جاهزية حسابه، ثم رسالة ترحيبه:

```
TT_SLUG=SLUG python3 ops/tt-identities.py     # لازم READY for DM ads
```

العميل ينشئ رسالة الترحيب من Business Center، وحملة DM تجريبية متوقفة، ثم تسحب رقمها بـ `TT_SLUG=SLUG python3 ops/tt-dm.py` وتحفظه بالبوت: `/welcome add <اسم> <الرقم>`. التفاصيل الكاملة بـ `central-knowledge.md`.

## قبل التسليم

- [ ] البوت رد على `/start`
- [ ] `/accounts` يعرض الحساب الصحيح
- [ ] `/balance` يعرض الرصيد
- [ ] الاشتراك مسجل (تاريخ الانتهاء بالجدول)
- [ ] bc_id مضبوط (إذا يستخدم /addbalance)
- [ ] (رسائل تيك توك) الفحص READY ورسالة الترحيب محفوظة
- [ ] ما انكتب أي توكن أو سر بالدردشة
