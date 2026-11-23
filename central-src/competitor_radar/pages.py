# -*- coding: utf-8 -*-
"""competitor_radar/pages.py — 🕵️ رادار المنافسين (واجهة تيليغرام). Module مستقل بنفس نمط guide/smart_audience:
build(b, w, sw, idx, reply, CRT) يضيف العقد:
  CR: data (PG: مفتاح التشغيل + حالة الجلسة + مفتاح التوقيع) → CR: plan → (need?) → CR: sign → CR: http (خدمة الرادار الداخلية) → CR: render → CR: save → CR: reply
لا Broker ولا أي منصة إعلانات. الخدمة لا تُستدعى إلا بطلب موقّع (HMAC) ويفرض عزل العميل بالقاعدة من ctx.
callback_data (≤48): cr:m | cr:a | cr:p:<منصة> | cr:l | cr:ls | cr:c:<id> | cr:r:<id> | cr:o:<id> | cr:x:<id> | cr:s:<id> | cr:n:<id> | cr:d:<id> | cr:dd:<id> | cr:k | cr:sp
النص: /radar أو /رادار ؛ والنص الحر يُوجَّه هنا فقط لما تكون حالة cr:<chat> بخطوة إدخال (add/smp/mk).
كل مخرجات الرادار «تحليل وتوصية» مع شارة ثقة؛ لا يُنشأ/يُشغَّل/يُعدَّل أي شي بالحملات."""
import json

SQL_DATA = ("SELECT 'cfg'::text AS kind, competitor_radar.config($1)::text AS a, NULL::text AS b "
            "UNION ALL SELECT 'state', data::text, age_s::text FROM api.ui_get($1, 'cr:' || $2) "
            "UNION ALL SELECT 'key', competitor_radar.service_key(), NULL")

SQL_SAVE = ("SELECT CASE WHEN $3::text <> '' THEN api.ui_set($1, 'cr:' || $2, 'v', coalesce(nullif($3::text, ''), '{}')::jsonb, 1800)::text END AS saved")

LIB = r"""
const sh = (s, n) => { s = String(s == null ? '' : s); return s.length > n ? s.slice(0, n - 1) + '…' : s; };
const IC = { high: '🟢', medium: '🟡', low: '🔴' }, LB = { high: 'ثقة عالية', medium: 'ثقة متوسطة', low: 'ثقة منخفضة' };
const badge = l => (IC[l] || '🔴') + ' ' + (LB[l] || LB.low);
const PL = { tiktok: '🎵 TikTok', instagram: '📸 Instagram', facebook: '📘 Facebook', snapchat: '👻 Snapchat', other: '🌐 أخرى' };
const ST = { new: '⚪ جديد', done: '🟢 تم التحليل', insufficient: '🟡 بيانات غير كافية', failed: '🔴 فشل' };
const LINE = '━━━━━━━━━━━━';
const HOME = [{ t: '🕵️ الرادار', c: 'cr:m' }, { t: '🏠 الرئيسية', c: 'h' }];
const UID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
"""

JS_PLAN = r"""
const d = $('Route').first().json;
const rows = $input.all().map(i => i.json);
let cfg = {}; try { cfg = JSON.parse((rows.find(r => r.kind === 'cfg') || {}).a || '{}'); } catch (e) {}
const key = String((rows.find(r => r.kind === 'key') || {}).a || '');
let S = {}; { const r = rows.find(r => r.kind === 'state'); if (r && Number(r.b) < 1800) { try { S = JSON.parse(r.a) || {}; } catch (e) {} } }
const isCb = !!d.cb;
const base = { ctx: d.ctx, chatId: d.chatId, edit: isCb, need: false, state: '' };
const say = (text, kb, state) => [{ json: { ...base, text, keyboard: kb || [HOME], state: state === undefined ? '{}' : JSON.stringify(state) } }];
if (!cfg.enabled) return say('🕵️ رادار المنافسين غير مفعّل لحسابك حالياً.', [[{ t: '🏠 الرئيسية', c: 'h' }]]);
if (!key) return say('⚠️ رادار المنافسين غير مهيأ بعد (مفتاح الخدمة). تواصل مع الإدارة.', [[{ t: '🏠 الرئيسية', c: 'h' }]]);
const call = (op, body, ui) => [{ json: { ...base, need: true, op, body: body || {}, key, ui: ui || {}, S } }];
let op = 'm', arg = '', text = '';
if (isCb) { const p = String(d.cb).split(':'); op = p[1] || 'm'; arg = p.slice(2).join(':'); } else { text = String(d.args || '').trim(); op = text && S.st ? 'text' : 'm'; }
const id = UID.test(arg) ? arg : '';
if (op === 'm') return say('🕵️ رادار المنافسين\n' + LINE + '\nحلّل منافسيك من معلومات عامة متاحة فقط (نصوص تلصقها أو روابط عامة)، وحوّل التحليل لخطة أصلية.\nما يُنشأ ولا يُعدَّل أي شي بحملاتك، والتقارير تحليلات وتوصيات وليست حقائق مؤكدة.',
  [[{ t: '➕ إضافة منافس', c: 'cr:a' }, { t: '📊 منافسي', c: 'cr:l' }], [{ t: '🌎 رادار السوق', c: 'cr:k' }, { t: '🥊 خطة المنافسة', c: 'cr:sp' }], [{ t: '⬅️ رجوع', c: 'h' }]]);
if (op === 'a') return say('➕ إضافة منافس\nاختر المنصة:', [[{ t: PL.tiktok, c: 'cr:p:tiktok' }, { t: PL.instagram, c: 'cr:p:instagram' }], [{ t: PL.facebook, c: 'cr:p:facebook' }, { t: PL.snapchat, c: 'cr:p:snapchat' }], [{ t: '🌐 أخرى', c: 'cr:p:other' }, { t: '⬅️ رجوع', c: 'cr:m' }]]);
if (op === 'p') { const pl = ['tiktok', 'instagram', 'facebook', 'snapchat', 'other'].includes(arg) ? arg : ''; if (!pl) return say('⚠️ منصة غير معروفة.');
  return say('➕ منافس على ' + PL[pl] + '\nأرسل الآن بسطرين:\n1) اسم المنافس أو النشاط\n2) رابط عام للصفحة أو الحساب (اختياري)\n\nمعلومات عامة فقط، لا حسابات خاصة ولا بيانات دخول.', [[{ t: '⬅️ إلغاء', c: 'cr:m' }]], { st: 'add', pl }); }
if (op === 'k') return say('🌎 رادار السوق\nاكتب وصف السوق بالسطر الأول، مثل: فساتين نسائية في العراق\n(اختياري) من السطر الثاني الصق عينات من إعلانات/منشورات السوق وافصل بينها بسطر فارغ.\nالتحليل يعتمد على منافسيك المحللين + عينات تلصقها. أي شي من معرفة عامة يُعلَّم 🔴.', [[{ t: '⬅️ إلغاء', c: 'cr:m' }]], { st: 'mk' });
if (op === 'text') {
  if (S.st === 'add') {
    const lines = text.split('\n').map(x => x.trim()).filter(Boolean); const name = lines.filter(x => !/^https?:\/\//i.test(x))[0] || ''; const url = (lines.find(x => /^https?:\/\/\S+$/i.test(x)) || '');
    if (!name || name.length > 80) return say('⚠️ اكتب اسم المنافس (حد أقصى 80 حرف) بالسطر الأول.', [[{ t: '⬅️ إلغاء', c: 'cr:m' }]], S);
    return call('competitor_add', { platform: S.pl, name: name, ...(url ? { url: url } : {}) }, { kind: 'added' });
  }
  if (S.st === 'smp' && UID.test(String(S.id || ''))) return call('competitor_samples', { id: S.id, text: text }, { kind: 'samples', id: S.id });
  if (S.st === 'mk') { const parts = text.split('\n'); const q = parts[0].trim(); const rest = parts.slice(1).join('\n').trim(); return call('market', { query: q, ...(rest ? { text: rest } : {}) }, { kind: 'market' }); }
  return say('اختر من القائمة:', [[{ t: '🕵️ الرادار', c: 'cr:m' }]]);
}
if (op === 'l' || op === 'ls') return call('competitor_list', {}, { kind: op === 'ls' ? 'list_s' : 'list' });
if (op === 'sp') return call('competitor_list', {}, { kind: 'list_s' });
if (!id && ['c', 'r', 'o', 'x', 's', 'n', 'd', 'dd'].includes(op)) return say('⚠️ معرّف غير صالح.');
if (op === 'c') return call('competitor_get', { id }, { kind: 'comp', id });
if (op === 'r') return call('report', { id }, { kind: 'report', id });
if (op === 'o') return call('report', { id }, { kind: 'opps', id });
if (op === 'x') return call('analyze', { id, force: true }, { kind: 'analyzed', id });
if (op === 's') return call('strategy', { id }, { kind: 'strategy', id });
if (op === 'n') return say('📝 أضف عينات للمنافس\nالصق نص منشورات/إعلانات/وصف المنافس، وافصل بين كل عينة وعينة بسطر فارغ (حتى 30 عينة).\nبعدها اضغط تحليل.', [[{ t: '⬅️ إلغاء', c: 'cr:c:' + id }]], { st: 'smp', id });
if (op === 'd') return say('🗑 حذف المنافس من رادارك؟\nيُحذف تقريره وعيناته نهائياً.', [[{ t: '✅ نعم احذف', c: 'cr:dd:' + id }, { t: '❌ لا', c: 'cr:c:' + id }]]);
if (op === 'dd') return call('competitor_delete', { id }, { kind: 'deleted' });
return say('اختر من القائمة:', [[{ t: '🕵️ الرادار', c: 'cr:m' }]]);
"""

JS_SIGN = r"""
const p = $input.first().json;
const raw = JSON.stringify({ ctx: p.ctx, ...p.body });
const ts = String(Math.floor(Date.now() / 1000));
const K = [0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2];
const rotr = (x, n) => (x >>> n) | (x << (32 - n));
const sha256 = (bytes) => {
  const l = bytes.length, nb = ((l + 9 + 63) >> 6) << 6, m = new Uint8Array(nb); m.set(bytes); m[l] = 0x80;
  const dv = new DataView(m.buffer); dv.setUint32(nb - 8, Math.floor((l * 8) / 4294967296)); dv.setUint32(nb - 4, (l * 8) >>> 0);
  let h = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]; const w = new Array(64);
  for (let o = 0; o < nb; o += 64) {
    for (let i = 0; i < 16; i++) w[i] = dv.getUint32(o + i * 4);
    for (let i = 16; i < 64; i++) { const s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >>> 3), s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >>> 10); w[i] = (w[i - 16] + s0 + w[i - 7] + s1) | 0; }
    let [a, b, c, d, e, f, g, hh] = h;
    for (let i = 0; i < 64; i++) { const S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25), ch = (e & f) ^ (~e & g), t1 = (hh + S1 + ch + K[i] + w[i]) | 0, S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22), mj = (a & b) ^ (a & c) ^ (b & c), t2 = (S0 + mj) | 0; hh = g; g = f; f = e; e = (d + t1) | 0; d = c; c = b; b = a; a = (t1 + t2) | 0; }
    h = [(h[0] + a) | 0, (h[1] + b) | 0, (h[2] + c) | 0, (h[3] + d) | 0, (h[4] + e) | 0, (h[5] + f) | 0, (h[6] + g) | 0, (h[7] + hh) | 0];
  }
  const out = new Uint8Array(32); const ov = new DataView(out.buffer); h.forEach((x, i) => ov.setUint32(i * 4, x >>> 0)); return out;
};
const enc = s => Uint8Array.from(Buffer.from(String(s), 'utf8'));
const hmac = (key, msg) => { let k = enc(key); if (k.length > 64) k = sha256(k); const ik = new Uint8Array(64), ok = new Uint8Array(64); for (let i = 0; i < 64; i++) { const v = k[i] || 0; ik[i] = v ^ 0x36; ok[i] = v ^ 0x5c; } const cat = (a, b) => { const r = new Uint8Array(a.length + b.length); r.set(a); r.set(b, a.length); return r; }; return sha256(cat(ok, sha256(cat(ik, msg)))); };
const sig = Array.from(hmac(p.key, enc(ts + '.' + '/v1/' + p.op + '.' + raw))).map(x => x.toString(16).padStart(2, '0')).join('');
return [{ json: { url: 'http://radar:8088/v1/' + p.op, raw, ts, sig } }];
"""

JS_RENDER = r"""
const P = $('CR: plan').first().json;
const r = $input.first().json;
const kb = (rows) => rows.slice(0, 8);
const done = (text, rows, state) => [{ json: { ctx: P.ctx, chatId: P.chatId, edit: P.edit, text: sh(text, 3800), keyboard: kb(rows || [HOME]), state: state === undefined ? '{}' : JSON.stringify(state) } }];
if (!P.need) return [{ json: { ctx: P.ctx, chatId: P.chatId, edit: P.edit, text: sh(P.text, 3800), keyboard: kb(P.keyboard || [HOME]), state: P.state } }];
const ui = P.ui || {};
const back = [{ t: '🕵️ الرادار', c: 'cr:m' }, { t: '🏠 الرئيسية', c: 'h' }];
if (!r || r.ok !== true) {
  const e = (r && r.error) || {}; const cls = String(e.class || '');
  const msg = { disabled: '🕵️ الرادار غير مفعّل حالياً.', rate_limited: '⏳ ' + (e.message || 'طلبات كثيرة، جرّب بعد قليل.'), limit: '⚠️ ' + (e.message || 'وصلت الحد الأقصى من المنافسين.'), no_report: '⚠️ ما في تقرير بعد. اضغط «تحليل» أولاً.', not_found: '⚠️ المنافس غير موجود.',
    bad_url: '⚠️ ' + (e.message || 'الرابط غير مقبول.'), invalid_params: '⚠️ ' + (e.message || 'مدخلات غير صالحة.'), no_samples: '⚠️ ' + (e.message || 'ما لقيت نصاً صالحاً.'), internal: '⚠️ خطأ داخلي بالرادار (لم يتأثر أي شي آخر).' }[cls];
  const keep = ['bad_url', 'invalid_params', 'no_samples'].includes(cls);
  const rowsE = ui.id ? [[{ t: '📄 المنافس', c: 'cr:c:' + ui.id }, back[0]]] : [back];
  return done(msg || '⚠️ خدمة الرادار غير متاحة حالياً. لم يتأثر أي شي بحملاتك، جرّب لاحقاً.', keep ? [[{ t: '⬅️ إلغاء', c: 'cr:m' }]] : rowsE, keep ? (P.S || {}) : {});
}
const D = r.data || {};
const compRows = (id, c) => [[{ t: '📊 التقرير', c: 'cr:r:' + id }, { t: '💡 الفرص', c: 'cr:o:' + id }], [{ t: '🥊 خطة المنافسة', c: 'cr:s:' + id }, { t: '🔄 إعادة التحليل', c: 'cr:x:' + id }], [{ t: '📝 إضافة عينات', c: 'cr:n:' + id }, { t: '🗑 حذف من راداري', c: 'cr:d:' + id }], [{ t: '📋 منافسي', c: 'cr:l' }, back[1]]];
const evN = x => (x && x.evidence && x.evidence.length) ? ' [' + x.evidence.length + ' عينة]' : '';
const fmtReport = (R) => {
  if (R.status !== 'ok') return '⚠️ بيانات غير كافية للتحليل.\n' + (R.needs || '') + '\n(لا يوجد ما نخمّنه — الرادار ما يخترع معلومات.)';
  const L = [];
  L.push('🏪 معلومات النشاط\n• الاسم: ' + (R.business.name || 'غير متاح') + '\n• المجال (استنتاج): ' + (R.business.domain || 'غير واضح') + '\n• المنصة: ' + (PL[R.platform] || R.platform) + '\n• عدد العينات المحللة: ' + R.usable_samples);
  if ((R.products || []).length) L.push('🛍️ المنتجات الظاهرة\n' + R.products.slice(0, 5).map(p => '• ' + p.name + ' (' + p.count + ' عينة) ' + badge(p.level)).join('\n'));
  if ((R.messages || []).length) L.push('🎯 الرسائل التسويقية (تحليل مو حقائق)\n' + R.messages.slice(0, 5).map(m => '• ' + m.label + ' — ' + m.count + '/' + m.of + ' ' + badge(m.level) + (m.quotes && m.quotes[0] ? '\n   «' + sh(m.quotes[0], 70) + '»' : '')).join('\n'));
  const c = R.content || {};
  const cl = []; if ((c.ctas || []).length) cl.push('• دعوة لإجراء: «' + c.ctas[0].phrase + '» ' + badge(c.ctas[0].level)); if ((c.hooks || []).length) cl.push('• بدايات جذابة: ' + c.hooks.length + ' عينة'); if (c.video_mentions) cl.push('• إشارات لفيديو: ' + c.video_mentions); if ((c.repeated || []).length) cl.push('• أفكار متكررة: ' + c.repeated.length);
  L.push('🎬 تحليل المحتوى\n' + (cl.length ? cl.join('\n') : '⚠️ بيانات غير كافية للتحليل.'));
  if ((R.strengths || []).length) L.push('💪 نقاط قوة (مبنية على البيانات)\n' + R.strengths.slice(0, 5).map((s, i) => (i + 1) + '. ' + s.text + ' ' + badge(s.level) + (s.kind === 'ai' ? ' · توصية AI' : '')).join('\n'));
  L.push('الثقة الكلية: ' + badge(R.overall_confidence) + '\n' + (R.disclaimer || ''));
  return L.join('\n\n');
};
const fmtOpps = (R) => R.status !== 'ok' ? '⚠️ بيانات غير كافية للتحليل.' : ((R.opportunities || []).length ? '💡 فرص محتملة (توصيات وليست حقائق)\n\n' + R.opportunities.slice(0, 6).map((o, i) => (i + 1) + '. ' + o.text + ' ' + badge(o.level) + (o.kind === 'ai' ? ' · توصية AI' : '')).join('\n\n') : 'ما ظهرت فرص واضحة من العينات الحالية. أضف عينات أكثر.');
const fmtPlan = (Pn) => {
  if (Pn.status === 'insufficient' || Pn.status === 'blocked') return '⚠️ ' + Pn.message;
  return '🥊 خطة المنافسة (توصية أصلية — ما تنسخ المنافس)\n' + LINE + '\n🎯 الزاوية المقترحة: ' + Pn.angle.label + '\n   ' + Pn.angle.why + '\n\n🪝 Hook مقترح:\n' + Pn.hook + '\n\n🎬 فكرة إعلان:\n' + Pn.ad_idea + '\n\n📣 CTA:\n' + Pn.cta + '\n\n👥 الجمهور المقترح:\n' + Pn.audience +
    '\n\n🧪 اختبارات مقترحة:\n' + Pn.tests.map((t, i) => (i + 1) + '. [' + t.angle + '] ' + t.hook + '\n   ' + t.idea).join('\n') + '\n\n💰 ميزانية الاختبار:\n' + Pn.budget + '\n\n' + badge(Pn.confidence) + (Pn.source === 'ai' ? ' · صياغة AI' : '') + '\n' + (Pn.disclaimer || '') + '\n✅ فحص الأصالة: تطابق ' + Math.round((Pn.originality.max_overlap || 0) * 100) + '%';
};
const fmtMarket = (M) => {
  if (M.status === 'invalid' || M.status === 'insufficient') return '⚠️ ' + M.message;
  const L = ['🌎 رادار السوق: ' + sh(M.query, 80) + '\nالمصادر: ' + M.sources.competitor_reports + ' تقرير منافس + ' + M.sources.pasted_samples + ' عينة ملصوقة'];
  if ((M.frequent_products || []).length) L.push('🛍️ الأكثر ظهوراً\n' + M.frequent_products.map(p => '• ' + p.name + ' (' + p.sources + ') ' + badge(p.level)).join('\n'));
  if ((M.frequent_angles || []).length) L.push('🎯 زوايا متكررة\n' + M.frequent_angles.map(a => '• ' + a.label + ' (' + a.sources + ') ' + badge(a.level)).join('\n'));
  const o = (M.opportunities || []).map((x, i) => (i + 1) + '. ' + x.text + ' ' + badge(x.level));
  if (o.length) L.push('💎 Market Opportunities (فرضيات للاختبار)\n' + o.join('\n'));
  if ((M.model_knowledge || []).length) L.push('🔴 معرفة عامة وليست بيانات حية\n' + M.model_knowledge.map(x => '• ' + x.text).join('\n'));
  L.push(M.note || ''); return L.join('\n\n');
};
const k = ui.kind;
if (k === 'added') { const id = D.id; return done('✅ انضاف المنافس.\nالحين الصق عينات من محتواه (نص منشورات/إعلانات/وصف)، وافصل بين كل عينة وعينة بسطر فارغ. أو اضغط تحليل إذا انحطّ له رابط عام.', [[{ t: '🔎 حلّل الآن', c: 'cr:x:' + id }, { t: '📄 المنافس', c: 'cr:c:' + id }], [back[0]]], { st: 'smp', id }); }
if (k === 'samples') return done('✅ انضافت ' + D.added + ' عينة (المجموع ' + D.total + ').\nتقدر تلصق عينات أكثر، أو اضغط تحليل.', [[{ t: '🔎 حلّل الآن', c: 'cr:x:' + ui.id }, { t: '📄 المنافس', c: 'cr:c:' + ui.id }]], { st: 'smp', id: ui.id });
if (k === 'list' || k === 'list_s') {
  const all = D.competitors || [], cs = all.slice(0, 7);   // 7 + صف الرجوع = 8 صفوف (حد تيليغرام/الواجهة)
  if (!cs.length) return done('📊 منافسي\nما أضفت منافسين بعد.', [[{ t: '➕ إضافة منافس', c: 'cr:a' }], [back[0], back[1]]]);
  return done((k === 'list_s' ? '🥊 اختر المنافس لخطة المنافسة:\n' : '📊 منافسي (' + (D.competitors || []).length + ')\n') + cs.map(c => '• ' + sh(c.name, 30) + ' — ' + (ST[c.status] || c.status) + (c.confidence ? ' ' + IC[c.confidence] : '')).join('\n') + (all.length > 7 ? '\n… و' + (all.length - 7) + ' غيرهم (احذف القديم لرؤية البقية)' : ''),
    cs.map(c => [{ t: sh(c.name, 28), c: (k === 'list_s' ? 'cr:s:' : 'cr:c:') + c.id }]).concat([[back[0], back[1]]]));
}
if (k === 'comp') { const c = D.competitor; return done('🕵️ ' + c.name + '\nالحالة: ' + (ST[c.status] || c.status) + '\nالمنصة: ' + (PL[c.platform] || c.platform) + '\nالعينات: ' + c.samples + (c.url ? '\nالرابط: ' + sh(c.url, 60) : '') + (c.confidence ? '\nالثقة: ' + badge(c.confidence) : ''), compRows(c.id, c)); }
if (k === 'report' || k === 'analyzed') { const R = D.report; return done((k === 'analyzed' ? (D.cached ? '♻️ تقرير محفوظ (أقل من 24 ساعة)\n' : '✅ تم التحليل\n') : '') + fmtReport(R), compRows(ui.id)); }
if (k === 'opps') return done(fmtOpps(D.report), compRows(ui.id));
if (k === 'strategy') return done(fmtPlan(D.plan), compRows(ui.id));
if (k === 'market') return done(fmtMarket(D.market), [[{ t: '🌎 تحليل سوق ثاني', c: 'cr:k' }], back]);
if (k === 'deleted') return done(D.deleted ? '🗑 انحذف المنافس من راداري.' : '⚠️ ما انحذف (غير موجود).', [[{ t: '📋 منافسي', c: 'cr:l' }, back[1]]]);
return done('تم.', [back]);
"""

JS_REPLY = r"""
const r = $input.first().json;
return [{ json: { ctx: r.ctx, chatId: r.chatId, text: r.text, keyboard: r.keyboard, edit: r.edit } }];
"""

def build(b, w, sw, idx, reply, CRT):
    code, pg = b.code, b.pg
    data = pg(w, "CR: data", SQL_DATA, "={{ [$('Route').first().json.ctx, String($('Route').first().json.chatId)] }}", CRT, always=True)
    w.nodes[-1]["onError"] = "continueRegularOutput"
    plan = code(w, "CR: plan", LIB + JS_PLAN)
    need = w.add("CR: need call?", "n8n-nodes-base.switch", 3.5, {"mode": "expression", "numberOutputs": 2, "output": "={{ $json.need ? 1 : 0 }}"})
    sign = code(w, "CR: sign", JS_SIGN)
    http = w.add("CR: http", "n8n-nodes-base.httpRequest", 4.2, {
        "method": "POST", "url": "={{ $json.url }}", "sendHeaders": True, "specifyHeaders": "keypair",
        "headerParameters": {"parameters": [{"name": "x-radar-ts", "value": "={{ $json.ts }}"}, {"name": "x-radar-sig", "value": "={{ $json.sig }}"}]},
        "sendBody": True, "contentType": "raw", "rawContentType": "application/json", "body": "={{ $json.raw }}",
        "options": {"timeout": 25000, "response": {"response": {"neverError": True, "responseFormat": "json"}}}})
    w.nodes[-1]["onError"] = "continueRegularOutput"
    w.nodes[-1]["alwaysOutputData"] = True
    render = code(w, "CR: render", LIB + JS_RENDER)
    save = pg(w, "CR: save state", SQL_SAVE, "={{ [$json.ctx, String($json.chatId), $json.state || ''] }}", CRT, always=True)
    w.nodes[-1]["onError"] = "continueRegularOutput"
    out = reply("CR: reply", JS_REPLY)
    w.chain(data, plan, need)
    w.link(need, render, 0)
    w.link(need, sign, 1)
    w.chain(sign, http, render)
    w.chain(render, out)
    w.link(render, save)   # حفظ حالة الجلسة بفرع جانبي: فشله ما يمنع الرد
    w.link(sw, data, idx)
