//__LIB__
const ai = $('استخراج نتيجة الـAI1').first().json;
const chat = String($('قراءة رسالة تليجرام').first().json.chatId || '');
const norm = (s) => String(s || '').toLowerCase().replace(/[\sً-ٟـ_\-]/g, '').replace(/[أإآ]/g, 'ا').replace(/ة/g, 'ه');
const reply = (t) => [{ json: { kind: 'reply', finalMessage: t } }];
const ctx = $('تجهيز سياق الـAI').first().json;
const byId = {};
for (const h of (ctx.campaignHistory || [])) { if (h && h.campaign_id) byId[String(h.campaign_id)] = { ...(byId[String(h.campaign_id)] || {}), ...Object.fromEntries(Object.entries(h).filter(([k, v]) => v !== '' && v != null)) }; }
const camps = Object.values(byId);
let existing = [];
try { existing = $('جدولة: الأحداث الحالية').all().map(i => i.json).filter(r => r && r.sid && String(r.phone) === chat); } catch (e) {}
const active = existing.filter(r => r.status === 'active');
const wanted = norm(ai.campaign_name);
let camp = null;
if (ai.campaign_id) camp = camps.find(c => String(c.campaign_id) === String(ai.campaign_id)) || null;
if (!camp && wanted) { const m = camps.filter(c => { const n = norm(c.name); return n && (n.includes(wanted) || wanted.includes(n)); }); camp = m[m.length - 1] || null; }
const lastNames = camps.slice(-5).map(c => '• ' + (c.name || c.campaign_id)).join('\n');
const nameOf = (r) => '"' + (r.campaign_name || r.campaign_id) + '"';

if (ai.action === 'schedule_list') {
  if (!active.length) return reply('ماكو أي جدولة فعالة عندك هسه.');
  const g = {};
  for (const r of active) (g[r.campaign_id] = g[r.campaign_id] || []).push(r);
  const lines = [];
  for (const arr of Object.values(g)) {
    lines.push('📌 ' + nameOf(arr[0]) + ' (' + (arr[0].platform === 'tiktok' ? 'تيك توك' : 'فيسبوك') + ')');
    arr.sort((a, b) => String(a.time).localeCompare(String(b.time)));
    for (const r of arr) lines.push('   ' + (r.action === 'on' ? '▶️ تشغيل' : '⏸️ إيقاف') + ' — ' + (r.repeat === 'daily' ? 'كل يوم' : r.run_date) + ' الساعة ' + t12(r.time));
  }
  return reply('⏰ الجدولة الفعالة:\n' + lines.join('\n') + '\n\nللإلغاء اكتب: الغ جدولة حملة (اسم الحملة)');
}

if (ai.action === 'schedule_cancel') {
  let target = camp;
  if (!target) {
    const ids = [...new Set(active.map(r => r.campaign_id))];
    if (wanted) return reply('ما لكيت حملة باسم "' + ai.campaign_name + '" بحملاتك.\nآخر حملاتك:\n' + lastNames);
    if (ids.length === 1) target = { campaign_id: ids[0], name: active[0].campaign_name };
    else if (!ids.length) return reply('ماكو أي جدولة فعالة حتى ألغيها.');
    else return reply('أي حملة تريد ألغي جدولتها؟\n' + [...new Set(active.map(r => nameOf(r)))].join('\n'));
  }
  const mine = active.filter(r => String(r.campaign_id) === String(target.campaign_id));
  if (!mine.length) return reply('ماكو جدولة فعالة للحملة "' + (target.name || target.campaign_id) + '".');
  const msg = '✅ ألغيت ' + mine.length + ' جدولة للحملة "' + (target.name || target.campaign_id) + '". الحملة تبقى بحالتها الحالية.';
  return mine.map(r => ({ json: { ...r, kind: 'row', status: 'cancelled', last_result: 'cancelled ' + dateB + ' ' + hmB, finalMessage: msg } }));
}

// action === 'schedule'
const sch = Array.isArray(ai.schedule) ? ai.schedule : [];
if (!camp) {
  if (!wanted && !ai.campaign_id && camps.length === 1) camp = camps[0];
  else if (wanted || ai.campaign_id) return reply('ما لكيت حملة باسم "' + (ai.campaign_name || ai.campaign_id) + '" بحملاتك.\nآخر حملاتك:\n' + lastNames);
  else return reply('أي حملة تريد أجدولها؟ اكتب اسمها.\nآخر حملاتك:\n' + (lastNames || '(ماكو حملات مسجلة)'));
}
const { evs, enforce } = buildEvents(sch);
if (!evs.length) return reply('فهمت إنك تريد جدولة حملة "' + (camp.name || camp.campaign_id) + '" بس ما وضح لي الوقت. مثال: "شغل حملة ' + (camp.name || 'X') + ' الساعة 10 الصبح وطفيها الساعة 1 بالليل".');
const platform = /tik/i.test(String(camp.platform || '')) ? 'tiktok' : 'meta';
let advertiser = '';
if (platform === 'tiktok') {
  const n10 = (p) => String(p || '').replace(/\D/g, '').replace(/^00/, '').slice(-10);
  const mine = $('جلب العملاء (للـAI)').all().map(i => i.json).filter(r => r && r.tiktok_advertiser_id && n10(r.phone) === n10(ctx.from));
  const pick = mine.find(r => String(r.client || '').trim() === String(camp.client || '').trim()) || (mine.length === 1 ? mine[0] : null);
  advertiser = pick ? String(pick.tiktok_advertiser_id).replace(/\D/g, '') : '';
  if (!advertiser) return reply('ما كدرت أحدد حساب تيك توك الإعلاني لحملة "' + (camp.name || camp.campaign_id) + '". اكتب اسم العميل مع الطلب.');
}
const base = { phone: chat, client: camp.client || '', platform, advertiser_id: advertiser, campaign_id: camp.campaign_id, campaign_name: camp.name || '' };
const oldMine = active.filter(r => String(r.campaign_id) === String(camp.campaign_id));
const lines = describe(evs, enforce);
const msg = '✅ جدولة حملة "' + (camp.name || camp.campaign_id) + '" (' + (platform === 'tiktok' ? 'تيك توك' : 'فيسبوك') + '):\n' + lines.join('\n')
  + (oldMine.length ? '\n\n🔁 استبدلت ' + oldMine.length + ' جدولة قديمة لنفس الحملة.' : '')
  + '\n\nيتنفذ تلقائياً بدقة ±5 دقائق بتوقيت العراق، ويوصلك إشعار عند كل تنفيذ.\nلعرض الجدولة: "شنو المجدول"، ولإلغائها: "الغ جدولة حملة ' + (camp.name || 'X') + '".';
const rows = oldMine.map(r => ({ ...r, kind: 'row', status: 'cancelled', last_result: 'replaced ' + dateB + ' ' + hmB }))
  .concat(evs.map(e => mkRow(e, base)));
return rows.map(r => ({ json: { ...r, finalMessage: msg } }));
