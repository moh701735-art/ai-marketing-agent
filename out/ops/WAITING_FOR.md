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
