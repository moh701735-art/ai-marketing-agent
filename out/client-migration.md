# نقل عميل من النظام القديم (n8n القديم) إلى المركزي — على نفس البوت

القاعدة: لا نعدّل النظام القديم (لا كود ولا بيانات). الشي الوحيد بالقديم: المشغّل يطفّي workflow بوت العميل من واجهة n8n القديم لحظة التحويل. لا أسرار بالدردشة (توكن البوت وApp Secret وauth_code تنكتب مخفية بالتيرمنال).

## ليش بهالترتيب
- البوت عنده webhook واحد فقط. `deploy/set-webhook.sh SLUG set` يحوّله للمركزي فوراً، وn8n القديم يرجّعه لنفسه إذا workflow البوت اشتغل/انعاد تشغيله ⇒ لازم يكون مطفّى قبل التحويل.
- `add-tenant.py` **بدون** `--set-webhook` ينشئ العميل ويخلي الـwebhook عند القديم ⇒ نجهّز كل شي والعميل لسه يشتغل على القديم.
- فحص R03 (webhook) ما ينجح إلا بعد التحويل، فالعميل يبقى `TESTING` لين التحويل (طبيعي).
- سجل الحملات/القواعد القديمة ما ينتقل؛ المركزي يقرأ من تيك توك مباشرة. القواعد التلقائية ورسالة الترحيب تنعاد من المركزي إذا مطلوبة.

## 0) اجمع (قراءة فقط من القديم)
اسم العميل، يوزر البوت (بدون @)، Telegram ID للمالك (+موظفين ID:دور)، **الأيام المتبقية** من اشتراكه (`--days N`) وتاريخ الانتهاء، حسابات تيك توك الإعلانية (+ العملة IQD/USD)، رقم واتساب Business إذا موجود، سقف تكلفة الرسالة/رسالة ترحيب خاصة إذا مخصصة. slug مقترح: `ali-qurashi` (إنجليزي صغير).

## 1) إنشاء العميل بدون تحويل البوت
```
cd /opt/central && export PG_CONTAINER=central-stg-pg BROKER_NETWORK=central-stg_backend BROKER_IMAGE=central-broker:prod ENV_FILE=deploy/.env TENANT_DB=central && python3 ops/add-tenant.py --slug SLUG --name "الاسم" --features schedule --owner TG_ID --bot-username BOT_USERNAME --plan standard --days N --tz Asia/Baghdad --currency IQD
```
(توكن البوت يُسأل مخفي: من BotFather ← /mybots ← البوت ← API Token.) لا تضيف `--set-webhook`.

## 2) ربط تيك توك (وكالة)
رابط التفويض (يرجع على `/tiktok-cb`، صفحته بيضاء لكن الكود يبقى بشريط العنوان):
`https://business-api.tiktok.com/portal/auth?app_id=7688235455380193301&state=agency3&redirect_uri=https%3A%2F%2Fagent.mohammedai.tech%2Ftiktok-cb`
انسخ قيمة `auth_code` فقط، ثم: `cd /opt/central && python3 ops/link-tiktok-agency.py` (slug، Enter للـApp ID، App Secret، الكود)، واختر **بالأرقام** حسابات العميل فقط (مو `all`). تأكد أن حسابه ظاهر. اضغط Enter أول لسطر نظيف قبل اللصق.

## 3) التحويل (دقايق، وقت هادئ، نبّه العميل)
1. بـn8n القديم: طفّي workflow(ات) بوت هالعميل (مفتاح Active).
2. `cd /opt/central && bash deploy/set-webhook.sh SLUG set`
3. `bash deploy/run-readiness.sh` مرتين ⇒ `SLUG READY` (إذا طلع TESTING/NEEDS_REVIEW راجع الفحص الساقط بـ`core.readiness_checks`).
4. العميل يكتب `/start` بنفس البوت ⇒ اللوحة، ثم `/accounts` و`/balance`.
5. تحقق: `bash deploy/set-webhook.sh SLUG info` ⇒ url المركزي، pending=0، بلا خطأ حديث.

## 4) تراجع
فعّل workflow البوت بالقديم (يسجّل webhook نفسه) أو أرجع رابط الـwebhook القديم. العميل بالمركزي يبقى كما هو بدون ضرر.

## 5) توثيق
أضف الصف بـ`out/clients.md` (البوت، المالك، البداية/النهاية، الحسابات، العملة، bc_id)، وحدّث سطر التواريخ بـCLAUDE.md.
