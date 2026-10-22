const B = new Date(Date.now() + 3 * 3600 * 1000);
const dateB = B.toISOString().slice(0, 10), hmB = B.toISOString().slice(11, 16);
const inp = $input.first().json;
const addDays = (d, n) => new Date(Date.parse(d + 'T00:00:00Z') + n * 86400000).toISOString().slice(0, 10);
const t12 = (hm) => { const p = String(hm).split(':').map(Number); const h = p[0], m = p[1]; return (h % 12 || 12) + ':' + String(m).padStart(2, '0') + ' ' + (h < 12 ? 'ص' : 'م'); };
const normT = (v) => { const m = String(v || '').trim().match(/^([01]?\d|2[0-3]):([0-5]\d)$/); return m ? String(m[1]).padStart(2, '0') + ':' + m[2] : ''; };
function buildEvents(sch) {
  const evs = [];
  for (const s of (Array.isArray(sch) ? sch : [])) {
    if (!s) continue;
    const action = (s.action === 'on' || s.action === 'off') ? s.action : '';
    if (!action) continue;
    const isNow = String(s.time || '').trim() === 'now';
    let time = isNow ? hmB : normT(s.time);
    if (!time) continue;
    if (s.repeat === 'daily' && !isNow) {
      evs.push({ action, repeat: 'daily', time, run_date: '', last_run_date: time <= hmB ? dateB : '' });
    } else {
      let d;
      const day = String(s.day || '').trim();
      if (isNow) d = dateB;
      else if (/^\d{4}-\d{2}-\d{2}$/.test(day)) d = day;
      else if (day === 'tomorrow') d = addDays(dateB, 1);
      else d = time >= hmB ? dateB : addDays(dateB, 1);
      evs.push({ action, repeat: 'once', time, run_date: d, last_run_date: '' });
    }
  }
  const don = evs.find(e => e.repeat === 'daily' && e.action === 'on'), doff = evs.find(e => e.repeat === 'daily' && e.action === 'off');
  let enforce = '';
  if (don && doff) {
    const inW = don.time < doff.time ? (hmB >= don.time && hmB < doff.time) : (hmB >= don.time || hmB < doff.time);
    enforce = inW ? 'on' : 'off';
    evs.push({ action: enforce, repeat: 'once', time: hmB, run_date: dateB, last_run_date: '' });
  }
  return { evs, enforce };
}
function describe(evs, enforce) {
  const dayWord = (d) => d === dateB ? 'اليوم' : (d === addDays(dateB, 1) ? 'باجر' : d);
  return evs.map(e => {
    const w = e.action === 'on' ? '▶️ تشغيل' : '⏸️ إيقاف';
    if (e.repeat === 'daily') return w + ' — كل يوم الساعة ' + t12(e.time);
    if (enforce && e.time === hmB && e.run_date === dateB && e.action === enforce) return (e.action === 'on' ? '▶️ تشغيل' : '⏸️ إيقاف') + ' — هسه (لأن الوقت الحالي ' + (e.action === 'on' ? 'داخل' : 'خارج') + ' الفترة المحددة)';
    if (e.time === hmB && e.run_date === dateB) return w + ' — هسه';
    return w + ' — ' + dayWord(e.run_date) + ' الساعة ' + t12(e.time);
  });
}
const mkRow = (e, base) => ({ kind: 'row', sid: 'S' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6), phone: base.phone, client: base.client || '', platform: base.platform, advertiser_id: base.advertiser_id || '', campaign_id: String(base.campaign_id), campaign_name: base.campaign_name || '', action: e.action, repeat: e.repeat, time: e.time, run_date: e.run_date || '', last_run_date: e.last_run_date || '', status: 'active', last_result: '', created_at: new Date().toISOString() });

function intake() {
  const ai = inp.ai || {}, chat = String(inp.chat || '');
  const norm = (s) => String(s || '').toLowerCase().replace(/[\sً-ٟـ_\-]/g, '').replace(/[أإآ]/g, 'ا').replace(/ة/g, 'ه');
  const reply = (t) => [{ kind: 'reply', finalMessage: t }];
  const byId = {};
  for (const h of (inp.camps || [])) { if (h && h.campaign_id) byId[String(h.campaign_id)] = { ...(byId[String(h.campaign_id)] || {}), ...Object.fromEntries(Object.entries(h).filter(([k, v]) => v !== '' && v != null)) }; }
  const camps = Object.values(byId);
  let existing = [];
  existing = (inp.existing || []).filter(r => r && r.sid && String(r.phone) === chat);
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
    return mine.map(r => ({ ...r, kind: 'row', status: 'cancelled', last_result: 'cancelled ' + dateB + ' ' + hmB, finalMessage: msg }));
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
    const mine = (inp.clients || []).filter(r => r && r.tiktok_advertiser_id && n10(r.phone) === n10(inp.from));
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
  return rows.map(r => ({ ...r, finalMessage: msg }));
}
function hook() {
  const ctx = inp.ctx || {}, saved = inp.saved || {};
  const sch = Array.isArray(ctx.schedule) ? ctx.schedule : [];
  const okCreate = ctx.action === 'create' && sch.length && saved.campaign_id && /^(true|1)$/i.test(String(saved.success));
  if (!okCreate) return [];
  const chat = String(inp.chat || '');
  const platform = /tik/i.test(String(saved.platform || '')) ? 'tiktok' : 'meta';
  const advertiser = platform === 'tiktok' ? String(ctx.tiktokAdvertiserId || '').replace(/\D/g, '') : '';
  if (platform === 'tiktok' && !advertiser) return [];
  const { evs, enforce } = buildEvents(sch);
  if (!evs.length) return [];
  const name = saved.name || ctx.campaign_name || '';
  const base = { phone: chat, client: ctx.client || saved.client || '', platform, advertiser_id: advertiser, campaign_id: saved.campaign_id, campaign_name: name };
  const msg = '⏰ سجّلت جدولة للحملة "' + (name || saved.campaign_id) + '":\n' + describe(evs, enforce).join('\n') + '\n\nيتنفذ تلقائياً بدقة ±5 دقائق بتوقيت العراق. للعرض: "شنو المجدول"، وللإلغاء: "الغ جدولة حملة ' + (name || 'X') + '".';
  return evs.map(e => ({ ...mkRow(e, base), finalMessage: msg }));
}
function due() {
  const nowTs = Date.parse(dateB + 'T' + hmB + ':00Z');
  const rows = (inp.rows || []).filter(r => r && r.sid && r.status === 'active');
  const due = [], out = [];
  for (const r of rows) {
    const t = String(r.time || '');
    if (!/^\d{2}:\d{2}$/.test(t)) continue;
    if (r.repeat === 'daily') {
      if (String(r.last_run_date) !== dateB && hmB >= t) due.push({ r, ts: Date.parse(dateB + 'T' + t + ':00Z') });
    } else {
      const d = String(r.run_date || '');
      if (!/^\d{4}-\d{2}-\d{2}$/.test(d)) continue;
      const ts = Date.parse(d + 'T' + t + ':00Z');
      if (ts > nowTs) continue;
      if (nowTs - ts > 12 * 3600000) out.push({ ...r, api: 'skip', skipReason: 'expired' });
      else due.push({ r, ts });
    }
  }
  const byC = {};
  for (const x of due) (byC[x.r.campaign_id] = byC[x.r.campaign_id] || []).push(x);
  for (const arr of Object.values(byC)) {
    arr.sort((a, b) => a.ts - b.ts);
    arr.forEach((x, i) => out.push({ ...x.r, api: i === arr.length - 1 ? 'apply' : 'skip', skipReason: i === arr.length - 1 ? '' : 'superseded' }));
  }
  return out;
}
function result() {
  const out = [];
  (inp.items || []).forEach((it) => {
    const r = it.r || {}, j = it.j || {};
    let ok, msg = '';
    if (r.api === 'skip') { ok = true; }
    else if (r.platform === 'tiktok') { ok = j.code === 0 && !j.error; msg = String(j.message || (typeof j.error === 'string' ? j.error : (j.error && j.error.message)) || ''); }
    else { ok = !j.error && (j.success === true || j.id != null); msg = String((j.error && (j.error.message || j.error.error_user_msg)) || ''); }
    const fails = Number((String(r.last_result || '').match(/^FAIL (\d)/) || [])[1]) || 0;
    let status = r.status, last_run_date = r.last_run_date, last_result, notify = false, finalMessage = '';
    const label = '"' + (r.campaign_name || r.campaign_id) + '" (' + (r.platform === 'tiktok' ? 'تيك توك' : 'فيسبوك') + ')';
    if (r.api === 'skip') {
      last_result = (r.skipReason === 'expired' ? 'EXPIRED ' : 'SUPERSEDED ') + dateB + ' ' + hmB;
      if (r.repeat === 'daily') last_run_date = dateB; else status = 'done';
    } else if (ok) {
      last_result = 'OK ' + dateB + ' ' + hmB;
      if (r.repeat === 'daily') last_run_date = dateB; else status = 'done';
      notify = true;
      finalMessage = '⏰ حسب الجدولة: ' + (r.action === 'on' ? '▶️ شغّلت' : '⏸️ وقفت') + ' حملة ' + label + ' الساعة ' + t12(hmB) + '.';
    } else {
      const n = fails + 1;
      last_result = 'FAIL ' + n + ': ' + msg.slice(0, 150);
      if (n >= 3) { if (r.repeat === 'daily') { last_run_date = dateB; last_result = 'FAIL 0 (gave up ' + dateB + '): ' + msg.slice(0, 120); } else status = 'failed'; }
      if (n === 1 || n >= 3) { notify = true; finalMessage = '⚠️ فشل تنفيذ الجدولة (' + (r.action === 'on' ? 'تشغيل' : 'إيقاف') + ' حملة ' + label + '): ' + msg.slice(0, 200) + (n >= 3 ? '\nوقفت المحاولات لهذا الموعد.' : '\nراح أعيد المحاولة بعد 5 دقائق.'); }
    }
    out.push({ sid: r.sid, phone: r.phone, client: r.client, platform: r.platform, advertiser_id: r.advertiser_id, campaign_id: r.campaign_id, campaign_name: r.campaign_name, action: r.action, repeat: r.repeat, time: r.time, run_date: r.run_date, last_run_date, status, last_result, created_at: r.created_at, notify, finalMessage });
  });
  return out;
}
const out = ({ intake, hook, due, result }[inp.mode] || (() => []))();
return out.map(json => ({ json }));
