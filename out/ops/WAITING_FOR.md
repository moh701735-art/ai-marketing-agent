# Waiting For

| Item | Who | Since | Next Action |
|------|-----|-------|-------------|
| صرف الحملة الفعلي (7.775M IQD) من TikTok Ads Manager + رقم الحملة والمجموعة | المالك | 2026-11-17 | يصوّرها؛ نحتاجها للتعويض وملف الإثبات |
| أي بوت/عميل أرسل طلب الـ5000؟ | المالك | 2026-11-17 | يخبرنا |
| تأكيد تطبيق p199 (`grep -c p199 n8n/wf_ingress.py` > 0) ثم تطبيق p200 | المالك | 2026-11-17 | يلصق الأمر واحد واحد وينتظر المؤشر `#` |
| ناتج `grep` على `n8n/wf_monitor.py` (ليش ما أوقفت قاعدة 0.3$ الحملة) | المالك | 2026-11-17 | يشغّل الأمر ويصوّر بدون ترجمة |
| مدة اشتراك زينة محمد الحقيقية | المالك | 2026-11-17 | يعطينا الأيام/التاريخ |
| تجربة معالج سناب الجديد بفيديو حقيقي | المالك | 2026-11-17 | يجرب من بوت موهم ويصوّر |
| بيانات علي القريشي: الأيام المتبقية، حساباته بتيك توك، العملة | المالك | 2026-11-17 | عند الاستئناف |
| قرار التعويض مع العميل المتضرر | المالك + العميل | 2026-11-17 | قرار تجاري؛ نحن نجهّز ملف الإثبات |
| نتيجة فحص حسابات تيك توك (p203) + تجربة «زيارات»/واجهة تيك توك اليدوية لسبب رفض create_campaign بحساب بنين ودالية | المالك | 2026-11-17 | يلصق out/p203s.txt ويصوّر |
| تجربة مصطفى حويجه (`/start` ثم `/accounts` المفروض 21 ثم `/balance`) من بوته | المالك + العميل | 2026-11-18 | بعد READY؛ يصوّر الردود |
| ناتج p206 الكامل كنص (الأقسام 3 و8 و9 والخلاصة) وأخطاء إنشاء الحملات | المالك | 2026-11-18 | ينسخ الناتج نصاً مو صورة |
| سجل Broker لحملة «موبايل» (`guard-stop-1882108700798066`) + وقت الصرف والمبلغ من تيك توك | المالك | 2026-11-18 | يثبت إذا أمر الإيقاف انطبق |
- 18-11: p213b (`out/p213bs.txt`) sent/ready — owner runs it, then tests (a)(b)(c) above; rollback `n8n/wf_ingress.py.pre213b` + `bash deploy/update.sh`.
- 18-11: p213b applied + verified by owner (done). Next chosen: p210 (deploy must not flip tenants to NEEDS_REVIEW): waiting for owner's step-0 text paste (update.sh + wf_readiness R03 greps).
- 18-11: p210 (`out/p210s.txt`) built — owner runs it (it deploys); expect «-- p210: ingress webhook registered after Ns» and all tenants READY without waiting. Rollback: `cp deploy/update.sh.pre210 deploy/update.sh`.
- 18-11: p210 applied + verified (done). Remaining open: p201b (guard stop text + report rule line; need wf_monitor.py/wf_job_report.py text), «موبايل» kept spending after guard `stopped` (Broker log guard-stop-1882108700798066), rotate BROKER_HMAC_KEY/ADMIN_KEY, hide Smart button, Meta/Snap Iraq-only, +964 lead filter.
- 18-11: p201b (`out/p201bs.txt`) sent — owner runs it (deploys). Next: hourly report rule line (needs `grep -n "rule\|noRes\|zero" n8n/wf_job_report.py` as TEXT).
- 18-11: p201b applied. Next: hourly-report rule line (wf_job_report.py grep as TEXT), then rotate exposed keys / hide Smart button / Iraq-only for Meta+Snap.
- 18-11: p201c (`out/p201cs.txt`) sent — owner runs it (deploys); then check the next hourly report shows «🛡 الحارس…» under each TikTok campaign. Rollback: `cp n8n/wf_job_report.py.pre201c n8n/wf_job_report.py` + update.sh.
- 19-11: p201c v2 sent (owner to run); p197e (`out/p197es.txt`) built — owner runs, then ONE Snap retry to read Snap's real rejection; delete draft campaign 7ccf6d9b-c94a-4397-90b0-7d8dfaca7105 in Snap Ads Manager.
- 19-11: p197e applied (Snap shows real reasons). p197f (`out/p197fs.txt`) built: owner runs it, retries ONE Snap sales launch; if still E3017 → the pixel lacks Purchase events (business-side) → use traffic/leads objective or fire the pixel first. Delete 3 leftover draft campaigns in Snap Ads Manager.
- 19-11: order page template built (`out/landing/order-page`); waiting for product details + WhatsApp number to publish on Netlify; owner still to answer: auto-delete empty Snap drafts (yes/no), p201c status (markers p201c=3?), delete 4 leftover Snap drafts.
- 19-11: `out/ttcleans.txt` (removes inactive interest 3412382896 from mohm «جمهور 1») sent; delete partial TikTok campaign 1882297114773570; then retry the launch. Next: prevention patch (pre-validate interest_ids in Broker launch) — needs server service.py excerpt. Also new client عمار (ammar-mohmaed, IQD, 30 days → 2026-12-19) waiting for add-tenant run.
- 19-11: p214 (`out/p214s.txt`) built — owner runs it (deploys Broker), then retries the «اختار جمهور 1» launch; also delete partial TikTok campaign 1882297114773570. New client عمار (ammar-mohmaed) still waiting.
- 19-11: عمار (`ammar-mohmaed`) created + linked + READY; waiting for the client's /start, /accounts, /balance test. p214 result (markers p214=2 + retry of «اختار جمهور 1» launch) still unconfirmed by owner.
- 19-11: agency switch for عمار done (new 3 accounts active, old 3 unlinked, READY). Waiting: client's /accounts + /balance check in Telegram.
- 19-11: p215 (`out/p215s.txt`) built — owner runs it (deploys Broker + creates api.tenant_countries), THEN `out/p215mohm.txt` (opens Gulf countries for mohm only), then retries the PUBG launch.
- 19-11 URGENT: p215 broke all TikTok launches → `out/p215bs.txt` hotfix must be applied NOW (owner). After it: retry PUBG Gulf launch (mohm has allowed_countries set). All TikTok launches (all tenants) fail until then.
- 19-11: p216 (`out/p216s.txt`) built (LLM parser retry on bad_response) — owner runs it, then resends the long PUBG message (also test /report etc. still fine). Still pending: PUBG Gulf launch result after p215b (blocked by this parser failure), p214 verification, عمار /accounts+/balance test, Snap pixel/dresses page, leftover drafts cleanup.
- 19-11: p217 (`out/p217s.txt`) built — owner runs it AFTER p216 (`out/p216s.txt`, still not applied: marker was 0 at 21:50). Then resend the PUBG message: expect no `llm.parse_command` call (log line `p217 cmdparse hit`), then the Gulf countries pass p215b/mohm allow-list.
- (20-11) عمار NEEDS_REVIEW: ينتظر تفويض تيك توك جديد (رابط out/client-migration.md، نفس تسجيل الدخول اللي يشوف الحسابات الثلاثة) ثم `python3 ops/relink-tiktok-token.py` (فحص) ثم `--apply`، ثم run-readiness ×2 وتجربة /start /accounts /balance. لا تشغّل unlink-connection لأي عميل لحد p219.
- (20-11) تيبا محمد `tipa-mohammed`: انربط بالوكالة الصحيحة وفُكّت الغلط. ينتظر: جاهزية مرتين + `/accounts` من بوته (3 حسابات جديدة فقط) + مراقبة R12 بعد 30 دقيقة وساعة. عمار: ينتظر لقطة `/accounts` و`/balance` من تلغرام. اقتراح: بث فيديو لكل البوتات (`ops/broadcast.py`) ينتظر إجابات المالك (حجم الفيديو، النص، المستلمون، الاستثناءات).
- (20-11) p220: صفحة واتساب أولى `https://wa.twasuliraq.com/w/hcnvkwua` (mohm، +9647829503973، «فستان») أُنشئت وCaddy حمّلها؛ ينتظر: تأكيد فتحها من الجوال + نتيجة مراجعة سناب بعد رفع حملة برابطها. إذا رُفضت لقلة المحتوى: نضيف صورة/فقرة. عمار وتيبا: ينتظران لقطات /accounts من تلغرام.
- (20-11) p221 (`out/p221s.txt`): رفع سناب من رسالة نصية + فيديو، مبني ومختبر (133+22 اختبار JS + محاكاة الرقعة) ولم يُنشر بعد؛ بعد النشر: المالك يجرب الرسالة بـ«زيارات» أولاً ويرسل الشاشة. سؤال معلّق: كيف يصل نص كابشن الفيديو بالـingress (`d.text` أو `d.caption`)؛ القاعدة تقرأ الاثنين.
